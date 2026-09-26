"""
YouTube Data API v3 client.

Handles all raw API operations with OAuth 2.0 authentication.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .models import VideoMetadata, PlaylistItem, ChannelInfo, PlaylistMetadata
from ..config import YouTubeConfig
from ..exceptions import (
    QuotaExceededError,
    APIError,
    TokenRefreshError,
    NetworkError,
)

logger = logging.getLogger(__name__)

# YouTube Data API v3 base URL
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"

# Quota units for various operations (approximate)
QUOTA_UNITS = {
    "channels.list": 1,
    "playlistItems.list": 1,
    "playlistItems.insert": 1,
    "playlistItems.delete": 1,
    "videos.list": 1,
    "search.list": 200,
}


class YouTubeClient:
    """
    YouTube Data API v3 client.
    
    Handles all API operations with automatic token refresh
    and quota-optimized batching.
    """
    
    def __init__(
        self,
        config: YouTubeConfig,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        """
        Initialize YouTube client.
        
        Args:
            config: YouTube configuration with OAuth credentials
            http_client: Optional custom HTTP client
        """
        self.config = config
        self._http_client = http_client or httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        self._credentials: Optional[Credentials] = None
        self._access_token: Optional[str] = None
        
        # Cache for channel uploads playlist IDs
        self._channel_uploads_cache: Dict[str, str] = {}
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        return self._http_client
    
    @property
    def credentials(self) -> Credentials:
        """Get or create credentials."""
        if self._credentials is None:
            self._credentials = Credentials(
                token=None,
                refresh_token=self.config.refresh_token,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                token_uri="https://oauth2.googleapis.com/token"
            )
        return self._credentials
    
    @property
    def access_token(self) -> str:
        """Get current access token, refreshing if necessary."""
        if self._access_token is None:
            self._refresh_access_token()
        return self._access_token
    
    def _refresh_access_token(self) -> None:
        """Refresh the access token."""
        try:
            request = Request()
            self.credentials.refresh(request)
            self._access_token = self.credentials.token
        except Exception as e:
            raise TokenRefreshError(f"Failed to refresh access token: {e}") from e
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make an API request with automatic retry on token errors.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (e.g., "playlistItems")
            params: Query parameters
            data: Request body
            headers: Custom headers
            
        Returns:
            API response as dictionary
            
        Raises:
            QuotaExceededError: When API quota is exceeded
            APIError: For other API errors
            NetworkError: For network-related errors
        """
        url = f"{YOUTUBE_API_URL}/{endpoint}"
        
        # Build headers
        request_headers = headers or {}
        request_headers["Authorization"] = f"Bearer {self.access_token}"
        request_headers["Accept"] = "application/json"
        
        # Build params
        request_params = params or {}
        request_params["key"] = self.config.api_key
        
        max_retries = 3
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = await self.http_client.request(
                    method,
                    url,
                    params=request_params,
                    json=data,
                    headers=request_headers
                )
                
                # Handle response
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 204:
                    # DELETE requests return 204 No Content
                    return {}
                
                elif response.status_code == 401 or response.status_code == 403:
                    # Token might be expired, try refreshing
                    try:
                        self._refresh_access_token()
                        continue  # Retry with new token
                    except TokenRefreshError:
                        raise APIError(
                            f"Authentication failed",
                            status_code=response.status_code,
                            response=response.text
                        )
                
                elif response.status_code == 403:
                    # Check for quota exceeded
                    try:
                        error_data = response.json()
                        if "quotaExceeded" in str(error_data):
                            raise QuotaExceededError(
                                "YouTube API quota exceeded"
                            )
                    except json.JSONDecodeError:
                        pass
                    raise APIError(
                        f"API request failed: {response.status_code}",
                        status_code=response.status_code,
                        response=response.text
                    )
                
                else:
                    raise APIError(
                        f"API request failed: {response.status_code} - {response.text}",
                        status_code=response.status_code,
                        response=response.text
                    )
                    
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Request timeout (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise NetworkError(f"Request timeout after {max_retries} attempts") from e
                
            except httpx.NetworkError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Network error (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise NetworkError(f"Network error after {max_retries} attempts") from e
        
        # This should not be reached, but just in case
        raise NetworkError(f"Request failed after {max_retries} attempts")
    
    async def get_channel_uploads_playlist_id(self, channel_id: str) -> str:
        """
        Get the uploads playlist ID for a channel.
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            Uploads playlist ID
        """
        # Check cache first
        if channel_id in self._channel_uploads_cache:
            return self._channel_uploads_cache[channel_id]
        
        # Fetch channel info
        response = await self._make_request(
            "GET",
            "channels",
            params={
                "part": "contentDetails",
                "id": channel_id
            }
        )
        
        items = response.get("items", [])
        if not items:
            raise APIError(f"Channel not found: {channel_id}")
        
        channel_info = ChannelInfo.from_dict(items[0])
        playlist_id = channel_info.uploads_playlist_id
        
        if not playlist_id:
            raise APIError(f"No uploads playlist found for channel: {channel_id}")
        
        # Cache the result
        self._channel_uploads_cache[channel_id] = playlist_id
        
        return playlist_id
    
    async def get_playlist_items(
        self,
        playlist_id: str,
        page_token: Optional[str] = None,
        max_results: int = 50,
        part: str = "snippet,contentDetails"
    ) -> Tuple[List[PlaylistItem], Optional[str]]:
        """
        Fetch items from a playlist.
        
        Args:
            playlist_id: Playlist ID to fetch
            page_token: Page token for pagination
            max_results: Maximum number of results per page (max 50)
            part: Comma-separated list of parts to retrieve
            
        Returns:
            Tuple of (playlist items, next page token or None)
        """
        params = {
            "part": part,
            "playlistId": playlist_id,
            "maxResults": min(max_results, 50)
        }
        
        if page_token:
            params["pageToken"] = page_token
        
        response = await self._make_request("GET", "playlistItems", params=params)
        
        items = []
        for item_data in response.get("items", []):
            items.append(PlaylistItem.from_dict(item_data))
        
        next_page_token = response.get("nextPageToken")
        
        return items, next_page_token
    
    async def get_all_playlist_items(
        self,
        playlist_id: str,
        max_results: int = 200
    ) -> List[PlaylistItem]:
        """
        Fetch all items from a playlist (handles pagination).
        
        Args:
            playlist_id: Playlist ID to fetch
            max_results: Maximum number of results to fetch
            
        Returns:
            List of all playlist items
        """
        all_items = []
        page_token = None
        
        while len(all_items) < max_results:
            items, next_page_token = await self.get_playlist_items(
                playlist_id,
                page_token=page_token,
                max_results=min(50, max_results - len(all_items))
            )
            
            all_items.extend(items)
            
            if not next_page_token or len(items) == 0:
                break
            
            page_token = next_page_token
        
        return all_items[:max_results]
    
    async def get_video_metadata(self, video_id: str) -> VideoMetadata:
        """
        Get metadata for a single video.
        
        Args:
            video_id: Video ID to fetch
            
        Returns:
            VideoMetadata object
        """
        videos = await self.get_videos_metadata([video_id])
        if not videos:
            raise APIError(f"Video not found: {video_id}")
        return videos[0]
    
    async def get_videos_metadata(
        self,
        video_ids: List[str],
        part: str = "snippet,contentDetails,status"
    ) -> List[VideoMetadata]:
        """
        Batch fetch metadata for multiple videos.
        
        Args:
            video_ids: List of video IDs to fetch (max 50 per request)
            part: Comma-separated list of parts to retrieve
            
        Returns:
            List of VideoMetadata objects
        """
        if not video_ids:
            return []
        
        # Split into chunks of 50 (YouTube API limit)
        chunks = [video_ids[i:i+50] for i in range(0, len(video_ids), 50)]
        all_videos = []
        
        for chunk in chunks:
            params = {
                "part": part,
                "id": ",".join(chunk)
            }
            
            response = await self._make_request("GET", "videos", params=params)
            
            for item_data in response.get("items", []):
                video = VideoMetadata.from_dict(item_data)
                all_videos.append(video)
        
        return all_videos
    
    async def add_video_to_playlist(
        self,
        playlist_id: str,
        video_id: str,
        position: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Add a video to a playlist.
        
        Args:
            playlist_id: Target playlist ID
            video_id: Video ID to add
            position: Optional position in playlist
            
        Returns:
            API response
        """
        snippet = {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id
            }
        }
        
        if position is not None:
            snippet["position"] = position
        
        data = {
            "snippet": snippet
        }
        
        response = await self._make_request(
            "POST",
            "playlistItems",
            params={"part": "snippet"},
            data=data
        )
        
        return response
    
    async def add_videos_to_playlist(
        self,
        playlist_id: str,
        video_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Add multiple videos to a playlist.
        
        Args:
            playlist_id: Target playlist ID
            video_ids: List of video IDs to add
            
        Returns:
            List of API responses
        """
        results = []
        for video_id in video_ids:
            result = await self.add_video_to_playlist(playlist_id, video_id)
            results.append(result)
        return results
    
    async def delete_playlist_item(self, playlist_item_id: str) -> Dict[str, Any]:
        """
        Delete a playlist item.
        
        Args:
            playlist_item_id: Playlist item ID to delete
            
        Returns:
            API response
        """
        response = await self._make_request(
            "DELETE",
            f"playlistItems",
            params={"id": playlist_item_id}
        )
        return response
    
    async def clear_playlist(self, playlist_id: str) -> int:
        """
        Remove all items from a playlist.
        
        Args:
            playlist_id: Playlist ID to clear
            
        Returns:
            Number of items deleted
        """
        # Get all items
        items = await self.get_all_playlist_items(playlist_id, max_results=200)
        
        # Delete all items
        count = 0
        for item in items:
            await self.delete_playlist_item(item.id)
            count += 1
        
        return count
    
    async def get_channel_info(self, channel_id: str) -> ChannelInfo:
        """
        Get channel information.
        
        Args:
            channel_id: Channel ID
            
        Returns:
            ChannelInfo object
        """
        response = await self._make_request(
            "GET",
            "channels",
            params={
                "part": "snippet,contentDetails",
                "id": channel_id
            }
        )
        
        items = response.get("items", [])
        if not items:
            raise APIError(f"Channel not found: {channel_id}")
        
        return ChannelInfo.from_dict(items[0])
    
    async def get_playlist_info(self, playlist_id: str) -> PlaylistMetadata:
        """
        Get playlist information.
        
        Args:
            playlist_id: Playlist ID
            
        Returns:
            PlaylistMetadata object
        """
        response = await self._make_request(
            "GET",
            "playlists",
            params={
                "part": "snippet,contentDetails,status",
                "id": playlist_id
            }
        )
        
        items = response.get("items", [])
        if not items:
            raise APIError(f"Playlist not found: {playlist_id}")
        
        return PlaylistMetadata.from_dict(items[0])
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http_client.aclose()
