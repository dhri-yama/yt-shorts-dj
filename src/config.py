"""
Configuration management for YouTube Shorts automation.
Supports environment variables and YAML files.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv

from .exceptions import ConfigurationError

# Load .env file if it exists
load_dotenv()


@dataclass
class YouTubeConfig:
    """YouTube API configuration."""
    
    api_key: str
    client_id: str
    client_secret: str
    refresh_token: str
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.api_key:
            raise ConfigurationError("YOUTUBE_API_KEY is required")
        if not self.client_id:
            raise ConfigurationError("YOUTUBE_CLIENT_ID is required")
        if not self.client_secret:
            raise ConfigurationError("YOUTUBE_CLIENT_SECRET is required")
        if not self.refresh_token:
            raise ConfigurationError("YOUTUBE_REFRESH_TOKEN is required")


@dataclass
class AppConfig:
    """Application configuration."""
    
    youtube: YouTubeConfig
    channel_ids: List[str]
    target_playlist_id: str
    batch_size: int = 15
    history_file: str = "history.json"
    max_retries: int = 3
    backoff_factor: float = 2.0
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.channel_ids:
            raise ConfigurationError("At least one channel ID is required")
        if not self.target_playlist_id:
            raise ConfigurationError("TARGET_PLAYLIST_ID is required")
        if not 5 <= self.batch_size <= 20:
            raise ConfigurationError("BATCH_SIZE must be between 10 and 20")
        if self.log_level.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ConfigurationError("Invalid LOG_LEVEL")


@dataclass
class Config:
    """Complete application configuration."""
    
    app: AppConfig
    youtube: YouTubeConfig
    
    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create config from dictionary."""
        youtube_data = data.get("youtube", {})
        app_data = data.get("app", {})
        
        youtube_config = YouTubeConfig(
            api_key=youtube_data.get("api_key", ""),
            client_id=youtube_data.get("client_id", ""),
            client_secret=youtube_data.get("client_secret", ""),
            refresh_token=youtube_data.get("refresh_token", "")
        )
        
        app_config = AppConfig(
            youtube=youtube_config,
            channel_ids=app_data.get("channel_ids", []),
            target_playlist_id=app_data.get("target_playlist_id", ""),
            batch_size=app_data.get("batch_size", 15),
            history_file=app_data.get("history_file", "history.json"),
            max_retries=app_data.get("max_retries", 3),
            backoff_factor=app_data.get("backoff_factor", 2.0),
            log_level=app_data.get("log_level", "INFO")
        )
        
        return cls(app=app_config, youtube=youtube_config)


def _load_yaml_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Failed to parse YAML config: {e}")


def _load_env_config() -> dict:
    """Load configuration from environment variables."""
    data = {}
    
    # YouTube configuration
    youtube_data = {}
    if os.environ.get("YOUTUBE_API_KEY"):
        youtube_data["api_key"] = os.environ["YOUTUBE_API_KEY"]
    if os.environ.get("YOUTUBE_CLIENT_ID"):
        youtube_data["client_id"] = os.environ["YOUTUBE_CLIENT_ID"]
    if os.environ.get("YOUTUBE_CLIENT_SECRET"):
        youtube_data["client_secret"] = os.environ["YOUTUBE_CLIENT_SECRET"]
    if os.environ.get("YOUTUBE_REFRESH_TOKEN"):
        youtube_data["refresh_token"] = os.environ["YOUTUBE_REFRESH_TOKEN"]
    
    if youtube_data:
        data["youtube"] = youtube_data
    
    # App configuration
    app_data = {}
    if os.environ.get("YOUTUBE_CHANNEL_IDS"):
        channel_ids = os.environ["YOUTUBE_CHANNEL_IDS"].split(",")
        app_data["channel_ids"] = [cid.strip() for cid in channel_ids if cid.strip()]
    if os.environ.get("TARGET_PLAYLIST_ID"):
        app_data["target_playlist_id"] = os.environ["TARGET_PLAYLIST_ID"]
    if os.environ.get("BATCH_SIZE"):
        app_data["batch_size"] = int(os.environ["BATCH_SIZE"])
    if os.environ.get("HISTORY_FILE"):
        app_data["history_file"] = os.environ["HISTORY_FILE"]
    if os.environ.get("MAX_RETRIES"):
        app_data["max_retries"] = int(os.environ["MAX_RETRIES"])
    if os.environ.get("BACKOFF_FACTOR"):
        app_data["backoff_factor"] = float(os.environ["BACKOFF_FACTOR"])
    if os.environ.get("LOG_LEVEL"):
        app_data["log_level"] = os.environ["LOG_LEVEL"]
    
    if app_data:
        data["app"] = app_data
    
    return data


def _merge_configs(*configs: dict) -> dict:
    """Merge multiple configuration dictionaries with precedence."""
    result = {}
    for config in configs:
        for key, value in config.items():
            if key not in result:
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                result[key] = _merge_configs(result[key], value)
            else:
                # Later configs override earlier ones
                result[key] = value
    return result


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load application configuration.
    
    Precedence order (highest to lowest):
    1. Environment variables
    2. YAML config file (if path provided)
    3. Default YAML config (config/default.yaml)
    
    Args:
        config_path: Optional path to YAML config file
        
    Returns:
        AppConfig instance with merged configuration
    """
    # Load configuration from all sources
    configs = []
    
    # Default config file
    default_config_path = Path(__file__).parent.parent / "config" / "default.yaml"
    if default_config_path.exists():
        configs.append(_load_yaml_config(default_config_path))
    
    # Custom config file
    if config_path:
        custom_config_path = Path(config_path)
        if custom_config_path.exists():
            configs.append(_load_yaml_config(custom_config_path))
    
    # Environment variables
    env_config = _load_env_config()
    configs.append(env_config)
    
    # Merge with precedence
    merged_config = _merge_configs(*configs)
    
    # Create config objects
    try:
        config = Config.from_dict(merged_config)
        return config.app
    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(f"Failed to create configuration: {e}")


def get_youtube_config(config_path: Optional[str] = None) -> YouTubeConfig:
    """Get YouTube-specific configuration."""
    app_config = load_config(config_path)
    return app_config.youtube
