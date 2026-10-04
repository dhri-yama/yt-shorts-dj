import sys
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig, YouTubeConfig
from src.youtube.models import VideoMetadata, PlaylistItem, Snippet, ContentDetails, Status
from src.tracking.tracker import HistoryTracker
from src.playlist.manager import PlaylistManager
from src.exceptions import InsufficientShortsError


def make_mock_short(video_id: str, channel_id: str) -> VideoMetadata:
    return VideoMetadata(
        id=video_id,
        snippet=Snippet(
            channel_id=channel_id,
            title=f"Short {video_id}",
            published_at=datetime.utcnow(),
            live_broadcast_content=None
        ),
        content_details=ContentDetails(duration="PT30S"),
        status=Status(privacy_status="public")
    )


async def test_fetch_unseen_shorts_for_channel_loop():
    """Test that fetch_unseen_shorts_for_channel loops across pages until target_count is reached."""
    # Mock storage and tracker
    storage = AsyncMock()
    # Assume vid1 and vid2 were already seen in history
    storage.read = AsyncMock(return_value={"vid1": "2026-10-01", "vid2": "2026-10-01"})
    tracker = HistoryTracker(storage)

    client = AsyncMock()
    client.get_channel_uploads_playlist_id = AsyncMock(return_value="UU-channel-1")

    # Page 1 has vid1 (seen), vid2 (seen), vid3 (unseen)
    # Page 2 has vid4 (unseen), vid5 (unseen)
    page1_items = [
        PlaylistItem(id="item1", snippet={}, content_details={"videoId": "vid1"}),
        PlaylistItem(id="item2", snippet={}, content_details={"videoId": "vid2"}),
        PlaylistItem(id="item3", snippet={}, content_details={"videoId": "vid3"}),
    ]
    page2_items = [
        PlaylistItem(id="item4", snippet={}, content_details={"videoId": "vid4"}),
        PlaylistItem(id="item5", snippet={}, content_details={"videoId": "vid5"}),
    ]

    async def mock_get_playlist_items(playlist_id, page_token=None, max_results=50):
        if page_token is None:
            return page1_items, "token_page_2"
        elif page_token == "token_page_2":
            return page2_items, None
        return [], None

    client.get_playlist_items = mock_get_playlist_items

    filter_ = AsyncMock()
    # Filter returns any unseen videos as valid shorts
    filter_.filter_shorts = AsyncMock(side_effect=lambda ids: ([make_mock_short(i, "UC-1") for i in ids], []))

    config = AppConfig(
        youtube=YouTubeConfig("k", "c", "s", "r"),
        channel_ids=["UC-1"],
        target_playlist_id="PL-1",
        batch_size=12
    )

    manager = PlaylistManager(client, filter_, tracker, config)

    # We want 3 unseen shorts from UC-1
    shorts = await manager.fetch_unseen_shorts_for_channel("UC-1", target_count=3)

    assert len(shorts) == 3
    short_ids = [s.id for s in shorts]
    assert short_ids == ["vid3", "vid4", "vid5"]
    print("test_fetch_unseen_shorts_for_channel_loop passed!")


async def test_select_balanced_shorts():
    """Test that select_balanced_shorts picks batch_size // num_channels from each channel and interleaves."""
    storage = AsyncMock()
    storage.read = AsyncMock(return_value={})
    tracker = HistoryTracker(storage)

    client = AsyncMock()
    filter_ = AsyncMock()

    config = AppConfig(
        youtube=YouTubeConfig("k", "c", "s", "r"),
        channel_ids=["UC-A", "UC-B", "UC-C"],
        target_playlist_id="PL-1",
        batch_size=12
    )
    # 12 // 3 = 4 videos per channel

    manager = PlaylistManager(client, filter_, tracker, config)

    # Mock fetch_unseen_shorts_for_channel
    async def mock_fetch_unseen(channel_id, target_count, max_scan_items=500):
        return [make_mock_short(f"{channel_id}_v{i}", channel_id) for i in range(target_count)]

    manager.fetch_unseen_shorts_for_channel = mock_fetch_unseen

    selected = await manager.select_balanced_shorts()

    assert len(selected) == 12
    # Verify counts per channel
    counts = {}
    for s in selected:
        cid = s.snippet.channel_id
        counts[cid] = counts.get(cid, 0) + 1

    assert counts["UC-A"] == 4
    assert counts["UC-B"] == 4
    assert counts["UC-C"] == 4

    # Verify interleaving (round-robin: A, B, C, A, B, C...)
    assert selected[0].snippet.channel_id == "UC-A"
    assert selected[1].snippet.channel_id == "UC-B"
    assert selected[2].snippet.channel_id == "UC-C"
    assert selected[3].snippet.channel_id == "UC-A"
    print("test_select_balanced_shorts passed!")


if __name__ == "__main__":
    asyncio.run(test_fetch_unseen_shorts_for_channel_loop())
    asyncio.run(test_select_balanced_shorts())
