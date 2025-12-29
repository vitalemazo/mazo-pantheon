"""
Helper functions for LLM with improved error handling and detailed error reporting.
"""

import json
import logging
import os
import time
import traceback
from pydantic import BaseModel
from src.llm.models import get_model, get_model_info
from src.utils.progress import progress
from src.graph.state import AgentState
from src.utils.rate_limiter import get_rate_limiter

# Configure logging
logger = logging.getLogger(__name__)

# Get rate limiter with configurable settings
# Reduce concurrent calls to prevent 429 errors with multiple agents
_rate_limiter = get_rate_limiter(
    max_concurrent=int(os.getenv("LLM_MAX_CONCURRENT", "2")),  # Reduced from 3 to 2
    requests_per_minute=int(os.getenv("LLM_REQUESTS_PER_MINUTE", "30")),  # Reduced from 60 to 30
)


class LLMError:
    """Tracks LLM call errors for debugging."""
    def __init__(self, agent_name: str, error: Exception, attempt: int, max_retries: int):
        self.agent_name = agent_name
        self.error = error
        self.error_type = type(error).__name__
        self.attempt = attempt
        self.max_retries = max_retries
        self.traceback = traceback.format_exc()
    
    def get_user_friendly_message(self) -> str:
        """Generate a user-friendly error message."""
        error_str = str(self.error).lower()
        
        if "rate limit" in error_str or "429" in error_str:
            return f"LLM rate limit exceeded. Tried {self.attempt}/{self.max_retries} times. Consider reducing concurrent requests."
        elif "timeout" in error_str:
            return f"LLM request timed out after {self.attempt} attempts. The model may be overloaded."
        elif "invalid_api_key" in error_str or "authentication" in error_str or "401" in error_str:
            return "Invalid LLM API key. Please check your API key configuration in Settings."
        elif "connection" in error_str:
            return f"Could not connect to LLM API. Check your network connection. Error: {self.error_type}"
        elif "json" in error_str or "parse" in error_str or "validation" in error_str:
            return f"LLM returned invalid response format. The model may not support structured output. Error: {self.error_type}"
        elif "context length" in error_str or "token" in error_str:
            return "Input too long for model context window. Consider using a model with larger context."
        else:
            return f"LLM error ({self.error_type}): {str(self.error)[:200]}"


def call_llm(
    prompt: any,
    pydantic_model: type[BaseModel],
    agent_name: str | None = None,
    state: AgentState | None = None,
    max_retries: int = 3,
    default_factory=None,
) -> BaseModel:
    """
    Makes an LLM call with retry logic, handling both JSON supported and non-JSON supported models.
    
    Includes improved error handling that:
    - Logs detailed error information for debugging
    - Provides user-friendly error messages in the default response
    - Tracks error types for monitoring
    
    Args:
        prompt: The prompt to send to the LLM
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates and model config extraction
        state: Optional state object to extract agent-specific model configuration
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure

    Returns:
        An instance of the specified Pydantic model
    """
    
    # Extract model configuration if state is provided and agent_name is available
    if state and agent_name:
        model_name, model_provider = get_agent_model_config(state, agent_name)
    else:
        # Use system defaults when no state or agent_name is provided
        model_name = "gpt-4.1"
        model_provider = "OPENAI"

    # Extract API keys from state if available
    api_keys = None
    if state:
        request = state.get("metadata", {}).get("request")
        if request and hasattr(request, 'api_keys'):
            api_keys = request.api_keys

    model_info = get_model_info(model_name, model_provider)
    
    try:
        llm = get_model(model_name, model_provider, api_keys)
    except Exception as e:
        logger.error(f"Failed to initialize LLM model {model_name}/{model_provider}: {e}")
        error = LLMError(agent_name or "unknown", e, 0, max_retries)
        return _create_error_response(pydantic_model, error.get_user_friendly_message(), default_factory)

    # For non-JSON support models, we can use structured output
    if not (model_info and not model_info.has_json_mode()):
        try:
            llm = llm.with_structured_output(
                pydantic_model,
                method="json_mode",
            )
        except Exception as e:
            logger.warning(f"Could not set structured output for {model_name}: {e}")
            # Continue without structured output

    last_error = None
    rate_limiter_acquired = False
    
    # Call the LLM with retries and rate limiting
    for attempt in range(max_retries):
        rate_limiter_acquired = False
        
        try:
            if agent_name:
                progress.update_status(agent_name, None, f"Waiting for LLM slot (attempt {attempt + 1}/{max_retries})")
            
            # Acquire rate limiter permission - wait up to 5 minutes
            if not _rate_limiter.acquire(blocking=True, timeout=300):
                logger.warning(f"Rate limiter timeout for {agent_name} - could not acquire slot")
                if agent_name:
                    progress.update_status(agent_name, None, "Rate limiter timeout")
                continue  # Try again
            
            rate_limiter_acquired = True
            
            if agent_name:
                progress.update_status(agent_name, None, f"Calling LLM (attempt {attempt + 1}/{max_retries})")
            
            # Call the LLM
            result = llm.invoke(prompt)
            
            # Record success for rate limiter backoff
            _rate_limiter.record_success()
            
            # Release rate limiter immediately after successful call
            _rate_limiter.release()
            rate_limiter_acquired = False

            # For non-JSON support models, we need to extract and parse the JSON manually
            if model_info and not model_info.has_json_mode():
                parsed_result = extract_json_from_response(result.content)
                if parsed_result:
                    try:
                        return pydantic_model(**parsed_result)
                    except Exception as validation_error:
                        logger.warning(f"Pydantic validation failed for {agent_name}: {validation_error}")
                        # Try to fix common issues
                        parsed_result = _fix_common_json_issues(parsed_result, pydantic_model)
                        if parsed_result:
                            return pydantic_model(**parsed_result)
                        raise validation_error
                else:
                    raise ValueError("Could not extract JSON from model response")
            else:
                # Validate the result is the correct type
                if isinstance(result, pydantic_model):
                    return result
                elif isinstance(result, dict):
                    return pydantic_model(**result)
                else:
                    # If result has content attribute (BaseMessage), try to parse it
                    if hasattr(result, 'content'):
                        parsed = extract_json_from_response(result.content)
                        if parsed:
                            return pydantic_model(**parsed)
                    return result

        except Exception as e:
            # Release rate limiter on error
            if rate_limiter_acquired:
                try:
                    _rate_limiter.release()
                except:
                    pass
                rate_limiter_acquired = False
            
            last_error = LLMError(agent_name or "unknown", e, attempt + 1, max_retries)
            
            # Check if it's a rate limit error
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str:
                _rate_limiter.record_429_error()
                logger.warning(f"Rate limited for {agent_name}, applying backoff")
            
            # Log detailed error info
            logger.warning(f"LLM call failed for {agent_name} (attempt {attempt + 1}/{max_retries}): {e}")
            logger.debug(f"Full error traceback:\n{last_error.traceback}")
            
            if agent_name:
                progress.update_status(agent_name, None, f"LLM error - retry {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1:
                # Final attempt failed - log detailed error
                logger.error(f"LLM call failed after {max_retries} attempts for {agent_name}: {e}")
                logger.error(f"Error type: {last_error.error_type}")
                
                # Create error response with detailed message
                error_msg = last_error.get_user_friendly_message()
                return _create_error_response(pydantic_model, error_msg, default_factory)
            
            # Wait a bit before retrying (exponential backoff)
            backoff_time = min(2 ** attempt, 30)  # Max 30 seconds
            time.sleep(backoff_time)

    # This should never be reached due to the retry logic above
    return _create_error_response(pydantic_model, "Unknown LLM error", default_factory)


def _create_error_response(
    model_class: type[BaseModel], 
    error_message: str, 
    default_factory=None
) -> BaseModel:
    """Creates an error response with a meaningful error message."""
    
    # If a default factory is provided, use it but try to inject error message
    if default_factory:
        result = default_factory()
        # Try to update the reasoning field with error info
        if hasattr(result, 'reasoning'):
            try:
                # Some models have mutable attributes
                object.__setattr__(result, 'reasoning', f"Analysis failed: {error_message}")
            except:
                pass
        return result
    
    # Create a default response with the error message
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field_name == "reasoning" or field_name == "explanation":
            default_values[field_name] = f"Analysis failed: {error_message}"
        elif field.annotation == str:
            default_values[field_name] = f"Error: {error_message}"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None

    return model_class(**default_values)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
    """Creates a safe default response based on the model's fields."""
    return _create_error_response(model_class, "Analysis could not be completed", None)


def _fix_common_json_issues(data: dict, model_class: type[BaseModel]) -> dict | None:
    """Attempt to fix common JSON parsing issues."""
    if not data:
        return None
    
    try:
        # Fix signal casing issues
        if "signal" in data and isinstance(data["signal"], str):
            data["signal"] = data["signal"].lower()
        
        # Fix confidence range issues (ensure 0-100)
        if "confidence" in data:
            try:
                conf = float(data["confidence"])
                if conf > 100:
                    data["confidence"] = 100.0
                elif conf < 0:
                    data["confidence"] = 0.0
                else:
                    data["confidence"] = conf
            except:
                data["confidence"] = 50.0
        
        return data
    except:
        return None


def extract_json_from_response(content: str) -> dict | None:
    """Extracts JSON from markdown-formatted response."""
    if not content:
        return None
    
    try:
        # First try direct JSON parsing
        return json.loads(content)
    except:
        pass
    
    try:
        # Try to find JSON in markdown code blocks
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7:]
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception as e:
        logger.debug(f"Error extracting JSON from markdown: {e}")
    
    try:
        # Try to find any JSON object in the content
        brace_start = content.find("{")
        brace_end = content.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            json_text = content[brace_start:brace_end + 1]
            return json.loads(json_text)
    except Exception as e:
        logger.debug(f"Error extracting JSON from braces: {e}")
    
    return None


def get_agent_model_config(state, agent_name):
    """
    Get model configuration for a specific agent from the state.
    Falls back to global model configuration if agent-specific config is not available.
    Always returns valid model_name and model_provider values.
    """
    request = state.get("metadata", {}).get("request")
    
    if request and hasattr(request, 'get_agent_model_config'):
        # Get agent-specific model configuration
        model_name, model_provider = request.get_agent_model_config(agent_name)
        # Ensure we have valid values
        if model_name and model_provider:
            return model_name, model_provider.value if hasattr(model_provider, 'value') else str(model_provider)
    
    # Fall back to global configuration (system defaults)
    model_name = state.get("metadata", {}).get("model_name") or "gpt-4.1"
    model_provider = state.get("metadata", {}).get("model_provider") or "OPENAI"
    
    # Convert enum to string if necessary
    if hasattr(model_provider, 'value'):
        model_provider = model_provider.value
    
    return model_name, model_provider
