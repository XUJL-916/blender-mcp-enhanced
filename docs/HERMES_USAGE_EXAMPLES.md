#!/usr/bin/env python3
"""
Blender-MCP Hermes Agent Usage Examples

Generated: 2026-06-01 | Version: 1.5.5-enh | Target: Blender 5.1.2 / Python 3.13

Complete examples of how Hermes Agent calls Blender-MCP tools
via the MCP protocol for 3D automation.
"""

# ========================================================================
# Example 1: Create a scene with objects and materials
# ========================================================================
# In Hermes Agent, use the "terminal" tool to call:
#     uvx blender-mcp
# Or via delegate_task with the "web" toolset for MCP server management.
#
# The typical flow is:
# 1. Start MCP server: uvx blender-mcp
# 2. Server connects to Blender addon via TCP on localhost:9876
# 3. Tools are registered with FastMCP
# 4. AI agent calls tools through MCP protocol

# ========================================================================
# Example 2: Blender MCP Tool Call (JSON-RPC)
# ========================================================================

import json

# Request to create a cube with a material
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "create_object",
        "arguments": {
            "object_type": "CUBE",
            "name": "MyCube",
            "location": [0, 0, 0],
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1]
        }
    },
    "id": 1
}

# Response structure:
# {
#   "result": {
#     "success": true,
#     "object_name": "MyCube",
#     "message": "Created cube object MyCube"
#   }
# }

# ========================================================================
# Example 3: Material and Node Editor
# ========================================================================

# Apply a procedural material with noise texture:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "create_material",
        "arguments": {
            "name": "Marble",
            "base_color": [0.95, 0.92, 0.88, 1.0],
            "roughness": 0.2,
            "metallic": 0.0,
            "normal_strength": 1.0
        }
    },
    "id": 2
}

# Add noise texture to material:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "image_texture",
        "arguments": {
            "material_name": "Marble",
            "texture_type": "procedural_noise",
            "noise_scale": 2.0,
            "noise_detail": 4
        }
    },
    "id": 3
}

# ========================================================================
# Example 4: Animation Keyframe
# ========================================================================

# Add animation to an object:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "set_transform",
        "arguments": {
            "object_name": "MyCube",
            "location": [5, 0, 0],
            "keyframe": True,
            "frame": 50
        }
    },
    "id": 4
}

# ========================================================================
# Example 5: Render Settings
# ========================================================================

# Configure and trigger render:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "render_scene",
        "arguments": {
            "engine": "BLENDER_EEVEE",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "samples": 128,
            "output_path": "C:/Users/admin/renders/output.png"
        }
    },
    "id": 5
}

# ========================================================================
# Example 6: Asset Import (GLTF/FBX)
# ========================================================================

# Import a 3D model:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "import_gltf",
        "arguments": {
            "filepath": "C:/Users/admin/assets/model.gltf",
            "merge_instances": True,
            "make_paths_relative": True
        }
    },
    "id": 6
}

# ========================================================================
# Example 7: Batch Operations
# ========================================================================

# Batch scale multiple objects:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "batch_scale",
        "arguments": {
            "objects": ["Cube.001", "Cube.002", "Cube.003"],
            "factor": 2.0,
            "axis": "XYZ"
        }
    },
    "id": 7
}

# ========================================================================
# Example 8: Scene Snapshot
# ========================================================================

# Capture viewport screenshot:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "capture_viewport_snapshot",
        "arguments": {
            "filepath": "C:/Users/admin/screenshots/viewport.png",
            "width": 1920,
            "height": 1080,
            "show_overlays": True,
            "show_grid": True
        }
    },
    "id": 8
}

# ========================================================================
# Example 9: 3D Asset Generation (AI)
# ========================================================================

# Generate 3D model from text prompt via Hyper3D:
tool_call = {
    "method": "tools/call",
    "params": {
        "name": "generate_3d_from_text",
        "arguments": {
            "prompt": "A detailed medieval sword",
            "mode": "MAIN_SITE",
            "api_key": "your_hyper3d_key",
            "texture": True
        }
    },
    "id": 9
}

# ========================================================================
# Example 10: Configuration Management
# ========================================================================

from blender_mcp.config import config

# Connection settings
print(f"Host: {config.connection.host}")
print(f"Port: {config.connection.port}")
print(f"Timeout: {config.connection.timeout}")

# API keys
print(f"Hyper3D: {bool(config.api_keys.hyper3d_api_key)}")
print(f"Hunyuan3D: {config.api_keys.has_hunyuan3d_key()}")

# Feature flags
print(f"PolyHaven: {config.blender.polyhaven_enabled}")
print(f"Sketchfab: {config.blender.sketchfab_enabled}")

# Get summary
summary = config.summary()
print(json.dumps(summary, indent=2))

# ========================================================================
# Example 11: Connection Recovery
# ========================================================================

from blender_mcp.connection_recovery import (
    create_connection_manager,
    get_connection_manager,
    CircuitBreaker,
    HealthMetrics
)

# Create a connection manager with custom settings
manager = create_connection_manager(
    host="localhost",
    port=9876,
    timeout=180.0,
    max_retries=3,
    retry_delay=1.0,
    health_threshold=0.8,
    health_window=10,
    auto_reconnect=True,
    max_consecutive_failures=3
)

# Check connection health
health = manager.get_health_status()
print(f"Status: {health['status']}")
print(f"Success Rate: {health['success_rate']:.2%}")
print(f"Last Error: {health['last_error']}")

# Use with circuit breaker protection
try:
    result = manager.execute("get_scene_info", {})
    print(f"Scene info: {result}")
except Exception as e:
    print(f"Connection failed: {e}")
    # Circuit breaker may open after too many failures
    # and prevent further calls until recovery timeout

# ========================================================================
# Example 12: Full Automation Pipeline
# ========================================================================

"""
End-to-end automation: create scene, apply materials,
add animation, and render.

import json

def run_pipeline():
    # 1. Create scene objects
    # tool: create_object(type='CUBE', name='Floor')
    # tool: create_object(type='SPHERE', name='LightSphere', scale=50)
    # tool: create_object(type='CONE', name='Cone1')

    # 2. Set up lighting
    # tool: set_lighting(type='three_point')

    # 3. Create and apply materials
    # tool: create_material(name='FloorMat', base_color=[0.8, 0.8, 0.8, 1], roughness=0.9)
    # tool: apply_material_to_object(object_name='Floor', material_name='FloorMat')

    # 4. Add animation
    # tool: set_transform(object_name='LightSphere', location=[0, 0, 5], keyframe=True, frame=1)
    # tool: set_transform(object_name='LightSphere', location=[10, 0, 5], keyframe=True, frame=50)

    # 5. Configure render
    # tool: set_render_eevee_default()
    # tool: set_render_output(output_path='C:/Users/admin/renders/pipeline')

    # 6. Render
    # tool: render_scene(engine='BLENDER_EEVEE', samples=64, output_path='...')

    # 7. Capture result
    # tool: capture_viewport_snapshot(filepath='C:/Users/admin/screenshots/final.png')

    print("Pipeline complete!")

if __name__ == "__main__":
    run_pipeline()
"""
