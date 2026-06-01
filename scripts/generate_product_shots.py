#================================================================
#  ================================================================
#  generate_product_shots.py
#  ================================================================
#  Project: Blender-MCP-Enhanced
#  Description: Generate product visualization scenes with studio lighting
#  Author: XUJL-916 | Shenzhen University (SZU)
#  Repository: https://github.com/XUJL-916/blender-mcp-enhanced
#  License: MIT
#  ================================================================
#================================================================

"""
Generate product visualization scenes.
Demonstrates studio lighting, material variety, and camera composition
suitable for e-commerce or product catalog rendering.
"""

import bpy
import os
import math

# Configuration
OUTPUT_DIR = r"C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main/demo_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "product_shots.png")
BLENDER_EXE = r"D:/Program Files/blender/blender.exe"

def clear_scene():
    """Clear all existing objects."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_material(name, base_color, metallic=0.0, roughness=0.5, clearcoat=0.0):
    """Create a material with proper node setup."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (*base_color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    # Blender 5.1.2: Clearcoat replaced by Coat system
    if clearcoat > 0:
        bsdf.inputs['Coat Weight'].default_value = clearcoat
        bsdf.inputs['Coat Roughness'].default_value = roughness * 0.3
        bsdf.inputs['Coat IOR'].default_value = 1.5
    return mat

def create_product_spheres():
    """Create a set of product spheres with different materials."""
    products = [
        # (name, location, radius, material_func)
        ("glossy_red", (0, 0, 0), 0.8, lambda: create_material("glossy_red", (0.8, 0.1, 0.1), 0.0, 0.1, 1.0)),
        ("matte_blue", (2.5, 0, 0), 0.7, lambda: create_material("matte_blue", (0.1, 0.3, 0.8), 0.0, 0.8, 0.0)),
        ("metallic_gold", (-2.5, 0, 0), 0.75, lambda: create_material("metallic_gold", (0.9, 0.7, 0.2), 1.0, 0.15, 0.0)),
        ("rubber_black", (0, 2.5, 0), 0.6, lambda: create_material("rubber_black", (0.05, 0.05, 0.05), 0.0, 0.9, 0.0)),
        ("pearl_white", (0, -2.5, 0), 0.65, lambda: create_material("pearl_white", (0.95, 0.95, 0.95), 0.0, 0.3, 0.5)),
    ]
    
    for name, location, radius, mat_func in products:
        # Create sphere
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius)
        sphere = bpy.context.active_object
        sphere.name = name
        sphere.location = (location[0], location[1], radius)  # Sit on ground
        sphere.data.materials.append(mat_func())

def create_product_cylinders():
    """Create cylindrical products (bottles/containers)."""
    # Glass bottle
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.4, depth=1.2)
    bottle = bpy.context.active_object
    bottle.name = "glass_bottle"
    bottle.location = (4, 1, 0.6)
    
    glass_mat = create_material("glass_mat", (0.2, 0.4, 0.6), 0.0, 0.05, 0.0)
    glass_mat.node_tree.nodes["Principled BSDF"].inputs['Transmission Weight'].default_value = 0.9
    bottle.data.materials.append(glass_mat)
    
    # Cap
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.3, depth=0.15)
    cap = bpy.context.active_object
    cap.name = "bottle_cap"
    cap.location = (4, 1, 1.275)
    cap.data.materials.append(create_material("cap_mat", (0.9, 0.9, 0.85), 0.0, 0.4, 0.0))
    
    # Metal can
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.5, depth=1.0)
    can = bpy.context.active_object
    can.name = "metal_can"
    can.location = (-4, 1, 0.5)
    can.data.materials.append(create_material("can_mat", (0.6, 0.6, 0.65), 1.0, 0.2, 0.0))
    
    # Label
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-4, 0.51, 0.5))
    label = bpy.context.active_object
    label.rotation_euler = (math.radians(90), 0, 0)
    label.scale = (0.8, 1.2, 1)
    label.data.materials.append(create_material("label_mat", (0.9, 0.15, 0.15), 0.0, 0.6, 0.0))

def create_ground():
    """Create smooth reflective ground."""
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "ground"
    
    # Slightly reflective ground
    ground_mat = create_material("ground_mat", (0.8, 0.8, 0.82), 0.0, 0.3, 0.2)
    ground.data.materials.append(ground_mat)

def setup_studio_lighting():
    """Setup professional 3-point studio lighting."""
    # Key light (main, warm)
    bpy.ops.object.light_add(type='AREA', location=(6, 6, 6))
    key = bpy.context.active_object
    key.name = "key_light"
    key.data.energy = 800
    key.data.color = (1, 0.95, 0.9)
    key.data.size = 8
    
    # Fill light (softer, from opposite side)
    bpy.ops.object.light_add(type='AREA', location=(-5, 4, 4))
    fill = bpy.context.active_object
    fill.name = "fill_light"
    fill.data.energy = 300
    fill.data.color = (0.9, 0.95, 1)
    fill.data.size = 6
    
    # Rim/back light (for edge definition)
    bpy.ops.object.light_add(type='AREA', location=(0, -8, 5))
    rim = bpy.context.active_object
    rim.name = "rim_light"
    rim.data.energy = 400
    rim.data.color = (0.8, 0.9, 1)
    rim.data.size = 5
    
    # Top light (diffuse fill)
    bpy.ops.object.light_add(type='AREA', location=(0, 0, 10))
    top = bpy.context.active_object
    top.name = "top_light"
    top.data.energy = 200
    top.data.color = (1, 1, 1)
    top.data.size = 10

def setup_camera():
    """Setup overhead angled camera for product display."""
    bpy.ops.object.camera_add(location=(5, 8, 6))
    camera = bpy.context.active_object
    camera.name = "camera"
    
    # Look at center of scene
    target = bpy.data.objects.new("camera_target", None)
    target.location = (0, 0, 0.5)
    bpy.context.collection.objects.link(target)
    
    # Track constraint
    track_constraint = camera.constraints.new(type='TRACK_TO')
    track_constraint.target = target
    track_constraint.track_axis = 'TRACK_NEGATIVE_Z'
    track_constraint.up_axis = 'UP_Y'
    
    bpy.context.scene.camera = camera
    camera.data.lens = 45  # Slightly wide for product showcase
    camera.data.sensor_width = 36

def setup_render():
    """Setup render settings."""
    scene = bpy.context.scene
    
    # Eevee for fast rendering
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 128
    
    # Blender 5.1.2 API
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.filepath = OUTPUT_FILE

def main():
    """Main execution."""
    print("Generating Product Shots Scene...")
    
    # Clear and setup
    clear_scene()
    setup_render()
    create_ground()
    create_product_spheres()
    create_product_cylinders()
    setup_studio_lighting()
    setup_camera()
    
    # Render
    print(f"Rendering to: {OUTPUT_FILE}")
    bpy.ops.render.render(write_still=True)
    print(f"✓ Scene generated: {OUTPUT_FILE}")
    
    return OUTPUT_FILE

if __name__ == "__main__":
    main()
