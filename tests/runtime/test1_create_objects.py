"""
阶段1 - 测试1: 真实对象创建
Blender 5.1.2 真实 bpy 操作，不 mock 任何内容。

测试:
- 创建 Cube
- 创建 Sphere
- 创建 Collection
- 创建 Parent 关系
验证 bpy.data.objects 真实存在
"""

import bpy
import sys
import os
import json
from pathlib import Path

# 解析命令行参数 (Blender 5.1.2 兼容)
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

# =====================
# 测试: 创建对象
# =====================
results = {
    "test": "create_objects",
    "blender_version": bpy.app.version_string,
    "objects": [],
    "collections": [],
    "relationships": [],
}

# 1. 创建 Cube
print("\n[1] 创建 Cube...")
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "TestCube"
cube.data.name = "TestCubeMesh"
print(f"  Cube 创建: name={cube.name}, type={cube.type}, location={tuple(cube.location)}")
results["objects"].append({
    "name": cube.name,
    "type": cube.type,
    "location": tuple(cube.location),
    "rotation": tuple(cube.rotation_euler),
    "scale": tuple(cube.scale),
    "dimensions": tuple(cube.dimensions),
})

# 2. 创建 Sphere
print("\n[2] 创建 Sphere...")
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, location=(5, 0, 0))
sphere = bpy.context.active_object
sphere.name = "TestSphere"
sphere.data.name = "TestSphereMesh"
print(f"  Sphere 创建: name={sphere.name}, type={sphere.type}, radius=1.5")
results["objects"].append({
    "name": sphere.name,
    "type": sphere.type,
    "location": tuple(sphere.location),
    "dimensions": tuple(sphere.dimensions),
    "mesh_vertices": len(sphere.data.vertices),
    "mesh_faces": len(sphere.data.polygons),
})

# 3. 创建 Cylinder
print("\n[3] 创建 Cylinder...")
# Blender 5.1.2: 'height' deprecated, use 'depth'
cylinder_args = {"radius": 1, "location": (0, 5, 0)}
if bpy.app.version >= (5, 0, 0):
    cylinder_args["depth"] = 3
else:
    cylinder_args["height"] = 3
bpy.ops.mesh.primitive_cylinder_add(**cylinder_args)
cylinder = bpy.context.active_object
cylinder.name = "TestCylinder"
print(f"  Cylinder 创建: name={cylinder.name}")
results["objects"].append({
    "name": cylinder.name,
    "type": cylinder.type,
    "location": tuple(cylinder.location),
})

# 4. 创建 Plane（必须在 Collection 循环之前创建）
print("\n[4] 创建 Plane...")
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, -2))
plane = bpy.context.active_object
plane.name = "TestPlane"

# 5. 创建 Collection
print("\n[5] 创建 Collection...")
collection = bpy.data.collections.new("TestCollection")
bpy.context.scene.collection.children.link(collection)
print(f"  Collection 创建: name={collection.name}")
results["collections"].append(collection.name)

# 将对象添加到 Collection
for obj in [cube, sphere, cylinder, plane]:
    if obj.name in collection.objects:
        collection.objects.unlink(obj)
    collection.objects.link(obj)
    print(f"  添加 {obj.name} 到 {collection.name}")

results["collections"].append({
    "name": collection.name,
    "objects": [obj.name for obj in collection.objects],
    "object_count": len(collection.objects),
})

# 5. 创建 Parent 关系
print("\n[5] 创建 Parent 关系...")
bpy.context.view_layer.objects.active = sphere
bpy.ops.object.select_all(action="DESELECT")
sphere.select_set(True)
cube.select_set(True)
bpy.context.view_layer.objects.active = cube
bpy.ops.object.parent_set(type="OBJECT")
sphere.parent = cube
print(f"  Sphere 父级: {sphere.parent.name if sphere.parent else 'None'}")
print(f"  Cube 子级: {[c.name for c in cube.children]}")
results["relationships"].append({
    "child": sphere.name,
    "parent": cube.name,
    "parent_type": sphere.parent_type,
})

# Cube -> Plane parent 关系
plane.parent = cube
print(f"  Plane 父级: {plane.parent.name}")
results["relationships"].append({
    "child": plane.name,
    "parent": cube.name,
    "parent_type": plane.parent_type,
})

# =====================
# 验证
# =====================
print("\n" + "=" * 60)
print("验证步骤:")
print("=" * 60)

# 验证 1: bpy.data.objects 包含所有创建的对象
all_obj_names = [obj.name for obj in bpy.data.objects]
print(f"\nbpy.data.objects 总数: {len(bpy.data.objects)}")
print(f"对象列表: {all_obj_names}")

required_objects = ["TestCube", "TestSphere", "TestCylinder", "TestPlane"]
missing = [name for name in required_objects if name not in all_obj_names]
if missing:
    print(f"  [FAIL] 缺失对象: {missing}")
    results["verification"] = {"status": "FAIL", "missing": missing}
else:
    print(f"  [PASS] 所有预期对象存在于 bpy.data.objects")
    results["verification"] = {"status": "PASS", "verified": required_objects}

# 验证 2: Collection 包含所有对象
print(f"\nTestCollection 对象: {[o.name for o in collection.objects]}")
col_obj_names = [o.name for o in collection.objects]
for obj_name in required_objects:
    if obj_name in col_obj_names:
        print(f"  [PASS] {obj_name} 在 TestCollection 中")
    else:
        print(f"  [FAIL] {obj_name} 不在 TestCollection 中")

# 验证 3: Parent 关系
print(f"\nParent 关系验证:")
for rel in results["relationships"]:
    child_obj = bpy.data.objects[rel["child"]]
    if child_obj.parent and child_obj.parent.name == rel["parent"]:
        print(f"  [PASS] {rel['child']} -> {rel['parent']}")
    else:
        print(f"  [FAIL] {rel['child']} parent != {rel['parent']}")

# 保存结果
output_path = output_dir / "test1_create_objects.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n结果保存至: {output_path}")

# 输出总结
status = results["verification"]["status"]
print(f"\n{'='*60}")
print(f"测试结果: {status}")
print(f"{'='*60}")

# 如果不是 pass，设置 exit code
if status != "PASS":
    sys.exit(1)
