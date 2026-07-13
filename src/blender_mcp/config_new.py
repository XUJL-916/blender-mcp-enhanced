# ================================================================
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
# ================================================================

import os
import logging
import runpy
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("blender-mcp.config")


@dataclass
class ConnectionConfig:
    """TCP connection settings for Blender addon communication."""
    host: str = "localhost"
    port: int = 9876
    timeout: float = 180.0
    max_retries: int = 3
    retry_delay: float = 1.0
    max_request_bytes: int = 8 * 1024 * 1024
    max_response_bytes: int = 64 * 1024 * 1024
    max_command_queue: int = 256
    max_async_jobs: int = 128
    max_async_workers: int = 2
    max_async_cpu_jobs: int = 2
    max_async_gpu_jobs: int = 1
    max_async_events: int = 2000
    async_state_path: str = ""

    @classmethod
    def from_env(cls) -> "ConnectionConfig":
        return cls(
            host=os.getenv("BLENDER_HOST", cls.host),
            port=int(os.getenv("BLENDER_PORT", str(cls.port))),
            timeout=float(os.getenv("BLENDER_MCP_TIMEOUT", str(cls.timeout))),
            max_retries=int(os.getenv("BLENDER_MCP_MAX_RETRIES", str(cls.max_retries))),
            retry_delay=float(os.getenv("BLENDER_MCP_RETRY_DELAY", str(cls.retry_delay))),
            max_request_bytes=int(os.getenv("BLENDER_MCP_MAX_REQUEST_BYTES", str(cls.max_request_bytes))),
            max_response_bytes=int(os.getenv("BLENDER_MCP_MAX_RESPONSE_BYTES", str(cls.max_response_bytes))),
            max_command_queue=int(os.getenv("BLENDER_MCP_MAX_COMMAND_QUEUE", str(cls.max_command_queue))),
            max_async_jobs=int(os.getenv("BLENDER_MCP_MAX_ASYNC_JOBS", str(cls.max_async_jobs))),
            max_async_workers=int(os.getenv("BLENDER_MCP_MAX_ASYNC_WORKERS", str(cls.max_async_workers))),
            max_async_cpu_jobs=int(os.getenv("BLENDER_MCP_MAX_ASYNC_CPU_JOBS", str(cls.max_async_cpu_jobs))),
            max_async_gpu_jobs=int(os.getenv("BLENDER_MCP_MAX_ASYNC_GPU_JOBS", str(cls.max_async_gpu_jobs))),
            max_async_events=int(os.getenv("BLENDER_MCP_MAX_ASYNC_EVENTS", str(cls.max_async_events))),
            async_state_path=os.getenv("BLENDER_MCP_ASYNC_STATE_PATH", cls.async_state_path),
        )


@dataclass
class APIKeys:
    """API keys for third-party integrations."""
    # Hyper3D Rodin
    hyper3d_api_key: str = ""
    hyper3d_fal_api_key: str = ""
    # Default free trial key — override with env var BLENDER_MCP_HYPER3D_API_KEY
    hyper3d_free_trial_key: str = ""
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
            hyper3d_free_trial_key=os.getenv("BLENDER_MCP_HYPER3D_FREE_TRIAL_KEY", cls.hyper3d_free_trial_key),
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

    _ENV_BY_SECTION = {
        "connection": {
            "host": "BLENDER_HOST",
            "port": "BLENDER_PORT",
            "timeout": "BLENDER_MCP_TIMEOUT",
            "max_retries": "BLENDER_MCP_MAX_RETRIES",
            "retry_delay": "BLENDER_MCP_RETRY_DELAY",
            "max_request_bytes": "BLENDER_MCP_MAX_REQUEST_BYTES",
            "max_response_bytes": "BLENDER_MCP_MAX_RESPONSE_BYTES",
            "max_command_queue": "BLENDER_MCP_MAX_COMMAND_QUEUE",
            "max_async_jobs": "BLENDER_MCP_MAX_ASYNC_JOBS",
            "max_async_workers": "BLENDER_MCP_MAX_ASYNC_WORKERS",
            "max_async_cpu_jobs": "BLENDER_MCP_MAX_ASYNC_CPU_JOBS",
            "max_async_gpu_jobs": "BLENDER_MCP_MAX_ASYNC_GPU_JOBS",
            "max_async_events": "BLENDER_MCP_MAX_ASYNC_EVENTS",
            "async_state_path": "BLENDER_MCP_ASYNC_STATE_PATH",
        },
        "api_keys": {
            "hyper3d_api_key": "BLENDER_MCP_HYPER3D_API_KEY",
            "hyper3d_fal_api_key": "BLENDER_MCP_HYPER3D_FAL_API_KEY",
            "hyper3d_free_trial_key": "BLENDER_MCP_HYPER3D_FREE_TRIAL_KEY",
            "hyper3d_mode": "BLENDER_MCP_HYPER3D_MODE",
            "hunyuan3d_secret_id": "BLENDER_MCP_HUNYUAN3D_SECRET_ID",
            "hunyuan3d_secret_key": "BLENDER_MCP_HUNYUAN3D_SECRET_KEY",
            "hunyuan3d_mode": "BLENDER_MCP_HUNYUAN3D_MODE",
            "polyhaven_api_key": "BLENDER_MCP_POLYHAVEN_API_KEY",
            "sketchfab_api_key": "BLENDER_MCP_SKETCHFAB_API_KEY",
            "supabase_url": "BLENDER_MCP_SUPABASE_URL",
            "supabase_anon_key": "BLENDER_MCP_SUPABASE_ANON_KEY",
        },
        "telemetry": {
            "max_prompt_length": "BLENDER_MCP_TELEMETRY_MAX_PROMPT",
            "event_queue_maxsize": "BLENDER_MCP_TELEMETRY_QUEUE_SIZE",
            "flush_interval": "BLENDER_MCP_TELEMETRY_FLUSH_INTERVAL",
        },
        "blender": {
            "polyhaven_enabled": "BLENDER_MCP_POLYHAVEN_ENABLED",
            "sketchfab_enabled": "BLENDER_MCP_SKETCHFAB_ENABLED",
            "telemetry_enabled": "BLENDER_MCP_TELEMETRY_ENABLED",
            "log_level": "BLENDER_MCP_LOG_LEVEL",
        },
    }

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
            raw = runpy.run_path(str(config_file))
            data = {
                "connection": raw.get("connection", {}),
                "api_keys": raw.get("api_keys", {}),
                "telemetry": raw.get("telemetry", {}),
                "blender": raw.get("blender", {}),
            }
            self._loaded_from_file = True
            logger.info(f"Loaded configuration from {config_file}")

            self._merge_section("connection", self.connection, data["connection"])
            self._merge_section("api_keys", self.api_keys, data["api_keys"])
            self._merge_section("telemetry", self.telemetry, data["telemetry"])
            self._merge_section("blender", self.blender, data["blender"])
        except Exception as e:
            logger.warning(f"Failed to load local config: {e}")

    def _merge_section(self, section: str, target: object, values: dict):
        """Merge local config values while preserving environment overrides."""
        env_names = self._ENV_BY_SECTION.get(section, {})
        for key, value in values.items():
            if not hasattr(target, key):
                logger.debug(f"Ignoring unknown config key: {section}.{key}")
                continue
            env_name = env_names.get(key)
            if env_name and env_name in os.environ:
                continue
            setattr(target, key, value)

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
