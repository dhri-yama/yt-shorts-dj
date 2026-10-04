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

    async def fetch_unseen_shorts_for_channel(
        self,
        channel_id: str,
        target_count: int,
        max_scan_items: int = 500
    ) -> List[VideoMetadata]:
        """
        Paginates through a channel's uploads playlist in a loop until at least
        target_count unseen Shorts are found (or all uploads are exhausted).
        
        Args:
            channel_id: Channel ID to scan
            target_count: Number of unseen Shorts required from this channel
            max_scan_items: Safety limit for maximum upload items to scan
            
        Returns:
            List of unseen VideoMetadata objects for Shorts from this channel
        """
        unseen_shorts: List[VideoMetadata] = []
        scanned_count = 0
        page_token: Optional[str] = None
        
        try:
            uploads_playlist_id = await self.client.get_channel_uploads_playlist_id(channel_id)
        except Exception as e:
            logger.error(f"Failed to get uploads playlist for channel {channel_id}: {e}")
            return []
        
        logger.info(f"Scanning channel {channel_id} for {target_count} unseen Shorts...")
        
        while len(unseen_shorts) < target_count and scanned_count < max_scan_items:
            try:
                items, next_page_token = await self.client.get_playlist_items(
                    uploads_playlist_id,
                    page_token=page_token,
                    max_results=50
                )
            except Exception as e:
                logger.error(f"Error fetching uploads page for channel {channel_id}: {e}")
                break
            
            if not items:
                break
            
            scanned_count += len(items)
            video_ids = [item.video_id for item in items if item.video_id]
            
            # Filter out seen IDs using history first to avoid unnecessary metadata API calls
            unseen_ids = await self.history.filter_unseen(video_ids)
            
            if unseen_ids:
                # Filter unseen IDs to only valid Shorts (duration, public, non-live)
                shorts, _ = await self.filter.filter_shorts(unseen_ids)
                unseen_shorts.extend(shorts)
                logger.debug(
                    f"Channel {channel_id}: scanned {scanned_count} uploads -> "
                    f"found {len(unseen_shorts)}/{target_count} unseen Shorts"
                )
            
            if not next_page_token or len(unseen_shorts) >= target_count:
                break
            
            page_token = next_page_token
        
        logger.info(
            f"Finished scanning channel {channel_id}: found {len(unseen_shorts)} "
            f"unseen Shorts across {scanned_count} scanned uploads (target: {target_count})"
        )
        return unseen_shorts

    async def select_balanced_shorts(self) -> List[VideoMetadata]:
        """
        Fetch unseen Shorts in a loop for each channel until batch_size // num_channels
        videos are found per channel, then select and interleave them.
        
        Returns:
            List of selected VideoMetadata objects
            
        Raises:
            InsufficientShortsError: If total unseen Shorts across channels is below batch_size
        """
        channels = self.config.channel_ids
        if not channels:
            raise PlaylistError("No channel IDs configured")
        
        num_channels = len(channels)
        base_count = self.config.batch_size // num_channels
        remainder = self.config.batch_size % num_channels
        
        # Calculate target per channel (distributing remainder so sum == batch_size)
        channel_targets: Dict[str, int] = {}
        for i, channel_id in enumerate(channels):
            channel_targets[channel_id] = base_count + (1 if i < remainder else 0)
        
        logger.info(
            f"Selecting balanced playlist of {self.config.batch_size} Shorts across "
            f"{num_channels} channels. Per-channel targets: {channel_targets}"
        )
        
        # Fetch unseen Shorts concurrently for all channels in a loop
        tasks = [
            self.fetch_unseen_shorts_for_channel(cid, target)
            for cid, target in channel_targets.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        pool_per_channel: Dict[str, List[VideoMetadata]] = {}
        selected_per_channel: Dict[str, List[VideoMetadata]] = {}
        
        for cid, res in zip(channels, results):
            if isinstance(res, Exception):
                logger.error(f"Failed to fetch unseen shorts for channel {cid}: {res}")
                pool_per_channel[cid] = []
            else:
                pool_per_channel[cid] = res
        
        # Select target count from each channel
        for cid in channels:
            target = channel_targets[cid]
            available = pool_per_channel.get(cid, [])
            if len(available) >= target:
                chosen = random.sample(available, target)
            else:
                chosen = list(available)
                logger.warning(
                    f"Channel {cid} only had {len(chosen)} unseen Shorts (target was {target})"
                )
            selected_per_channel[cid] = chosen
        
        total_selected: List[VideoMetadata] = []
        for cid in channels:
            total_selected.extend(selected_per_channel[cid])
        
        # If any channel fell short of its quota, top up from channels with excess unseen shorts
        deficit = self.config.batch_size - len(total_selected)
        if deficit > 0:
            logger.info(f"Attempting to fill deficit of {deficit} videos from channels with extra candidates...")
            for cid in channels:
                chosen_ids = {v.id for v in selected_per_channel[cid]}
                extras = [v for v in pool_per_channel.get(cid, []) if v.id not in chosen_ids]
                if extras:
                    take = min(len(extras), deficit)
                    picked = random.sample(extras, take)
                    selected_per_channel[cid].extend(picked)
                    total_selected.extend(picked)
                    deficit -= take
                    if deficit == 0:
                        break
        
        # Check if we met the required batch_size
        if len(total_selected) < self.config.batch_size:
            raise InsufficientShortsError(
                f"Only {len(total_selected)} unseen Shorts available across all channels, need {self.config.batch_size}",
                available=len(total_selected),
                requested=self.config.batch_size
            )
        
        # Interleave channels round-robin for an alternating DJ mix
        interleaved: List[VideoMetadata] = []
        channel_queues = [list(selected_per_channel[cid]) for cid in channels]
        while any(channel_queues):
            for q in channel_queues:
                if q:
                    interleaved.append(q.pop(0))
        
        return interleaved
    
    async def select_unseen_shorts(
        self,
        count: int
    ) -> List[VideoMetadata]:
        """
        Select unseen Shorts using balanced per-channel selection.
        
        Args:
            count: Number of Shorts to select
            
        Returns:
            List of selected unseen Shorts
        """
        selected = await self.select_balanced_shorts()
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
        1. Loop and paginate per channel to fetch unseen Shorts until each channel
           reaches batch_size // num_channels videos
        2. Balance and interleave the selected Shorts
        3. Mark selected Shorts as seen in history
        4. Clear existing items from target playlist
        5. Add selected Shorts to target playlist
        
        Returns:
            SyncResult with detailed statistics
            
        Raises:
            InsufficientShortsError: If not enough unseen Shorts available
            PlaylistError: If playlist operations fail
        """
        start_time = datetime.utcnow()
        result = SyncResult()
        
        try:
            # Steps 1, 2, 3: Looped fetching, filtering, deduplication & balanced selection
            selected = await self.select_balanced_shorts()
            result.shorts_fetched = len(selected)
            result.shorts_filtered = len(selected)
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
