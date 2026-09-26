"""
JSON file storage backend for history tracking.

This is the default storage implementation using a JSON file.
"""

import json
import os
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from .base import StorageBackend
from ...exceptions import StorageError


class JSONFileStorage(StorageBackend):
    """
    JSON file storage implementation.
    
    Stores history as a JSON file with video IDs as keys and
    ISO-formatted timestamps as values.
    
    Example file content:
    {
        "video_id_1": "2024-01-01T12:00:00+00:00",
        "video_id_2": "2024-01-02T12:00:00+00:00"
    }
    """
    
    def __init__(self, file_path: str):
        """
        Initialize JSON file storage.
        
        Args:
            file_path: Path to the JSON file
        """
        self.file_path = Path(file_path)
        
        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for read operations
        self._cache: Optional[Dict[str, datetime]] = None
    
    async def read(self) -> Dict[str, datetime]:
        """
        Read all stored video IDs with timestamps.
        
        Uses lazy loading with in-memory cache.
        
        Returns:
            Dictionary mapping video IDs to timestamps
        """
        # Use cache if available
        if self._cache is not None:
            return self._cache
        
        # Load from file
        if not self.file_path.exists():
            self._cache = {}
            return self._cache
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert string timestamps to datetime
            self._cache = {}
            for video_id, timestamp_str in data.items():
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    self._cache[video_id] = timestamp
                except (ValueError, TypeError):
                    # Skip invalid entries
                    continue
            
            return self._cache
            
        except (json.JSONDecodeError, KeyError, IOError) as e:
            # Corrupted file, start fresh
            self._cache = {}
            raise StorageError(f"Failed to read storage file: {e}")
    
    async def write(self, data: Dict[str, datetime]) -> None:
        """
        Write/overwrite all data to file.
        
        Uses atomic write (temp file + rename) to prevent corruption.
        
        Args:
            data: Dictionary mapping video IDs to timestamps
        """
        # Convert datetime to ISO format strings
        serialized = {
            vid: ts.isoformat()
            for vid, ts in data.items()
        }
        
        # Create temp file
        temp_path = self.file_path.with_suffix('.tmp')
        
        try:
            # Write to temp file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            os.replace(temp_path, self.file_path)
            
            # Update cache
            self._cache = dict(data)
            
        except IOError as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except IOError:
                    pass
            raise StorageError(f"Failed to write storage file: {e}")
    
    async def add(self, video_id: str, timestamp: datetime) -> None:
        """
        Add a single video ID to storage.
        
        Args:
            video_id: Video ID to add
            timestamp: Timestamp for this entry
        """
        data = await self.read()
        data[video_id] = timestamp
        await self.write(data)
    
    async def add_batch(self, video_ids: List[str], timestamp: datetime) -> None:
        """
        Add multiple video IDs to storage.
        
        Args:
            video_ids: List of video IDs to add
            timestamp: Timestamp for these entries
        """
        data = await self.read()
        for video_id in video_ids:
            data[video_id] = timestamp
        await self.write(data)
    
    async def contains(self, video_id: str) -> bool:
        """
        Check if a video ID exists in storage.
        
        Args:
            video_id: Video ID to check
            
        Returns:
            True if video ID exists, False otherwise
        """
        data = await self.read()
        return video_id in data
    
    async def contains_batch(self, video_ids: List[str]) -> Dict[str, bool]:
        """
        Batch check for multiple video IDs.
        
        Args:
            video_ids: List of video IDs to check
            
        Returns:
            Dictionary mapping video IDs to boolean (exists or not)
        """
        data = await self.read()
        return {vid: vid in data for vid in video_ids}
    
    async def flush(self) -> None:
        """
        Flush the in-memory cache.
        
        Forces re-read from file on next access.
        """
        self._cache = None
    
    async def clear(self) -> None:
        """
        Clear all data from storage.
        """
        await self.write({})
