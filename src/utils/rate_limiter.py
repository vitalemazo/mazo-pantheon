"""
Rate Limiter for LLM API Calls

Implements a token bucket algorithm to prevent 429 rate limit errors
by proactively throttling concurrent LLM requests.
"""

import asyncio
import logging
import os
import random
import time
from typing import Optional
from threading import Lock, Semaphore

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for LLM API calls.
    
    Prevents 429 errors by:
    1. Limiting concurrent requests (semaphore)
    2. Limiting requests per time window (token bucket)
    3. Providing backoff on 429 errors
    4. Enforcing minimum delay between requests
    """
    
    def __init__(
        self,
        max_concurrent: int = 1,  # Max concurrent LLM calls - default to 1 for safety
        requests_per_minute: int = 15,  # Token bucket rate - conservative default
        backoff_base: float = 3.0,  # Exponential backoff base (more aggressive)
        max_backoff: float = 120.0,  # Max backoff seconds (2 minutes)
        min_request_interval: float = 2.0,  # Minimum seconds between requests
    ):
        self.max_concurrent = max_concurrent
        self.requests_per_minute = requests_per_minute
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        self.min_request_interval = min_request_interval
        
        # Semaphore for concurrent requests
        self.semaphore = Semaphore(max_concurrent)
        
        # Token bucket
        self.tokens = requests_per_minute
        self.last_refill = time.time()
        self.token_lock = Lock()
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        
        # Track 429 errors for backoff
        self.consecutive_429s = 0
        self.last_429_time = 0
        self.backoff_lock = Lock()
        
        # Track last request time for minimum interval
        self.last_request_time = 0
        self.request_time_lock = Lock()
        
        logger.info(
            f"Rate limiter initialized: max_concurrent={max_concurrent}, "
            f"requests_per_minute={requests_per_minute}, "
            f"min_interval={min_request_interval}s"
        )
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        with self.token_lock:
            now = time.time()
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * self.refill_rate
            
            if tokens_to_add > 0:
                self.tokens = min(
                    self.requests_per_minute,
                    self.tokens + tokens_to_add
                )
                self.last_refill = now
    
    def _acquire_token(self) -> bool:
        """Try to acquire a token from the bucket"""
        self._refill_tokens()
        
        with self.token_lock:
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False
    
    def _calculate_backoff(self) -> float:
        """Calculate backoff delay based on consecutive 429 errors"""
        with self.backoff_lock:
            if self.consecutive_429s == 0:
                return 0.0
            
            # Exponential backoff: base^429_count seconds, capped at max_backoff
            # More aggressive: start at base seconds and grow quickly
            backoff = min(
                self.backoff_base ** min(self.consecutive_429s, 6),  # Cap exponent to prevent overflow
                self.max_backoff
            )
            
            # Add jitter to prevent thundering herd (10-30% of backoff)
            jitter = random.uniform(backoff * 0.1, backoff * 0.3)
            
            total_backoff = backoff + jitter
            logger.debug(
                f"Backoff calculated: {total_backoff:.1f}s "
                f"(consecutive_429s={self.consecutive_429s})"
            )
            return total_backoff
    
    def _wait_for_minimum_interval(self) -> float:
        """Wait for minimum interval between requests, return actual wait time"""
        with self.request_time_lock:
            now = time.time()
            elapsed = now - self.last_request_time
            
            if elapsed < self.min_request_interval:
                wait_time = self.min_request_interval - elapsed
                # Add small jitter to prevent request bursts
                wait_time += random.uniform(0.1, 0.5)
                return wait_time
            return 0.0
    
    def record_429_error(self):
        """Record a 429 error and update backoff"""
        with self.backoff_lock:
            self.consecutive_429s += 1
            self.last_429_time = time.time()
            logger.warning(
                f"429 error recorded. Consecutive 429s: {self.consecutive_429s}. "
                f"Next backoff will be: {self._calculate_backoff():.1f}s"
            )
    
    def record_success(self):
        """Record a successful request (gradually reset 429 counter)"""
        with self.backoff_lock:
            # Gradually reduce the counter instead of resetting to 0
            # This provides more stable rate limiting after 429 errors
            if self.consecutive_429s > 0:
                self.consecutive_429s = max(0, self.consecutive_429s - 1)
        
        # Update last request time
        with self.request_time_lock:
            self.last_request_time = time.time()
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None):
        """
        Acquire permission to make an LLM call (synchronous).
        
        This will:
        1. Wait for semaphore slot (concurrent limit)
        2. Wait for minimum interval since last request
        3. Wait for token (rate limit)
        4. Apply backoff if recent 429 errors
        
        Args:
            blocking: If True, wait until available. If False, return immediately.
            timeout: Maximum time to wait (None = wait forever)
        
        Returns:
            True if acquired, False if non-blocking and not available
        """
        start_time = time.time()
        
        # Wait for semaphore (concurrent requests)
        if not self.semaphore.acquire(blocking=blocking, timeout=timeout):
            logger.debug("Rate limiter: failed to acquire semaphore")
            return False
        
        try:
            # Wait for minimum interval between requests
            min_interval_wait = self._wait_for_minimum_interval()
            if min_interval_wait > 0:
                if timeout and (time.time() - start_time + min_interval_wait) > timeout:
                    self.semaphore.release()
                    return False
                logger.debug(f"Rate limiter: waiting {min_interval_wait:.1f}s for minimum interval")
                time.sleep(min_interval_wait)
            
            # Check for backoff due to 429 errors
            backoff_delay = self._calculate_backoff()
            if backoff_delay > 0:
                if timeout and (time.time() - start_time + backoff_delay) > timeout:
                    self.semaphore.release()
                    return False
                logger.info(f"Rate limiter: applying {backoff_delay:.1f}s backoff due to 429 errors")
                time.sleep(backoff_delay)
            
            # Wait for token (rate limit bucket)
            token_wait_start = time.time()
            max_token_wait = 30.0  # Max 30 seconds waiting for token
            
            while not self._acquire_token():
                if timeout and (time.time() - start_time) >= timeout:
                    self.semaphore.release()
                    return False
                
                if (time.time() - token_wait_start) > max_token_wait:
                    logger.warning("Rate limiter: token wait timeout, proceeding anyway")
                    break
                
                # Wait until next token is available
                wait_time = (1.0 - self.tokens) / max(self.refill_rate, 0.001)
                if wait_time > 0:
                    sleep_time = min(wait_time, 2.0)  # Cap at 2 seconds
                    if timeout and (time.time() - start_time + sleep_time) > timeout:
                        self.semaphore.release()
                        return False
                    time.sleep(sleep_time)
                self._refill_tokens()
            
            total_wait = time.time() - start_time
            if total_wait > 1.0:
                logger.debug(f"Rate limiter: acquired after {total_wait:.1f}s wait")
            
            return True
            
        except Exception as e:
            # Release semaphore on error
            logger.error(f"Rate limiter acquire error: {e}")
            self.semaphore.release()
            raise
    
    def release(self):
        """Release the semaphore after LLM call completes"""
        self.semaphore.release()


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    max_concurrent: int = 1,  # Default to 1 for safety
    requests_per_minute: int = 15,  # Conservative default
    min_request_interval: float = 2.0,  # 2 seconds between requests
) -> RateLimiter:
    """Get or create the global rate limiter"""
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        # Read from environment with conservative defaults
        max_concurrent = int(os.getenv("LLM_MAX_CONCURRENT", str(max_concurrent)))
        requests_per_minute = int(os.getenv("LLM_REQUESTS_PER_MINUTE", str(requests_per_minute)))
        min_request_interval = float(os.getenv("LLM_MIN_REQUEST_INTERVAL", str(min_request_interval)))
        
        _global_rate_limiter = RateLimiter(
            max_concurrent=max_concurrent,
            requests_per_minute=requests_per_minute,
            min_request_interval=min_request_interval,
        )
    
    return _global_rate_limiter


def reset_rate_limiter():
    """Reset the global rate limiter (useful for testing)"""
    global _global_rate_limiter
    _global_rate_limiter = None


def get_rate_limiter_status() -> dict:
    """Get current status of the rate limiter for monitoring"""
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        return {"initialized": False}
    
    rl = _global_rate_limiter
    return {
        "initialized": True,
        "max_concurrent": rl.max_concurrent,
        "requests_per_minute": rl.requests_per_minute,
        "min_request_interval": rl.min_request_interval,
        "current_tokens": rl.tokens,
        "consecutive_429s": rl.consecutive_429s,
        "current_backoff_seconds": rl._calculate_backoff(),
    }
