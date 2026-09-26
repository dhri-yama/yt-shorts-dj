"""
Playlist manager for high-level orchestration.

Handles fetching, filtering, deduplication, selection, and playlist updates.
"""

import asyncio
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from ..youtube.client import YouTubeClient
from ..youtube.models import VideoMetadata
from ..filters.shorts_filter import ShortsFilter
from ..tracking.tracker import HistoryTracker
from ..config import AppConfig
from ..exceptions import InsufficientShortsError, PlaylistError, APIError

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a daily sync operation."""
    
    status: str = "success"
    shorts_fetched: int = 0
    shorts_filtered: int = 0
    shorts_selected: int = 0
    playlist_cleared: int = 0
    playlist_updated: int = 0
    new_history_entries: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    selected_video_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "shorts_fetched": self.shorts_fetched,
            "shorts_filtered": self.shorts_filtered,
            "shorts_selected": self.shorts_selected,
            "playlist_cleared": self.playlist_cleared,
            "playlist_updated": self.playlist_updated,
            "new_history_entries": self.new_history_entries,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "selected_video_ids": self.selected_video_ids
        }


class PlaylistManager:
    """
    High-level orchestration of the YouTube Shorts workflow.
    
    Provides methods for:
    - Fetching Shorts from configured channels
    - Filtering and deduplicating Shorts
    - Selecting random subset for daily update
    - Clearing and updating target playlist
    - Running complete daily sync workflow
    """
    
    def __init__(
        self,
        youtube_client: YouTubeClient,
        shorts_filter: ShortsFilter,
        history_tracker: HistoryTracker,
        config: AppConfig
    ):
        """
        Initialize playlist manager.
        
        Args:
            youtube_client: YouTube client for API calls
            shorts_filter: Filter for identifying Shorts
            history_tracker: Tracker for deduplication
            config: Application configuration
        """
        self.client = youtube_client
        self.filter = shorts_filter
        self.history = history_tracker
        self.config = config
    
    async def fetch_shorts_from_channels(
        self,
        limit_per_channel: Optional[int] = None
    ) -> List[VideoMetadata]:
        """
        Fetch Shorts from all configured channels.
        
        Args:
            limit_per_channel: Maximum videos to fetch per channel
                          (default: batch_size * 2)
            
        Returns:
            List of all Shorts from all channels
        """
        limit = limit_per_channel or self.config.batch_size * 2
        
        try:
            shorts = await self.filter.get_shorts_from_channels(
                self.config.channel_ids,
                max_videos_per_channel=limit
            )
            logger.info(f"Fetched {len(shorts)} Shorts from {len(self.config.channel_ids)} channels")
            return shorts
        except Exception as e:
            logger.error(f"Failed to fetch Shorts from channels: {e}")
            raise PlaylistError(f"Failed to fetch Shorts: {e}") from e
    
    async def _filter_unseen_candidates(
        self,
        candidates: List[VideoMetadata]
    ) -> List[VideoMetadata]:
        """
        Filter out already-seen candidates.
        
        Args:
            candidates: List of candidate Shorts
            
        Returns:
            List of unseen Shorts
        """
        candidate_ids = [v.id for v in candidates]
        unseen_ids = await self.history.filter_unseen(candidate_ids)
        return [v for v in candidates if v.id in unseen_ids]
    
    async def select_unseen_shorts(
        self,
        count: int
    ) -> List[VideoMetadata]:
        """
        Select N unseen Shorts randomly.
        
        Args:
            count: Number of Shorts to select
            
        Returns:
            List of selected unseen Shorts
            
        Raises:
            InsufficientShortsError: If not enough unseen Shorts available
        """
        # Fetch candidate Shorts
        candidates = await self.fetch_shorts_from_channels()
        
        # Filter unseen
        unseen = await self._filter_unseen_candidates(candidates)
        
        if len(unseen) < count:
            raise InsufficientShortsError(
                f"Only {len(unseen)} unseen Shorts available, need {count}",
                available=len(unseen),
                requested=count
            )
        
        # Random selection
        selected = random.sample(unseen, count)
        
        # Mark as seen (before playlist update to prevent duplicates)
        await self.history.mark_seen([v.id for v in selected])
        
        logger.info(f"Selected {len(selected)} unseen Shorts")
        return selected
    
    async def clear_target_playlist(self) -> int:
        """
        Remove all items from target playlist.
        
        Returns:
            Number of items removed
        """
        try:
            count = await self.client.clear_playlist(self.config.target_playlist_id)
            logger.info(f"Cleared {count} items from target playlist")
            return count
        except APIError as e:
            logger.error(f"Failed to clear target playlist: {e}")
            raise PlaylistError(f"Failed to clear playlist: {e}") from e
    
    async def update_playlist(
        self,
        video_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Add videos to target playlist.
        
        Args:
            video_ids: List of video IDs to add
            
        Returns:
            List of API responses
        """
        if not video_ids:
            return []
        
        try:
            results = await self.client.add_videos_to_playlist(
                self.config.target_playlist_id,
                video_ids
            )
            logger.info(f"Added {len(results)} videos to target playlist")
            return results
        except APIError as e:
            logger.error(f"Failed to update playlist: {e}")
            raise PlaylistError(f"Failed to update playlist: {e}") from e
    
    async def run_daily_sync(self) -> SyncResult:
        """
        Execute the complete daily synchronization workflow.
        
        Steps:
        1. Fetch Shorts from all configured channels
        2. Filter out already-seen Shorts
        3. Randomly select N Shorts (batch_size)
        4. Mark selected Shorts as seen in history
        5. Clear existing items from target playlist
        6. Add selected Shorts to target playlist
        
        Returns:
            SyncResult with detailed statistics
            
        Raises:
            InsufficientShortsError: If not enough unseen Shorts available
            PlaylistError: If playlist operations fail
        """
        start_time = datetime.utcnow()
        
        result = SyncResult()
        
        try:
            # Step 1: Fetch Shorts from channels
            all_shorts = await self.fetch_shorts_from_channels()
            result.shorts_fetched = len(all_shorts)
            
            # Step 2: Filter unseen
            unseen = await self._filter_unseen_candidates(all_shorts)
            result.shorts_filtered = len(unseen)
            
            # Step 3: Select random subset
            count = min(len(unseen), self.config.batch_size)
            selected = random.sample(unseen, count)
            result.shorts_selected = len(selected)
            result.selected_video_ids = [v.id for v in selected]
            
            # Step 4: Mark as seen in history
            await self.history.mark_seen([v.id for v in selected])
            result.new_history_entries = len(selected)
            
            # Step 5: Clear target playlist
            cleared_count = await self.clear_target_playlist()
            result.playlist_cleared = cleared_count
            
            # Step 6: Add new Shorts to playlist
            await self.update_playlist([v.id for v in selected])
            result.playlist_updated = len(selected)
            
            result.status = "success"
            
        except InsufficientShortsError as e:
            result.status = "error"
            result.errors.append(f"Insufficient Shorts: {e}")
            raise
        except Exception as e:
            result.status = "error"
            result.errors.append(str(e))
            raise PlaylistError(f"Daily sync failed: {e}") from e
        finally:
            result.duration_seconds = (
                datetime.utcnow() - start_time
            ).total_seconds()
        
        logger.info(f"Daily sync completed in {result.duration_seconds:.2f}s: {result.to_dict()}")
        return result
    
    async def get_current_playlist_items(self) -> List[str]:
        """
        Get all video IDs currently in the target playlist.
        
        Returns:
            List of video IDs in the target playlist
        """
        try:
            items = await self.client.get_all_playlist_items(
                self.config.target_playlist_id,
                max_results=200
            )
            return [item.video_id for item in items if item.video_id]
        except APIError as e:
            logger.error(f"Failed to get current playlist items: {e}")
            return []
    
    async def verify_playlist_state(
        self,
        expected_video_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Verify that the playlist contains the expected videos.
        
        Args:
            expected_video_ids: List of video IDs that should be in playlist
            
        Returns:
            Dictionary with verification results
        """
        current_items = await self.get_current_playlist_items()
        
        expected_set = set(expected_video_ids)
        current_set = set(current_items)
        
        missing = expected_set - current_set
        extra = current_set - expected_set
        
        return {
            "expected_count": len(expected_video_ids),
            "current_count": len(current_items),
            "missing": list(missing),
            "extra": list(extra),
            "is_correct": len(missing) == 0 and len(extra) == 0
        }
