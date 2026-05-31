"""
阶段1 - 测试4: 真实渲染系统
Blender 5.1.2 真实渲染，验证 Eevee 和 Cycles 引擎。
测试:
- EEVEE 渲染 PNG
- Cycles 渲染 PNG
验证渲染文件真实生成
"""

import bpy
import sys
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


# 确保输出目录存在
output_dir.mkdir(parents=True, exist_ok=True)

print(f"输出目录: {output_dir}")
print(f"Blender 版本: {bpy.app.version_string}")

# 清理场景
bpy.ops.wm.read_factory_settings(use_empty=True)

results = {
    "test": "render_system",
    "blender_version": bpy.app.version_string,
    "renders": [],
    "verification": {},
}

# =====================
# 创建测试场景
# =====================
print("\n创建测试场景...")

# 添加 Cube
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "RenderTestCube"

# 添加 Sphere
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(4, 0, 0))
sphere = bpy.context.active_object
sphere.name = "RenderTestSphere"

# 添加光源
bpy.ops.object.light_add(type="SUN", location=(5, -5, 5))
sun = bpy.context.active_object
sun.name = "TestSun"
sun.data.energy = 5.0

# 添加相机
bpy.ops.object.camera_add(location=(5, -5, 3))
camera = bpy.context.active_object
camera.name = "TestCamera"
camera.data.lens = 50
bpy.context.scene.camera = camera

# 创建简单材质
mat = bpy.data.materials.new(name="TestMat")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()
bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.5, 0.3, 0.8, 1.0)
output = nodes.new(type="ShaderNodeOutputMaterial")
links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

cube.data.materials.append(mat)
sphere.data.materials.append(mat)

print(f"场景: 2 个对象 + 1 光源 + 1 相机")

# =====================
# 渲染1: EEVEE 引擎
# =====================
print("\n" + "=" * 60)
print("[1] EEVEE 渲染测试")
print("=" * 60)

scene = bpy.context.scene
render = scene.render

# 配置 EEVEE
scene.render.engine = "BLENDER_EEVEE"
scene.cycles.device = "CPU"  # headless 模式用 CPU

print(f"引擎: {scene.render.engine}")
print(f"渲染设备: {scene.cycles.device}")

# 设置输出
render.filepath = str(output_dir / "test4_eevee_render.png")
render.image_settings.file_format = "PNG"
render.image_settings.color_mode = "RGBA"
render.image_settings.color_depth = "16"
render.use_compositing = False
render.use_stamp = False

# 设置分辨率
render.resolution_x = 256
render.resolution_y = 256
render.resolution_percentage = 100

# 设置帧
scene.frame_current = 1

# 渲染
print(f"输出: {render.filepath}")
print(f"分辨率: {render.resolution_x}x{render.resolution_y}")

start_time = __import__('time').time()
try:
    bpy.ops.render.render(write_standalone=True, use_viewport=True)
    elapsed = __import__('time').time() - start_time
    print(f"EEVEE 渲染完成: {elapsed:.1f}s")
    
    # 验证文件
    render_path = Path(render.filepath)
    if render_path.exists():
        size = render_path.stat().st_size
        print(f"  [PASS] 文件存在: {render_path} ({size} bytes)")
        results["renders"].append({
            "engine": "EEVEE",
            "filepath": str(render_path),
            "exists": True,
            "size": size,
            "elapsed": elapsed,
        })
    else:
        print(f"  [FAIL] 文件不存在: {render_path}")
        results["renders"].append({
            "engine": "EEVEE",
            "filepath": str(render_path),
            "exists": False,
            "error": "文件未生成",
        })
except Exception as e:
    print(f"  [FAIL] 渲染错误: {e}")
    results["renders"].append({
        "engine": "EEVEE",
        "filepath": str(render_path),
        "exists": False,
        "error": str(e),
    })

# =====================
# 渲染2: Cycles 引擎
# =====================
print("\n" + "=" * 60)
print("[2] Cycles 渲染测试")
print("=" * 60)

# 配置 Cycles
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 64  # 低采样数加速测试
scene.cycles.min_bounces = 0
scene.cycles.max_bounces = 4

print(f"引擎: {scene.render.engine}")
print(f"渲染设备: {scene.cycles.device}")
print(f"采样数: {scene.cycles.samples}")

# 设置输出
render.filepath = str(output_dir / "test4_cycles_render.png")

# 渲染
start_time = __import__('time').time()
try:
    bpy.ops.render.render(write_standalone=True, use_viewport=True)
    elapsed = __import__('time').time() - start_time
    print(f"Cycles 渲染完成: {elapsed:.1f}s")
    
    # 验证文件
    render_path = Path(render.filepath)
    if render_path.exists():
        size = render_path.stat().st_size
        print(f"  [PASS] 文件存在: {render_path} ({size} bytes)")
        results["renders"].append({
            "engine": "Cycles",
            "filepath": str(render_path),
            "exists": True,
            "size": size,
            "elapsed": elapsed,
            "samples": scene.cycles.samples,
        })
    else:
        print(f"  [FAIL] 文件不存在: {render_path}")
        results["renders"].append({
            "engine": "Cycles",
            "filepath": str(render_path),
            "exists": False,
            "error": "文件未生成",
        })
except Exception as e:
    print(f"  [FAIL] 渲染错误: {e}")
    results["renders"].append({
        "engine": "Cycles",
        "filepath": str(render.filepath),
        "exists": False,
        "error": str(e),
    })

# =====================
# 验证
# =====================
print("\n" + "=" * 60)
print("验证步骤:")
print("=" * 60)

all_valid = True
eevee_ok = False
cycles_ok = False

for r in results["renders"]:
    if r["engine"] == "EEVEE":
        if r["exists"]:
            print(f"  [PASS] EEVEE 渲染文件: {r['size']} bytes ({r['elapsed']:.1f}s)")
            eevee_ok = True
        else:
            print(f"  [FAIL] EEVEE 渲染失败: {r.get('error', 'unknown')}")
            all_valid = False
    
    if r["engine"] == "Cycles":
        if r["exists"]:
            print(f"  [PASS] Cycles 渲染文件: {r['size']} bytes ({r['elapsed']:.1f}s)")
            cycles_ok = True
        else:
            print(f"  [FAIL] Cycles 渲染失败: {r.get('error', 'unknown')}")
            all_valid = False

# 验证引擎切换
print(f"\n引擎切换验证:")
if scene.render.engine == "CYCLES":
    print(f"  [PASS] 当前引擎: {scene.render.engine}")
else:
    print(f"  [FAIL] 当前引擎不是 Cycles: {scene.render.engine}")

# 保存结果
output_path = output_dir / "test4_render_system.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n结果保存至: {output_path}")

status = "PASS" if (eevee_ok and cycles_ok) else "FAIL"
results["verification"] = {"status": status, "eevee": eevee_ok, "cycles": cycles_ok}

print(f"\n{'='*60}")
print(f"测试结果: {status}")
print(f"{'='*60}")

if status != "PASS":
    sys.exit(1)
