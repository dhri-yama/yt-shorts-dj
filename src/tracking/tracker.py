"""
History tracker for deduplication.

Manages reading/writing seen video IDs from persistent storage.
"""

import logging
from datetime import datetime
from typing import List, Set, Optional

from .storage.base import StorageBackend
from ..exceptions import StorageError

logger = logging.getLogger(__name__)


class HistoryTracker:
    """
    Manages deduplication state using a storage backend.
    
    Provides caching for performance and batch operations for efficiency.
    """
    
    def __init__(self, storage: StorageBackend):
        """
        Initialize history tracker.
        
        Args:
            storage: Storage backend to use for persistence
        """
        self.storage = storage
        self._cached_history: Optional[Set[str]] = None
    
    async def _ensure_cache(self) -> Set[str]:
        """
        Lazy load history into cache.
        
        Returns:
            Set of all seen video IDs
        """
        if self._cached_history is None:
            try:
                data = await self.storage.read()
                self._cached_history = set(data.keys())
                logger.debug(f"Loaded {len(self._cached_history)} video IDs from history")
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
                self._cached_history = set()
        
        return self._cached_history
    
    async def get_seen_ids(self) -> Set[str]:
        """
        Get all seen video IDs.
        
        Returns:
            Set of all seen video IDs
        """
        return await self._ensure_cache()
    
    async def is_seen(self, video_id: str) -> bool:
        """
        Check if a video ID was already added.
        
        Args:
            video_id: Video ID to check
            
        Returns:
            True if video was already added, False otherwise
        """
        seen = await self._ensure_cache()
        return video_id in seen
    
    async def filter_unseen(self, video_ids: List[str]) -> List[str]:
        """
        Filter out already-seen video IDs.
        
        Args:
            video_ids: List of video IDs to filter
            
        Returns:
            List of video IDs that have not been seen
        """
        seen = await self._ensure_cache()
        return [vid for vid in video_ids if vid not in seen]
    
    async def mark_seen(self, video_ids: List[str]) -> None:
        """
        Mark video IDs as seen and persist to storage.
        
        Args:
            video_ids: List of video IDs to mark as seen
        """
        now = datetime.utcnow()
        
        try:
            # Update cache first
            if self._cached_history is None:
                await self._ensure_cache()
            
            # Add to cache
            new_ids = [vid for vid in video_ids if vid not in self._cached_history]
            if new_ids:
                self._cached_history.update(new_ids)
                logger.debug(f"Marked {len(new_ids)} new video IDs as seen")
            
            # Persist to storage
            if new_ids:
                await self.storage.add_batch(new_ids, now)
                logger.info(f"Added {len(new_ids)} video IDs to history storage")
                
        except Exception as e:
            logger.error(f"Failed to mark video IDs as seen: {e}")
            raise StorageError(f"Failed to mark video IDs as seen: {e}") from e
    
    async def mark_seen_and_flush(self, video_ids: List[str]) -> None:
        """
        Mark video IDs as seen and force flush to storage.
        
        Args:
            video_ids: List of video IDs to mark as seen
        """
        await self.mark_seen(video_ids)
        # Clear cache to force re-read on next access
        self._cached_history = None
    
    async def flush_cache(self) -> None:
        """Flush the in-memory cache."""
        self._cached_history = None
    
    async def get_count(self) -> int:
        """
        Get the number of seen video IDs.
        
        Returns:
            Number of video IDs in history
        """
        try:
            return await self.storage.get_count()
        except Exception as e:
            logger.error(f"Failed to get history count: {e}")
            return 0
    
    async def get_history(self) -> dict:
        """
        Get the complete history dictionary.
        
        Returns:
            Dictionary mapping video IDs to timestamps
        """
        try:
            return await self.storage.read()
        except Exception as e:
            logger.error(f"Failed to read history: {e}")
            return {}
    
    async def clear(self) -> None:
        """Clear all history."""
        try:
            await self.storage.clear()
            self._cached_history = None
            logger.info("History cleared")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            raise StorageError(f"Failed to clear history: {e}") from e
