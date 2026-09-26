"""
Data models for YouTube API responses.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class VideoType(Enum):
    """Types of YouTube videos."""
    SHORT = "short"
    STANDARD = "standard"
    LIVE = "live"
    UPCOMING = "upcoming"
    PREMIERE = "premiere"


@dataclass
class VideoDuration:
    """Parsed duration in ISO 8601 format (PT#H#M#S)."""
    
    total_seconds: float
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    
    @classmethod
    def from_iso8601(cls, duration_str: str) -> "VideoDuration":
        """
        Parse ISO 8601 duration format.
        
        Examples:
            PT30S -> 30 seconds
            PT1M30S -> 1 minute 30 seconds
            PT1H2M3S -> 1 hour 2 minutes 3 seconds
        """
        if not duration_str:
            return cls(total_seconds=0.0)
        
        # Remove PT prefix
        duration_str = duration_str.upper().replace("PT", "")
        
        # Parse components
        hours = 0
        minutes = 0
        seconds = 0
        
        # Find hours
        hour_match = re.search(r'(\d+)H', duration_str)
        if hour_match:
            hours = int(hour_match.group(1))
            duration_str = duration_str.replace(hour_match.group(0), "")
        
        # Find minutes
        minute_match = re.search(r'(\d+)M', duration_str)
        if minute_match:
            minutes = int(minute_match.group(1))
            duration_str = duration_str.replace(minute_match.group(0), "")
        
        # Find seconds
        second_match = re.search(r'(\d+)S', duration_str)
        if second_match:
            seconds = int(second_match.group(1))
        
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return cls(
            total_seconds=total_seconds,
            hours=hours,
            minutes=minutes,
            seconds=seconds
        )
    
    @property
    def is_short(self) -> bool:
        """Check if duration is <= 60 seconds."""
        return self.total_seconds <= 300.0
    
    def __str__(self) -> str:
        """Return ISO 8601 format."""
        parts = []
        if self.hours > 0:
            parts.append(f"{self.hours}H")
        if self.minutes > 0:
            parts.append(f"{self.minutes}M")
        if self.seconds > 0 or not parts:
            parts.append(f"{self.seconds}S")
        return f"PT{''.join(parts)}"


@dataclass
class Thumbnail:
    """Video thumbnail information."""
    url: str
    width: int
    height: int


@dataclass
class Snippet:
    """Basic video snippet information."""
    published_at: Optional[datetime] = None
    channel_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnails: Dict[str, Thumbnail] = field(default_factory=dict)
    channel_title: Optional[str] = None
    tags: Optional[list] = None
    category_id: Optional[str] = None
    live_broadcast_content: Optional[str] = None


@dataclass
class ContentDetails:
    """Video content details."""
    duration: Optional[str] = None
    dimension: Optional[str] = None
    definition: Optional[str] = None
    caption: Optional[str] = None
    licensed_content: Optional[bool] = None
    content_rating: Optional[dict] = None
    projection: Optional[str] = None


@dataclass
class Status:
    """Video status."""
    upload_status: Optional[str] = None
    failure_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    privacy_status: Optional[str] = None
    publish_at: Optional[datetime] = None
    license: Optional[str] = None
    embeddable: Optional[bool] = None
    public_stats_viewable: Optional[bool] = None
    made_for_kids: Optional[bool] = None
    self_declared_made_for_kids: Optional[bool] = None


@dataclass
class VideoMetadata:
    """Complete video metadata."""
    
    id: str
    snippet: Snippet = field(default_factory=Snippet)
    content_details: ContentDetails = field(default_factory=ContentDetails)
    status: Status = field(default_factory=Status)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], video_id: Optional[str] = None) -> "VideoMetadata":
        """Create VideoMetadata from API response dictionary."""
        snippet_data = data.get("snippet", {})
        content_details_data = data.get("contentDetails", {})
        status_data = data.get("status", {})
        
        # Parse published_at
        published_at = None
        if snippet_data.get("publishedAt"):
            published_at = datetime.fromisoformat(
                snippet_data["publishedAt"].replace("Z", "+00:00")
            )
        
        # Parse thumbnails
        thumbnails = {}
        if snippet_data.get("thumbnails"):
            for name, thumb_data in snippet_data["thumbnails"].items():
                thumbnails[name] = Thumbnail(
                    url=thumb_data.get("url", ""),
                    width=thumb_data.get("width", 0),
                    height=thumb_data.get("height", 0)
                )
        
        # Parse publish_at from status
        publish_at = None
        if status_data.get("publishAt"):
            publish_at = datetime.fromisoformat(
                status_data["publishAt"].replace("Z", "+00:00")
            )
        
        return cls(
            id=video_id or data.get("id", ""),
            snippet=Snippet(
                published_at=published_at,
                channel_id=snippet_data.get("channelId"),
                title=snippet_data.get("title"),
                description=snippet_data.get("description"),
                thumbnails=thumbnails,
                channel_title=snippet_data.get("channelTitle"),
                tags=snippet_data.get("tags"),
                category_id=snippet_data.get("categoryId"),
                live_broadcast_content=snippet_data.get("liveBroadcastContent")
            ),
            content_details=ContentDetails(
                duration=content_details_data.get("duration"),
                dimension=content_details_data.get("dimension"),
                definition=content_details_data.get("definition"),
                caption=content_details_data.get("caption"),
                licensed_content=content_details_data.get("licensedContent"),
                content_rating=content_details_data.get("contentRating"),
                projection=content_details_data.get("projection")
            ),
            status=Status(
                upload_status=status_data.get("uploadStatus"),
                failure_reason=status_data.get("failureReason"),
                rejection_reason=status_data.get("rejectionReason"),
                privacy_status=status_data.get("privacyStatus"),
                publish_at=publish_at,
                license=status_data.get("license"),
                embeddable=status_data.get("embeddable"),
                public_stats_viewable=status_data.get("publicStatsViewable"),
                made_for_kids=status_data.get("madeForKids"),
                self_declared_made_for_kids=status_data.get("selfDeclaredMadeForKids")
            )
        )
    
    @property
    def is_short(self) -> bool:
        """Check if this video is a YouTube Short."""
        # Primary check: duration
        if self.content_details.duration:
            duration = VideoDuration.from_iso8601(self.content_details.duration)
            if duration.is_short:
                return True
        
        # Fallback: check URL or live status
        # Shorts don't have live broadcast content
        if self.snippet.live_broadcast_content:
            return False
        
        return False
    
    @property
    def is_public(self) -> bool:
        """Check if video is public."""
        return self.status.privacy_status == "public"
    
    @property
    def is_live(self) -> bool:
        """Check if video is live or was live."""
        return self.snippet.live_broadcast_content in ["live", "upcoming"]
    
    @property
    def url(self) -> str:
        """Get video URL."""
        return f"https://www.youtube.com/watch?v={self.id}"
    
    @property
    def short_url(self) -> str:
        """Get short URL."""
        return f"https://youtu.be/{self.id}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "snippet": {
                "publishedAt": self.snippet.published_at.isoformat() if self.snippet.published_at else None,
                "channelId": self.snippet.channel_id,
                "title": self.snippet.title,
                "description": self.snippet.description,
                "channelTitle": self.snippet.channel_title,
                "tags": self.snippet.tags,
                "categoryId": self.snippet.category_id,
                "liveBroadcastContent": self.snippet.live_broadcast_content
            },
            "contentDetails": {
                "duration": self.content_details.duration
            },
            "status": {
                "privacyStatus": self.status.privacy_status
            }
        }


@dataclass
class PlaylistItem:
    """Playlist item information."""
    
    id: str
    snippet: Dict[str, Any]
    content_details: Optional[Dict[str, Any]] = None
    status: Optional[Dict[str, Any]] = None
    
    @property
    def video_id(self) -> str:
        """Get the video ID from this playlist item."""
        if self.content_details and "videoId" in self.content_details:
            return self.content_details["videoId"]
        if self.snippet.get("resourceId", {}).get("videoId"):
            return self.snippet["resourceId"]["videoId"]
        return ""
    
    @property
    def playlist_id(self) -> str:
        """Get the playlist ID."""
        return self.snippet.get("playlistId", "")
    
    @property
    def position(self) -> int:
        """Get the position in the playlist."""
        return int(self.snippet.get("position", 0))
    
    @property
    def published_at(self) -> Optional[datetime]:
        """Get the published date."""
        if self.snippet.get("publishedAt"):
            return datetime.fromisoformat(
                self.snippet["publishedAt"].replace("Z", "+00:00")
            )
        return None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaylistItem":
        """Create PlaylistItem from API response dictionary."""
        return cls(
            id=data.get("id", ""),
            snippet=data.get("snippet", {}),
            content_details=data.get("contentDetails"),
            status=data.get("status")
        )


@dataclass
class ChannelInfo:
    """Channel information."""
    
    id: str
    snippet: Dict[str, Any]
    content_details: Optional[Dict[str, Any]] = None
    
    @property
    def uploads_playlist_id(self) -> str:
        """Get the uploads playlist ID."""
        if self.content_details:
            related_playlists = self.content_details.get("relatedPlaylists", {})
            return related_playlists.get("uploads", "")
        return ""
    
    @property
    def title(self) -> str:
        """Get channel title."""
        return self.snippet.get("title", "")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelInfo":
        """Create ChannelInfo from API response dictionary."""
        return cls(
            id=data.get("id", ""),
            snippet=data.get("snippet", {}),
            content_details=data.get("contentDetails")
        )


@dataclass
class PlaylistMetadata:
    """Playlist metadata."""
    
    id: str
    snippet: Dict[str, Any]
    content_details: Optional[Dict[str, Any]] = None
    status: Optional[Dict[str, Any]] = None
    
    @property
    def title(self) -> str:
        """Get playlist title."""
        return self.snippet.get("title", "")
    
    @property
    def item_count(self) -> int:
        """Get item count."""
        return int(self.content_details.get("itemCount", 0)) if self.content_details else 0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaylistMetadata":
        """Create PlaylistMetadata from API response dictionary."""
        return cls(
            id=data.get("id", ""),
            snippet=data.get("snippet", {}),
            content_details=data.get("contentDetails"),
            status=data.get("status")
        )
