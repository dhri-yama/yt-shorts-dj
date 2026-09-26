# YouTube Shorts Daily Playlist Sync

Automatically fetches YouTube Shorts from configured channels and updates a target playlist daily.

## Features

- Fetches Shorts from multiple channels
- Filters by duration (60 seconds or less)
- Deduplicates using persistent history
- Random selection of 10-20 Shorts daily
- Clears previous day's items before adding new ones
- Automatic history persistence via Git
- Quota-optimized API usage
- Exponential backoff and retry logic
- Comprehensive error handling

## Prerequisites

- Python 3.11+
- YouTube Data API v3 enabled
- Google OAuth 2.0 credentials
- GitHub repository for scheduling

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd yt-shorts-dj

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure YouTube API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "YouTube Data API v3"
4. Create OAuth 2.0 credentials (Desktop app)
5. Generate a refresh token (see [OAuth Setup Guide](#oauth-20-setup))

### 3. Configure GitHub Repository

1. Go to Settings > Secrets > Actions
2. Add the following secrets:
   - `YOUTUBE_CLIENT_ID`: Your OAuth client ID
   - `YOUTUBE_CLIENT_SECRET`: Your OAuth client secret
   - `YOUTUBE_REFRESH_TOKEN`: Your refresh token
   - `YOUTUBE_API_KEY`: Your YouTube Data API key
   - `YOUTUBE_CHANNEL_IDS`: Comma-separated list of channel IDs
   - `TARGET_PLAYLIST_ID`: Your target playlist ID

### 4. Create Initial History File

```bash
# Create empty history file
touch history.json
git add history.json
git commit -m "Add initial history file"
git push
```

### 5. Test Locally

```bash
# Create .env file with your credentials
cp .env.template .env
# Edit .env with your credentials

# Run manually
python -m src.main --verbose
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `YOUTUBE_CLIENT_ID` | Yes | - | OAuth 2.0 Client ID |
| `YOUTUBE_CLIENT_SECRET` | Yes | - | OAuth 2.0 Client Secret |
| `YOUTUBE_REFRESH_TOKEN` | Yes | - | OAuth 2.0 Refresh Token |
| `YOUTUBE_API_KEY` | Yes | - | YouTube Data API v3 Key |
| `YOUTUBE_CHANNEL_IDS` | Yes | - | Comma-separated channel IDs |
| `TARGET_PLAYLIST_ID` | Yes | - | Target playlist ID |
| `BATCH_SIZE` | No | 15 | Number of Shorts to add daily (10-20) |
| `HISTORY_FILE` | No | history.json | Path to history file |
| `LOG_LEVEL` | No | INFO | Logging level |
| `MAX_RETRIES` | No | 3 | Maximum retry attempts |
| `BACKOFF_FACTOR` | No | 2.0 | Exponential backoff multiplier |

### YAML Configuration

Alternatively, create `config/config.yaml`:

```yaml
# YouTube API Configuration
youtube:
  api_key: "your-api-key"
  client_id: "your-client-id"
  client_secret: "your-client-secret"
  refresh_token: "your-refresh-token"

# Application Configuration
app:
  channel_ids:
    - "UC-channel-1"
    - "UC-channel-2"
  target_playlist_id: "PL-target-id"
  batch_size: 15
  history_file: "history.json"
  max_retries: 3
  backoff_factor: 2.0
  log_level: "INFO"
```

## OAuth 2.0 Setup

### Method A: Using Google OAuth Playground (Recommended)

1. Go to [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click the gear icon (Select & authorize APIs)
3. Select "YouTube Data API v3"
4. Check both scopes:
   - `https://www.googleapis.com/auth/youtube`
   - `https://www.googleapis.com/auth/youtube.readonly`
5. Click "Authorize APIs"
6. Sign in with your Google account
7. Click "Exchange authorization code for tokens"
8. Copy the **refresh_token** value

### Method B: Using Python Script

```bash
# Install required packages
pip install google-auth google-auth-oauthlib

# Create auth_script.py
cat > auth_script.py << 'EOF'
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.readonly'
]

flow = InstalledAppFlow.from_client_secrets_file(
    'client_secret.json',
    scopes=SCOPES
)

credentials = flow.run_local_server(port=8080)

print("Refresh Token:", credentials.refresh_token)
EOF

# Download client_secret.json from Google Cloud Console
# Run the script
python auth_script.py
```

## Getting Channel and Playlist IDs

- **Channel ID**: Found in channel URL: `https://www.youtube.com/channel/UCxxx` or `https://www.youtube.com/@ChannelName`
- **Playlist ID**: Found in playlist URL: `https://www.youtube.com/playlist?list=PLxxx`
- **Uploads Playlist**: Every channel has a special "Uploads" playlist with ID: `UU` + channel ID (e.g., `UUabc` for channel `UCabc`)

## Project Structure

```
yt-shorts-dj/
├── src/
│   ├── config.py              # Configuration loading and validation
│   ├── main.py                # Entry point and orchestration
│   ├── exceptions.py          # Custom exception hierarchy
│   ├── youtube/
│   │   ├── client.py          # YouTube API client
│   │   ├── models.py          # Data models
│   │   └── auth.py            # OAuth 2.0 authentication
│   ├── filters/
│   │   └── shorts_filter.py   # Shorts identification logic
│   ├── tracking/
│   │   ├── tracker.py         # History tracking
│   │   └── storage/           # Storage backends
│   │       ├── base.py        # Abstract interface
│   │       └── json_file.py   # JSON file implementation
│   ├── playlist/
│   │   └── manager.py         # Playlist management
│   └── utils/
│       ├── logging.py         # Logging setup
│       └── retry.py           # Retry logic
├── tests/                     # Unit tests
├── .github/workflows/        # GitHub Actions workflows
│   └── daily_shorts.yml
├── config/                    # Configuration files
│   └── default.yaml
├── history.json              # Persistent state
├── requirements.txt
└── README.md
```

## Architecture

The application follows SOLID principles:

- **SRP (Single Responsibility)**: Each class has one responsibility
  - `YouTubeClient`: Raw API calls
  - `ShortsFilter`: Business logic for identifying Shorts
  - `HistoryTracker`: Deduplication state management
  - `PlaylistManager`: High-level orchestration

- **OCP (Open/Closed)**: Storage backends can be swapped without modifying business logic

- **DIP (Dependency Inversion)**: Dependencies are injected via constructors

## Error Handling

- **Quota Exceeded**: Automatically detected and raised as `QuotaExceededError`
- **Token Refresh**: Automatic retry on 401/403 errors
- **Network Errors**: Exponential backoff with retry
- **Structured Logging**: All operations logged with configurable levels

## Quota Usage

The application is optimized to minimize YouTube API quota usage:

| Operation | Quota Units | Notes |
|-----------|-------------|-------|
| `channels.list` | 1 | Cached after first call |
| `playlistItems.list` | 1-3 | Fetch channel uploads |
| `videos.list` | 1 | Batch up to 50 IDs |
| `playlistItems.insert` | 1 | Add to playlist |
| `playlistItems.delete` | 1 | Remove from playlist |

**Estimated daily usage**: ~55 quota units (with 5 channels, 100 videos each)

**Free tier**: 10,000 units/day = ~180 days of buffer

## Troubleshooting

### Quota Exceeded Errors

- Check your quota usage at: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas
- Reduce the number of channels or batch size
- Request a quota increase from Google

### OAuth Token Errors

- Refresh tokens expire after 6 months of inactivity
- Regenerate refresh token if you get `invalid_grant` errors
- Ensure your OAuth consent screen is configured correctly

### GitHub Actions Issues

- Check Actions tab for detailed logs
- Ensure `GITHUB_TOKEN` has write permissions
- Verify all secrets are correctly configured

## License

MIT
