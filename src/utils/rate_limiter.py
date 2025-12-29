"""
Rate Limiter for LLM API Calls

Implements a token bucket algorithm to prevent 429 rate limit errors
by proactively throttling concurrent LLM requests.
"""

import asyncio
import time
from typing import Optional
from threading import Lock, Semaphore


class RateLimiter:
    """
    Token bucket rate limiter for LLM API calls.
    
    Prevents 429 errors by:
    1. Limiting concurrent requests (semaphore)
    2. Limiting requests per time window (token bucket)
    3. Providing backoff on 429 errors
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,  # Max concurrent LLM calls
        requests_per_minute: int = 60,  # Token bucket rate
        backoff_base: float = 2.0,  # Exponential backoff base
        max_backoff: float = 60.0,  # Max backoff seconds
    ):
        self.max_concurrent = max_concurrent
        self.requests_per_minute = requests_per_minute
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        
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
            
            # Exponential backoff: 2^429_count seconds, capped at max_backoff
            backoff = min(
                self.backoff_base ** self.consecutive_429s,
                self.max_backoff
            )
            
            # Add jitter to prevent thundering herd
            import random
            jitter = random.uniform(0, backoff * 0.1)
            return backoff + jitter
    
    def record_429_error(self):
        """Record a 429 error and update backoff"""
        with self.backoff_lock:
            self.consecutive_429s += 1
            self.last_429_time = time.time()
    
    def record_success(self):
        """Record a successful request (reset 429 counter)"""
        with self.backoff_lock:
            self.consecutive_429s = 0
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None):
        """
        Acquire permission to make an LLM call (synchronous).
        
        This will:
        1. Wait for semaphore slot (concurrent limit)
        2. Wait for token (rate limit)
        3. Apply backoff if recent 429 errors
        
        Args:
            blocking: If True, wait until available. If False, return immediately.
            timeout: Maximum time to wait (None = wait forever)
        
        Returns:
            True if acquired, False if non-blocking and not available
        """
        import time
        
        start_time = time.time()
        
        # Wait for semaphore (concurrent requests)
        if not self.semaphore.acquire(blocking=blocking, timeout=timeout):
            return False
        
        try:
            # Check for backoff
            backoff_delay = self._calculate_backoff()
            if backoff_delay > 0:
                if timeout and (time.time() - start_time + backoff_delay) > timeout:
                    self.semaphore.release()
                    return False
                time.sleep(backoff_delay)
            
            # Wait for token (rate limit)
            while not self._acquire_token():
                if timeout and (time.time() - start_time) >= timeout:
                    self.semaphore.release()
                    return False
                
                # Wait until next token is available
                wait_time = (1.0 - self.tokens) / self.refill_rate
                if wait_time > 0:
                    sleep_time = min(wait_time, 1.0)  # Cap at 1 second
                    if timeout and (time.time() - start_time + sleep_time) > timeout:
                        self.semaphore.release()
                        return False
                    time.sleep(sleep_time)
                self._refill_tokens()
            
            return True
            
        except Exception as e:
            # Release semaphore on error
            self.semaphore.release()
            raise
    
    def release(self):
        """Release the semaphore after LLM call completes"""
        self.semaphore.release()


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    max_concurrent: int = 3,
    requests_per_minute: int = 60,
) -> RateLimiter:
    """Get or create the global rate limiter"""
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(
            max_concurrent=max_concurrent,
            requests_per_minute=requests_per_minute,
        )
    
    return _global_rate_limiter


def reset_rate_limiter():
    """Reset the global rate limiter (useful for testing)"""
    global _global_rate_limiter
    _global_rate_limiter = None
