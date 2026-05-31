#================================================================
#  ================================================================
#  test2_material_system.py
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
import sys
import json
from pathlib import Path

# 解析输出路径 (Blender 5.1.2 兼容)
# 解析输出路径 (Blender 5.1.2 sys.argv 兼容)
# sys.argv 格式: [blender_path, -b, --python, script.py, --, --output, path]
output_dir = Path("/tmp")
for i, arg in enumerate(sys.argv):
    if arg == "--":
        # 找到 -- 后的 --output 值
        for j in range(i + 1, len(sys.argv)):
            if sys.argv[j] == "--output" and j + 1 < len(sys.argv):
                output_dir = Path(sys.argv[j + 1])
                break
        break

output_dir.mkdir(parents=True, exist_ok=True)


print(f"输出目录: {output_dir}")
print(f"Blender 版本: {bpy.app.version_string}")

# 清理场景
bpy.ops.wm.read_factory_settings(use_empty=True)

results = {
    "test": "material_system",
    "blender_version": bpy.app.version_string,
    "materials": [],
    "connections": [],
    "verification": {},
}

# =====================
# 创建测试对象
# =====================
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "MaterialTestCube"

# =====================
# 材质1: Principled BSDF 基础材质
# =====================
print("\n[1] 创建 Principled BSDF 基础材质...")
mat = bpy.data.materials.new(name="BasicPrincipled")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# 清除默认节点
nodes.clear()

# 创建 Principled BSDF
bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
bsdf.location = (0, 0)
bsdf.inputs["Base Color"].default_value = (0.8, 0.2, 0.2, 1.0)
bsdf.inputs["Roughness"].default_value = 0.3
bsdf.inputs["Metallic"].default_value = 0.7
print(f"  Principled BSDF: BaseColor=(0.8,0.2,0.2), Roughness=0.3, Metallic=0.7")

# 创建输出
output = nodes.new(type="ShaderNodeOutputMaterial")
output.location = (300, 0)

# 连接
links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
print(f"  连接: Principled BSDF -> Material Output")

results["materials"].append({
    "name": mat.name,
    "type": "principled_bsdf",
    "nodes": ["BSDF", "Output"],
    "connections": 1,
})

# 分配材质
cube.data.materials.append(mat)
print(f"  分配至 {cube.name}")

# =====================
# 材质2: Image Texture + Principled BSDF
# =====================
print("\n[2] 创建 Image Texture 材质...")

# 创建测试图片 (16x16 红色)
img_data = bytearray([255, 0, 0, 255] * 16 * 16)
img = bpy.data.images.new("TestTexture", width=16, height=16, alpha=True)
img.pixels = img_data
print(f"  创建测试图片: 16x16 红色")

mat2 = bpy.data.materials.new(name="TextureMaterial")
mat2.use_nodes = True
nodes2 = mat2.node_tree.nodes
links2 = mat2.node_tree.links
nodes2.clear()

# Image Texture
tex_image = nodes2.new(type="ShaderNodeTexImage")
tex_image.location = (-400, 0)
tex_image.image = img
print(f"  Image Texture: TestTexture (16x16)")

# Principled BSDF
bsdf2 = nodes2.new(type="ShaderNodeBsdfPrincipled")
bsdf2.location = (0, 0)

# Output
output2 = nodes2.new(type="ShaderNodeOutputMaterial")
output2.location = (300, 0)

# 连接
links2.new(tex_image.outputs["Color"], bsdf2.inputs["Base Color"])
links2.new(bsdf2.outputs["BSDF"], output2.inputs["Surface"])
print(f"  连接: ImageTexture.Color -> BSDF.BaseColor")
print(f"  连接: BSDF.BSDF -> Output.Surface")

results["materials"].append({
    "name": mat2.name,
    "type": "image_texture_principled",
    "nodes": ["TexImage", "BSDF", "Output"],
    "connections": 2,
})

# 创建第二个对象并分配
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(5, 0, 0))
sphere = bpy.context.active_object
sphere.name = "TextureTestSphere"
sphere.data.materials.append(mat2)

results["connections"].append({
    "material": mat2.name,
    "from_node": "TexImage",
    "from_socket": "Color",
    "to_node": "BSDF",
    "to_socket": "Base Color",
})
results["connections"].append({
    "material": mat2.name,
    "from_node": "BSDF",
    "from_socket": "BSDF",
    "to_node": "Output",
    "to_socket": "Surface",
})

# =====================
# 材质3: Normal Map + Color Ramp
# =====================
print("\n[3] 创建 Normal Map + Color Ramp 材质...")

mat3 = bpy.data.materials.new(name="NormalRampMaterial")
mat3.use_nodes = True
nodes3 = mat3.node_tree.nodes
links3 = mat3.node_tree.links
nodes3.clear()

# Image Texture (normal map)
normal_tex = nodes3.new(type="ShaderNodeTexImage")
normal_tex.location = (-500, 100)
normal_tex.image = img
normal_tex.image.colorspace_settings.name = "Non-Color"
print(f"  Normal Map Texture: Non-Color")

# Normal Map 节点
normal_map = nodes3.new(type="ShaderNodeNormalMap")
normal_map.location = (-200, 100)
print(f"  Normal Map 节点")

# Color Ramp
color_ramp = nodes3.new(type="ShaderNodeValToRGB")
color_ramp.location = (-500, -100)
color_ramp.color_ramp.interpolation = "EASE"
# 设置颜色渐变
color_ramp.color_ramp.elements[0].color = (0.0, 0.0, 1.0, 1.0)  # 蓝色
color_ramp.color_ramp.elements[1].color = (1.0, 0.0, 0.0, 1.0)  # 红色
print(f"  Color Ramp: Blue -> Red (EASE)")

# Principled BSDF
bsdf3 = nodes3.new(type="ShaderNodeBsdfPrincipled")
bsdf3.location = (0, 0)

# Output
output3 = nodes3.new(type="ShaderNodeOutputMaterial")
output3.location = (300, 0)

# 连接
links3.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
links3.new(normal_map.outputs["Normal"], bsdf3.inputs["Normal"])
links3.new(color_ramp.outputs["Color"], bsdf3.inputs["Base Color"])
links3.new(bsdf3.outputs["BSDF"], output3.inputs["Surface"])
print(f"  连接: TexImage.Color -> NormalMap.Color")
print(f"  连接: NormalMap.Normal -> BSDF.Normal")
print(f"  连接: ColorRamp.Color -> BSDF.BaseColor")
print(f"  连接: BSDF.BSDF -> Output.Surface")

results["materials"].append({
    "name": mat3.name,
    "type": "normal_map_color_ramp",
    "nodes": ["TexImage", "NormalMap", "ValToRGB", "BSDF", "Output"],
    "connections": 4,
})

# 创建第三个对象并分配
bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=2, location=(-5, 0, 0))
cylinder = bpy.context.active_object
cylinder.name = "NormalRampTestCylinder"
cylinder.data.materials.append(mat3)

for conn in [
    ("TexImage", "Color", "NormalMap", "Color"),
    ("NormalMap", "Normal", "BSDF", "Normal"),
    ("ValToRGB", "Color", "BSDF", "Base Color"),
    ("BSDF", "BSDF", "Output", "Surface"),
]:
    results["connections"].append({
        "material": mat3.name,
        "from_node": conn[0],
        "from_socket": conn[1],
        "to_node": conn[2],
        "to_socket": conn[3],
    })

# =====================
# 材质4: Emission
# =====================
print("\n[4] 创建 Emission 材质...")

mat4 = bpy.data.materials.new(name="EmissionMaterial")
mat4.use_nodes = True
nodes4 = mat4.node_tree.nodes
links4 = mat4.node_tree.links
nodes4.clear()

# Emission 节点
emission = nodes4.new(type="ShaderNodeEmission")
emission.location = (0, 0)
emission.inputs["Color"].default_value = (1.0, 0.5, 0.0, 1.0)  # 橙色
emission.inputs["Strength"].default_value = 10.0
print(f"  Emission: Color=(1.0,0.5,0.0), Strength=10.0")

# Mix Shader
mix = nodes4.new(type="ShaderNodeMixShader")
mix.location = (-200, 0)
mix.inputs["Fac"].default_value = 0.5
print(f"  Mix Shader: Fac=0.5")

# BSDF for mix
bsdf4 = nodes4.new(type="ShaderNodeBsdfPrincipled")
bsdf4.location = (-400, 100)
bsdf4.inputs["Base Color"].default_value = (0.2, 0.8, 0.2, 1.0)  # 绿色
print(f"  BSDF (mix): BaseColor=(0.2,0.8,0.2)")

# Output
output4 = nodes4.new(type="ShaderNodeOutputMaterial")
output4.location = (300, 0)

# 连接
links4.new(bsdf4.outputs["BSDF"], mix.inputs[1])
links4.new(emission.outputs["Emission"], mix.inputs[2])
links4.new(mix.outputs["Shader"], output4.inputs["Surface"])
print(f"  连接: BSDF -> Mix.Shader1")
print(f"  连接: Emission -> Mix.Shader2")
print(f"  连接: Mix.Shader -> Output.Surface")

results["materials"].append({
    "name": mat4.name,
    "type": "emission_mix",
    "nodes": ["BSDF", "Emission", "Mix", "Output"],
    "connections": 3,
})

# 创建第四个对象
bpy.ops.mesh.primitive_torus_add(location=(5, 5, 0))
torus = bpy.context.active_object
torus.name = "EmissionTestTorus"
torus.data.materials.append(mat4)

for conn in [
    ("BSDF", "BSDF", "Mix", "Shader 1"),
    ("Emission", "Emission", "Mix", "Shader 2"),
    ("Mix", "Shader", "Output", "Surface"),
]:
    results["connections"].append({
        "material": mat4.name,
        "from_node": conn[0],
        "from_socket": conn[1],
        "to_node": conn[2],
        "to_socket": conn[3],
    })

# =====================
# 验证
# =====================
print("\n" + "=" * 60)
print("验证步骤:")
print("=" * 60)

# 验证 1: bpy.data.materials
all_mat_names = [m.name for m in bpy.data.materials]
print(f"\nbpy.data.materials 总数: {len(bpy.data.materials)}")
print(f"材质列表: {all_mat_names}")

required_mats = ["BasicPrincipled", "TextureMaterial", "NormalRampMaterial", "EmissionMaterial"]
missing_mats = [name for name in required_mats if name not in all_mat_names]
if missing_mats:
    print(f"  [FAIL] 缺失材质: {missing_mats}")
    results["verification"] = {"status": "FAIL", "missing": missing_mats}
else:
    print(f"  [PASS] 所有预期材质存在")

# 验证 2: 节点连接
all_valid = True
for mat_name in required_mats:
    mat = bpy.data.materials[mat_name]
    if not mat.use_nodes:
        print(f"  [FAIL] {mat_name} 未启用节点")
        all_valid = False
        continue
    
    tree = mat.node_tree
    if not tree:
        print(f"  [FAIL] {mat_name} 无 node_tree")
        all_valid = False
        continue
    
    node_count = len(tree.nodes)
    link_count = len(tree.links)
    print(f"  {mat_name}: {node_count} 节点, {link_count} 连接")
    
    if node_count < 2 or link_count < 1:
        print(f"    [FAIL] 节点或连接数不足")
        all_valid = False

# 验证 3: 节点类型存在
print(f"\n节点类型验证:")
bsdf_found = False
tex_found = False
normal_found = False
emission_found = False
color_ramp_found = False

for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            bsdf_found = True
        if node.type == "TEX_IMAGE":
            tex_found = True
        if node.type == "NORMAL_MAP":
            normal_found = True
        if node.type == "EMISSION":
            emission_found = True
        if node.type == "VALTORGB":
            color_ramp_found = True

for name, found in [
    ("Principled BSDF", bsdf_found),
    ("Image Texture", tex_found),
    ("Normal Map", normal_found),
    ("Emission", emission_found),
    ("Color Ramp", color_ramp_found),
]:
    if found:
        print(f"  [PASS] {name} 节点存在")
    else:
        print(f"  [FAIL] {name} 节点缺失")
        all_valid = False

# 验证 4: 材质分配到对象
print(f"\n材质分配验证:")
for obj_mat in [cube, sphere, cylinder, torus]:
    if obj_mat.data.materials and obj_mat.data.materials[0]:
        print(f"  [PASS] {obj_mat.name} 分配了材质: {obj_mat.data.materials[0].name}")
    else:
        print(f"  [FAIL] {obj_mat.name} 未分配材质")
        all_valid = False

results["verification"] = {
    "status": "PASS" if all_valid else "FAIL",
    "materials_count": len(bpy.data.materials),
    "objects_with_materials": sum(1 for o in [cube, sphere, cylinder, torus] if o.data.materials),
    "all_nodes_valid": all([bsdf_found, tex_found, normal_found, emission_found, color_ramp_found]),
}

# 保存结果
output_path = output_dir / "test2_material_system.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n结果保存至: {output_path}")

status = results["verification"]["status"]
print(f"\n{'='*60}")
print(f"测试结果: {status}")
print(f"{'='*60}")

if status != "PASS":
    sys.exit(1)
