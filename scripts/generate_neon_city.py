#================================================================
#  ================================================================
#  generate_neon_city.py
#  ================================================================
#  Project: Blender-MCP-Enhanced
#  Description: Generate a cyberpunk neon city scene for AI Demo
#  Author: XUJL-916 | Shenzhen University (SZU)
#  Repository: https://github.com/XUJL-916/blender-mcp-enhanced
#  License: MIT
#  ================================================================
#================================================================

"""
Generate a cyberpunk neon city scene.
Creates a futuristic cityscape with glowing buildings, neon signs,
rain effects, and dramatic lighting.
"""

import bpy
import os
import math

# Configuration
OUTPUT_DIR = r"C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main/demo_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "neon_city.png")
BLENDER_EXE = r"D:/Program Files/blender/blender.exe"

def clear_scene():
    """Clear all existing objects."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_building(x, z, width, depth, height, color=(0.1, 0.1, 0.2)):
    """Create a building with neon window strips."""
    # Main building body
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, z))
    building = bpy.context.active_object
    building.name = f"building_{x:.0f}_{z:.0f}"
    building.scale = (width, depth, height)
    
    # Dark metallic material
    mat = bpy.data.materials.new(name=f"building_mat_{x:.0f}_{z:.0f}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = 0.8
    bsdf.inputs['Roughness'].default_value = 0.3
    
    building.data.materials.append(mat)
    
    # Neon window strips
    for i in range(max(1, int(height / 1.5))):
        y_pos = -height/2 + 0.5 + i * 1.5
        if y_pos < height/2 - 0.2:
            bpy.ops.mesh.primitive_plane_add(size=1, location=(x, width/2 + 0.01, y_pos))
            window = bpy.context.active_object
            window.scale = (depth * 0.8, 0.8, 1)
            
            # Neon material (bright cyan/magenta)
            neon_color = (0, 1, 1) if i % 2 == 0 else (1, 0, 1)
            neon_mat = bpy.data.materials.new(name=f"neon_window_{x:.0f}_{i}")
            neon_mat.use_nodes = True
            bsdf_neon = neon_mat.node_tree.nodes["Principled BSDF"]
            bsdf_neon.inputs['Base Color'].default_value = (*neon_color, 1)
            bsdf_neon.inputs['Emission Color'].default_value = (*neon_color, 1)
            bsdf_neon.inputs['Emission Strength'].default_value = 5.0
            bsdf_neon.inputs['Metallic'].default_value = 0.0
            bsdf_neon.inputs['Roughness'].default_value = 0.0
            
            window.data.materials.append(neon_mat)

def create_ground():
    """Create reflective wet ground."""
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, -0.01))
    ground = bpy.context.active_object
    ground.name = "ground"
    
    mat = bpy.data.materials.new(name="ground_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.1, 1)
    bsdf.inputs['Metallic'].default_value = 0.9
    bsdf.inputs['Roughness'].default_value = 0.1
    bsdf.inputs['Specular IOR Level'].default_value = 0.8
    
    ground.data.materials.append(mat)

def create_neon_signs():
    """Create glowing neon signs."""
    neon_positions = [
        (5, 2, 0.5, (1, 0, 0.5)),
        (-3, 1, 0.3, (0, 1, 1)),
        (8, -2, 0.4, (1, 1, 0)),
    ]
    
    for x, z, width, color in neon_positions:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, z, 2))
        sign = bpy.context.active_object
        sign.scale = (width, 0.05, 0.5)
        
        mat = bpy.data.materials.new(name=f"neon_sign_{x:.0f}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs['Base Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = 10.0
        
        sign.data.materials.append(mat)

def setup_lighting():
    """Setup dramatic neon lighting."""
    # Main ambient light (dark blue)
    bpy.ops.object.light_add(type='AREA', location=(0, 5, 5))
    main_light = bpy.context.active_object
    main_light.name = "main_light"
    main_light.data.energy = 100
    main_light.data.color = (0.2, 0.3, 0.8)
    
    # Accent lights
    colors = [(1, 0, 1), (0, 1, 1), (1, 1, 0)]
    for i, color in enumerate(colors):
        bpy.ops.object.light_add(type='POINT', location=(i*6 - 6, 0, 3))
        accent = bpy.context.active_object
        accent.name = f"accent_{i}"
        accent.data.color = color
        accent.data.energy = 500

def setup_camera():
    """Setup camera for cinematic shot."""
    bpy.ops.object.camera_add(location=(15, 12, 8))
    camera = bpy.context.active_object
    camera.name = "camera"
    camera.rotation_euler = (math.radians(45), 0, math.radians(30))
    
    bpy.context.scene.camera = camera

def setup_render():
    """Setup render settings for Eevee (faster for emissive materials)."""
    scene = bpy.context.scene
    
    # Use Eevee for emissive materials (faster, supports bloom)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 64
    # Eevee in 5.1.x has no bloom - emissive materials render as flat bright color
    
    # Blender 5.1.2 API changes
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.filepath = OUTPUT_FILE

def main():
    """Main execution."""
    print("Generating Neon City Scene...")
    
    # Clear and setup
    clear_scene()
    setup_render()
    create_ground()
    
    # Create buildings
    building_configs = [
        (0, 0, 3, 3, 8),
        (5, 0, 2.5, 2.5, 12),
        (-5, 0, 3.5, 3.5, 6),
        (0, 5, 4, 2, 10),
        (0, -5, 3, 4, 7),
        (10, 3, 2, 2, 15),
        (-10, -3, 3, 3, 9),
        (7, -5, 2.5, 2.5, 11),
        (-7, 6, 3, 3, 8),
        (12, -6, 2, 2, 13),
    ]
    
    for x, z, w, d, h in building_configs:
        create_building(x, z, w, d, h)
    
    # Add details
    create_neon_signs()
    setup_lighting()
    setup_camera()
    
    # Render
    print(f"Rendering to: {OUTPUT_FILE}")
    bpy.ops.render.render(write_still=True)
    print(f"✓ Scene generated: {OUTPUT_FILE}")
    
    return OUTPUT_FILE

if __name__ == "__main__":
    main()
