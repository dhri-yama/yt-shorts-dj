"""
Main entry point for YouTube Shorts daily playlist sync.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import load_config, AppConfig
from .youtube.client import YouTubeClient
from .filters.shorts_filter import ShortsFilter
from .tracking.tracker import HistoryTracker
from .tracking.storage.json_file import JSONFileStorage
from .playlist.manager import PlaylistManager
from .utils.logging import setup_logging
from .utils.retry import with_retry
from .exceptions import (
    YouTubeShortsError,
    ConfigurationError,
    QuotaExceededError,
    InsufficientShortsError,
    PlaylistError,
)

logger = logging.getLogger(__name__)


async def main(
    config_path: Optional[str] = None,
    verbose: bool = False
) -> int:
    """
    Main application entry point.
    
    Args:
        config_path: Optional path to configuration file
        verbose: Enable verbose logging
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load configuration first (before logging setup)
    config = load_config(config_path)
    
    if verbose:
        config.log_level = "DEBUG"
    
    # Setup logging with configured level
    setup_logging(config.log_level)
    
    # Get logger after setup
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting YouTube Shorts daily sync")
        logger.debug(f"Configuration: batch_size={config.batch_size}, "
                     f"channel_ids={config.channel_ids}, "
                     f"target_playlist_id={config.target_playlist_id}")
        
        # Initialize storage
        logger.info(f"Initializing storage at {config.history_file}")
        storage = JSONFileStorage(config.history_file)
        
        # Initialize YouTube client
        logger.info("Initializing YouTube client...")
        youtube_client = YouTubeClient(config.youtube)
        
        # Build dependency chain
        logger.info("Initializing components...")
        shorts_filter = ShortsFilter(youtube_client)
        history_tracker = HistoryTracker(storage)
        playlist_manager = PlaylistManager(
            youtube_client=youtube_client,
            shorts_filter=shorts_filter,
            history_tracker=history_tracker,
            config=config
        )
        
        # Execute daily sync with retry
        logger.info("Running daily sync...")
        result = await with_retry(
            playlist_manager.run_daily_sync,
            max_retries=config.max_retries,
            backoff_factor=config.backoff_factor
        )
        
        logger.info(f"Daily sync completed successfully!")
        logger.info(f"  Shorts fetched: {result.shorts_fetched}")
        logger.info(f"  Shorts filtered: {result.shorts_filtered}")
        logger.info(f"  Shorts selected: {result.shorts_selected}")
        logger.info(f"  Playlist cleared: {result.playlist_cleared}")
        logger.info(f"  Playlist updated: {result.playlist_updated}")
        logger.info(f"  New history entries: {result.new_history_entries}")
        logger.info(f"  Duration: {result.duration_seconds:.2f}s")
        
        # Ensure history is flushed to disk
        await storage.flush()
        
        return 0
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return 1
        
    except QuotaExceededError as e:
        logger.error(f"YouTube API quota exceeded: {e}")
        return 1
        
    except InsufficientShortsError as e:
        logger.error(f"Not enough unseen Shorts available: {e}")
        return 1
        
    except PlaylistError as e:
        logger.error(f"Playlist error: {e}")
        return 1
        
    except YouTubeShortsError as e:
        logger.error(f"Application error: {e}")
        return 1
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 1
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Daily Playlist Sync"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: config/default.yaml or environment variables)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(main(args.config, args.verbose))
    sys.exit(exit_code)
