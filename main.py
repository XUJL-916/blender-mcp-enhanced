#================================================================
#  ================================================================
#  main.py
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
#      MCP server entry point — FastMCP initialization and server launch
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
#================================================================

from blender_mcp.server import main as server_main

def main():
    """Entry point for the blender-mcp package"""
    server_main()

if __name__ == "__main__":
    main()
