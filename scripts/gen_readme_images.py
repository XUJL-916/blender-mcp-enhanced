"""Generate 4 demo renders for README - Blender 5.1.2 compatible.

Fixes: use_rendering_complete handler to save PNG directly after each render.
"""

import bpy
import os
import math
import mathutils

OUTPUT_DIR = r"C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main/assets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def setup_render(scene):
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.film_transparent = True
    scene.eevee.taa_render_samples = 64
    scene.view_settings.exposure = 0.2

def make_world(color=(0.05, 0.05, 0.05), strength=0.5):
    world = bpy.data.worlds.new('World')
    world.color = color
    if world.node_tree:
        for n in world.node_tree.nodes:
            if n.type == 'BACKGROUND':
                n.inputs['Strength'].default_value = strength
    bpy.context.scene.world = world

def make_mat(name, color, metallic=0.0, roughness=0.5, transmission_weight=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if transmission_weight > 0:
        bsdf.inputs['Transmission Weight'].default_value = transmission_weight
    return mat

def area_light(name, loc, energy, color=(1,1,1), size=2.0):
    ld = bpy.data.lights.new(name=f"{name}_L", type='AREA')
    ld.energy = energy
    ld.color = color
    ld.size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    return ob

def cam_at(loc, target, lens=35):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.data.lens = lens
    bpy.context.scene.camera = cam
    dir_vec = (mathutils.Vector(target) - mathutils.Vector(loc)).normalized()
    cam.rotation_euler = dir_vec.to_track_quat('Z', 'Y').to_euler()
    return cam

def apply_material(obj, mat):
    if obj.data.materials:
        obj.data.materials.clear()
    obj.data.materials.append(mat)

def save_render(name):
    """Render and save PNG using write_still."""
    path = os.path.join(OUTPUT_DIR, name)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"  -> {path} ({os.path.getsize(path)/1024:.0f} KB)")

def make_scene1():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render(bpy.context.scene)
    make_world((0.05, 0.05, 0.08), 0.5)

    bpy.ops.mesh.primitive_torus_add(location=(0, 0, 0), major_radius=2.5, minor_radius=0.8)
    torus = bpy.context.active_object
    torus.name = "Torus"
    apply_material(torus, make_mat("Mat_Torus", (0.9, 0.6, 0.2), 0.8, 0.2))

    bpy.ops.mesh.primitive_ico_sphere_add(location=(-5, -3, 1), radius=1.5)
    ico = bpy.context.active_object
    ico.name = "IcoSphere"
    apply_material(ico, make_mat("Mat_Ico", (0.7, 0.3, 0.9), 0.6, 0.3))

    for i, pos in enumerate([(3, 2, 0), (6, -1, 0), (-2, 4, 0)]):
        s = 1 + i*0.3
        bpy.ops.mesh.primitive_cube_add(location=pos, scale=(s, s, s))
        ob = bpy.context.active_object
        ob.name = f"Cube_{i+1}"
        colors = [(0.2, 0.8, 0.5), (0.9, 0.3, 0.3), (0.3, 0.6, 0.9)]
        apply_material(ob, make_mat(f"Mat_C{i}", colors[i], 0.3, 0.4))

    bpy.ops.mesh.primitive_cylinder_add(location=(4, 3, 0), radius=1, depth=2.5)
    cyl = bpy.context.active_object
    cyl.name = "Cylinder"
    apply_material(cyl, make_mat("Mat_Cyl", (0.3, 0.6, 0.9), 0.9, 0.15))

    area_light("Key", (8, -8, 10), 150)
    area_light("Fill", (-8, -5, 8), 75)
    area_light("Rim", (-3, 8, 12), 100, (0.4, 0.6, 1.0))
    cam_at((12, 10, 10), (0, 0, 0))
    save_render("readme_feature_1_object_creation.png")

def make_scene2():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render(bpy.context.scene)
    make_world((0.15, 0.15, 0.25), 1.5)

    specs = [
        ("Glossy", (0.8, 0.2, 0.2), 0.0, 0.1, (-6, 0, 0)),
        ("Metal", (0.9, 0.7, 0.3), 0.95, 0.15, (-3, 0, 0)),
        ("Rubber", (0.2, 0.4, 0.7), 0.0, 0.9, (0, 0, 0)),
        ("Glass", (0.3, 0.8, 0.9), 0.0, 0.05, (3, 0, 0)),
        ("Plastic", (0.9, 0.9, 0.4), 0.1, 0.4, (6, 0, 0)),
    ]

    for name, color, metal, rough, loc in specs:
        bpy.ops.mesh.primitive_uv_sphere_add(location=loc, segments=32, ring_count=16, radius=1.5)
        ob = bpy.context.active_object
        ob.name = name
        if "Glass" in name:
            apply_material(ob, make_mat(name, color, metal, rough, transmission_weight=0.95))
        else:
            apply_material(ob, make_mat(name, color, metal, rough))

    bpy.ops.mesh.primitive_plane_add(location=(0, 0, -2), scale=(10, 10, 10))
    ground = bpy.context.active_object
    apply_material(ground, make_mat("Ground", (0.1, 0.1, 0.15), 0.2, 0.8))

    area_light("Key", (5, -5, 10), 180)
    area_light("Fill", (-5, -3, 8), 90)
    area_light("Top", (0, 5, 12), 60, (0.6, 0.7, 1.0))
    cam_at((10, 5, 8), (0, 0, 0))
    save_render("readme_feature_2_material_system.png")

def make_scene3():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render(bpy.context.scene)
    make_world((0.02, 0.02, 0.05), 0.3)

    bpy.ops.mesh.primitive_ico_sphere_add(location=(0, 0, 0), radius=1.5)
    center = bpy.context.active_object
    center.name = "Center"
    apply_material(center, make_mat("Mat_Center", (0.9, 0.5, 0.1), 0.5, 0.3))

    for i, (r, color) in enumerate([(3.5, (1.0,0.3,0.3)), (5.0, (0.3,1.0,0.3)),
                                      (6.5, (0.3,0.3,1.0)), (8.0, (1.0,1.0,0.3))]):
        bpy.ops.mesh.primitive_uv_sphere_add(location=(r, 0, 0), segments=16, ring_count=8, radius=0.5)
        ob = bpy.context.active_object
        ob.name = f"Planet_{i+1}"
        apply_material(ob, make_mat(f"Mat_P{i+1}", color, 0.3, 0.3))

    bpy.ops.mesh.primitive_torus_add(location=(0, 0, 0), rotation=(math.radians(90), 0, 0), major_radius=4.5, minor_radius=0.08)
    ring = bpy.context.active_object
    ring.name = "Ring"
    apply_material(ring, make_mat("Mat_Ring", (0.9, 0.9, 0.9), 0.9, 0.1))

    for i in range(4):
        ob = bpy.data.objects[f"Planet_{i+1}"]
        ob.rotation_euler = (0, 0, 0)
        ob.keyframe_insert(data_path="rotation_euler", frame=1, index=2)
        ob.rotation_euler = (0, 0, math.radians(360))
        ob.keyframe_insert(data_path="rotation_euler", frame=50, index=2)

    area_light("Key", (6, -6, 8), 160)
    area_light("Fill", (-6, -4, 6), 80)
    cam_at((8, 6, 6), (0, 0, 0))
    save_render("readme_feature_3_animation.png")

def make_scene4():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render(bpy.context.scene)
    make_world((0.05, 0.05, 0.12), 0.8)

    boxes = [
        ("AI_Client", (0, 8, 0), (0.9, 0.3, 0.9)),
        ("MCP_Server", (0, 5, 0), (0.3, 0.8, 1.0)),
        ("Blender_Addon", (0, 2, 0), (1.0, 0.6, 0.2)),
        ("BPy_API", (0, -1, 0), (0.4, 1.0, 0.5)),
        ("Engine", (0, -4, 0), (0.7, 0.4, 1.0)),
    ]

    for name, loc, color in boxes:
        bpy.ops.mesh.primitive_cube_add(location=loc)
        ob = bpy.context.active_object
        ob.name = name
        ob.scale = (3.5, 1.2, 1.0)
        apply_material(ob, make_mat(f"Mat_{name}", color, 0.3, 0.3))

    for i in range(len(boxes)-1):
        y1 = boxes[i][1][1]
        y2 = boxes[i+1][1][1]
        mid_y = (y1 + y2) / 2
        h = abs(y1-y2) - 0.5
        bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=h, location=(0, mid_y, 0))
        cyl = bpy.context.active_object
        cyl.name = f"Link_{i}"
        apply_material(cyl, make_mat(f"Mat_Link{i}", (0.6, 0.8, 1.0), 0.5, 0.2))

    bpy.ops.mesh.primitive_plane_add(location=(0, 0, -5), scale=(10, 10, 10))
    grid = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.subdivide(number_cuts=20)
    bpy.ops.object.mode_set(mode='OBJECT')
    apply_material(grid, make_mat("Grid", (0.3, 0.3, 0.4), 0.2, 0.8))

    area_light("Key", (8, 0, 10), 200)
    area_light("Fill", (-8, 0, 8), 100, (0.5, 0.6, 1.0))
    cam_at((12, 8, 8), (0, 2, 0))
    save_render("readme_feature_4_architecture.png")

if __name__ == "__main__":
    print("Scene 1: Object Creation...")
    make_scene1()
    print("Scene 2: Material System...")
    make_scene2()
    print("Scene 3: Animation...")
    make_scene3()
    print("Scene 4: Architecture...")
    make_scene4()
    print(f"\nAll renders saved to: {OUTPUT_DIR}")
    print("Done!")
