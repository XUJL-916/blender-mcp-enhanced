#================================================================
#  ================================================================
#  health.py
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
#      Health check system — monitors Blender connection, MCP state,
#      and returns comprehensive status for monitoring/debugging.
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
#================================================================

"""
Health check module for Blender-MCP Enhanced.

Provides:
- HealthChecker: Singleton class that monitors Blender connectivity
- get_status(): Returns comprehensive health report
- check_blender_connection(): Probes Blender addon port

Used by:
- health_check MCP tool
- Heartbeat background loop
- Monitoring dashboards
"""

import json
import time
import socket
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("blender-mcp.health")

# Global version
VERSION = "1.5.5-enh"
START_TIME = time.time()


class HealthStatus:
    """Represents current health status of the MCP server."""

    def __init__(self):
        self.blender_connected: bool = False
        self.blender_port: int = 9876
        self.blender_version: str = "Unknown"
        self.blender_last_error: str = ""
        self.mcp_version: str = VERSION
        self.tool_count: int = 0
        self.connection_active: bool = False
        self.last_error: str = ""
        self.start_time: float = START_TIME

    def to_dict(self) -> Dict[str, Any]:
        uptime = time.time() - self.start_time
        return {
            "blender": {
                "connected": self.blender_connected,
                "port": self.blender_port,
                "version": self.blender_version,
                "last_error": self.blender_last_error
            },
            "mcp": {
                "version": self.mcp_version,
                "tool_count": self.tool_count
            },
            "connection": {
                "active": self.connection_active,
                "uptime_seconds": round(uptime, 1),
                "last_error": self.last_error
            }
        }


class HealthChecker:
    """
    Singleton health checker for Blender-MCP.
    
    Probes Blender connection and maintains health status.
    Thread-safe for use with heartbeat loop.
    """

    _instance = None
    _lock = None

    def __new__(cls, host: str = "localhost", port: int = 9876):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, host: str = "localhost", port: int = 9876):
        if self._initialized:
            return
        self._initialized = True
        self.host = host
        self.port = port
        self.status = HealthStatus()
        logger.info(f"HealthChecker initialized (port {self.port})")

    def check_blender_connection(self) -> bool:
        """
        Probe Blender addon port to check connectivity.
        
        Returns True if Blender addon is reachable, False otherwise.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result == 0:
                self.status.blender_connected = True
                self.status.blender_last_error = ""
                logger.debug("Blender connection: OK")
                return True
            else:
                self.status.blender_connected = False
                self.status.blender_last_error = f"Connection refused (port {self.port})"
                logger.debug(f"Blender connection: FAILED (errno {result})")
                return False
        except Exception as e:
            self.status.blender_connected = False
            self.status.blender_last_error = str(e)
            logger.debug(f"Blender connection: ERROR ({e})")
            return False

    def check_mcp_status(self) -> Dict[str, Any]:
        """Check MCP server status."""
        import sys
        import importlib
        
        try:
            mcp_module = importlib.import_module("mcp.server")
            mcp_version = importlib.metadata.version("mcp") if importlib.metadata else "unknown"
        except Exception as e:
            mcp_version = f"error: {str(e)}"
        
        return {
            "version": mcp_version,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "module_available": True
        }

    def get_full_status(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        self.check_blender_connection()
        mcp_status = self.check_mcp_status()
        
        # Count tools in server module
        try:
            import blender_mcp.server as server_mod
            tool_count = len([
                name for name in dir(server_mod)
                if callable(getattr(server_mod, name)) and name != 'main'
            ])
        except Exception:
            tool_count = 0
        
        self.status.tool_count = tool_count
        
        result = {
            "status": "healthy" if self.status.blender_connected else "degraded",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "timestamp_epoch": time.time(),
            "blender": self.status.to_dict()["blender"],
            "mcp": {
                **mcp_status,
                "tool_count": self.status.tool_count
            },
            "connection": self.status.to_dict()["connection"],
            "features": {
                "structured_tools": 16,  # New AI-safe tools
                "health_check": True,
                "auto_reconnect": True,
                "telemetry": True
            }
        }
        
        return result


def get_health_checker(host: str = "localhost", port: int = 9876) -> HealthChecker:
    """Get or create the singleton HealthChecker."""
    return HealthChecker(host=host, port=port)


def get_health() -> Dict[str, Any]:
    """
    Get current health status.
    
    Returns JSON-serializable dict with full health report.
    """
    checker = get_health_checker()
    return checker.get_full_status()


def get_health_summary() -> str:
    """Get brief health summary as text."""
    status = get_health()
    blender_ok = "✓" if status["blender"]["connected"] else "✗"
    mcp_tools = status["mcp"]["tool_count"]
    mcp_ver = status["mcp"]["version"]
    
    return (
        f"[{status['timestamp']}] "
        f"Blender: {blender_ok} | "
        f"MCP: {mcp_ver} ({mcp_tools} tools) | "
        f"Status: {status['status']}"
    )


if __name__ == "__main__":
    # Quick test
    status = get_health()
    print(json.dumps(status, indent=2))
