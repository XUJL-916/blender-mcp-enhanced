#================================================================
#  ================================================================
#  generate_robotic_arm.py
#  ================================================================
#  Project: Blender-MCP-Enhanced
#  Description: Generate an articulated robotic arm scene with joints
#  Author: XUJL-916 | Shenzhen University (SZU)
#  Repository: https://github.com/XUJL-916/blender-mcp-enhanced
#  License: MIT
#  ================================================================
#================================================================

"""
Generate an articulated robotic arm scene.
Demonstrates complex hierarchical modeling, metallic materials, and
mechanical joint details suitable for industrial visualization.
"""

import bpy
import os
import math

# Configuration
OUTPUT_DIR = r"C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main/demo_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "robotic_arm.png")
BLENDER_EXE = r"D:/Program Files/blender/blender.exe"

def clear_scene():
    """Clear all existing objects."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_metal_material(name, base_color=(0.3, 0.3, 0.35), metallic=1.0, roughness=0.2):
    """Create a metallic material with proper node setup."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (*base_color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return mat, bsdf

def create_robotic_segment(name, radius, length, rotation_axis, rotation_angle, material):
    """Create a robotic arm segment with cylindrical geometry."""
    # Main cylinder
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=length)
    segment = bpy.context.active_object
    segment.name = name
    segment.rotation_euler = rotation_axis
    segment.rotation_euler[2] = rotation_angle
    segment.data.materials.append(material)
    return segment

def create_joint(name, radius, position, material):
    """Create a joint sphere."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius)
    joint = bpy.context.active_object
    joint.name = name
    joint.location = position
    joint.data.materials.append(material)
    return joint

def create_base():
    """Create the robotic arm base platform."""
    # Base cylinder
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=2, depth=0.5)
    base = bpy.context.active_object
    base.name = "robot_base"
    base.location = (0, 0, -2)
    
    mat = create_metal_material("base_metal", (0.15, 0.15, 0.2), 0.9, 0.3)[0]
    base.data.materials.append(mat)
    
    # Base ring (decorative)
    bpy.ops.mesh.primitive_torus_add(major_radius=2.2, minor_radius=0.15, location=(0, 0, -1.75))
    ring = bpy.context.active_object
    ring.name = "base_ring"
    
    ring_mat, ring_bsdf = create_metal_material("ring_metal", (0.8, 0.2, 0.1), 1.0, 0.1)
    ring_bsdf.inputs['Emission Color'].default_value = (0.8, 0.2, 0.1, 1)
    ring_bsdf.inputs['Emission Strength'].default_value = 3.0
    ring.data.materials.append(ring_mat)

def create_upper_arm():
    """Create the main upper arm structure."""
    # Lower arm segment
    create_robotic_segment("lower_arm", 0.3, 3, (0, math.radians(90), 0), 0,
                          create_metal_material("lower_arm_mat", (0.25, 0.25, 0.3), 0.8, 0.25)[0])
    # Position
    lower = bpy.context.active_object
    lower.location = (0, 0, 0.5)
    
    # Mid joint
    create_joint("elbow_joint", 0.4, (0, 0, 0.5),
                create_metal_material("elbow_mat", (0.15, 0.15, 0.2), 1.0, 0.15)[0])
    
    # Upper arm segment
    create_robotic_segment("upper_arm", 0.25, 2.5, (0, math.radians(75), 0), 0,
                          create_metal_material("upper_arm_mat", (0.3, 0.3, 0.35), 0.8, 0.25)[0])
    # Position upper arm relative to elbow
    upper = bpy.context.active_object
    upper.location = (0, 0, 2.2)
    upper.rotation_euler[0] = math.radians(15)
    
    # Upper joint
    create_joint("shoulder_joint", 0.5, (0, 0, 2.2),
                create_metal_material("shoulder_mat", (0.15, 0.15, 0.2), 1.0, 0.15)[0])

def create_end_effector():
    """Create the robotic gripper/claw."""
    # Base plate
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
    plate = bpy.context.active_object
    plate.name = "gripper_base"
    plate.scale = (0.6, 0.4, 0.1)
    plate.location = (0, 0, 3.8)
    
    plate_mat, plate_bsdf = create_metal_material("gripper_mat", (0.2, 0.2, 0.25), 0.9, 0.2)
    plate_bsdf.inputs['Emission Color'].default_value = (0, 0.6, 1, 1)
    plate_bsdf.inputs['Emission Strength'].default_value = 2.0
    plate.data.materials.append(plate_mat)
    
    # Left gripper finger
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.15, 0, 0.3))
    finger_l = bpy.context.active_object
    finger_l.name = "gripper_left"
    finger_l.scale = (0.1, 0.2, 0.6)
    finger_l.location = (-0.4, 0, 3.8)
    finger_l.data.materials.append(create_metal_material("finger_l_mat", (0.35, 0.35, 0.4), 0.9, 0.15)[0])
    
    # Right gripper finger
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.15, 0, 0.3))
    finger_r = bpy.context.active_object
    finger_r.name = "gripper_right"
    finger_r.scale = (0.1, 0.2, 0.6)
    finger_r.location = (0.4, 0, 3.8)
    finger_r.data.materials.append(create_metal_material("finger_r_mat", (0.35, 0.35, 0.4), 0.9, 0.15)[0])

def create_cables():
    """Create cable bundles along the arm."""
    # Simple cable using torus segments
    for i in range(5):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.08, minor_radius=0.02, 
                                        location=(0.3, i*0.02, 0.5 + i*0.5))
        cable = bpy.context.active_object
        cable.name = f"cable_{i}"
        cable.rotation_euler = (math.radians(90), 0, 0)
        
        cable_mat = bpy.data.materials.new(name=f"cable_{i}_mat")
        cable_mat.use_nodes = True
        bsdf = cable_mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs['Base Color'].default_value = (0.1, 0.1, 0.1, 1)
        bsdf.inputs['Roughness'].default_value = 0.7
        cable.data.materials.append(cable_mat)

def setup_lighting():
    """Setup studio lighting for product visualization."""
    # Key light (warm)
    bpy.ops.object.light_add(type='AREA', location=(5, 5, 5))
    key = bpy.context.active_object
    key.name = "key_light"
    key.data.energy = 500
    key.data.color = (1, 0.9, 0.8)
    key.data.size = 5
    
    # Fill light (cool)
    bpy.ops.object.light_add(type='AREA', location=(-5, 3, 3))
    fill = bpy.context.active_object
    fill.name = "fill_light"
    fill.data.energy = 200
    fill.data.color = (0.7, 0.8, 1)
    fill.data.size = 4
    
    # Rim light (backlight for edge definition)
    bpy.ops.object.light_add(type='AREA', location=(0, -6, 4))
    rim = bpy.context.active_object
    rim.name = "rim_light"
    rim.data.energy = 300
    rim.data.color = (0.8, 0.9, 1)
    rim.data.size = 4
    
    # Ambient light (very dim)
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    ambient = bpy.context.active_object
    ambient.name = "ambient_light"
    ambient.data.energy = 20

def setup_camera():
    """Setup camera for isometric-like product shot."""
    bpy.ops.object.camera_add(location=(6, 6, 4))
    camera = bpy.context.active_object
    camera.name = "camera"
    camera.rotation_euler = (math.radians(50), 0, math.radians(-45))
    
    bpy.context.scene.camera = camera
    
    # Perspective
    camera.data.lens = 50
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
    print("Generating Robotic Arm Scene...")
    
    # Clear and setup
    clear_scene()
    setup_render()
    
    # Create scene hierarchy
    create_base()
    create_upper_arm()
    create_end_effector()
    create_cables()
    setup_lighting()
    setup_camera()
    
    # Render
    print(f"Rendering to: {OUTPUT_FILE}")
    bpy.ops.render.render(write_still=True)
    print(f"✓ Scene generated: {OUTPUT_FILE}")
    
    return OUTPUT_FILE

if __name__ == "__main__":
    main()
