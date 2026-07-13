#================================================================
#  ================================================================
#  server.py
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
#      MCP server — FastMCP tool definitions, JSON-RPC request handling, TCP bridge to Blender addon
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
#================================================================

# blender_mcp_server.py
from mcp.server.fastmcp import FastMCP, Context, Image
import socket
import json
import asyncio
import logging
import tempfile
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List
import os
from pathlib import Path
import base64
import re
from urllib.parse import urlparse

# Import telemetry
from .telemetry import record_startup, get_telemetry
from .telemetry_decorator import telemetry_tool

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BlenderMCPServer")

# Default configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9876
DEFAULT_MAX_REQUEST_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024

_SENSITIVE_KEY = re.compile(r"(api[_-]?key|token|secret|password|authorization|cookie|credential)", re.I)


def _redact_sensitive(value: Any) -> Any:
    """Return a log-safe copy of nested command parameters."""
    if isinstance(value, dict):
        return {key: ("<redacted>" if _SENSITIVE_KEY.search(str(key)) else _redact_sensitive(item))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive(item) for item in value]
    return value


class BlenderProtocolError(RuntimeError):
    """Raised when the TCP peer violates protocol or message limits."""


class BlenderCommandError(RuntimeError):
    """Structured Blender command failure preserving addon error metadata."""

    def __init__(self, command: str, message: str, *, code: str = "BLENDER_COMMAND_ERROR",
                 error_type: str = "BlenderCommandError", retriable: bool = False,
                 meta: Dict[str, Any] = None):
        super().__init__(message)
        self.command = command
        self.code = code
        self.error_type = error_type
        self.retriable = retriable
        self.meta = meta or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"command": self.command, "code": self.code, "type": self.error_type,
                "message": str(self), "retriable": self.retriable, "meta": self.meta}

@dataclass
class BlenderConnection:
    host: str
    port: int
    sock: socket.socket = None  # Changed from 'socket' to 'sock' to avoid naming conflict
    timeout: float = 180.0
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES

    def connect(self) -> bool:
        """Connect to the Blender addon socket server"""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Blender at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Blender: {str(e)}")
            # Ensure socket is closed on failure
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
                self.sock = None
            return False

    def disconnect(self):
        """Disconnect from the Blender addon"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from Blender: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, sock, buffer_size=8192):
        """Receive the complete response, potentially in multiple chunks"""
        chunks = []
        received_size = 0
        # Use a consistent timeout value that matches the addon's timeout
        sock.settimeout(self.timeout)

        try:
            while True:
                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        # If we get an empty chunk, the connection might be closed
                        if not chunks:  # If we haven't received anything yet, this is an error
                            raise Exception("Connection closed before receiving any data")
                        break

                    chunks.append(chunk)
                    received_size += len(chunk)
                    if received_size > self.max_response_bytes:
                        raise BlenderProtocolError(
                            f"Blender response exceeded {self.max_response_bytes} bytes")

                    # Check if we've received a complete JSON object
                    try:
                        data = b''.join(chunks)
                        json.loads(data.decode('utf-8'))
                        # If we get here, it parsed successfully
                        logger.info(f"Received complete response ({len(data)} bytes)")
                        return data
                    except json.JSONDecodeError:
                        # Incomplete JSON, continue receiving
                        continue
                except socket.timeout:
                    # If we hit a timeout during receiving, break the loop and try to use what we have
                    logger.warning("Socket timeout during chunked receive")
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error(f"Socket connection error during receive: {str(e)}")
                    raise  # Re-raise to be handled by the caller
        except socket.timeout:
            logger.warning("Socket timeout during chunked receive")
        except Exception as e:
            logger.error(f"Error during receive: {str(e)}")
            raise

        # If we get here, we either timed out or broke out of the loop
        # Try to use what we have
        if chunks:
            data = b''.join(chunks)
            logger.info(f"Returning data after receive completion ({len(data)} bytes)")
            try:
                # Try to parse what we have
                json.loads(data.decode('utf-8'))
                return data
            except json.JSONDecodeError:
                # If we can't parse it, it's incomplete
                raise Exception("Incomplete JSON response received")
        else:
            raise Exception("No data received")

    def send_command(self, command_type: str, params: Dict[str, Any] = None,
                     max_retries: int = 2, return_envelope: bool = False) -> Dict[str, Any]:
        """Send a command to Blender and return the response.

        Auto-reconnects on transient socket errors with exponential backoff.
        max_retries controls how many times to retry after an initial failure.
        """
        command = {
            "type": command_type,
            "params": params or {}
        }
        encoded_command = json.dumps(command).encode('utf-8')
        if len(encoded_command) > self.max_request_bytes:
            raise BlenderProtocolError(
                f"Command '{command_type}' exceeded {self.max_request_bytes} request bytes")

        last_error = None
        max_attempts = max_retries + 1
        for attempt in range(1, max_attempts + 1):
            try:
                # Ensure connected
                if not self.sock:
                    logger.info(f"send_command #{attempt}: no socket, connecting...")
                    if not self.connect():
                        raise ConnectionError("Not connected to Blender")

                logger.info("Sending command (attempt %s/%s): %s with params: %s",
                            attempt, max_attempts, command_type, _redact_sensitive(params or {}))

                # Send the command
                self.sock.sendall(encoded_command)
                self.sock.settimeout(self.timeout)

                # Receive the response
                response_data = self.receive_full_response(self.sock)
                logger.info(f"Received {len(response_data)} bytes of data")

                response = json.loads(response_data.decode('utf-8'))
                logger.info(f"Response parsed, status: {response.get('status', 'unknown')}")

                if response.get("status") == "error":
                    error = response.get("error") or {}
                    message = error.get("message") or response.get("message", "Unknown error from Blender")
                    logger.error(f"Blender error: {message}")
                    if return_envelope:
                        return response
                    raise BlenderCommandError(
                        command_type, message,
                        code=error.get("code", "BLENDER_COMMAND_ERROR"),
                        error_type=error.get("type", "BlenderCommandError"),
                        retriable=bool(error.get("retriable", False)),
                        meta=response.get("meta") or {},
                    )

                return response if return_envelope else response.get("result", {})

            except (socket.timeout, BrokenPipeError, ConnectionResetError, ConnectionError) as e:
                last_error = str(e)
                was_connected = bool(self.sock)
                logger.warning(f"Transient error attempt {attempt}/{max_attempts}: {e}")
                # Invalidate broken socket
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None

                if attempt < max_attempts:
                    backoff = min(2 ** (attempt - 1), 10)  # 1s, 2s, capped at 10s
                    logger.info(f"Reconnecting in {backoff}s...")
                    # Small sleep before retry
                    import time
                    time.sleep(backoff)
                    continue
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from Blender: {str(e)}")
                raise BlenderProtocolError(f"Invalid response from Blender: {str(e)}") from e
            except Exception as e:
                # Non-transient error — raise immediately
                logger.error(f"Error communicating with Blender: {str(e)}")
                raise

        # All retries exhausted
        raise ConnectionError(f"All {max_attempts} attempts failed. Last error: {last_error}")

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    heartbeat_task = None
    try:
        logger.info("BlenderMCP server starting up")

        try:
            record_startup()
        except Exception as e:
            logger.debug(f"Failed to record startup telemetry: {e}")

        try:
            blender = get_blender_connection()
            logger.info("Successfully connected to Blender on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Blender on startup: {str(e)}")
            logger.warning("Make sure the Blender addon is running before using Blender resources or tools")

        heartbeat_task = asyncio.create_task(_heartbeat_loop())
        yield {}
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        global _blender_connection
        if _blender_connection:
            logger.info("Disconnecting from Blender on shutdown")
            _blender_connection.disconnect()
            _blender_connection = None
        logger.info("BlenderMCP server shut down")

# Create the MCP server with lifespan support
mcp = FastMCP(
    "BlenderMCP",
    lifespan=server_lifespan
)

# Resource endpoints

# Global connection for resources (since resources can't access context)
_blender_connection = None
_polyhaven_enabled = False  # Add this global variable

def get_blender_connection():
    """Get or create a persistent Blender connection.

    Trusts the existing connection unless an error proves it dead.
    No ping on every call — avoids unnecessary latency.
    """
    global _blender_connection, _polyhaven_enabled

    if _blender_connection is not None:
        return _blender_connection

    # Create a new connection if needed
    if _blender_connection is None:
        host = os.getenv("BLENDER_HOST", DEFAULT_HOST)
        port = int(os.getenv("BLENDER_PORT", DEFAULT_PORT))
        _blender_connection = BlenderConnection(
            host=host,
            port=port,
            timeout=float(os.getenv("BLENDER_MCP_TIMEOUT", "180")),
            max_request_bytes=int(os.getenv("BLENDER_MCP_MAX_REQUEST_BYTES", str(DEFAULT_MAX_REQUEST_BYTES))),
            max_response_bytes=int(os.getenv("BLENDER_MCP_MAX_RESPONSE_BYTES", str(DEFAULT_MAX_RESPONSE_BYTES))),
        )
        if not _blender_connection.connect():
            logger.error("Failed to connect to Blender")
            _blender_connection = None
            raise Exception("Could not connect to Blender. Make sure the Blender addon is running.")
        logger.info("Created new persistent connection to Blender")

    return _blender_connection


@telemetry_tool("get_scene_info")
@mcp.tool()
def get_scene_info(ctx: Context) -> str:
    """Get detailed information about the current Blender scene"""
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_scene_info")

        # Just return the JSON representation of what Blender sent us
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting scene info from Blender: {str(e)}")
        return f"Error getting scene info: {str(e)}"

@telemetry_tool("get_object_info")
@mcp.tool()
def get_object_info(ctx: Context, object_name: str) -> str:
    """
    Get detailed information about a specific object in the Blender scene.

    Parameters:
    - object_name: The name of the object to get information about
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_object_info", {"name": object_name})

        # Just return the JSON representation of what Blender sent us
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting object info from Blender: {str(e)}")
        return f"Error getting object info: {str(e)}"

@telemetry_tool("get_viewport_screenshot")
@mcp.tool()
def get_viewport_screenshot(ctx: Context, max_size: int = 800) -> Image:
    """
    Capture a screenshot of the current Blender 3D viewport.

    Parameters:
    - max_size: Maximum size in pixels for the largest dimension (default: 800)

    Returns the screenshot as an Image.
    """
    try:
        blender = get_blender_connection()

        # Create temp file path
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"blender_screenshot_{os.getpid()}.png")

        result = blender.send_command("get_viewport_screenshot", {
            "max_size": max_size,
            "filepath": temp_path,
            "format": "png"
        })

        if "error" in result:
            raise Exception(result["error"])

        if not os.path.exists(temp_path):
            raise Exception("Screenshot file was not created")

        # Read the file
        with open(temp_path, 'rb') as f:
            image_bytes = f.read()

        # Delete the temp file
        os.remove(temp_path)

        return Image(data=image_bytes, format="png")

    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        raise Exception(f"Screenshot failed: {str(e)}")


@telemetry_tool("execute_blender_code")
@mcp.tool()
def execute_blender_code(ctx: Context, code: str) -> str:
    """
    Execute arbitrary Python code in Blender. Make sure to do it step-by-step by breaking it into smaller chunks.

    Parameters:
    - code: The Python code to execute
    """
    try:
        # Get the global connection
        blender = get_blender_connection()
        result = blender.send_command("execute_code", {"code": code})
        return f"Code executed successfully: {result.get('result', '')}"
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        return f"Error executing code: {str(e)}"

@telemetry_tool("get_polyhaven_categories")
@mcp.tool()
def get_polyhaven_categories(ctx: Context, asset_type: str = "hdris") -> str:
    """
    Get a list of categories for a specific asset type on Polyhaven.

    Parameters:
    - asset_type: The type of asset to get categories for (hdris, textures, models, all)
    """
    try:
        blender = get_blender_connection()
        if not _polyhaven_enabled:
            return "PolyHaven integration is disabled. Select it in the sidebar in BlenderMCP, then run it again."
        result = blender.send_command("get_polyhaven_categories", {"asset_type": asset_type})

        if "error" in result:
            return f"Error: {result['error']}"

        # Format the categories in a more readable way
        categories = result["categories"]
        formatted_output = f"Categories for {asset_type}:\n\n"

        # Sort categories by count (descending)
        sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)

        for category, count in sorted_categories:
            formatted_output += f"- {category}: {count} assets\n"

        return formatted_output
    except Exception as e:
        logger.error(f"Error getting Polyhaven categories: {str(e)}")
        return f"Error getting Polyhaven categories: {str(e)}"

@telemetry_tool("search_polyhaven_assets")
@mcp.tool()
def search_polyhaven_assets(
    ctx: Context,
    asset_type: str = "all",
    categories: str = None
) -> str:
    """
    Search for assets on Polyhaven with optional filtering.

    Parameters:
    - asset_type: Type of assets to search for (hdris, textures, models, all)
    - categories: Optional comma-separated list of categories to filter by

    Returns a list of matching assets with basic information.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("search_polyhaven_assets", {
            "asset_type": asset_type,
            "categories": categories
        })

        if "error" in result:
            return f"Error: {result['error']}"

        # Format the assets in a more readable way
        assets = result["assets"]
        total_count = result["total_count"]
        returned_count = result["returned_count"]

        formatted_output = f"Found {total_count} assets"
        if categories:
            formatted_output += f" in categories: {categories}"
        formatted_output += f"\nShowing {returned_count} assets:\n\n"

        # Sort assets by download count (popularity)
        sorted_assets = sorted(assets.items(), key=lambda x: x[1].get("download_count", 0), reverse=True)

        for asset_id, asset_data in sorted_assets:
            formatted_output += f"- {asset_data.get('name', asset_id)} (ID: {asset_id})\n"
            formatted_output += f"  Type: {['HDRI', 'Texture', 'Model'][asset_data.get('type', 0)]}\n"
            formatted_output += f"  Categories: {', '.join(asset_data.get('categories', []))}\n"
            formatted_output += f"  Downloads: {asset_data.get('download_count', 'Unknown')}\n\n"

        return formatted_output
    except Exception as e:
        logger.error(f"Error searching Polyhaven assets: {str(e)}")
        return f"Error searching Polyhaven assets: {str(e)}"

@telemetry_tool("download_polyhaven_asset")
@mcp.tool()
def download_polyhaven_asset(
    ctx: Context,
    asset_id: str,
    asset_type: str,
    resolution: str = "1k",
    file_format: str = None
) -> str:
    """
    Download and import a Polyhaven asset into Blender.

    Parameters:
    - asset_id: The ID of the asset to download
    - asset_type: The type of asset (hdris, textures, models)
    - resolution: The resolution to download (e.g., 1k, 2k, 4k)
    - file_format: Optional file format (e.g., hdr, exr for HDRIs; jpg, png for textures; gltf, fbx for models)

    Returns a message indicating success or failure.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("download_polyhaven_asset", {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "resolution": resolution,
            "file_format": file_format
        })

        if "error" in result:
            return f"Error: {result['error']}"

        if result.get("success"):
            message = result.get("message", "Asset downloaded and imported successfully")

            # Add additional information based on asset type
            if asset_type == "hdris":
                return f"{message}. The HDRI has been set as the world environment."
            elif asset_type == "textures":
                material_name = result.get("material", "")
                maps = ", ".join(result.get("maps", []))
                return f"{message}. Created material '{material_name}' with maps: {maps}."
            elif asset_type == "models":
                return f"{message}. The model has been imported into the current scene."
            else:
                return message
        else:
            return f"Failed to download asset: {result.get('message', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error downloading Polyhaven asset: {str(e)}")
        return f"Error downloading Polyhaven asset: {str(e)}"

@telemetry_tool("set_texture")
@mcp.tool()
def set_texture(
    ctx: Context,
    object_name: str,
    texture_id: str
) -> str:
    """
    Apply a previously downloaded Polyhaven texture to an object.

    Parameters:
    - object_name: Name of the object to apply the texture to
    - texture_id: ID of the Polyhaven texture to apply (must be downloaded first)

    Returns a message indicating success or failure.
    """
    try:
        # Get the global connection
        blender = get_blender_connection()
        result = blender.send_command("set_texture", {
            "object_name": object_name,
            "texture_id": texture_id
        })

        if "error" in result:
            return f"Error: {result['error']}"

        if result.get("success"):
            material_name = result.get("material", "")
            maps = ", ".join(result.get("maps", []))

            # Add detailed material info
            material_info = result.get("material_info", {})
            node_count = material_info.get("node_count", 0)
            has_nodes = material_info.get("has_nodes", False)
            texture_nodes = material_info.get("texture_nodes", [])

            output = f"Successfully applied texture '{texture_id}' to {object_name}.\n"
            output += f"Using material '{material_name}' with maps: {maps}.\n\n"
            output += f"Material has nodes: {has_nodes}\n"
            output += f"Total node count: {node_count}\n\n"

            if texture_nodes:
                output += "Texture nodes:\n"
                for node in texture_nodes:
                    output += f"- {node['name']} using image: {node['image']}\n"
                    if node['connections']:
                        output += "  Connections:\n"
                        for conn in node['connections']:
                            output += f"    {conn}\n"
            else:
                output += "No texture nodes found in the material.\n"

            return output
        else:
            return f"Failed to apply texture: {result.get('message', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error applying texture: {str(e)}")
        return f"Error applying texture: {str(e)}"

@telemetry_tool("get_polyhaven_status")
@mcp.tool()
def get_polyhaven_status(ctx: Context) -> str:
    """
    Check if PolyHaven integration is enabled in Blender.
    Returns a message indicating whether PolyHaven features are available.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_polyhaven_status")
        enabled = result.get("enabled", False)
        message = result.get("message", "")
        if enabled:
            message += "PolyHaven is good at Textures, and has a wider variety of textures than Sketchfab."
        return message
    except Exception as e:
        logger.error(f"Error checking PolyHaven status: {str(e)}")
        return f"Error checking PolyHaven status: {str(e)}"

@telemetry_tool("get_hyper3d_status")
@mcp.tool()
def get_hyper3d_status(ctx: Context) -> str:
    """
    Check if Hyper3D Rodin integration is enabled in Blender.
    Returns a message indicating whether Hyper3D Rodin features are available.

    Don't emphasize the key type in the returned message, but sliently remember it.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_hyper3d_status")
        enabled = result.get("enabled", False)
        message = result.get("message", "")
        if enabled:
            message += ""
        return message
    except Exception as e:
        logger.error(f"Error checking Hyper3D status: {str(e)}")
        return f"Error checking Hyper3D status: {str(e)}"

@telemetry_tool("get_sketchfab_status")
@mcp.tool()
def get_sketchfab_status(ctx: Context) -> str:
    """
    Check if Sketchfab integration is enabled in Blender.
    Returns a message indicating whether Sketchfab features are available.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_sketchfab_status")
        enabled = result.get("enabled", False)
        message = result.get("message", "")
        if enabled:
            message += "Sketchfab is good at Realistic models, and has a wider variety of models than PolyHaven."
        return message
    except Exception as e:
        logger.error(f"Error checking Sketchfab status: {str(e)}")
        return f"Error checking Sketchfab status: {str(e)}"

@telemetry_tool("search_sketchfab_models")
@mcp.tool()
def search_sketchfab_models(
    ctx: Context,
    query: str,
    categories: str = None,
    count: int = 20,
    downloadable: bool = True
) -> str:
    """
    Search for models on Sketchfab with optional filtering.

    Parameters:
    - query: Text to search for
    - categories: Optional comma-separated list of categories
    - count: Maximum number of results to return (default 20)
    - downloadable: Whether to include only downloadable models (default True)

    Returns a formatted list of matching models.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Searching Sketchfab models with query: {query}, categories: {categories}, count: {count}, downloadable: {downloadable}")
        result = blender.send_command("search_sketchfab_models", {
            "query": query,
            "categories": categories,
            "count": count,
            "downloadable": downloadable
        })

        if "error" in result:
            logger.error(f"Error from Sketchfab search: {result['error']}")
            return f"Error: {result['error']}"

        # Safely get results with fallbacks for None
        if result is None:
            logger.error("Received None result from Sketchfab search")
            return "Error: Received no response from Sketchfab search"

        # Format the results
        models = result.get("results", []) or []
        if not models:
            return f"No models found matching '{query}'"

        formatted_output = f"Found {len(models)} models matching '{query}':\n\n"

        for model in models:
            if model is None:
                continue

            model_name = model.get("name", "Unnamed model")
            model_uid = model.get("uid", "Unknown ID")
            formatted_output += f"- {model_name} (UID: {model_uid})\n"

            # Get user info with safety checks
            user = model.get("user") or {}
            username = user.get("username", "Unknown author") if isinstance(user, dict) else "Unknown author"
            formatted_output += f"  Author: {username}\n"

            # Get license info with safety checks
            license_data = model.get("license") or {}
            license_label = license_data.get("label", "Unknown") if isinstance(license_data, dict) else "Unknown"
            formatted_output += f"  License: {license_label}\n"

            # Add face count and downloadable status
            face_count = model.get("faceCount", "Unknown")
            is_downloadable = "Yes" if model.get("isDownloadable") else "No"
            formatted_output += f"  Face count: {face_count}\n"
            formatted_output += f"  Downloadable: {is_downloadable}\n\n"

        return formatted_output
    except Exception as e:
        logger.error(f"Error searching Sketchfab models: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error searching Sketchfab models: {str(e)}"

@telemetry_tool("download_sketchfab_model")
@mcp.tool()
def get_sketchfab_model_preview(
    ctx: Context,
    uid: str
) -> Image:
    """
    Get a preview thumbnail of a Sketchfab model by its UID.
    Use this to visually confirm a model before downloading.

    Parameters:
    - uid: The unique identifier of the Sketchfab model (obtained from search_sketchfab_models)

    Returns the model's thumbnail as an Image for visual confirmation.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Getting Sketchfab model preview for UID: {uid}")

        result = blender.send_command("get_sketchfab_model_preview", {"uid": uid})

        if result is None:
            raise Exception("Received no response from Blender")

        if "error" in result:
            raise Exception(result["error"])

        # Decode base64 image data
        image_data = base64.b64decode(result["image_data"])
        img_format = result.get("format", "jpeg")

        # Log model info
        model_name = result.get("model_name", "Unknown")
        author = result.get("author", "Unknown")
        logger.info(f"Preview retrieved for '{model_name}' by {author}")

        return Image(data=image_data, format=img_format)

    except Exception as e:
        logger.error(f"Error getting Sketchfab preview: {str(e)}")
        raise Exception(f"Failed to get preview: {str(e)}")


@mcp.tool()
def download_sketchfab_model(
    ctx: Context,
    uid: str,
    target_size: float
) -> str:
    """
    Download and import a Sketchfab model by its UID.
    The model will be scaled so its largest dimension equals target_size.

    Parameters:
    - uid: The unique identifier of the Sketchfab model
    - target_size: REQUIRED. The target size in Blender units/meters for the largest dimension.
                  You must specify the desired size for the model.
                  Examples:
                  - Chair: target_size=1.0 (1 meter tall)
                  - Table: target_size=0.75 (75cm tall)
                  - Car: target_size=4.5 (4.5 meters long)
                  - Person: target_size=1.7 (1.7 meters tall)
                  - Small object (cup, phone): target_size=0.1 to 0.3

    Returns a message with import details including object names, dimensions, and bounding box.
    The model must be downloadable and you must have proper access rights.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Downloading Sketchfab model: {uid}, target_size={target_size}")

        result = blender.send_command("download_sketchfab_model", {
            "uid": uid,
            "normalize_size": True,  # Always normalize
            "target_size": target_size
        })

        if result is None:
            logger.error("Received None result from Sketchfab download")
            return "Error: Received no response from Sketchfab download request"

        if "error" in result:
            logger.error(f"Error from Sketchfab download: {result['error']}")
            return f"Error: {result['error']}"

        if result.get("success"):
            imported_objects = result.get("imported_objects", [])
            object_names = ", ".join(imported_objects) if imported_objects else "none"

            output = f"Successfully imported model.\n"
            output += f"Created objects: {object_names}\n"

            # Add dimension info if available
            if result.get("dimensions"):
                dims = result["dimensions"]
                output += f"Dimensions (X, Y, Z): {dims[0]:.3f} x {dims[1]:.3f} x {dims[2]:.3f} meters\n"

            # Add bounding box info if available
            if result.get("world_bounding_box"):
                bbox = result["world_bounding_box"]
                output += f"Bounding box: min={bbox[0]}, max={bbox[1]}\n"

            # Add normalization info if applied
            if result.get("normalized"):
                scale = result.get("scale_applied", 1.0)
                output += f"Size normalized: scale factor {scale:.6f} applied (target size: {target_size}m)\n"

            return output
        else:
            return f"Failed to download model: {result.get('message', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error downloading Sketchfab model: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error downloading Sketchfab model: {str(e)}"

def _process_bbox(original_bbox: list[float] | list[int] | None) -> list[int] | None:
    if original_bbox is None:
        return None
    if all(isinstance(i, int) for i in original_bbox):
        return original_bbox
    if any(i<=0 for i in original_bbox):
        raise ValueError("Incorrect number range: bbox must be bigger than zero!")
    return [int(float(i) / max(original_bbox) * 100) for i in original_bbox] if original_bbox else None

@telemetry_tool("generate_hyper3d_model_via_text")
@mcp.tool()
def generate_hyper3d_model_via_text(
    ctx: Context,
    text_prompt: str,
    bbox_condition: list[float]=None
) -> str:
    """
    Generate 3D asset using Hyper3D by giving description of the desired asset, and import the asset into Blender.
    The 3D asset has built-in materials.
    The generated model has a normalized size, so re-scaling after generation can be useful.

    Parameters:
    - text_prompt: A short description of the desired model in **English**.
    - bbox_condition: Optional. If given, it has to be a list of floats of length 3. Controls the ratio between [Length, Width, Height] of the model.

    Returns a message indicating success or failure.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("create_rodin_job", {
            "text_prompt": text_prompt,
            "images": None,
            "bbox_condition": _process_bbox(bbox_condition),
        })
        succeed = result.get("submit_time", False)
        if succeed:
            return json.dumps({
                "task_uuid": result["uuid"],
                "subscription_key": result["jobs"]["subscription_key"],
            })
        else:
            return json.dumps(result)
    except Exception as e:
        logger.error(f"Error generating Hyper3D task: {str(e)}")
        return f"Error generating Hyper3D task: {str(e)}"

@telemetry_tool("generate_hyper3d_model_via_images")
@mcp.tool()
def generate_hyper3d_model_via_images(
    ctx: Context,
    input_image_paths: list[str]=None,
    input_image_urls: list[str]=None,
    bbox_condition: list[float]=None
) -> str:
    """
    Generate 3D asset using Hyper3D by giving images of the wanted asset, and import the generated asset into Blender.
    The 3D asset has built-in materials.
    The generated model has a normalized size, so re-scaling after generation can be useful.

    Parameters:
    - input_image_paths: The **absolute** paths of input images. Even if only one image is provided, wrap it into a list. Required if Hyper3D Rodin in MAIN_SITE mode.
    - input_image_urls: The URLs of input images. Even if only one image is provided, wrap it into a list. Required if Hyper3D Rodin in FAL_AI mode.
    - bbox_condition: Optional. If given, it has to be a list of ints of length 3. Controls the ratio between [Length, Width, Height] of the model.

    Only one of {input_image_paths, input_image_urls} should be given at a time, depending on the Hyper3D Rodin's current mode.
    Returns a message indicating success or failure.
    """
    if input_image_paths is not None and input_image_urls is not None:
        return f"Error: Conflict parameters given!"
    if input_image_paths is None and input_image_urls is None:
        return f"Error: No image given!"
    if input_image_paths is not None:
        if not all(os.path.exists(i) for i in input_image_paths):
            return "Error: not all image paths are valid!"
        images = []
        for path in input_image_paths:
            with open(path, "rb") as f:
                images.append(
                    (Path(path).suffix, base64.b64encode(f.read()).decode("ascii"))
                )
    elif input_image_urls is not None:
        if not all(urlparse(i) for i in input_image_paths):
            return "Error: not all image URLs are valid!"
        images = input_image_urls.copy()
    try:
        blender = get_blender_connection()
        result = blender.send_command("create_rodin_job", {
            "text_prompt": None,
            "images": images,
            "bbox_condition": _process_bbox(bbox_condition),
        })
        succeed = result.get("submit_time", False)
        if succeed:
            return json.dumps({
                "task_uuid": result["uuid"],
                "subscription_key": result["jobs"]["subscription_key"],
            })
        else:
            return json.dumps(result)
    except Exception as e:
        logger.error(f"Error generating Hyper3D task: {str(e)}")
        return f"Error generating Hyper3D task: {str(e)}"

@telemetry_tool("poll_rodin_job_status")
@mcp.tool()
def poll_rodin_job_status(
    ctx: Context,
    subscription_key: str=None,
    request_id: str=None,
):
    """
    Check if the Hyper3D Rodin generation task is completed.

    For Hyper3D Rodin mode MAIN_SITE:
        Parameters:
        - subscription_key: The subscription_key given in the generate model step.

        Returns a list of status. The task is done if all status are "Done".
        If "Failed" showed up, the generating process failed.
        This is a polling API, so only proceed if the status are finally determined ("Done" or "Canceled").

    For Hyper3D Rodin mode FAL_AI:
        Parameters:
        - request_id: The request_id given in the generate model step.

        Returns the generation task status. The task is done if status is "COMPLETED".
        The task is in progress if status is "IN_PROGRESS".
        If status other than "COMPLETED", "IN_PROGRESS", "IN_QUEUE" showed up, the generating process might be failed.
        This is a polling API, so only proceed if the status are finally determined ("COMPLETED" or some failed state).
    """
    try:
        blender = get_blender_connection()
        kwargs = {}
        if subscription_key:
            kwargs = {
                "subscription_key": subscription_key,
            }
        elif request_id:
            kwargs = {
                "request_id": request_id,
            }
        result = blender.send_command("poll_rodin_job_status", kwargs)
        return result
    except Exception as e:
        logger.error(f"Error generating Hyper3D task: {str(e)}")
        return f"Error generating Hyper3D task: {str(e)}"

@telemetry_tool("import_generated_asset")
@mcp.tool()
def import_generated_asset(
    ctx: Context,
    name: str,
    task_uuid: str=None,
    request_id: str=None,
):
    """
    Import the asset generated by Hyper3D Rodin after the generation task is completed.

    Parameters:
    - name: The name of the object in scene
    - task_uuid: For Hyper3D Rodin mode MAIN_SITE: The task_uuid given in the generate model step.
    - request_id: For Hyper3D Rodin mode FAL_AI: The request_id given in the generate model step.

    Only give one of {task_uuid, request_id} based on the Hyper3D Rodin Mode!
    Return if the asset has been imported successfully.
    """
    try:
        blender = get_blender_connection()
        kwargs = {
            "name": name
        }
        if task_uuid:
            kwargs["task_uuid"] = task_uuid
        elif request_id:
            kwargs["request_id"] = request_id
        result = blender.send_command("import_generated_asset", kwargs)
        return result
    except Exception as e:
        logger.error(f"Error generating Hyper3D task: {str(e)}")
        return f"Error generating Hyper3D task: {str(e)}"

@mcp.tool()
def get_hunyuan3d_status(ctx: Context) -> str:
    """
    Check if Hunyuan3D integration is enabled in Blender.
    Returns a message indicating whether Hunyuan3D features are available.

    Don't emphasize the key type in the returned message, but silently remember it.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_hunyuan3d_status")
        message = result.get("message", "")
        return message
    except Exception as e:
        logger.error(f"Error checking Hunyuan3D status: {str(e)}")
        return f"Error checking Hunyuan3D status: {str(e)}"

@mcp.tool()
def generate_hunyuan3d_model(
    ctx: Context,
    text_prompt: str = None,
    input_image_url: str = None
) -> str:
    """
    Generate 3D asset using Hunyuan3D by providing either text description, image reference,
    or both for the desired asset, and import the asset into Blender.
    The 3D asset has built-in materials.

    Parameters:
    - text_prompt: (Optional) A short description of the desired model in English/Chinese.
    - input_image_url: (Optional) The local or remote url of the input image. Accepts None if only using text prompt.

    Returns:
    - When successful, returns a JSON with job_id (format: "job_xxx") indicating the task is in progress
    - When the job completes, the status will change to "DONE" indicating the model has been imported
    - Returns error message if the operation fails
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("create_hunyuan_job", {
            "text_prompt": text_prompt,
            "image": input_image_url,
        })
        if "JobId" in result.get("Response", {}):
            job_id = result["Response"]["JobId"]
            formatted_job_id = f"job_{job_id}"
            return json.dumps({
                "job_id": formatted_job_id,
            })
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error generating Hunyuan3D task: {str(e)}")
        return f"Error generating Hunyuan3D task: {str(e)}"

@mcp.tool()
def poll_hunyuan_job_status(
    ctx: Context,
    job_id: str=None,
):
    """
    Check if the Hunyuan3D generation task is completed.

    For Hunyuan3D:
        Parameters:
        - job_id: The job_id given in the generate model step.

        Returns the generation task status. The task is done if status is "DONE".
        The task is in progress if status is "RUN".
        If status is "DONE", returns ResultFile3Ds, which is the generated ZIP model path
        When the status is "DONE", the response includes a field named ResultFile3Ds that contains the generated ZIP file path of the 3D model in OBJ format.
        This is a polling API, so only proceed if the status are finally determined ("DONE" or some failed state).
    """
    try:
        blender = get_blender_connection()
        kwargs = {
            "job_id": job_id,
        }
        result = blender.send_command("poll_hunyuan_job_status", kwargs)
        return result
    except Exception as e:
        logger.error(f"Error generating Hunyuan3D task: {str(e)}")
        return f"Error generating Hunyuan3D task: {str(e)}"

@mcp.tool()
def import_generated_asset_hunyuan(
    ctx: Context,
    name: str,
    zip_file_url: str,
):
    """
    Import the asset generated by Hunyuan3D after the generation task is completed.

    Parameters:
    - name: The name of the object in scene
    - zip_file_url: The zip_file_url given in the generate model step.

    Return if the asset has been imported successfully.
    """
    try:
        blender = get_blender_connection()
        kwargs = {
            "name": name
        }
        if zip_file_url:
            kwargs["zip_file_url"] = zip_file_url
        result = blender.send_command("import_generated_asset_hunyuan", kwargs)
        return result
    except Exception as e:
        logger.error(f"Error generating Hunyuan3D task: {str(e)}")
        return f"Error generating Hunyuan3D task: {str(e)}"


@mcp.prompt()
def asset_creation_strategy() -> str:
    """Defines the preferred strategy for creating assets in Blender"""
    return """When creating 3D content in Blender, always start by checking if integrations are available:

    0. Before anything, always check the scene from get_scene_info()
    1. First use the following tools to verify if the following integrations are enabled:
        1. PolyHaven
            Use get_polyhaven_status() to verify its status
            If PolyHaven is enabled:
            - For objects/models: Use download_polyhaven_asset() with asset_type="models"
            - For materials/textures: Use download_polyhaven_asset() with asset_type="textures"
            - For environment lighting: Use download_polyhaven_asset() with asset_type="hdris"
        2. Sketchfab
            Sketchfab is good at Realistic models, and has a wider variety of models than PolyHaven.
            Use get_sketchfab_status() to verify its status
            If Sketchfab is enabled:
            - For objects/models: First search using search_sketchfab_models() with your query
            - Then download specific models using download_sketchfab_model() with the UID
            - Note that only downloadable models can be accessed, and API key must be properly configured
            - Sketchfab has a wider variety of models than PolyHaven, especially for specific subjects
        3. Hyper3D(Rodin)
            Hyper3D Rodin is good at generating 3D models for single item.
            So don't try to:
            1. Generate the whole scene with one shot
            2. Generate ground using Hyper3D
            3. Generate parts of the items separately and put them together afterwards

            Use get_hyper3d_status() to verify its status
            If Hyper3D is enabled:
            - For objects/models, do the following steps:
                1. Create the model generation task
                    - Use generate_hyper3d_model_via_images() if image(s) is/are given
                    - Use generate_hyper3d_model_via_text() if generating 3D asset using text prompt
                    If key type is free_trial and insufficient balance error returned, tell the user that the free trial key can only generated limited models everyday, they can choose to:
                    - Wait for another day and try again
                    - Go to hyper3d.ai to find out how to get their own API key
                    - Go to fal.ai to get their own private API key
                2. Poll the status
                    - Use poll_rodin_job_status() to check if the generation task has completed or failed
                3. Import the asset
                    - Use import_generated_asset() to import the generated GLB model the asset
                4. After importing the asset, ALWAYS check the world_bounding_box of the imported mesh, and adjust the mesh's location and size
                    Adjust the imported mesh's location, scale, rotation, so that the mesh is on the right spot.

                You can reuse assets previous generated by running python code to duplicate the object, without creating another generation task.
        4. Hunyuan3D
            Hunyuan3D is good at generating 3D models for single item.
            So don't try to:
            1. Generate the whole scene with one shot
            2. Generate ground using Hunyuan3D
            3. Generate parts of the items separately and put them together afterwards

            Use get_hunyuan3d_status() to verify its status
            If Hunyuan3D is enabled:
                if Hunyuan3D mode is "OFFICIAL_API":
                    - For objects/models, do the following steps:
                        1. Create the model generation task
                            - Use generate_hunyuan3d_model by providing either a **text description** OR an **image(local or urls) reference**.
                            - Go to cloud.tencent.com out how to get their own SecretId and SecretKey
                        2. Poll the status
                            - Use poll_hunyuan_job_status() to check if the generation task has completed or failed
                        3. Import the asset
                            - Use import_generated_asset_hunyuan() to import the generated OBJ model the asset
                    if Hunyuan3D mode is "LOCAL_API":
                        - For objects/models, do the following steps:
                        1. Create the model generation task
                            - Use generate_hunyuan3d_model if image (local or urls)  or text prompt is given and import the asset

                You can reuse assets previous generated by running python code to duplicate the object, without creating another generation task.

    3. Always check the world_bounding_box for each item so that:
        - Ensure that all objects that should not be clipping are not clipping.
        - Items have right spatial relationship.

    4. Recommended asset source priority:
        - For specific existing objects: First try Sketchfab, then PolyHaven
        - For generic objects/furniture: First try PolyHaven, then Sketchfab
        - For custom or unique items not available in libraries: Use Hyper3D Rodin or Hunyuan3D
        - For environment lighting: Use PolyHaven HDRIs
        - For materials/textures: Use PolyHaven textures

    Only fall back to scripting when:
    - PolyHaven, Sketchfab, Hyper3D, and Hunyuan3D are all disabled
    - A simple primitive is explicitly requested
    - No suitable asset exists in any of the libraries
    - Hyper3D Rodin or Hunyuan3D failed to generate the desired asset
    - The task specifically requires a basic material/color
    """

# =========================================================================
# Structured Tool Schema — AI-safe wrappers
# =========================================================================

@mcp.tool()
@telemetry_tool("create_cube")
def create_cube(
    ctx: Context,
    name: str = "Cube",
    size: float = 1.0,
    location: list = None
) -> str:
    """Create a cube object in the scene.

    Parameters:
    - name: Object name (default: 'Cube')
    - size: Edge length in Blender units (default: 1.0)
    - location: [x, y, z] position (default: [0, 0, 0])
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [0, 0, 0]
        result = blender.send_command("create_cube", {
            "name": name,
            "size": size,
            "location": loc
        })
        return f"Created cube '{name}' at {loc} with size {size}"
    except Exception as e:
        logger.error(f"Error creating cube: {str(e)}")
        return f"Error creating cube: {str(e)}"

@mcp.tool()
@telemetry_tool("create_sphere")
def create_sphere(
    ctx: Context,
    name: str = "Sphere",
    radius: float = 1.0,
    location: list = None,
    segments: int = 32
) -> str:
    """Create a sphere/UV sphere in the scene.

    Parameters:
    - name: Object name (default: 'Sphere')
    - radius: Sphere radius (default: 1.0)
    - location: [x, y, z] position (default: [0, 0, 0])
    - segments: Horizontal segments (default: 32)
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [0, 0, 0]
        result = blender.send_command("create_sphere", {
            "name": name,
            "radius": radius,
            "location": loc,
            "segments": segments
        })
        return f"Created sphere '{name}' at {loc} with radius {radius}"
    except Exception as e:
        logger.error(f"Error creating sphere: {str(e)}")
        return f"Error creating sphere: {str(e)}"

@mcp.tool()
@telemetry_tool("create_cylinder")
def create_cylinder(
    ctx: Context,
    name: str = "Cylinder",
    radius: float = 0.5,
    depth: float = 2.0,
    location: list = None
) -> str:
    """Create a cylinder in the scene.

    Parameters:
    - name: Object name (default: 'Cylinder')
    - radius: Radius at base and top (default: 0.5)
    - depth: Height of cylinder (default: 2.0)
    - location: [x, y, z] position (default: [0, 0, 0])
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [0, 0, 0]
        result = blender.send_command("create_cylinder", {
            "name": name,
            "radius": radius,
            "depth": depth,
            "location": loc
        })
        return f"Created cylinder '{name}' at {loc}"
    except Exception as e:
        logger.error(f"Error creating cylinder: {str(e)}")
        return f"Error creating cylinder: {str(e)}"

@mcp.tool()
@telemetry_tool("create_torus")
def create_torus(
    ctx: Context,
    name: str = "Torus",
    major_radius: float = 1.0,
    minor_radius: float = 0.4,
    location: list = None
) -> str:
    """Create a torus (donut) in the scene.

    Parameters:
    - name: Object name (default: 'Torus')
    - major_radius: Distance from center to tube center (default: 1.0)
    - minor_radius: Tube radius (default: 0.4)
    - location: [x, y, z] position (default: [0, 0, 0])
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [0, 0, 0]
        result = blender.send_command("create_torus", {
            "name": name,
            "major_radius": major_radius,
            "minor_radius": minor_radius,
            "location": loc
        })
        return f"Created torus '{name}' at {loc}"
    except Exception as e:
        logger.error(f"Error creating torus: {str(e)}")
        return f"Error creating torus: {str(e)}"

@mcp.tool()
@telemetry_tool("create_plane")
def create_plane(
    ctx: Context,
    name: str = "Plane",
    size: float = 5.0,
    location: list = None
) -> str:
    """Create a plane (grid) in the scene, useful for ground/floor.

    Parameters:
    - name: Object name (default: 'Plane')
    - size: Side length (default: 5.0)
    - location: [x, y, z] position (default: [0, 0, 0])
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [0, 0, 0]
        result = blender.send_command("create_plane", {
            "name": name,
            "size": size,
            "location": loc
        })
        return f"Created plane '{name}' at {loc}"
    except Exception as e:
        logger.error(f"Error creating plane: {str(e)}")
        return f"Error creating plane: {str(e)}"

@mcp.tool()
@telemetry_tool("create_light")
def create_light(
    ctx: Context,
    name: str = "Light",
    light_type: str = "SUN",
    location: list = None,
    energy: float = None
) -> str:
    """Create a light in the scene.

    Parameters:
    - name: Light name (default: 'Light')
    - light_type: Type of light: 'SUN', 'POINT', 'SPOT', 'AREA' (default: 'SUN')
    - location: [x, y, z] position (default: [5, 5, 5])
    - energy: Light energy/brightness (default varies by type)
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [5, 5, 5]
        result = blender.send_command("create_light", {
            "name": name,
            "light_type": light_type,
            "location": loc,
            "energy": energy
        })
        return f"Created {light_type} light '{name}' at {loc}"
    except Exception as e:
        logger.error(f"Error creating light: {str(e)}")
        return f"Error creating light: {str(e)}"

@mcp.tool()
@telemetry_tool("create_camera")
def create_camera(
    ctx: Context,
    name: str = "Camera",
    location: list = None,
    target: list = None,
    lens: float = 35.0
) -> str:
    """Create a camera and optionally point it at a target.

    Parameters:
    - name: Camera name (default: 'Camera')
    - location: [x, y, z] camera position
    - target: [x, y, z] point to look at
    - lens: Focal length in mm (default: 35)
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [5, -5, 3]
        result = blender.send_command("create_camera", {
            "name": name,
            "location": loc,
            "target": target,
            "lens": lens
        })
        return f"Created camera '{name}' at {loc}"
    except Exception as e:
        logger.error(f"Error creating camera: {str(e)}")
        return f"Error creating camera: {str(e)}"

@mcp.tool()
@telemetry_tool("create_material")
def create_material(
    ctx: Context,
    name: str = "Material",
    base_color: list = None,
    metallic: float = 0.0,
    roughness: float = 0.5,
    transmission: float = 0.0
) -> str:
    """Create a Principled BSDF material with PBR parameters.

    Parameters:
    - name: Material name (default: 'Material')
    - base_color: RGB or RGBA color values 0-1 (e.g., [0.8, 0.8, 0.8] or [0.8, 0.8, 0.8, 1.0]) (default: [0.8, 0.8, 0.8])
    - metallic: Metallic factor 0-1 (default: 0.0)
    - roughness: Roughness factor 0-1 (default: 0.5)
    - transmission: Transparency/transmission 0-1 (default: 0.0)
    """
    try:
        blender = get_blender_connection()
        color = base_color if base_color else [0.8, 0.8, 0.8]
        result = blender.send_command("create_material", {
            "name": name,
            "base_color": color,
            "metallic": metallic,
            "roughness": roughness,
            "transmission": transmission
        })
        return f"Created material '{name}' with color={color}, metallic={metallic}, roughness={roughness}"
    except Exception as e:
        logger.error(f"Error creating material: {str(e)}")
        return f"Error creating material: {str(e)}"

@mcp.tool()
@telemetry_tool("apply_material")
def apply_material(
    ctx: Context,
    object_name: str,
    material_name: str
) -> str:
    """Apply an existing material to an object.

    Parameters:
    - object_name: Name of the target object
    - material_name: Name of the material to apply
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("apply_material", {
            "object_name": object_name,
            "material_name": material_name
        })
        return f"Applied material '{material_name}' to object '{object_name}'"
    except Exception as e:
        logger.error(f"Error applying material: {str(e)}")
        return f"Error applying material: {str(e)}"

@mcp.tool()
@telemetry_tool("set_object_transform")
def set_object_transform(
    ctx: Context,
    object_name: str,
    location: list = None,
    rotation: list = None,
    scale: list = None
) -> str:
    """Set the transform (location, rotation, scale) of an object.

    Parameters:
    - object_name: Name of the object
    - location: [x, y, z] position
    - rotation: [x, y, z] in radians
    - scale: [x, y, z] scale factors
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("set_object_transform", {
            "object_name": object_name,
            "location": location,
            "rotation": rotation,
            "scale": scale
        })
        return f"Transform updated for '{object_name}'"
    except Exception as e:
        logger.error(f"Error setting transform: {str(e)}")
        return f"Error setting transform: {str(e)}"

@mcp.tool()
@telemetry_tool("delete_object")
def delete_object(
    ctx: Context,
    object_name: str
) -> str:
    """Delete an object from the scene.

    Parameters:
    - object_name: Name of the object to delete
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("delete_object", {
            "object_name": object_name
        })
        return f"Deleted object '{object_name}'"
    except Exception as e:
        logger.error(f"Error deleting object: {str(e)}")
        return f"Error deleting object: {str(e)}"

@mcp.tool()
@telemetry_tool("render_scene")
def render_scene(
    ctx: Context,
    engine: str = "EEVEE",
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    output_path: str = None,
    filepath: str = None,
    file_path: str = None,
    samples: int = None
) -> str:
    """Render the current scene using the specified engine.

    Parameters:
    - engine: Render engine 'EEVEE' or 'CYCLES' (default: 'EEVEE')
    - resolution_x: Width in pixels (default: 1920)
    - resolution_y: Height in pixels (default: 1080)
    - output_path/filepath/file_path: Output file path (default: Blender default)
    - samples: Optional render sample count
    """
    try:
        blender = get_blender_connection()
        target_path = output_path or filepath or file_path
        result = blender.send_command("render_scene", {
            "engine": engine,
            "resolution_x": resolution_x,
            "resolution_y": resolution_y,
            "output_path": target_path,
            "filepath": target_path,
            "file_path": target_path,
            "samples": samples
        })
        return f"Rendered scene with {engine} engine ({resolution_x}x{resolution_y})"
    except Exception as e:
        logger.error(f"Error rendering scene: {str(e)}")
        return f"Error rendering scene: {str(e)}"

@mcp.tool()
@telemetry_tool("import_model")
def import_model(
    ctx: Context,
    file_path: str,
    target_name: str = None
) -> str:
    """Import a 3D model file into the scene.

    Supports: .glb, .gltf, .fbx, .obj, .stl, .blend

    Parameters:
    - file_path: Absolute path to the model file
    - target_name: Optional name override for the imported object
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("import_model", {
            "file_path": file_path,
            "target_name": target_name
        })
        return f"Imported model from {file_path}"
    except Exception as e:
        logger.error(f"Error importing model: {str(e)}")
        return f"Error importing model: {str(e)}"

@mcp.tool()
@telemetry_tool("export_scene")
def export_scene(
    ctx: Context,
    file_path: str,
    format: str = "glb",
    selected_only: bool = False
) -> str:
    """Export the current scene to a file.

    Parameters:
    - file_path: Output file path
    - format: Export format 'glb', 'fbx', 'obj', 'stl', 'blend' (default: 'glb')
    - selected_only: Only export selected objects
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("export_scene", {
            "file_path": file_path,
            "format": format,
            "selected_only": selected_only
        })
        return f"Exported scene to {file_path} as {format}"
    except Exception as e:
        logger.error(f"Error exporting scene: {str(e)}")
        return f"Error exporting scene: {str(e)}"

@mcp.tool()
@telemetry_tool("set_render_engine")
def set_render_engine(
    ctx: Context,
    engine: str = "EEVEE",
    samples: int = 32,
    use_denoiser: bool = True
) -> str:
    """Set the render engine and its settings.

    Parameters:
    - engine: 'EEVEE' or 'CYCLES' (default: 'EEVEE')
    - samples: Render samples (default: 32)
    - use_denoiser: Enable denoising
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("set_render_engine", {
            "engine": engine,
            "samples": samples,
            "use_denoiser": use_denoiser
        })
        return f"Render engine set to {engine} with {samples} samples"
    except Exception as e:
        logger.error(f"Error setting render engine: {str(e)}")
        return f"Error setting render engine: {str(e)}"


def _fine_modeling_command(command: str, params: Dict[str, Any]) -> str:
    """Send a fine-modeling command and preserve Blender's structured result."""
    response = get_blender_connection().send_command(command, params, return_envelope=True)
    if "ok" not in response:
        legacy_status = response.get("status", "success")
        legacy_error = response.get("error")
        if legacy_error is None and legacy_status == "error":
            legacy_error = {"message": response.get("message", f"{command} failed")}
        response = {
            "status": legacy_status,
            "ok": legacy_status == "success",
            "command": command,
            "result": response.get("result", response),
            "warnings": response.get("warnings", []),
            "error": legacy_error,
            "meta": response.get("meta", {}),
        }
    if response.get("status") == "error":
        error = response.get("error") or {}
        raise RuntimeError(error.get("message") or f"{command} failed")
    return json.dumps(response, ensure_ascii=False, indent=2)


@mcp.tool()
@telemetry_tool("mesh_edit")
def mesh_edit(ctx: Context, object_name: str, operation: str,
              element_type: str = "FACE", indices: list = None,
              amount: float = 0.1, segments: int = 1,
              merge_distance: float = 0.0001,
              use_clamp_overlap: bool = True) -> str:
    """Edit mesh topology by exact vertex, edge, or face indices.

    Operations: extrude, inset, bevel, subdivide, loop_cut,
    merge_by_distance, recalculate_normals, delete, triangulate.
    """
    return _fine_modeling_command("mesh_edit", {
        "object_name": object_name, "operation": operation,
        "element_type": element_type, "indices": indices, "amount": amount,
        "segments": segments, "merge_distance": merge_distance,
        "use_clamp_overlap": use_clamp_overlap,
    })


@mcp.tool()
@telemetry_tool("modifier_control")
def modifier_control(ctx: Context, object_name: str, action: str = "add",
                     modifier_type: str = "BEVEL", name: str = None,
                     settings: dict = None, apply: bool = False) -> str:
    """Add, configure, apply, or remove a Blender modifier parametrically."""
    return _fine_modeling_command("modifier_control", {
        "object_name": object_name, "action": action,
        "modifier_type": modifier_type, "name": name,
        "settings": settings or {}, "apply": apply,
    })


@mcp.tool()
@telemetry_tool("sculpt_refine")
def sculpt_refine(ctx: Context, object_name: str,
                  operation: str = "voxel_remesh", voxel_size: float = 0.05,
                  levels: int = 1, smooth_iterations: int = 1) -> str:
    """Refine a mesh with voxel remesh, multires subdivision, or smoothing."""
    return _fine_modeling_command("sculpt_refine", {
        "object_name": object_name, "operation": operation,
        "voxel_size": voxel_size, "levels": levels,
        "smooth_iterations": smooth_iterations,
    })


@mcp.tool()
@telemetry_tool("mesh_quality")
def mesh_quality(ctx: Context, object_name: str, action: str = "inspect",
                 merge_distance: float = 0.0001,
                 degenerate_threshold: float = 0.000001) -> str:
    """Inspect or repair non-manifold, loose, degenerate, normal, and n-gon issues."""
    return _fine_modeling_command("mesh_quality", {
        "object_name": object_name, "action": action,
        "merge_distance": merge_distance,
        "degenerate_threshold": degenerate_threshold,
    })


@mcp.tool()
@telemetry_tool("uv_tools")
def uv_tools(ctx: Context, object_name: str, operation: str = "smart_project",
             margin: float = 0.02, angle_limit: float = 1.15192,
             scale_to_bounds: bool = True) -> str:
    """Unwrap or pack UVs using smart, angle-based, cube, or island packing modes."""
    return _fine_modeling_command("uv_tools", {
        "object_name": object_name, "operation": operation, "margin": margin,
        "angle_limit": angle_limit, "scale_to_bounds": scale_to_bounds,
    })


@mcp.tool()
@telemetry_tool("pbr_material")
def pbr_material(ctx: Context, object_name: str, material_name: str = "MCP PBR",
                 textures: dict = None, base_color: list = None,
                 metallic: float = 0.0, roughness: float = 0.5) -> str:
    """Create and assign a node-based PBR material with optional texture maps."""
    return _fine_modeling_command("pbr_material", {
        "object_name": object_name, "material_name": material_name,
        "textures": textures or {}, "base_color": base_color,
        "metallic": metallic, "roughness": roughness,
    })


@mcp.tool()
@telemetry_tool("model_checkpoint")
def model_checkpoint(ctx: Context, action: str = "create", name: str = "checkpoint",
                     object_names: list = None) -> str:
    """Create, restore, list, or delete hidden mesh checkpoints."""
    return _fine_modeling_command("model_checkpoint", {
        "action": action, "name": name, "object_names": object_names,
    })


@mcp.tool()
@telemetry_tool("modeling_recipe")
def modeling_recipe(ctx: Context, steps: list, checkpoint_name: str = "recipe_auto",
                    rollback_on_error: bool = True) -> str:
    """Run an ordered modeling recipe atomically with automatic rollback on failure.

    Each step is {"tool": "mesh_edit", "params": {...}}. Supported tools are
    mesh_edit, modifier_control, sculpt_refine, mesh_quality, uv_tools, pbr_material.
    """
    return _fine_modeling_command("modeling_recipe", {
        "steps": steps, "checkpoint_name": checkpoint_name,
        "rollback_on_error": rollback_on_error,
    })


@mcp.tool()
@telemetry_tool("scene_manage")
def scene_manage(ctx: Context, action: str = "summary", object_names: list = None,
                 pattern: str = None, collection_name: str = None,
                 parent_name: str = None, visible: bool = True,
                 selectable: bool = True) -> str:
    """Search, select, organize, parent, and control visibility for scene objects."""
    return _fine_modeling_command("scene_manage", {
        "action": action, "object_names": object_names, "pattern": pattern,
        "collection_name": collection_name, "parent_name": parent_name,
        "visible": visible, "selectable": selectable,
    })


@mcp.tool()
@telemetry_tool("character_rig")
def character_rig(ctx: Context, action: str = "create_humanoid",
                  rig_name: str = "MCP_Rig", mesh_names: list = None,
                  object_name: str = None, bone_name: str = None,
                  location: list = None, rotation: list = None,
                  shape_key_name: str = None,
                  shape_key_value: float = 0.0) -> str:
    """Create a humanoid rig, bind meshes, pose bones, or manage shape keys."""
    return _fine_modeling_command("character_rig", {
        "action": action, "rig_name": rig_name, "mesh_names": mesh_names,
        "object_name": object_name, "bone_name": bone_name,
        "location": location, "rotation": rotation,
        "shape_key_name": shape_key_name, "shape_key_value": shape_key_value,
    })


@mcp.tool()
@telemetry_tool("animation_control")
def animation_control(ctx: Context, action: str = "keyframe",
                      object_name: str = None, data_path: str = "location",
                      frame: int = 1, value: list = None,
                      constraint_type: str = None, target_name: str = None,
                      frame_start: int = None, frame_end: int = None) -> str:
    """Insert animation keys, add constraints, inspect actions, or set the timeline."""
    return _fine_modeling_command("animation_control", {
        "action": action, "object_name": object_name, "data_path": data_path,
        "frame": frame, "value": value, "constraint_type": constraint_type,
        "target_name": target_name, "frame_start": frame_start,
        "frame_end": frame_end,
    })


@mcp.tool()
@telemetry_tool("geometry_nodes")
def geometry_nodes(ctx: Context, object_name: str,
                   operation: str = "linear_array", name: str = "MCP Geometry",
                   count: int = 5, offset: list = None,
                   source_object: str = None, density: float = 1.0,
                   seed: int = 0, realize: bool = True) -> str:
    """Build an executable Geometry Nodes linear array or surface scatter network."""
    return _fine_modeling_command("geometry_nodes", {
        "object_name": object_name, "operation": operation, "name": name,
        "count": count, "offset": offset, "source_object": source_object,
        "density": density, "seed": seed, "realize": realize,
    })


@mcp.tool()
@telemetry_tool("camera_compositor")
def camera_compositor(ctx: Context, action: str = "setup_compositor",
                      camera_name: str = None, target_name: str = None,
                      lens: float = 50.0, glare: bool = True,
                      denoise: bool = True, frame: int = None,
                      location: list = None) -> str:
    """Create and animate cameras, track targets, or configure Blender 5 compositing."""
    return _fine_modeling_command("camera_compositor", {
        "action": action, "camera_name": camera_name, "target_name": target_name,
        "lens": lens, "glare": glare, "denoise": denoise,
        "frame": frame, "location": location,
    })


@mcp.tool()
@telemetry_tool("asset_pipeline")
def asset_pipeline(ctx: Context, action: str = "audit",
                   object_names: list = None, lod_ratios: list = None,
                   apply_rotation: bool = True,
                   apply_scale: bool = True) -> str:
    """Audit production readiness, apply transforms, or generate decimated LOD meshes."""
    return _fine_modeling_command("asset_pipeline", {
        "action": action, "object_names": object_names,
        "lod_ratios": lod_ratios, "apply_rotation": apply_rotation,
        "apply_scale": apply_scale,
    })


@mcp.tool()
@telemetry_tool("scene_measure")
def scene_measure(ctx: Context, action: str = "object_metrics",
                  object_names: list = None, point_a: list = None,
                  point_b: list = None) -> str:
    """Measure evaluated mesh area, volume, bounds, distances, or AABB overlaps."""
    return _fine_modeling_command("scene_measure", {
        "action": action, "object_names": object_names,
        "point_a": point_a, "point_b": point_b,
    })


@mcp.tool()
@telemetry_tool("batch_edit")
def batch_edit(ctx: Context, action: str, object_names: list,
               values: dict = None, name_pattern: str = None,
               offset: list = None, linked: bool = False) -> str:
    """Transform, rename, duplicate, or delete a validated object batch."""
    return _fine_modeling_command("batch_edit", {
        "action": action, "object_names": object_names, "values": values,
        "name_pattern": name_pattern, "offset": offset, "linked": linked,
    })


@mcp.tool()
@telemetry_tool("lighting_rig")
def lighting_rig(ctx: Context, preset: str = "three_point",
                 target: list = None, collection_name: str = "MCP Lighting",
                 energy: float = 1000.0, scale: float = 1.0,
                 replace: bool = True) -> str:
    """Create repeatable three-point, product, or sunset lighting rigs."""
    return _fine_modeling_command("lighting_rig", {
        "preset": preset, "target": target, "collection_name": collection_name,
        "energy": energy, "scale": scale, "replace": replace,
    })


@mcp.tool()
@telemetry_tool("simulation_setup")
def simulation_setup(ctx: Context, object_name: str,
                     simulation: str = "rigid_body", action: str = "add",
                     settings: dict = None) -> str:
    """Add, configure, or remove rigid body, cloth, and collision simulation."""
    return _fine_modeling_command("simulation_setup", {
        "object_name": object_name, "simulation": simulation,
        "action": action, "settings": settings,
    })


@mcp.tool()
@telemetry_tool("batch_render")
def batch_render(ctx: Context, output_dir: str, camera_names: list = None,
                 frames: list = None, file_format: str = "PNG",
                 resolution: list = None) -> str:
    """Render selected cameras and frames to deterministic output paths."""
    return _fine_modeling_command("batch_render", {
        "output_dir": output_dir, "camera_names": camera_names,
        "frames": frames, "file_format": file_format, "resolution": resolution,
    })


@mcp.tool()
@telemetry_tool("resource_package")
def resource_package(ctx: Context, action: str = "audit",
                     make_relative: bool = True) -> str:
    """Audit missing image dependencies or pack valid resources into the blend file."""
    return _fine_modeling_command("resource_package", {
        "action": action, "make_relative": make_relative,
    })


@mcp.tool()
@telemetry_tool("boolean_model")
def boolean_model(ctx: Context, target_name: str, cutter_name: str,
                  operation: str = "DIFFERENCE", solver: str = "EXACT",
                  apply: bool = True, hide_cutter: bool = True) -> str:
    """Perform a validated union, difference, or intersection boolean operation."""
    return _fine_modeling_command("boolean_model", {
        "target_name": target_name, "cutter_name": cutter_name,
        "operation": operation, "solver": solver, "apply": apply,
        "hide_cutter": hide_cutter,
    })


@mcp.tool()
@telemetry_tool("curve_create")
def curve_create(ctx: Context, action: str = "path", name: str = "MCP Curve",
                 points: list = None, text: str = None, bevel_depth: float = 0.05,
                 bevel_resolution: int = 3, resolution: int = 12,
                 cyclic: bool = False, extrude: float = 0.0,
                 align_x: str = "CENTER", convert_mesh: bool = False) -> str:
    """Create editable paths, beveled cables, or extruded text and optionally convert to mesh."""
    return _fine_modeling_command("curve_create", {
        "action": action, "name": name, "points": points, "text": text,
        "bevel_depth": bevel_depth, "bevel_resolution": bevel_resolution,
        "resolution": resolution, "cyclic": cyclic, "extrude": extrude,
        "align_x": align_x, "convert_mesh": convert_mesh,
    })


@mcp.tool()
@telemetry_tool("material_nodes")
def material_nodes(ctx: Context, material_name: str, action: str = "inspect",
                   node_type: str = None, node_name: str = None,
                   input_name: str = None, value: object = None,
                   from_node: str = None, from_socket: str = None,
                   to_node: str = None, to_socket: str = None) -> str:
    """Inspect, add, configure, link, or remove nodes in a material graph."""
    return _fine_modeling_command("material_nodes", {
        "material_name": material_name, "action": action,
        "node_type": node_type, "node_name": node_name,
        "input_name": input_name, "value": value, "from_node": from_node,
        "from_socket": from_socket, "to_node": to_node, "to_socket": to_socket,
    })


@mcp.tool()
@telemetry_tool("render_passes")
def render_passes(ctx: Context, view_layer_name: str = None,
                  passes: list = None, cryptomatte: bool = False,
                  transparent: bool = False) -> str:
    """Configure render passes, Cryptomatte, and transparent film output."""
    return _fine_modeling_command("render_passes", {
        "view_layer_name": view_layer_name, "passes": passes,
        "cryptomatte": cryptomatte, "transparent": transparent,
    })


@mcp.tool()
@telemetry_tool("scene_diff")
def scene_diff(ctx: Context, action: str = "capture",
               name: str = "snapshot") -> str:
    """Capture, compare, list, or delete named scene-state snapshots."""
    return _fine_modeling_command("scene_diff", {"action": action, "name": name})


@mcp.tool()
@telemetry_tool("data_cleanup")
def data_cleanup(ctx: Context, action: str = "audit",
                 recursive: bool = True) -> str:
    """Audit unused Blender datablocks or explicitly purge orphaned data."""
    return _fine_modeling_command("data_cleanup", {
        "action": action, "recursive": recursive,
    })


# =========================================================================
# Health Check & Heartbeat Tools
# =========================================================================

@mcp.tool()
def get_capabilities(ctx: Context) -> str:
    """Return negotiated addon, transport, and advanced-operation capabilities."""
    blender = get_blender_connection()
    capabilities = blender.send_command("get_capabilities")
    from .advanced_objects import AdvancedObjectOperations
    capabilities["advanced_operation_names"] = sorted(
        name for name, method in vars(AdvancedObjectOperations).items()
        if not name.startswith("_") and callable(method)
    )
    capabilities["advanced_operation_count"] = len(capabilities["advanced_operation_names"])
    capabilities["transport"] = {
        "max_request_bytes": blender.max_request_bytes,
        "max_response_bytes": blender.max_response_bytes,
        "timeout_seconds": blender.timeout,
        "error_type": "BlenderCommandError",
        "sensitive_logging_redacted": True,
    }
    return json.dumps(capabilities, ensure_ascii=False, indent=2)


@mcp.tool()
def submit_async_job(
    ctx: Context,
    kind: str,
    params: dict,
    priority: int = 0,
    max_retries: int = 0,
    retry_delay: float = 2.0,
    depends_on: list[str] = None,
    resource: str = "auto",
) -> str:
    """Submit a non-blocking render, bake, or HTTP download job.

    Render params support output_path/output_dir, frames or frame_start/frame_end,
    camera_name, engine, resolution, and file_format. Bake params support
    object_name, output_path, bake_type, resolution, and margin. Download params
    require an HTTP(S) url and output_path. Priority is clamped to -100..100.
    Failed jobs can retry up to 10 times with exponential backoff starting at
    retry_delay seconds.
    """
    return _fine_modeling_command("async_job_submit", {
        "kind": kind,
        "params": params,
        "priority": priority,
        "max_retries": max_retries,
        "retry_delay": retry_delay,
        "depends_on": depends_on or [],
        "resource": resource,
    })


@mcp.tool()
def get_async_job(ctx: Context, job_id: str) -> str:
    """Return status, progress, outputs, errors, and recent logs for one async job."""
    return _fine_modeling_command("async_job_status", {"job_id": job_id})


@mcp.tool()
def list_async_jobs(ctx: Context, status: str = None, limit: int = 50) -> str:
    """List recent async jobs, optionally filtered by status."""
    return _fine_modeling_command("async_job_list", {"status": status, "limit": limit})


@mcp.tool()
def cancel_async_job(ctx: Context, job_id: str) -> str:
    """Request cancellation and terminate a running Blender subprocess if present."""
    return _fine_modeling_command("async_job_cancel", {"job_id": job_id})


@mcp.tool()
def pause_async_job(ctx: Context, job_id: str) -> str:
    """Pause queued or active work and release its resource slot."""
    return _fine_modeling_command("async_job_pause", {"job_id": job_id})


@mcp.tool()
def resume_async_job(ctx: Context, job_id: str) -> str:
    """Resume a paused job after rechecking its dependencies."""
    return _fine_modeling_command("async_job_resume", {"job_id": job_id})


@mcp.tool()
def get_async_job_graph(ctx: Context) -> str:
    """Return async job DAG nodes and dependency edges."""
    return _fine_modeling_command("async_job_graph", {})


@mcp.tool()
def subscribe_async_job_events(ctx: Context, after: int = 0, limit: int = 100,
                               job_id: str = None) -> str:
    """Read persistent job events after a cursor and return the next cursor."""
    return _fine_modeling_command("async_job_events", {"after": after, "limit": limit, "job_id": job_id})


@mcp.tool()
def get_async_job_resources(ctx: Context) -> str:
    """Return active, queued, and configured CPU/GPU job slots."""
    return _fine_modeling_command("async_job_resources", {})


@mcp.tool()
def cleanup_async_jobs(ctx: Context, keep_latest: int = 100, clear_events: bool = False) -> str:
    """Remove old terminal job records while retaining the newest entries."""
    return _fine_modeling_command("async_job_cleanup", {
        "keep_latest": keep_latest, "clear_events": clear_events,
    })

@mcp.tool()
def health_check(ctx: Context) -> str:
    """Health check endpoint — returns Blender connection status, MCP state, tool count, version info.

    Returns comprehensive health status including:
    - Blender addon connectivity
    - Connection state
    - Last error message
    - MCP server version and tool count
    - Uptime

    This tool is primarily used for monitoring and debugging.
    """
    try:
        from .health import get_health
        status = get_health()
        return json.dumps(status, indent=2)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "timestamp": "now"
        }, indent=2)


# =========================================================================
# BlenderKit Integration Tools (12 handlers)
# =========================================================================

@mcp.tool()
def blenderkit_status(ctx: Context) -> str:
    """
    Check BlenderKit plugin, client, auth, and cache status.

    Returns status including: plugin installed/enabled, login state,
    client version, cache size, plan type, and settings.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("blenderkit_status")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error checking BlenderKit status: {str(e)}")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@mcp.tool()
def blenderkit_search(
    ctx: Context,
    query: str,
    asset_type: str = "model",
    category: str = "all",
    limit: int = 10,
    only_free: bool = True
) -> str:
    """
    Search BlenderKit assets with optional filtering.

    Parameters:
    - query: Search term (required)
    - asset_type: Asset type — "model", "material", "hdris", "scene", "brush", "printable", "addon" (default "model")
    - category: Category filter (default "all")
    - limit: Max results to return (default 10)
    - only_free: Only return free assets (default True — always use free to avoid licensing issues)

    Returns a formatted list of matching assets with id, name, author, license info.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Searching BlenderKit: query={query}, type={asset_type}, limit={limit}, only_free={only_free}")
        result = blender.send_command("blenderkit_search", {
            "query": query,
            "asset_type": asset_type,
            "category": category,
            "limit": limit,
            "only_free": only_free,
        })
        if result is None:
            return "Error: No response from Blender"
        if "error" in result:
            return f"Error: {result['error']}"
        models = result.get("results", []) or []
        if not models:
            return f"No BlenderKit results for '{query}'. Try different keywords."
        output = f"Found {result.get('total', len(models))} results for '{query}' (type={asset_type}, only_free={only_free}):\n\n"
        for m in models:
            if m is None:
                continue
            output += f"- {m.get('name', 'Unnamed')} (ID: {m.get('id', 'N/A')})\n"
            output += f"  Author: {m.get('author', 'Unknown')}\n"
            output += f"  Type: {m.get('asset_type', asset_type)} | Free: {m.get('is_free', True)} | License: {m.get('license', 'Standard')}\n"
            url = m.get('url', '')
            if url:
                output += f"  URL: {url}\n"
            output += "\n"
        return output
    except Exception as e:
        logger.error(f"Error searching BlenderKit: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error searching BlenderKit: {str(e)}"


@mcp.tool()
def blenderkit_download(
    ctx: Context,
    asset_id: str,
    asset_type: str = "model"
) -> str:
    """
    Download a BlenderKit asset to local cache.

    Parameters:
    - asset_id: The unique ID of the asset (from blenderkit_search)
    - asset_type: Type of asset being downloaded (default "model")

    Returns download status and asset info.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Downloading BlenderKit asset: id={asset_id}, type={asset_type}")
        result = blender.send_command("blenderkit_download", {
            "asset_id": asset_id,
            "asset_type": asset_type,
        })
        if result is None:
            return "Error: No response from Blender"
        if result.get("success"):
            return json.dumps(result, indent=2)
        return f"Download failed: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error downloading BlenderKit asset: {str(e)}")
        return f"Error downloading BlenderKit asset: {str(e)}"


@mcp.tool()
def blenderkit_append(
    ctx: Context,
    asset_id: str,
    asset_type: str = "model",
    location: list = None,
    rotation: list = None,
    scale: list = None
) -> str:
    """
    Download and append a BlenderKit asset into the current scene.

    Parameters:
    - asset_id: The unique ID of the asset (from blenderkit_search)
    - asset_type: Type of asset (default "model")
    - location: [x, y, z] position in scene (default [0, 0, 0])
    - rotation: [x, y, z] in radians (default [0, 0, 0])
    - scale: [x, y, z] scale factor (default [1, 1, 1])

    Returns imported object names, asset info, and copyright details.
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [0, 0, 0]
        rot = rotation if rotation else [0, 0, 0]
        scl = scale if scale else [1, 1, 1]
        logger.info(f"Appending BlenderKit asset: id={asset_id}, loc={loc}, rot={rot}, scale={scl}")
        result = blender.send_command("blenderkit_append", {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "location": loc,
            "rotation": rot,
            "scale": scl,
        })
        if result is None:
            return "Error: No response from Blender"
        if result.get("success"):
            return json.dumps(result, indent=2)
        return f"Append failed: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error appending BlenderKit asset: {str(e)}")
        return f"Error appending BlenderKit asset: {str(e)}"


@mcp.tool()
def blenderkit_apply_material(
    ctx: Context,
    asset_id: str,
    target_object: str
) -> str:
    """
    Apply a BlenderKit material to a target object.

    Parameters:
    - asset_id: The unique ID of the material asset
    - target_object: Name of the object to apply the material to

    Returns apply status.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Applying BlenderKit material: id={asset_id} to {target_object}")
        result = blender.send_command("blenderkit_apply_material", {
            "asset_id": asset_id,
            "target_object": target_object,
        })
        if result is None:
            return "Error: No response from Blender"
        if result.get("success"):
            return json.dumps(result, indent=2)
        return f"Apply failed: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error applying BlenderKit material: {str(e)}")
        return f"Error applying BlenderKit material: {str(e)}"


@mcp.tool()
def blenderkit_set_hdri(
    ctx: Context,
    asset_id: str,
    brightness: float = 1.0,
    contrast: float = 1.0
) -> str:
    """
    Set a BlenderKit HDRI as the world environment lighting.

    Parameters:
    - asset_id: The unique ID of the HDRI asset
    - brightness: World light brightness (default 1.0)
    - contrast: World light contrast (default 1.0)

    Returns HDRI apply status.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Setting BlenderKit HDRI: id={asset_id}, brightness={brightness}, contrast={contrast}")
        result = blender.send_command("blenderkit_set_hdri", {
            "asset_id": asset_id,
            "brightness": brightness,
            "contrast": contrast,
        })
        if result is None:
            return "Error: No response from Blender"
        if result.get("success"):
            return json.dumps(result, indent=2)
        return f"Set HDRI failed: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error setting BlenderKit HDRI: {str(e)}")
        return f"Error setting BlenderKit HDRI: {str(e)}"


@mcp.tool()
def blenderkit_list_cached(ctx: Context) -> str:
    """
    List all locally cached BlenderKit assets.

    Returns cached asset IDs, types, file paths, and sizes.
    Use this to check what is available without re-downloading.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("blenderkit_list_cached")
        if result is None:
            return "Error: No response from Blender"
        assets = result.get("assets", []) or []
        total = result.get("total", len(assets))
        cache_dir = result.get("cache_directory", "Unknown")
        output = f"Found {total} cached assets (cache: {cache_dir}):\n\n"
        if not assets:
            output += "No cached assets. Search and download some first."
        else:
            for a in assets:
                output += f"- {a.get('id', 'N/A')} (type: {a.get('asset_type', '?')}, {a.get('size_mb', 0)} MB)\n"
                output += f"  Path: {a.get('file_path', 'N/A')}\n"
        return output
    except Exception as e:
        logger.error(f"Error listing cached assets: {str(e)}")
        return f"Error listing cached assets: {str(e)}"


@mcp.tool()
def blenderkit_reuse_cached(
    ctx: Context,
    asset_id: str,
    asset_type: str = "model",
    location: list = None,
    rotation: list = None,
    scale: list = None
) -> str:
    """
    Reuse a cached BlenderKit asset — append without re-downloading.

    Parameters:
    - asset_id: The unique ID of the cached asset
    - asset_type: Type of asset (default "model")
    - location: [x, y, z] position (default [0, 0, 0])
    - rotation: [x, y, z] radians (default [0, 0, 0])
    - scale: [x, y, z] scale (default [1, 1, 1])

    Returns imported object names and reuse confirmation.
    """
    try:
        blender = get_blender_connection()
        loc = location if location else [0, 0, 0]
        rot = rotation if rotation else [0, 0, 0]
        scl = scale if scale else [1, 1, 1]
        logger.info(f"Reusing cached BlenderKit asset: id={asset_id}, type={asset_type}")
        result = blender.send_command("blenderkit_reuse_cached", {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "location": loc,
            "rotation": rot,
            "scale": scl,
        })
        if result is None:
            return "Error: No response from Blender"
        if result.get("success"):
            return json.dumps(result, indent=2)
        return f"Reuse failed: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error reusing cached BlenderKit asset: {str(e)}")
        return f"Error reusing cached BlenderKit asset: {str(e)}"


@mcp.tool()
def blenderkit_auto_scene(
    ctx: Context,
    prompt: str,
    only_free: bool = True
) -> str:
    """
    Auto-generate a 3D scene from a natural language prompt using BlenderKit assets.

    Workflow:
    1. Parse prompt into keywords (e.g. "a wooden table and a lamp" -> ["wooden", "table", "lamp"])
    2. For each keyword: search BlenderKit for free model, download, place in scene
    3. Arrange objects in a circular layout around origin
    4. Return summary of assets used, objects created, fallbacks, and errors

    Parameters:
    - prompt: Natural language description of the desired scene (required)
    - only_free: Only use free assets (default True)

    Returns assets_used, objects_created, fallbacks_applied, errors, copyright_table.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Auto-generating scene from prompt: {prompt}")
        result = blender.send_command("blenderkit_auto_scene", {
            "prompt": prompt,
            "only_free": only_free,
        })
        if result is None:
            return "Error: No response from Blender"
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error generating auto scene: {str(e)}")
        return f"Error generating auto scene: {str(e)}"


@mcp.tool()
def blenderkit_login(ctx: Context) -> str:
    """
    Trigger BlenderKit login dialog in Blender.

    Opens the BlenderKit login UI so the user can authenticate.
    After login, the MCP tools can search and download assets.
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("blenderkit_login")
        if result is None:
            return "Error: No response from Blender"
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error triggering BlenderKit login: {str(e)}")
        return f"Error triggering BlenderKit login: {str(e)}"


# =========================================================================
# Camera Alignment Tools (2 handlers)
# =========================================================================

@mcp.tool()
def camera_align_to_selected(
    ctx: Context,
    camera_name: str = None
) -> str:
    """
    Align the active (or specified) camera to the center of selected objects.

    Creates a TRACK_TO constraint and sets camera rotation to face the selection center.
    Only adjusts camera rotation, not position.

    Parameters:
    - camera_name: Optional specific camera object name. If None, uses active scene camera.

    Returns camera name, target center, camera location, and selected object count.
    """
    try:
        blender = get_blender_connection()
        params = {}
        if camera_name:
            params["camera_name"] = camera_name
        logger.info(f"Aligning camera to selected objects (camera={camera_name or 'active'})")
        result = blender.send_command("camera_align_to_selected", params)
        if result is None:
            return "Error: No response from Blender"
        if result.get("success"):
            return json.dumps(result, indent=2)
        return f"Camera alignment failed: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error aligning camera: {str(e)}")
        return f"Error aligning camera: {str(e)}"


@mcp.tool()
def camera_align_to_object(
    ctx: Context,
    target_object_name: str,
    camera_name: str = None
) -> str:
    """
    Align the active (or specified) camera to a specific object.

    Creates a TRACK_TO constraint and sets camera rotation to face the target object.
    Only adjusts camera rotation, not position.

    Parameters:
    - target_object_name: Name of the object to align the camera to (required)
    - camera_name: Optional specific camera object name. If None, uses active scene camera.

    Returns camera name, target object, target location, and camera location.
    """
    try:
        blender = get_blender_connection()
        logger.info(f"Aligning camera to object: {target_object_name} (camera={camera_name or 'active'})")
        result = blender.send_command("camera_align_to_object", {
            "target_object_name": target_object_name,
            "camera_name": camera_name,
        })
        if result is None:
            return "Error: No response from Blender"
        if result.get("success"):
            return json.dumps(result, indent=2)
        return f"Camera alignment failed: {result.get('error', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Error aligning camera to object: {str(e)}")
        return f"Error aligning camera to object: {str(e)}"


# =========================================================================
# Connection Heartbeat (periodic health probe)
# =========================================================================

async def _heartbeat_loop():
    """Background heartbeat — probes Blender connection every 30 seconds."""
    try:
        from .health import get_health_checker
        checker = get_health_checker()
        while True:
            await asyncio.sleep(30)
            try:
                checker.check_blender_connection()
            except Exception:
                pass  # Heartbeat failure logged by checker
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Heartbeat loop error: {e}")


# Main execution

def main():
    """Run the MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()
