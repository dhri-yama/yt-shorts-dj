"""
Pytest fixtures for YouTube Shorts automation tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any

from src.config import AppConfig, YouTubeConfig
from src.youtube.models import VideoMetadata, VideoDuration, PlaylistItem
from src.tracking.storage.json_file import JSONFileStorage
from src.tracking.tracker import HistoryTracker
from src.filters.shorts_filter import ShortsFilter
from src.playlist.manager import PlaylistManager


@pytest.fixture
def mock_youtube_config():
    """Create a mock YouTube configuration."""
    return YouTubeConfig(
        api_key="test-api-key",
        client_id="test-client-id",
        client_secret="test-client-secret",
        refresh_token="test-refresh-token"
    )


@pytest.fixture
def mock_app_config(mock_youtube_config):
    """Create a mock application configuration."""
    return AppConfig(
        youtube=mock_youtube_config,
        channel_ids=["UC-test-1", "UC-test-2"],
        target_playlist_id="PL-test",
        batch_size=15,
        history_file="test_history.json",
        max_retries=3,
        backoff_factor=2.0,
        log_level="DEBUG"
    )


@pytest.fixture
def mock_video_metadata():
    """Create mock video metadata."""
    return VideoMetadata(
        id="test-video-id",
        snippet=MagicMock(
            channel_id="UC-test",
            title="Test Video",
            description="Test Description",
            channel_title="Test Channel",
            live_broadcast_content=None,
            published_at=datetime.utcnow()
        ),
        content_details=MagicMock(
            duration="PT30S"  # 30 seconds
        ),
        status=MagicMock(
            privacy_status="public"
        )
    )


@pytest.fixture
def mock_short_video_metadata():
    """Create mock Short video metadata."""
    return VideoMetadata(
        id="short-video-id",
        snippet=MagicMock(
            channel_id="UC-test",
            title="Test Short",
            channel_title="Test Channel",
            live_broadcast_content=None,
            published_at=datetime.utcnow()
        ),
        content_details=MagicMock(
            duration="PT45S"  # 45 seconds
        ),
        status=MagicMock(
            privacy_status="public"
        )
    )


@pytest.fixture
def mock_long_video_metadata():
    """Create mock long video metadata."""
    return VideoMetadata(
        id="long-video-id",
        snippet=MagicMock(
            channel_id="UC-test",
            title="Test Long Video",
            channel_title="Test Channel",
            live_broadcast_content=None,
            published_at=datetime.utcnow()
        ),
        content_details=MagicMock(
            duration="PT5M"  # 5 minutes
        ),
        status=MagicMock(
            privacy_status="public"
        )
    )


@pytest.fixture
def mock_live_video_metadata():
    """Create mock live video metadata."""
    return VideoMetadata(
        id="live-video-id",
        snippet=MagicMock(
            channel_id="UC-test",
            title="Live Stream",
            channel_title="Test Channel",
            live_broadcast_content="live",
            published_at=datetime.utcnow()
        ),
        content_details=MagicMock(
            duration="PT1H"  # 1 hour
        ),
        status=MagicMock(
            privacy_status="public"
        )
    )


@pytest.fixture
def mock_playlist_item():
    """Create mock playlist item."""
    return PlaylistItem(
        id="test-item-id",
        snippet={
            "playlistId": "PL-test",
            "resourceId": {
                "kind": "youtube#video",
                "videoId": "test-video-id"
            },
            "position": 0,
            "publishedAt": datetime.utcnow().isoformat() + "Z"
        },
        content_details={
            "videoId": "test-video-id"
        }
    )


@pytest.fixture
def mock_youtube_client(mock_youtube_config):
    """Create a mock YouTube client."""
    client = AsyncMock()
    client.config = mock_youtube_config
    return client


@pytest.fixture
def mock_shorts_filter(mock_youtube_client):
    """Create a mock Shorts filter."""
    return ShortsFilter(mock_youtube_client)


@pytest.fixture
def mock_storage(tmp_path):
    """Create a temporary JSON file storage."""
    file_path = tmp_path / "test_history.json"
    return JSONFileStorage(str(file_path))


@pytest.fixture
def mock_history_tracker(mock_storage):
    """Create a mock history tracker."""
    return HistoryTracker(mock_storage)


@pytest.fixture
def mock_playlist_manager(mock_youtube_client, mock_shorts_filter, 
                          mock_history_tracker, mock_app_config):
    """Create a mock playlist manager."""
    return PlaylistManager(
        youtube_client=mock_youtube_client,
        shorts_filter=mock_shorts_filter,
        history_tracker=mock_history_tracker,
        config=mock_app_config
    )
