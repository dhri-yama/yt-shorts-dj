"""
OAuth 2.0 authentication for YouTube API.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..config import YouTubeConfig
from ..exceptions import TokenRefreshError, OAuthError


class YouTubeAuth:
    """
    OAuth 2.0 authentication manager for YouTube API.
    
    Handles token refresh and access token caching.
    """
    
    YOUTUBE_SCOPES = [
        'https://www.googleapis.com/auth/youtube',
        'https://www.googleapis.com/auth/youtube.readonly'
    ]
    
    TOKEN_URI = "https://oauth2.googleapis.com/token"
    
    def __init__(self, config: YouTubeConfig):
        """
        Initialize authentication manager.
        
        Args:
            config: YouTube configuration with OAuth credentials
        """
        self.config = config
        self._credentials: Optional[Credentials] = None
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def credentials(self) -> Credentials:
        """Get or create credentials."""
        if self._credentials is None:
            self._credentials = Credentials(
                token=None,
                refresh_token=self.config.refresh_token,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                token_uri=self.TOKEN_URI
            )
        return self._credentials
    
    @property
    def access_token(self) -> str:
        """Get current access token, refreshing if necessary."""
        if self._access_token is None or self._is_token_expired:
            self._refresh_access_token()
        return self._access_token
    
    @property
    def _is_token_expired(self) -> bool:
        """Check if current access token is expired."""
        if self._token_expiry is None:
            return True
        # Consider token expired 5 minutes before actual expiry for safety
        return datetime.utcnow() >= (self._token_expiry - timedelta(minutes=5))
    
    def _refresh_access_token(self) -> None:
        """Refresh the access token."""
        try:
            # Use synchronous request for token refresh
            request = Request()
            self.credentials.refresh(request)
            
            self._access_token = self.credentials.token
            # Set expiry to 1 hour (standard YouTube token lifetime)
            self._token_expiry = datetime.utcnow() + timedelta(hours=1)
            
        except Exception as e:
            raise TokenRefreshError(f"Failed to refresh access token: {e}") from e
    
    async def get_access_token(self) -> str:
        """
        Get access token asynchronously.
        
        Returns:
            Current access token (refreshed if expired)
        """
        return self.access_token
    
    async def close(self) -> None:
        """Clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    @classmethod
    def generate_refresh_token(cls, client_secret_file: str, scopes: Optional[list] = None) -> str:
        """
        Generate a new refresh token using OAuth flow.
        
        This is a helper method for initial setup.
        
        Args:
            client_secret_file: Path to client secret JSON file
            scopes: OAuth scopes (defaults to YouTube scopes)
            
        Returns:
            Refresh token
        """
        scopes = scopes or cls.YOUTUBE_SCOPES
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file,
                scopes=scopes
            )
            
            credentials = flow.run_local_server(port=8080)
            
            if not credentials.refresh_token:
                raise OAuthError("No refresh token returned from OAuth flow")
            
            return credentials.refresh_token
            
        except Exception as e:
            raise OAuthError(f"Failed to generate refresh token: {e}") from e
