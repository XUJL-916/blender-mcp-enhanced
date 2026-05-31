#================================================================
#  ================================================================
#  generate_demo_screenshot.py
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
#================================================================

import bpy
import os

# Clean scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Set up world color (Blender 5.1.2: use bpy.data.worlds)
world = bpy.data.worlds.new("World") if "World" not in bpy.data.worlds else bpy.data.worlds["World"]
world.use_nodes = True
world_node = world.node_tree.nodes['Background']
world_node.inputs['Color'].default_value = (0.1, 0.1, 0.15, 1.0)
world_node.inputs['Strength'].default_value = 0.5
bpy.context.scene.world = world

# Add three-point lighting
# Key light (main) - Blender 5.1.2 uses bpy.data.lights.new + scene.collection.objects.link
key_light_data = bpy.data.lights.new(name='KeyLight', type='SUN')
key_light = bpy.data.objects.new('KeyLight', key_light_data)
key_light.location = (5, -5, 5)
key_light_data.energy = 5.0
key_light_data.angle = 0.1
bpy.context.scene.collection.objects.link(key_light)

# Fill light
fill_light_data = bpy.data.lights.new(name='FillLight', type='SUN')
fill_light = bpy.data.objects.new('FillLight', fill_light_data)
fill_light.location = (-5, 3, 3)
fill_light_data.energy = 2.0
fill_light_data.angle = 0.3
bpy.context.scene.collection.objects.link(fill_light)

# Back light
back_light_data = bpy.data.lights.new(name='BackLight', type='SUN')
back_light = bpy.data.objects.new('BackLight', back_light_data)
back_light.location = (0, 5, 3)
back_light_data.energy = 3.0
back_light_data.angle = 0.1
bpy.context.scene.collection.objects.link(back_light)

# Create central group of objects
# Main cube with metallic material
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.5))
cube = bpy.context.active_object
cube.name = "Main_Cube"

mat = bpy.data.materials.new(name="Metallic_Red")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Clear default nodes
nodes.clear()

# Principled BSDF
bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (200, 0)
bsdf.inputs['Base Color'].default_value = (0.8, 0.1, 0.1, 1.0)
bsdf.inputs['Metallic'].default_value = 0.9
bsdf.inputs['Roughness'].default_value = 0.2

# Output
output = nodes.new(type='ShaderNodeOutputMaterial')
output.location = (500, 0)

links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

cube.data.materials.append(mat)

# Sphere
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.5, location=(2.5, 0, 0.5))
sphere = bpy.context.active_object
sphere.name = "Golden_Sphere"

mat_gold = bpy.data.materials.new(name="Gold")
mat_gold.use_nodes = True
nodes = mat_gold.node_tree.nodes
links = mat_gold.node_tree.links
nodes.clear()

bsdf2 = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf2.location = (200, 0)
bsdf2.inputs['Base Color'].default_value = (0.9, 0.7, 0.2, 1.0)
bsdf2.inputs['Metallic'].default_value = 1.0
bsdf2.inputs['Roughness'].default_value = 0.1

output2 = nodes.new(type='ShaderNodeOutputMaterial')
output2.location = (500, 0)

links.new(bsdf2.outputs['BSDF'], output2.inputs['Surface'])
sphere.data.materials.append(mat_gold)

# Cylinder
bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=1.5, location=(-2.5, 0, 0.75))
cylinder = bpy.context.active_object
cylinder.name = "Green_Cylinder"

mat_green = bpy.data.materials.new(name="Matte_Green")
mat_green.use_nodes = True
nodes = mat_green.node_tree.nodes
links = mat_green.node_tree.links
nodes.clear()

bsdf3 = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf3.location = (200, 0)
bsdf3.inputs['Base Color'].default_value = (0.1, 0.6, 0.2, 1.0)
bsdf3.inputs['Metallic'].default_value = 0.0
bsdf3.inputs['Roughness'].default_value = 0.8

output3 = nodes.new(type='ShaderNodeOutputMaterial')
output3.location = (500, 0)

links.new(bsdf3.outputs['BSDF'], output3.inputs['Surface'])
cylinder.data.materials.append(mat_green)

# Small torus (donut)
bpy.ops.mesh.primitive_torus_add(major_radius=0.4, minor_radius=0.15, location=(0, 2.5, 0.4))
torus = bpy.context.active_object
torus.name = "Blue_Torus"

mat_blue = bpy.data.materials.new(name="Matte_Blue")
mat_blue.use_nodes = True
nodes = mat_blue.node_tree.nodes
links = mat_blue.node_tree.links
nodes.clear()

bsdf4 = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf4.location = (200, 0)
bsdf4.inputs['Base Color'].default_value = (0.1, 0.3, 0.8, 1.0)
bsdf4.inputs['Metallic'].default_value = 0.3
bsdf4.inputs['Roughness'].default_value = 0.5

output4 = nodes.new(type='ShaderNodeOutputMaterial')
output4.location = (500, 0)

links.new(bsdf4.outputs['BSDF'], output4.inputs['Surface'])
torus.data.materials.append(mat_blue)

# Ground plane
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
plane = bpy.context.active_object
plane.name = "Ground"

mat_ground = bpy.data.materials.new(name="Ground_Matte")
mat_ground.use_nodes = True
nodes = mat_ground.node_tree.nodes
links = mat_ground.node_tree.links
nodes.clear()

bsdf5 = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf5.location = (200, 0)
bsdf5.inputs['Base Color'].default_value = (0.05, 0.05, 0.08, 1.0)
bsdf5.inputs['Metallic'].default_value = 0.0
bsdf5.inputs['Roughness'].default_value = 1.0

output5 = nodes.new(type='ShaderNodeOutputMaterial')
output5.location = (500, 0)

links.new(bsdf5.outputs['BSDF'], output5.inputs['Surface'])
plane.data.materials.append(mat_ground)

# Camera
bpy.ops.object.camera_add(location=(4, -4, 4), rotation=(-0.6, 0, 0.3))
camera = bpy.context.active_object
camera.data.lens = 50
camera.data.sensor_width = 36
bpy.context.scene.camera = camera

# Scene settings for nice render
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.image_settings.color_mode = 'RGBA'

# Render
output_dir = os.path.join(os.path.dirname(__file__), '..')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'demo_scene.png')
bpy.context.scene.render.filepath = output_path
bpy.ops.render.render(write_still=True)

print(f"Demo scene rendered to: {output_path}")
