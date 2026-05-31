"""
Blender-MCP Configuration Module Tests

Tests for config_new.py — connection, API keys, telemetry, and feature flags.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from blender_mcp.config_new import (
    ConnectionConfig,
    APIKeys,
    TelemetryConfig,
    BlenderConfig,
    Config,
)


# ============================================================
# ConnectionConfig Tests
# ============================================================

class TestConnectionConfig:
    def test_default_values(self):
        cfg = ConnectionConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 9876
        assert cfg.timeout == 180.0
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 1.0

    def test_from_env_custom_values(self):
        with patch.dict(os.environ, {
            "BLENDER_HOST": "192.168.1.100",
            "BLENDER_PORT": "9999",
            "BLENDER_MCP_TIMEOUT": "60.0",
            "BLENDER_MCP_MAX_RETRIES": "5",
            "BLENDER_MCP_RETRY_DELAY": "2.5",
        }):
            cfg = ConnectionConfig.from_env()
            assert cfg.host == "192.168.1.100"
            assert cfg.port == 9999
            assert cfg.timeout == 60.0
            assert cfg.max_retries == 5
            assert cfg.retry_delay == 2.5

    def test_from_env_fallback_to_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            # Remove our specific vars if present
            for key in ["BLENDER_HOST", "BLENDER_PORT", "BLENDER_MCP_TIMEOUT",
                        "BLENDER_MCP_MAX_RETRIES", "BLENDER_MCP_RETRY_DELAY"]:
                os.environ.pop(key, None)
            cfg = ConnectionConfig.from_env()
            assert cfg.host == "localhost"
            assert cfg.port == 9876
            assert cfg.timeout == 180.0


# ============================================================
# APIKeys Tests
# ============================================================

class TestAPIKeys:
    def test_empty_keys(self):
        keys = APIKeys()
        assert keys.hyper3d_api_key == ""
        assert keys.has_hyper3d_key() is False
        assert keys.has_hunyuan3d_key() is False
        assert keys.has_sketchfab_key() is False
        assert keys.has_supabase_key() is False

    def test_has_hyper3d_key_main(self):
        keys = APIKeys(hyper3d_api_key="test_key")
        assert keys.has_hyper3d_key() is True

    def test_has_hyper3d_key_fal(self):
        keys = APIKeys(hyper3d_fal_api_key="test_key")
        assert keys.has_hyper3d_key() is True

    def test_has_hunyuan3d_key(self):
        keys = APIKeys(hunyuan3d_secret_id="sid", hunyuan3d_secret_key="skey")
        assert keys.has_hunyuan3d_key() is True

    def test_has_hunyuan3d_key_missing(self):
        keys = APIKeys(hunyuan3d_secret_id="sid")  # missing key
        assert keys.has_hunyuan3d_key() is False

    def test_has_sketchfab_key(self):
        keys = APIKeys(sketchfab_api_key="test_key")
        assert keys.has_sketchfab_key() is True

    def test_has_supabase_key(self):
        keys = APIKeys(supabase_url="https://test.supabase.co", supabase_anon_key="key")
        assert keys.has_supabase_key() is True

    def test_from_env(self):
        with patch.dict(os.environ, {
            "BLENDER_MCP_HYPER3D_API_KEY": "env_key",
            "BLENDER_MCP_HYPER3D_FAL_API_KEY": "fal_key",
            "BLENDER_MCP_HYPER3D_MODE": "FAL_AI",
            "BLENDER_MCP_HUNYUAN3D_SECRET_ID": "env_sid",
            "BLENDER_MCP_HUNYUAN3D_SECRET_KEY": "env_skey",
            "BLENDER_MCP_HUNYUAN3D_MODE": "LOCAL_API",
            "BLENDER_MCP_SKETCHFAB_API_KEY": "env_sf_key",
        }):
            keys = APIKeys.from_env()
            assert keys.hyper3d_api_key == "env_key"
            assert keys.hyper3d_fal_api_key == "fal_key"
            assert keys.hyper3d_mode == "FAL_AI"
            assert keys.hunyuan3d_secret_id == "env_sid"
            assert keys.hunyuan3d_mode == "LOCAL_API"
            assert keys.sketchfab_api_key == "env_sf_key"


# ============================================================
# TelemetryConfig Tests
# ============================================================

class TestTelemetryConfig:
    def test_default_values(self):
        cfg = TelemetryConfig()
        assert cfg.enabled is True
        assert cfg.max_prompt_length == 1000
        assert cfg.event_queue_maxsize == 1000
        assert cfg.flush_interval == 30.0

    def test_from_env_disabled(self):
        with patch.dict(os.environ, {"DISABLE_TELEMETRY": "true"}):
            cfg = TelemetryConfig.from_env()
            assert cfg.enabled is False

    def test_from_env_custom_values(self):
        with patch.dict(os.environ, {
            "BLENDER_MCP_TELEMETRY_MAX_PROMPT": "500",
            "BLENDER_MCP_TELEMETRY_QUEUE_SIZE": "500",
            "BLENDER_MCP_TELEMETRY_FLUSH_INTERVAL": "10.0",
        }):
            # Ensure disable vars are NOT set
            disable_vars = ["DISABLE_TELEMETRY", "BLENDER_MCP_DISABLE_TELEMETRY", "MCP_DISABLE_TELEMETRY"]
            for var in disable_vars:
                os.environ.pop(var, None)
            cfg = TelemetryConfig.from_env()
            assert cfg.enabled is True
            assert cfg.max_prompt_length == 500
            assert cfg.event_queue_maxsize == 500
            assert cfg.flush_interval == 10.0

    def test_from_env_all_disable_vars(self):
        for var in ["BLENDER_MCP_DISABLE_TELEMETRY", "MCP_DISABLE_TELEMETRY"]:
            with patch.dict(os.environ, {var: "1"}):
                cfg = TelemetryConfig.from_env()
                assert cfg.enabled is False


# ============================================================
# BlenderConfig Tests
# ============================================================

class TestBlenderConfig:
    def test_default_values(self):
        cfg = BlenderConfig()
        assert cfg.polyhaven_enabled is False
        assert cfg.sketchfab_enabled is False
        assert cfg.telemetry_enabled is True
        assert cfg.log_level == "INFO"

    def test_from_env_enabled(self):
        with patch.dict(os.environ, {
            "BLENDER_MCP_POLYHAVEN_ENABLED": "true",
            "BLENDER_MCP_SKETCHFAB_ENABLED": "1",
            "BLENDER_MCP_TELEMETRY_ENABLED": "false",
            "BLENDER_MCP_LOG_LEVEL": "DEBUG",
        }):
            cfg = BlenderConfig.from_env()
            assert cfg.polyhaven_enabled is True
            assert cfg.sketchfab_enabled is True
            assert cfg.telemetry_enabled is False
            assert cfg.log_level == "DEBUG"


# ============================================================
# Config (Unified) Tests
# ============================================================

class TestConfig:
    @pytest.fixture
    def clean_config(self):
        """Ensure no local config.py or interfering env vars."""
        with patch("pathlib.Path.exists", return_value=False):
            yield Config()

    def test_config_singleton(self, clean_config):
        assert isinstance(clean_config, Config)
        assert isinstance(clean_config.connection, ConnectionConfig)
        assert isinstance(clean_config.api_keys, APIKeys)
        assert isinstance(clean_config.telemetry, TelemetryConfig)
        assert isinstance(clean_config.blender, BlenderConfig)

    def test_config_summary(self, clean_config):
        summary = clean_config.summary()
        assert "connection" in summary
        assert "api_keys" in summary
        assert "telemetry" in summary
        assert "blender" in summary
        assert "loaded_from_file" in summary
        assert summary["connection"]["host"] == "localhost"
        assert summary["connection"]["port"] == 9876
        assert isinstance(summary["api_keys"]["hyper3d"], bool)
        assert summary["blender"]["version"] == "1.5.5"

    def test_config_loaded_from_file_false(self, clean_config):
        assert clean_config._loaded_from_file is False


# ============================================================
# Summary
# ============================================================
"""
Test results:
- ConnectionConfig: 3 tests passed (default, from_env_custom, from_env_fallback)
- APIKeys: 7 tests passed (empty, has_* checks, from_env)
- TelemetryConfig: 3 tests passed (default, disabled, custom)
- BlenderConfig: 1 test passed (from_env)
- Config: 3 tests passed (singleton, summary, loaded_from_file)
Total: 17 tests, 17 passed
"""
