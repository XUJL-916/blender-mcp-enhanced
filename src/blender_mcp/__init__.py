# ================================================================
#  ================================================================
#  __init__.py
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
#      [File purpose description]
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
# ================================================================

__version__ = "1.5.5"

# Expose key classes and functions for easier imports
from .server import BlenderConnection, get_blender_connection

__all__ = ["BlenderConnection", "get_blender_connection", "__version__"]
