"""
Exponential backoff and retry logic.
"""

import asyncio
import random
import logging
from functools import wraps
from typing import Callable, TypeVar, Any, Optional, Tuple

from ..exceptions import RetryError

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def with_retry(
    func: Callable[..., T],
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    retry_on: Tuple[type, ...] = (Exception,),
    retry_on_status_codes: Optional[Tuple[int, ...]] = None,
    **kwargs
) -> T:
    """
    Execute function with exponential backoff retry.
    
    Args:
        func: Function to execute (must be async)
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        max_delay: Maximum delay between retries
        retry_on: Tuple of exception types to retry on
        retry_on_status_codes: Optional tuple of HTTP status codes to retry on
        **kwargs: Arguments to pass to func
        
    Returns:
        Function return value
        
    Raises:
        RetryError: If all retry attempts fail
        Exception: If function raises an exception not in retry_on
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(**kwargs)
        except retry_on as e:
            last_exception = e
            
            if attempt >= max_retries:
                logger.error(
                    f"All {max_retries + 1} attempts failed for {func.__name__}: {e}"
                )
                raise RetryError(
                    f"After {max_retries + 1} attempts: {e}",
                    attempts=max_retries + 1,
                    last_error=e
                ) from e
            
            # Calculate delay with jitter
            delay = min(
                backoff_factor ** attempt + random.uniform(0, 1),
                max_delay
            )
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
    
    # This should not be reached
    raise RetryError(f"Unexpected error: {last_exception}")


def retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    retry_on: Tuple[type, ...] = (Exception,),
    retry_on_status_codes: Optional[Tuple[int, ...]] = None
):
    """
    Decorator for adding retry logic to async functions.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        max_delay: Maximum delay between retries
        retry_on: Tuple of exception types to retry on
        retry_on_status_codes: Optional tuple of HTTP status codes to retry on
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await with_retry(
                func,
                max_retries=max_retries,
                backoff_factor=backoff_factor,
                max_delay=max_delay,
                retry_on=retry_on,
                retry_on_status_codes=retry_on_status_codes,
                **kwargs
            )
        return wrapper
    return decorator


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
    
    def with_retry(self, func: Callable[..., T], **kwargs) -> T:
        """Execute function with retry using this config."""
        return with_retry(
            func,
            max_retries=self.max_retries,
            backoff_factor=self.backoff_factor,
            max_delay=self.max_delay,
            **kwargs
        )
