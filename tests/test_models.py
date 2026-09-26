"""
Tests for YouTube models.
"""

import pytest
from datetime import datetime

from src.youtube.models import (
    VideoDuration,
    VideoMetadata,
    PlaylistItem,
    ChannelInfo
)


class TestVideoDuration:
    """Tests for VideoDuration."""
    
    def test_from_iso8601_seconds(self):
        """Test parsing seconds-only duration."""
        duration = VideoDuration.from_iso8601("PT30S")
        assert duration.total_seconds == 30.0
        assert duration.seconds == 30
        assert duration.minutes == 0
        assert duration.hours == 0
        assert duration.is_short is True
    
    def test_from_iso8601_minutes(self):
        """Test parsing minutes and seconds duration."""
        duration = VideoDuration.from_iso8601("PT1M30S")
        assert duration.total_seconds == 90.0
        assert duration.seconds == 30
        assert duration.minutes == 1
        assert duration.hours == 0
        assert duration.is_short is True
    
    def test_from_iso8601_hours(self):
        """Test parsing hours, minutes, and seconds duration."""
        duration = VideoDuration.from_iso8601("PT1H2M3S")
        assert duration.total_seconds == 3723.0
        assert duration.seconds == 3
        assert duration.minutes == 2
        assert duration.hours == 1
        assert duration.is_short is False
    
    def test_from_iso8601_exactly_60_seconds(self):
        """Test duration exactly at 60 seconds."""
        duration = VideoDuration.from_iso8601("PT1M")
        assert duration.total_seconds == 60.0
        assert duration.is_short is True
    
    def test_from_iso8601_just_over_60_seconds(self):
        """Test duration just over 60 seconds."""
        duration = VideoDuration.from_iso8601("PT1M1S")
        assert duration.total_seconds == 61.0
        assert duration.is_short is False
    
    def test_from_iso8601_empty(self):
        """Test empty duration string."""
        duration = VideoDuration.from_iso8601("")
        assert duration.total_seconds == 0.0
    
    def test_from_iso8601_none(self):
        """Test None duration."""
        duration = VideoDuration.from_iso8601(None)
        assert duration.total_seconds == 0.0
    
    def test_to_string(self):
        """Test converting duration to string."""
        duration = VideoDuration.from_iso8601("PT1H2M3S")
        assert str(duration) == "PT1H2M3S"
    
    def test_to_string_minutes_only(self):
        """Test converting minutes-only duration to string."""
        duration = VideoDuration.from_iso8601("PT5M")
        assert str(duration) == "PT5M0S"


class TestPlaylistItem:
    """Tests for PlaylistItem."""
    
    def test_from_dict(self):
        """Test creating PlaylistItem from dict."""
        data = {
            "id": "test-item-id",
            "snippet": {
                "playlistId": "PL-test",
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": "test-video-id"
                },
                "position": 0
            },
            "contentDetails": {
                "videoId": "test-video-id"
            }
        }
        
        item = PlaylistItem.from_dict(data)
        
        assert item.id == "test-item-id"
        assert item.video_id == "test-video-id"
        assert item.playlist_id == "PL-test"
        assert item.position == 0


class TestChannelInfo:
    """Tests for ChannelInfo."""
    
    def test_uploads_playlist_id(self):
        """Test extracting uploads playlist ID."""
        data = {
            "id": "UC-test",
            "snippet": {
                "title": "Test Channel"
            },
            "contentDetails": {
                "relatedPlaylists": {
                    "uploads": "UU-test-uploads"
                }
            }
        }
        
        channel = ChannelInfo.from_dict(data)
        
        assert channel.id == "UC-test"
        assert channel.title == "Test Channel"
        assert channel.uploads_playlist_id == "UU-test-uploads"
