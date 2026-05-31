"""
Phase 3: Stress Test
Create 100/500/1000/5000/10000 objects, measure CPU, memory, response time.
"""

import bpy
import sys
import time
import os
import json
import tracemalloc
from pathlib import Path
from datetime import datetime

# Parse output path (Blender 5.1.2 兼容)
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


output_dir.mkdir(parents=True, exist_ok=True)

print(f"Blender 版本: {bpy.app.version_string}")
print(f"输出目录: {output_dir}")

# Cleanup
bpy.ops.wm.read_factory_settings(use_empty=True)

results = {
    "test": "stress_test",
    "test_date": datetime.now().isoformat(),
    "blender_version": bpy.app.version_string,
    "runs": [],
    "verification": {},
}

# Get initial memory
import ctypes
def get_windows_memory():
    """Get Windows process memory usage"""
    try:
        import ctypes
        class MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_ulonglong),
                ('WorkingSetSize', ctypes.c_ulonglong),
                ('CommitCharge', ctypes.c_ulong),
                ('QuotaPeakPagedPoolUsage', ctypes.c_ulong),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_ulong),
                ('QuotaPeakPagefileUsage', ctypes.c_ulong),
                ('PrivateUsage', ctypes.c_ulong),
            ]
        hprocess = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, os.getpid())
        if not hprocess:
            return None
        mc = MEMORY_COUNTERS()
        ctypes.windll.psapi.GetProcessMemoryInfo(hprocess, ctypes.byref(mc), ctypes.sizeof(mc))
        ctypes.windll.kernel32.CloseHandle(hprocess)
        return {
            "working_set_mb": mc.WorkingSetSize / (1024 * 1024),
            "peak_working_set_mb": mc.PeakWorkingSetSize / (1024 * 1024),
            "private_usage_mb": mc.PrivateUsage / (1024 * 1024),
        }
    except:
        return None

def create_objects(count, obj_type="cube"):
    """Create N objects of given type"""
    start = time.time()
    for i in range(count):
        if obj_type == "cube":
            bpy.ops.mesh.primitive_cube_add(
                size=0.5,
                location=(
                    (i % 10) * 2.0 - 10,
                    (i // 10) * 2.0 - 10,
                    0
                )
            )
            obj = bpy.context.active_object
            obj.name = f"StressCube_{i}"
            # Small random offset to avoid exact duplicates
            obj.location.z += i * 0.001

        elapsed = time.time() - start
        if i % 100 == 0:
            print(f"  Created {i}/{count} objects...")
    
    return time.time() - start

def get_scene_stats():
    """Get current scene statistics"""
    stats = {
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "vertices_total": sum(len(m.vertices) for m in bpy.data.meshes),
        "faces_total": sum(len(m.polygons) for m in bpy.data.meshes),
        "edges_total": sum(len(m.edges) for m in bpy.data.meshes),
    }
    mem = get_windows_memory()
    if mem:
        stats["memory"] = mem
    return stats

# Stress test levels
test_levels = [100, 500, 1000, 5000, 10000]

for level in test_levels:
    print(f"\n{'='*60}")
    print(f"Stress Level: {level} objects")
    print("="*60)
    
    start_time = time.time()
    tracemalloc.start()
    
    # Create objects
    creation_time = create_objects(level)
    
    # Flush BLF cache
    bpy.context.view_layer.update()
    
    elapsed = time.time() - start_time
    
    # Memory
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Scene stats
    stats = get_scene_stats()
    stats["memory_traced_mb"] = {
        "current": current / (1024 * 1024),
        "peak": peak / (1024 * 1024),
    }
    
    # Per-object metrics
    metrics = {
        "objects": level,
        "creation_time_sec": round(creation_time, 2),
        "total_time_sec": round(elapsed, 2),
        "objects_per_sec": round(level / creation_time) if creation_time > 0 else 0,
        "total_vertices": stats["vertices_total"],
        "total_faces": stats["faces_total"],
        "total_edges": stats["edges_total"],
        "traced_memory_mb": round(stats["memory_traced_mb"]["peak"], 2),
        "memory_per_object_kb": round(
            (stats["memory_traced_mb"]["peak"] * 1024) / level, 2
        ) if level > 0 else 0,
    }
    
    if stats.get("memory"):
        metrics["working_set_mb"] = round(stats["memory"]["working_set_mb"], 2)
        metrics["peak_working_set_mb"] = round(stats["memory"]["peak_working_set_mb"], 2)
    
    results["runs"].append({
        "level": level,
        "metrics": metrics,
        "scene_stats": stats,
    })
    
    print(f"  Created: {level} objects in {creation_time:.1f}s")
    print(f"  Rate: {metrics['objects_per_sec']} objects/sec")
    print(f"  Total time: {elapsed:.1f}s")
    print(f"  Vertices: {stats['vertices_total']:,}")
    print(f"  Faces: {stats['faces_total']:,}")
    print(f"  Traced peak: {metrics['traced_memory_mb']} MB")
    if "working_set_mb" in metrics:
        print(f"  Working set: {metrics['working_set_mb']} MB")
    
    # Clear objects for next level
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)

# Final summary
print(f"\n{'='*80}")
print("  STRESS TEST SUMMARY")
print("="*80)
print(f"  {'Count':>8} {'Time(s)':>8} {'Rate(obj/s)':>12} {'Vert':>10} {'Faces':>10} {'Mem(MB)':>8}")
print(f"  {'-'*8} {'-'*8} {'-'*12} {'-'*10} {'-'*10} {'-'*8}")
for run in results["runs"]:
    m = run["metrics"]
    print(f"  {m['objects']:>8,} {m['total_time_sec']:>8.1f} {m['objects_per_sec']:>12,} "
          f"{m['total_vertices']:>10,} {m['total_faces']:>10,} {m['traced_memory_mb']:>8.1f}")

# Verify stability
all_ok = True
for run in results["runs"]:
    if run["metrics"]["total_time_sec"] == 0:
        all_ok = False
        print(f"\n  [FAIL] {run['metrics']['objects']} objects: zero time")

results["verification"] = {
    "status": "PASS" if all_ok else "FAIL",
    "max_level": max(r["metrics"]["objects"] for r in results["runs"]),
    "best_rate": max(r["metrics"]["objects_per_sec"] for r in results["runs"]),
    "peak_memory_mb": max(r["metrics"]["traced_memory_mb"] for r in results["runs"]),
}

# Save
result_path = output_dir / "test7_stress_test.json"
with open(result_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nResults saved to: {result_path}")

if results["verification"]["status"] != "PASS":
    sys.exit(1)
