#!/usr/bin/env python
"""
Basic test script to verify the application structure.
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from src.config import load_config, AppConfig, YouTubeConfig, ConfigurationError
        print("  config: OK")
    except Exception as e:
        print(f"  config: FAILED - {e}")
        return False
    
    try:
        from src.exceptions import (
            YouTubeShortsError, ConfigurationError, QuotaExceededError,
            OAuthError, TokenRefreshError, InsufficientShortsError,
            StorageError, PlaylistError, APIError, NetworkError, RetryError
        )
        print("  exceptions: OK")
    except Exception as e:
        print(f"  exceptions: FAILED - {e}")
        return False
    
    try:
        from src.youtube.models import VideoDuration, VideoMetadata, PlaylistItem, ChannelInfo
        print("  youtube.models: OK")
    except Exception as e:
        print(f"  youtube.models: FAILED - {e}")
        return False
    
    try:
        from src.youtube.client import YouTubeClient
        print("  youtube.client: OK")
    except Exception as e:
        print(f"  youtube.client: FAILED - {e}")
        return False
    
    try:
        from src.youtube.auth import YouTubeAuth
        print("  youtube.auth: OK")
    except Exception as e:
        print(f"  youtube.auth: FAILED - {e}")
        return False
    
    try:
        from src.filters.shorts_filter import ShortsFilter
        print("  filters.shorts_filter: OK")
    except Exception as e:
        print(f"  filters.shorts_filter: FAILED - {e}")
        return False
    
    try:
        from src.tracking.storage.base import StorageBackend
        print("  tracking.storage.base: OK")
    except Exception as e:
        print(f"  tracking.storage.base: FAILED - {e}")
        return False
    
    try:
        from src.tracking.storage.json_file import JSONFileStorage
        print("  tracking.storage.json_file: OK")
    except Exception as e:
        print(f"  tracking.storage.json_file: FAILED - {e}")
        return False
    
    try:
        from src.tracking.tracker import HistoryTracker
        print("  tracking.tracker: OK")
    except Exception as e:
        print(f"  tracking.tracker: FAILED - {e}")
        return False
    
    try:
        from src.playlist.manager import PlaylistManager, SyncResult
        print("  playlist.manager: OK")
    except Exception as e:
        print(f"  playlist.manager: FAILED - {e}")
        return False
    
    try:
        from src.utils.logging import setup_logging, get_logger
        print("  utils.logging: OK")
    except Exception as e:
        print(f"  utils.logging: FAILED - {e}")
        return False
    
    try:
        from src.utils.retry import with_retry, retry, RetryConfig
        print("  utils.retry: OK")
    except Exception as e:
        print(f"  utils.retry: FAILED - {e}")
        return False
    
    try:
        from src.main import main
        print("  main: OK")
    except Exception as e:
        print(f"  main: FAILED - {e}")
        return False
    
    print("\nAll imports successful!")
    return True


def test_video_duration():
    """Test VideoDuration parsing."""
    from src.youtube.models import VideoDuration
    
    print("\nTesting VideoDuration...")
    
    # Test seconds
    d1 = VideoDuration.from_iso8601("PT30S")
    assert d1.total_seconds == 30.0
    assert d1.is_short is True
    print("  PT30S: OK")
    
    # Test minutes and seconds
    d2 = VideoDuration.from_iso8601("PT1M30S")
    assert d2.total_seconds == 90.0
    assert d2.is_short is False  # 90 seconds > 60, not a Short
    print("  PT1M30S: OK")
    
    # Test exactly 60 seconds
    d3 = VideoDuration.from_iso8601("PT1M")
    assert d3.total_seconds == 60.0
    assert d3.is_short is True
    print("  PT1M: OK")
    
    # Test just over 60 seconds
    d4 = VideoDuration.from_iso8601("PT1M1S")
    assert d4.total_seconds == 61.0
    assert d4.is_short is False
    print("  PT1M1S: OK")
    
    # Test hours
    d5 = VideoDuration.from_iso8601("PT1H2M3S")
    assert d5.total_seconds == 3723.0
    assert d5.is_short is False
    print("  PT1H2M3S: OK")
    
    print("VideoDuration tests passed!")
    return True


async def test_storage():
    """Test JSON file storage."""
    import tempfile
    from datetime import datetime
    from src.tracking.storage.json_file import JSONFileStorage
    
    print("\nTesting JSONFileStorage...")
    
    # Create temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.json"
        storage = JSONFileStorage(str(file_path))
        
        # Test write and read
        test_data = {
            "vid1": datetime.utcnow(),
            "vid2": datetime.utcnow()
        }
        await storage.write(test_data)
        print("  Write: OK")
        
        # Test read
        read_data = await storage.read()
        assert len(read_data) == 2
        assert "vid1" in read_data
        assert "vid2" in read_data
        print("  Read: OK")
        
        # Test contains
        assert await storage.contains("vid1") is True
        assert await storage.contains("vid3") is False
        print("  Contains: OK")
        
        # Test add
        new_time = datetime.utcnow()
        await storage.add("vid3", new_time)
        assert await storage.contains("vid3") is True
        print("  Add: OK")
        
        # Test contains_batch
        results = await storage.contains_batch(["vid1", "vid3", "vid4"])
        assert results["vid1"] is True
        assert results["vid3"] is True
        assert results["vid4"] is False
        print("  Contains batch: OK")
        
        # Test add_batch
        await storage.add_batch(["vid4", "vid5"], datetime.utcnow())
        assert await storage.contains("vid4") is True
        assert await storage.contains("vid5") is True
        print("  Add batch: OK")
    
    print("JSONFileStorage tests passed!")
    return True


async def test_history_tracker():
    """Test HistoryTracker."""
    import tempfile
    from datetime import datetime
    from src.tracking.storage.json_file import JSONFileStorage
    from src.tracking.tracker import HistoryTracker
    
    print("\nTesting HistoryTracker...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.json"
        storage = JSONFileStorage(str(file_path))
        tracker = HistoryTracker(storage)
        
        # Test mark_seen
        await tracker.mark_seen(["vid1", "vid2", "vid3"])
        
        # Test is_seen
        assert await tracker.is_seen("vid1") is True
        assert await tracker.is_seen("vid4") is False
        print("  Mark seen: OK")
        
        # Test filter_unseen
        unseen = await tracker.filter_unseen(["vid1", "vid4", "vid5"])
        assert "vid1" not in unseen
        assert "vid4" in unseen
        assert "vid5" in unseen
        print("  Filter unseen: OK")
        
        # Test get_seen_ids
        seen_ids = await tracker.get_seen_ids()
        assert "vid1" in seen_ids
        assert "vid2" in seen_ids
        assert "vid3" in seen_ids
        print("  Get seen IDs: OK")
        
        # Test get_count
        count = await tracker.get_count()
        assert count == 3
        print("  Get count: OK")
    
    print("HistoryTracker tests passed!")
    return True


async def test_main_functionality():
    """Test main application structure."""
    print("\nTesting main application structure...")
    
    from src.config import YouTubeConfig, AppConfig
    from src.youtube.client import YouTubeClient
    from src.filters.shorts_filter import ShortsFilter
    from src.tracking.storage.json_file import JSONFileStorage
    from src.tracking.tracker import HistoryTracker
    from src.playlist.manager import PlaylistManager
    
    # Create mock config
    config = AppConfig(
        youtube=YouTubeConfig(
            api_key="test-key",
            client_id="test-client",
            client_secret="test-secret",
            refresh_token="test-token"
        ),
        channel_ids=["UC-test"],
        target_playlist_id="PL-test"
    )
    
    # Create components
    client = YouTubeClient(config.youtube)
    storage = JSONFileStorage("test_history.json")
    filter_ = ShortsFilter(client)
    tracker = HistoryTracker(storage)
    manager = PlaylistManager(
        youtube_client=client,
        shorts_filter=filter_,
        history_tracker=tracker,
        config=config
    )
    
    print("  Component creation: OK")
    print("  Dependency injection: OK")
    
    # Verify manager has all dependencies
    assert manager.client is client
    assert manager.filter is filter_
    assert manager.history is tracker
    assert manager.config is config
    print("  Dependency verification: OK")
    
    print("Main application structure tests passed!")
    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("YouTube Shorts Daily Playlist Sync - Basic Tests")
    print("=" * 60)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test VideoDuration
    if not test_video_duration():
        all_passed = False
    
    # Test storage
    if not await test_storage():
        all_passed = False
    
    # Test history tracker
    if not await test_history_tracker():
        all_passed = False
    
    # Test main functionality
    if not await test_main_functionality():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
