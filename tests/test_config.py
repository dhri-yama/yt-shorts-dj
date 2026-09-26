"""
Tests for configuration module.
"""

import pytest
import os
import tempfile
from pathlib import Path

from src.config import (
    load_config,
    YouTubeConfig,
    AppConfig,
    ConfigurationError
)


class TestYouTubeConfig:
    """Tests for YouTubeConfig."""
    
    def test_valid_config(self):
        """Test valid YouTube configuration."""
        config = YouTubeConfig(
            api_key="test-api-key",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token"
        )
        assert config.api_key == "test-api-key"
        assert config.client_id == "test-client-id"
        assert config.client_secret == "test-client-secret"
        assert config.refresh_token == "test-refresh-token"
    
    def test_missing_api_key(self):
        """Test missing API key raises error."""
        with pytest.raises(ConfigurationError, match="YOUTUBE_API_KEY is required"):
            YouTubeConfig(
                api_key="",
                client_id="test-client-id",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token"
            )
    
    def test_missing_client_id(self):
        """Test missing client ID raises error."""
        with pytest.raises(ConfigurationError, match="YOUTUBE_CLIENT_ID is required"):
            YouTubeConfig(
                api_key="test-api-key",
                client_id="",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token"
            )
    
    def test_missing_client_secret(self):
        """Test missing client secret raises error."""
        with pytest.raises(ConfigurationError, match="YOUTUBE_CLIENT_SECRET is required"):
            YouTubeConfig(
                api_key="test-api-key",
                client_id="test-client-id",
                client_secret="",
                refresh_token="test-refresh-token"
            )
    
    def test_missing_refresh_token(self):
        """Test missing refresh token raises error."""
        with pytest.raises(ConfigurationError, match="YOUTUBE_REFRESH_TOKEN is required"):
            YouTubeConfig(
                api_key="test-api-key",
                client_id="test-client-id",
                client_secret="test-client-secret",
                refresh_token=""
            )


class TestAppConfig:
    """Tests for AppConfig."""
    
    def test_valid_config(self, mock_youtube_config):
        """Test valid application configuration."""
        config = AppConfig(
            youtube=mock_youtube_config,
            channel_ids=["UC-test-1", "UC-test-2"],
            target_playlist_id="PL-test",
            batch_size=15
        )
        assert config.batch_size == 15
        assert config.channel_ids == ["UC-test-1", "UC-test-2"]
        assert config.target_playlist_id == "PL-test"
    
    def test_missing_channel_ids(self, mock_youtube_config):
        """Test missing channel IDs raises error."""
        with pytest.raises(ConfigurationError, match="At least one channel ID is required"):
            AppConfig(
                youtube=mock_youtube_config,
                channel_ids=[],
                target_playlist_id="PL-test"
            )
    
    def test_missing_target_playlist_id(self, mock_youtube_config):
        """Test missing target playlist ID raises error."""
        with pytest.raises(ConfigurationError, match="TARGET_PLAYLIST_ID is required"):
            AppConfig(
                youtube=mock_youtube_config,
                channel_ids=["UC-test-1"],
                target_playlist_id=""
            )
    
    def test_batch_size_too_small(self, mock_youtube_config):
        """Test batch size below minimum raises error."""
        with pytest.raises(ConfigurationError, match="BATCH_SIZE must be between 10 and 20"):
            AppConfig(
                youtube=mock_youtube_config,
                channel_ids=["UC-test-1"],
                target_playlist_id="PL-test",
                batch_size=5
            )
    
    def test_batch_size_too_large(self, mock_youtube_config):
        """Test batch size above maximum raises error."""
        with pytest.raises(ConfigurationError, match="BATCH_SIZE must be between 10 and 20"):
            AppConfig(
                youtube=mock_youtube_config,
                channel_ids=["UC-test-1"],
                target_playlist_id="PL-test",
                batch_size=25
            )
    
    def test_invalid_log_level(self, mock_youtube_config):
        """Test invalid log level raises error."""
        with pytest.raises(ConfigurationError, match="Invalid LOG_LEVEL"):
            AppConfig(
                youtube=mock_youtube_config,
                channel_ids=["UC-test-1"],
                target_playlist_id="PL-test",
                log_level="INVALID"
            )


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-api-key")
        monkeypatch.setenv("YOUTUBE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "test-client-secret")
        monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "test-refresh-token")
        monkeypatch.setenv("YOUTUBE_CHANNEL_IDS", "UC-test-1,UC-test-2")
        monkeypatch.setenv("TARGET_PLAYLIST_ID", "PL-test")
        monkeypatch.setenv("BATCH_SIZE", "15")
        
        config = load_config()
        
        assert config.youtube.api_key == "test-api-key"
        assert config.youtube.client_id == "test-client-id"
        assert config.channel_ids == ["UC-test-1", "UC-test-2"]
        assert config.target_playlist_id == "PL-test"
        assert config.batch_size == 15
    
    def test_load_from_yaml(self, tmp_path, monkeypatch):
        """Test loading configuration from YAML file."""
        # Clear environment variables
        for key in ["YOUTUBE_API_KEY", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET",
                    "YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CHANNEL_IDS", "TARGET_PLAYLIST_ID"]:
            monkeypatch.delenv(key, raising=False)
        
        # Create YAML config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
youtube:
  api_key: "yaml-api-key"
  client_id: "yaml-client-id"
  client_secret: "yaml-client-secret"
  refresh_token: "yaml-refresh-token"

app:
  channel_ids:
    - "UC-yaml-1"
    - "UC-yaml-2"
  target_playlist_id: "PL-yaml"
  batch_size: 10
""")
        
        config = load_config(str(config_file))
        
        assert config.youtube.api_key == "yaml-api-key"
        assert config.youtube.client_id == "yaml-client-id"
        assert config.channel_ids == ["UC-yaml-1", "UC-yaml-2"]
        assert config.target_playlist_id == "PL-yaml"
        assert config.batch_size == 10
    
    def test_env_overrides_yaml(self, tmp_path, monkeypatch):
        """Test environment variables override YAML config."""
        # Create YAML config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
youtube:
  api_key: "yaml-api-key"
  client_id: "yaml-client-id"
  client_secret: "yaml-client-secret"
  refresh_token: "yaml-refresh-token"

app:
  channel_ids:
    - "UC-yaml-1"
  target_playlist_id: "PL-yaml"
  batch_size: 10
""")
        
        # Set environment variables
        monkeypatch.setenv("YOUTUBE_API_KEY", "env-api-key")
        monkeypatch.setenv("TARGET_PLAYLIST_ID", "PL-env")
        monkeypatch.setenv("BATCH_SIZE", "20")
        
        config = load_config(str(config_file))
        
        # Environment variables should override YAML
        assert config.youtube.api_key == "env-api-key"
        assert config.target_playlist_id == "PL-env"
        assert config.batch_size == 20
        # YAML values should be used for non-overridden fields
        assert config.youtube.client_id == "yaml-client-id"
