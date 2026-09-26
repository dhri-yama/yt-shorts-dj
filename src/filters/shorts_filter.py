"""
Filter for identifying YouTube Shorts.

Handles business logic for identifying Shorts by duration and URL patterns.
"""

import asyncio
import logging
from typing import List, Tuple, Optional

from ..youtube.client import YouTubeClient
from ..youtube.models import VideoMetadata
from ..exceptions import APIError

logger = logging.getLogger(__name__)


class ShortsFilter:
    """
    Business logic for identifying and filtering YouTube Shorts.
    
    A YouTube Short is defined as:
    - Duration <= 60 seconds (primary check)
    - Not a live video or premiere
    - Public or unlisted (not private)
    """
    
    def __init__(self, youtube_client: YouTubeClient):
        """
        Initialize Shorts filter.
        
        Args:
            youtube_client: YouTube client for API calls
        """
        self.client = youtube_client
    
    async def is_short(self, video_id: str) -> bool:
        """
        Check if a video is a Short by fetching its metadata.
        
        Args:
            video_id: Video ID to check
            
        Returns:
            True if video is a Short, False otherwise
        """
        try:
            metadata = await self.client.get_video_metadata(video_id)
            return self._is_short_by_metadata(metadata)
        except APIError as e:
            logger.warning(f"Failed to check if {video_id} is a Short: {e}")
            return False
    
    async def is_short_by_url(self, url: str) -> bool:
        """
        Check if URL pattern indicates a Short.
        
        This is a fallback method that doesn't require API calls.
        
        Args:
            url: Video URL to check
            
        Returns:
            True if URL pattern indicates a Short, False otherwise
        """
        if not url:
            return False
        
        # Normalize URL
        url_lower = url.lower()
        
        # Check for /shorts/ in URL
        if "/shorts/" in url_lower:
            return True
        
        # Check for youtu.be/shorts/
        if "youtu.be/shorts/" in url_lower:
            return True
        
        return False
    
    def _is_short_by_metadata(self, metadata: VideoMetadata) -> bool:
        """
        Check if video is a Short based on metadata.
        
        Args:
            metadata: Video metadata
            
        Returns:
            True if video is a Short, False otherwise
        """
        # Check if it's a live video
        if metadata.is_live:
            return False
        
        # Check if it's private
        if not metadata.is_public:
            # We can still consider unlisted videos as Shorts
            # but not private ones
            if metadata.status.privacy_status == "private":
                return False
        
        # Primary check: duration <= 60 seconds
        if metadata.content_details.duration:
            from ..youtube.models import VideoDuration
            duration = VideoDuration.from_iso8601(metadata.content_details.duration)
            return duration.is_short
        
        # If duration is not available, we can't determine
        return False
    
    async def filter_shorts(
        self,
        video_ids: List[str]
    ) -> Tuple[List[VideoMetadata], List[VideoMetadata]]:
        """
        Filter list of video IDs into Shorts and non-Shorts.
        
        Uses batch fetching for efficiency.
        
        Args:
            video_ids: List of video IDs to filter
            
        Returns:
            Tuple of (shorts, non_shorts) as VideoMetadata lists
        """
        if not video_ids:
            return [], []
        
        # Batch fetch metadata
        metadatas = await self.client.get_videos_metadata(video_ids)
        
        shorts = []
        non_shorts = []
        
        for metadata in metadatas:
            if self._is_short_by_metadata(metadata):
                shorts.append(metadata)
            else:
                non_shorts.append(metadata)
        
        return shorts, non_shorts
    
    async def filter_shorts_by_id(
        self,
        video_ids: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Filter list of video IDs into Shorts and non-Shorts.
        
        Returns only the video IDs (not full metadata).
        
        Args:
            video_ids: List of video IDs to filter
            
        Returns:
            Tuple of (short_video_ids, non_short_video_ids)
        """
        shorts, non_shorts = await self.filter_shorts(video_ids)
        return [v.id for v in shorts], [v.id for v in non_shorts]
    
    async def get_shorts_from_channel(
        self,
        channel_id: str,
        max_videos: int = 200
    ) -> List[VideoMetadata]:
        """
        Fetch recent videos from a channel and filter Shorts.
        
        Args:
            channel_id: Channel ID to fetch from
            max_videos: Maximum number of videos to fetch
            
        Returns:
            List of Shorts from the channel
        """
        try:
            # Get channel uploads playlist ID
            uploads_playlist_id = await self.client.get_channel_uploads_playlist_id(
                channel_id
            )
            
            # Fetch recent videos from uploads playlist
            items = await self.client.get_all_playlist_items(
                uploads_playlist_id,
                max_results=max_videos
            )
            
            # Extract video IDs
            video_ids = [item.video_id for item in items if item.video_id]
            
            # Filter Shorts
            shorts, _ = await self.filter_shorts(video_ids)
            
            return shorts
            
        except APIError as e:
            logger.error(f"Failed to get Shorts from channel {channel_id}: {e}")
            return []
    
    async def get_shorts_from_channels(
        self,
        channel_ids: List[str],
        max_videos_per_channel: int = 200
    ) -> List[VideoMetadata]:
        """
        Fetch Shorts from multiple channels concurrently.
        
        Args:
            channel_ids: List of channel IDs
            max_videos_per_channel: Maximum videos to fetch per channel
            
        Returns:
            List of all Shorts from all channels
        """
        all_shorts = []
        
        # Create tasks for all channels
        tasks = []
        for channel_id in channel_ids:
            task = asyncio.create_task(
                self.get_shorts_from_channel(channel_id, max_videos_per_channel)
            )
            tasks.append(task)
        
        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error fetching Shorts from channel: {result}")
            else:
                all_shorts.extend(result)
        
        return all_shorts
    
    async def is_short_url(self, url: str) -> bool:
        """
        Check if a URL is a Shorts URL.
        
        This checks the URL pattern without making API calls.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is a Shorts URL
        """
        return await self.is_short_by_url(url)
