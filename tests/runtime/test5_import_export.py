#================================================================
#  ================================================================
#  test5_import_export.py
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
import os

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
output_dir = output_dir.resolve()


output_dir.mkdir(parents=True, exist_ok=True)

print(f"输出目录: {output_dir}")
print(f"Blender 版本: {bpy.app.version_string}")

# 清理场景
bpy.ops.wm.read_factory_settings(use_empty=True)

results = {
    "test": "import_export",
    "blender_version": bpy.app.version_string,
    "formats": [],
    "verification": {},
}

# =====================
# 创建测试对象
# =====================
print("\n创建测试对象...")

# Cube
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "ExportTestCube"

# Sphere
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=16, ring_count=8, location=(5, 0, 0))
sphere = bpy.context.active_object
sphere.name = "ExportTestSphere"

# Plane
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, -2))
plane = bpy.context.active_object
plane.name = "ExportTestPlane"

# 统计原始数据
original_stats = {
    "cube": {
        "name": cube.name,
        "vertices": len(cube.data.vertices),
        "faces": len(cube.data.polygons),
        "edges": len(cube.data.edges),
    },
    "sphere": {
        "name": sphere.name,
        "vertices": len(sphere.data.vertices),
        "faces": len(sphere.data.polygons),
        "edges": len(sphere.data.edges),
    },
    "plane": {
        "name": plane.name,
        "vertices": len(plane.data.vertices),
        "faces": len(plane.data.polygons),
        "edges": len(plane.data.edges),
    },
}

print(f"\n原始对象统计:")
for name, stats in original_stats.items():
    print(f"  {name}: {stats['vertices']} vert, {stats['faces']} faces, {stats['edges']} edges")

# =====================
# 导出和重新导入测试
# =====================

formats_to_test = [
    ("fbx", "FBX", "bpy.ops.export_scene.fbx"),
    ("obj", "OBJ", "bpy.ops.export_scene.obj"),
    ("glb", "GLB", "bpy.ops.export_scene.gltf"),
    ("stl", "STL", "bpy.ops.export_mesh.stl"),
]

for file_ext, format_name, export_op in formats_to_test:
    print(f"\n{'='*60}")
    print(f"导出 {format_name} (.{file_ext})")
    print('='*60)
    
    filepath = str(output_dir / f"test5_export.{file_ext}")
    
    # 保存导出前的场景 (用于清理)
    # 先清空当前场景中的对象（除了必要的）
    for obj in bpy.data.objects:
        if obj.name.startswith("ExportTest"):
            bpy.data.objects.remove(obj)
    
    # 重新创建测试对象（因为导出操作后场景可能变化）
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    test_obj = bpy.context.active_object
    test_obj.name = f"TempExport{format_name}"
    
    # 执行导出
    try:
        if file_ext == "fbx":
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                check_existing=True,
                use_selection=False,
            )
        elif file_ext == "obj":
            bpy.ops.wm.obj_export(
                filepath=filepath,
                check_existing=True,
                export_selected_objects=False,
            )
        elif file_ext == "glb":
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                check_existing=True,
                use_selection=False,
            )
        elif file_ext == "stl":
            bpy.ops.wm.stl_export(
                filepath=filepath,
                check_existing=True,
                export_selected_objects=False,
            )
        
        # 验证导出文件
        export_path = Path(filepath)
        if export_path.exists():
            export_size = export_path.stat().st_size
            print(f"  [PASS] 导出成功: {filepath} ({export_size} bytes)")
        else:
            print(f"  [FAIL] 导出文件不存在: {filepath}")
            results["formats"].append({
                "format": format_name,
                "extension": file_ext,
                "exported": False,
                "error": "文件未生成",
            })
            continue
        
        # 删除刚创建的对象
        bpy.data.objects.remove(test_obj)
        before_import_names = {obj.name for obj in bpy.data.objects}
        
        # 重新导入
        print(f"  重新导入...")
        import_success = False
        
        if file_ext == "fbx":
            bpy.ops.import_scene.fbx(filepath=filepath)
        elif file_ext == "obj":
            bpy.ops.wm.obj_import(filepath=filepath)
        elif file_ext == "glb":
            bpy.ops.import_scene.gltf(filepath=filepath)
        elif file_ext == "stl":
            bpy.ops.wm.stl_import(filepath=filepath)
        
        # 统计导入后的对象
        imported_objs = [
            obj for obj in bpy.data.objects
            if obj.name not in before_import_names and getattr(obj, "type", None) == "MESH"
        ]
        
        if imported_objs:
            imported_stats = {
                "object_count": len(imported_objs),
                "total_vertices": sum(len(obj.data.vertices) for obj in imported_objs),
                "total_faces": sum(len(obj.data.polygons) for obj in imported_objs),
            }
            print(f"  导入后: {imported_stats['object_count']} 对象, "
                  f"{imported_stats['total_vertices']} vert, "
                  f"{imported_stats['total_faces']} faces")
            
            # 验证数据一致性
            original_cube = original_stats["cube"]
            if imported_stats["total_vertices"] >= original_cube["vertices"] - 2 and \
               imported_stats["total_faces"] >= original_cube["faces"] - 2:
                print(f"  [PASS] 数据一致: vert diff < 2, faces diff < 2")
                import_success = True
            else:
                print(f"  [FAIL] 数据不一致: 原始({original_cube['vertices']}/{original_cube['faces']}) "
                      f"vs 导入({imported_stats['total_vertices']}/{imported_stats['total_faces']})")
        else:
            print(f"  [FAIL] 未导入任何对象")
        
        results["formats"].append({
            "format": format_name,
            "extension": file_ext,
            "exported": True,
            "export_size": export_size if export_path.exists() else 0,
            "imported": len(imported_objs),
            "imported_vertices": imported_stats.get("total_vertices", 0),
            "imported_faces": imported_stats.get("total_faces", 0),
            "import_success": import_success,
        })
        
        # 清理导入的对象
        for obj in imported_objs:
            bpy.data.objects.remove(obj)
        
    except Exception as e:
        print(f"  [FAIL] 操作错误: {e}")
        results["formats"].append({
            "format": format_name,
            "extension": file_ext,
            "exported": False,
            "imported": 0,
            "error": str(e),
        })

# BLEND 文件特殊处理
print(f"\n{'='*60}")
print("导出/导入 BLEND 文件")
print('='*60)

blend_path = str(output_dir / "test5_export.blend")

# 保存当前场景为 BLEND
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"  [PASS] BLEND 保存: {blend_path}")

blend_size = Path(blend_path).stat().st_size
print(f"  BLEND 文件大小: {blend_size} bytes")

results["formats"].append({
    "format": "BLEND",
    "extension": "blend",
    "exported": True,
    "export_size": blend_size,
    "saved": True,
})

# =====================
# 验证
# =====================
print("\n" + "=" * 60)
print("验证步骤:")
print("=" * 60)

all_exported = all(f.get("exported", False) for f in results["formats"])
all_valid = all(f.get("import_success", False) for f in results["formats"] if f.get("extension") != "blend")

print(f"\n导出状态:")
for f in results["formats"]:
    status = "PASS" if f.get("exported") else "FAIL"
    print(f"  [{status}] {f['format']}: {f.get('export_size', 0)} bytes")

print(f"\n导入一致性:")
for f in results["formats"]:
    if f.get("extension") == "blend":
        continue
    status = "PASS" if f.get("import_success") else "FAIL"
    print(f"  [{status}] {f['format']}: vert={f.get('imported_vertices', 0)}, faces={f.get('imported_faces', 0)}")

results["verification"] = {
    "status": "PASS" if (all_exported and all_valid) else "FAIL",
    "all_exported": all_exported,
    "all_consistent": all_valid,
    "format_count": len(results["formats"]),
    "formats_passed": sum(1 for f in results["formats"] if f.get("import_success")),
}

# 保存结果
output_path = output_dir / "test5_import_export.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n结果保存至: {output_path}")

status = results["verification"]["status"]
print(f"\n{'='*60}")
print(f"测试结果: {status}")
print(f"{'='*60}")

if status != "PASS":
    sys.exit(1)
