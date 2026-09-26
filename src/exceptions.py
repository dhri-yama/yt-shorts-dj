"""
Custom exception hierarchy for YouTube Shorts automation.
"""

from datetime import datetime
from typing import Optional


class YouTubeShortsError(Exception):
    """Base exception for all application errors."""
    pass


class ConfigurationError(YouTubeShortsError):
    """Raised when configuration is invalid or missing."""
    pass


class QuotaExceededError(YouTubeShortsError):
    """Raised when YouTube API quota is exceeded."""
    
    def __init__(self, message: str = "YouTube API quota exceeded", 
                 reset_time: Optional[datetime] = None):
        super().__init__(message)
        self.reset_time = reset_time


class OAuthError(YouTubeShortsError):
    """Raised for OAuth-related errors."""
    pass


class TokenRefreshError(OAuthError):
    """Raised when token refresh fails."""
    pass


class TokenExpiredError(OAuthError):
    """Raised when access token is expired."""
    pass


class InsufficientShortsError(YouTubeShortsError):
    """Raised when not enough unseen Shorts are available."""
    
    def __init__(self, message: str, available: int, requested: int):
        super().__init__(message)
        self.available = available
        self.requested = requested


class StorageError(YouTubeShortsError):
    """Raised for storage backend errors."""
    pass


class PlaylistError(YouTubeShortsError):
    """Raised for playlist operation errors."""
    pass


class APIError(YouTubeShortsError):
    """Raised for YouTube API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None,
                 response: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class NetworkError(YouTubeShortsError):
    """Raised for network-related errors."""
    pass


class RetryError(YouTubeShortsError):
    """Raised when all retry attempts fail."""
    
    def __init__(self, message: str, attempts: int = 0, last_error: Optional[Exception] = None):
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error
