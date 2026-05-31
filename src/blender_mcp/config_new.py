#================================================================
#  ================================================================
#  config_new.py
#  ================================================================
#
#  Copyright (c) 2026  XUJL
#  Affiliation:  Shenzhen University (SZU)
#
#  Project:        Blender-MCP Enhanced (v1.5.5-enh)
#  Repository:     https://github.com/XUJL-916/blender-mcp-enhanced
#  Created:        2026
#  License:        MIT
#
#  Description:
#      Configuration management — settings loading, validation, environment variable handling and defaults
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
#================================================================

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("blender-mcp.config")


@dataclass
class ConnectionConfig:
    """TCP connection settings for Blender addon communication."""
    host: str = "localhost"
    port: int = 9876
    timeout: float = 180.0
    max_retries: int = 3
    retry_delay: float = 1.0

    @classmethod
    def from_env(cls) -> "ConnectionConfig":
        return cls(
            host=os.getenv("BLENDER_HOST", cls.host),
            port=int(os.getenv("BLENDER_PORT", str(cls.port))),
            timeout=float(os.getenv("BLENDER_MCP_TIMEOUT", str(cls.timeout))),
            max_retries=int(os.getenv("BLENDER_MCP_MAX_RETRIES", str(cls.max_retries))),
            retry_delay=float(os.getenv("BLENDER_MCP_RETRY_DELAY", str(cls.retry_delay))),
        )


@dataclass
class APIKeys:
    """API keys for third-party integrations."""
    # Hyper3D Rodin
    hyper3d_api_key: str = ""
    hyper3d_fal_api_key: str = ""
    # Default free trial key — override with env var BLENDER_MCP_HYPER3D_API_KEY
    hyper3d_free_trial_key: str = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"
    hyper3d_mode: str = "MAIN_SITE"  # MAIN_SITE | FAL_AI

    # Hunyuan3D
    hunyuan3d_secret_id: str = ""
    hunyuan3d_secret_key: str = ""
    hunyuan3d_mode: str = "OFFICIAL_API"  # OFFICIAL_API | LOCAL_API

    # PolyHaven
    polyhaven_api_key: str = ""

    # Sketchfab
    sketchfab_api_key: str = ""

    # Telemetry (Supabase)
    supabase_url: str = ""
    supabase_anon_key: str = ""

    def has_hyper3d_key(self) -> bool:
        return bool(self.hyper3d_api_key or self.hyper3d_fal_api_key)

    def has_hunyuan3d_key(self) -> bool:
        return bool(self.hunyuan3d_secret_id and self.hunyuan3d_secret_key)

    def has_sketchfab_key(self) -> bool:
        return bool(self.sketchfab_api_key)

    def has_supabase_key(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @classmethod
    def from_env(cls) -> "APIKeys":
        return cls(
            hyper3d_api_key=os.getenv("BLENDER_MCP_HYPER3D_API_KEY", cls.hyper3d_api_key),
            hyper3d_fal_api_key=os.getenv("BLENDER_MCP_HYPER3D_FAL_API_KEY", cls.hyper3d_fal_api_key),
            hyper3d_mode=os.getenv("BLENDER_MCP_HYPER3D_MODE", cls.hyper3d_mode),
            hunyuan3d_secret_id=os.getenv("BLENDER_MCP_HUNYUAN3D_SECRET_ID", cls.hunyuan3d_secret_id),
            hunyuan3d_secret_key=os.getenv("BLENDER_MCP_HUNYUAN3D_SECRET_KEY", cls.hunyuan3d_secret_key),
            hunyuan3d_mode=os.getenv("BLENDER_MCP_HUNYUAN3D_MODE", cls.hunyuan3d_mode),
            polyhaven_api_key=os.getenv("BLENDER_MCP_POLYHAVEN_API_KEY", cls.polyhaven_api_key),
            sketchfab_api_key=os.getenv("BLENDER_MCP_SKETCHFAB_API_KEY", cls.sketchfab_api_key),
            supabase_url=os.getenv("BLENDER_MCP_SUPABASE_URL", cls.supabase_url),
            supabase_anon_key=os.getenv("BLENDER_MCP_SUPABASE_ANON_KEY", cls.supabase_anon_key),
        )


@dataclass
class TelemetryConfig:
    """Telemetry collection settings."""
    enabled: bool = True
    max_prompt_length: int = 1000
    event_queue_maxsize: int = 1000
    batch_size: int = 10
    flush_interval: float = 30.0  # seconds

    @classmethod
    def from_env(cls) -> "TelemetryConfig":
        disable_vars = ["DISABLE_TELEMETRY", "BLENDER_MCP_DISABLE_TELEMETRY", "MCP_DISABLE_TELEMETRY"]
        disabled = any(
            os.environ.get(var, "").lower() in ("true", "1", "yes", "on")
            for var in disable_vars
        )
        return cls(
            enabled=not disabled,
            max_prompt_length=int(os.getenv("BLENDER_MCP_TELEMETRY_MAX_PROMPT", str(cls.max_prompt_length))),
            event_queue_maxsize=int(os.getenv("BLENDER_MCP_TELEMETRY_QUEUE_SIZE", str(cls.event_queue_maxsize))),
            flush_interval=float(os.getenv("BLENDER_MCP_TELEMETRY_FLUSH_INTERVAL", str(cls.flush_interval))),
        )


@dataclass
class BlenderConfig:
    """Feature flags and Blender-specific settings."""
    polyhaven_enabled: bool = False
    sketchfab_enabled: bool = False
    telemetry_enabled: bool = True
    addon_version: str = "1.2"
    mcp_version: str = "1.5.5"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "BlenderConfig":
        return cls(
            polyhaven_enabled=os.getenv("BLENDER_MCP_POLYHAVEN_ENABLED", "false").lower() in ("true", "1"),
            sketchfab_enabled=os.getenv("BLENDER_MCP_SKETCHFAB_ENABLED", "false").lower() in ("true", "1"),
            telemetry_enabled=os.getenv("BLENDER_MCP_TELEMETRY_ENABLED", "true").lower() in ("true", "1"),
            log_level=os.getenv("BLENDER_MCP_LOG_LEVEL", cls.log_level).upper(),
        )


class Config:
    """Unified configuration holder. All configs merged from env vars and local file."""

    def __init__(self):
        self.connection: ConnectionConfig = ConnectionConfig.from_env()
        self.api_keys: APIKeys = APIKeys.from_env()
        self.telemetry: TelemetryConfig = TelemetryConfig.from_env()
        self.blender: BlenderConfig = BlenderConfig.from_env()
        self._loaded_from_file = False
        self._load_local_config()

    def _load_local_config(self):
        """Load config from local config.py if it exists."""
        config_file = Path(__file__).parent / "config.py"
        if not config_file.exists():
            logger.debug("No local config.py found, using env vars only")
            return

        try:
            import tomli
            with open(config_file, "rb") as f:
                data = tomli.load(f)
            self._loaded_from_file = True
            logger.info(f"Loaded configuration from {config_file}")

            # Merge local config (env vars take precedence)
            if "connection" in data:
                for k, v in data["connection"].items():
                    if k not in os.environ:
                        setattr(self.connection, k, v)

            if "api_keys" in data:
                for k, v in data["api_keys"].items():
                    if k not in os.environ:
                        setattr(self.api_keys, k, v)

            if "telemetry" in data:
                for k, v in data["telemetry"].items():
                    if k not in os.environ:
                        setattr(self.telemetry, k, v)

            if "blender" in data:
                for k, v in data["blender"].items():
                    if k not in os.environ:
                        setattr(self.blender, k, v)

        except ImportError:
            logger.warning("tomli not available, skipping local config.py parsing")
        except Exception as e:
            logger.warning(f"Failed to load local config: {e}")

    def summary(self) -> dict:
        """Return a non-sensitive summary of the configuration."""
        return {
            "connection": {
                "host": self.connection.host,
                "port": self.connection.port,
                "timeout": self.connection.timeout,
            },
            "api_keys": {
                "hyper3d": bool(self.api_keys.hyper3d_api_key or self.api_keys.hyper3d_fal_api_key),
                "hunyuan3d": self.api_keys.has_hunyuan3d_key(),
                "sketchfab": self.api_keys.has_sketchfab_key(),
                "supabase": self.api_keys.has_supabase_key(),
            },
            "telemetry": {
                "enabled": self.telemetry.enabled,
                "max_prompt_length": self.telemetry.max_prompt_length,
            },
            "blender": {
                "polyhaven_enabled": self.blender.polyhaven_enabled,
                "sketchfab_enabled": self.blender.sketchfab_enabled,
                "version": self.blender.mcp_version,
            },
            "loaded_from_file": self._loaded_from_file,
        }


# Global singleton instance
config = Config()
