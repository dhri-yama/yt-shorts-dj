"""
Abstract base class for storage backends.

This implements the OCP (Open/Closed Principle) by allowing
storage backends to be swapped without modifying business logic.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional


class StorageBackend(ABC):
    """
    Abstract interface for history storage.
    
    Implement this class to create custom storage backends
    (e.g., SQLite, Redis, PostgreSQL, etc.).
    """
    
    @abstractmethod
    async def read(self) -> Dict[str, datetime]:
        """
        Read all stored video IDs with timestamps.
        
        Returns:
            Dictionary mapping video IDs to timestamps
        """
        pass
    
    @abstractmethod
    async def write(self, data: Dict[str, datetime]) -> None:
        """
        Write/overwrite all data.
        
        Args:
            data: Dictionary mapping video IDs to timestamps
        """
        pass
    
    @abstractmethod
    async def add(self, video_id: str, timestamp: datetime) -> None:
        """
        Add a single video ID to storage.
        
        Args:
            video_id: Video ID to add
            timestamp: Timestamp for this entry
        """
        pass
    
    @abstractmethod
    async def add_batch(self, video_ids: List[str], timestamp: datetime) -> None:
        """
        Add multiple video IDs to storage.
        
        Args:
            video_ids: List of video IDs to add
            timestamp: Timestamp for these entries
        """
        pass
    
    @abstractmethod
    async def contains(self, video_id: str) -> bool:
        """
        Check if a video ID exists in storage.
        
        Args:
            video_id: Video ID to check
            
        Returns:
            True if video ID exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def contains_batch(self, video_ids: List[str]) -> Dict[str, bool]:
        """
        Batch check for multiple video IDs.
        
        Args:
            video_ids: List of video IDs to check
            
        Returns:
            Dictionary mapping video IDs to boolean (exists or not)
        """
        pass
    
    async def get_all(self) -> Dict[str, datetime]:
        """
        Get all entries from storage.
        
        Returns:
            Dictionary mapping video IDs to timestamps
        """
        return await self.read()
    
    async def get_count(self) -> int:
        """
        Get the number of entries in storage.
        
        Returns:
            Number of video IDs stored
        """
        data = await self.read()
        return len(data)
