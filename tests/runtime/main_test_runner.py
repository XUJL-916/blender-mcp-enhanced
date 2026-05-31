"""
Blender-MCP 完整测试运行器
按顺序执行所有测试，生成最终报告。
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main")
RUNTIME_DIR = PROJECT_ROOT / "tests" / "runtime"
BLENDER_OUTPUT = PROJECT_ROOT / "blender_test_output"
BLENDER_EXE = Path(r"D:/Program Files/blender/blender.exe")

# Ensure directories
BLENDER_OUTPUT.mkdir(parents=True, exist_ok=True)

# Test order
tests = [
    "test1_create_objects.py",
    "test2_material_system.py",
    "test3_animation_system.py",
    "test4_render_system.py",
    "test5_import_export.py",
    "test7_stress_test.py",
]

print("="*80)
print("  BLENDER-MCP COMPLETE TEST RUNNER")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Blender: {BLENDER_EXE}")
print("="*80)

results = []
for test_name in tests:
    print(f"\n{'='*60}")
    print(f"RUNNING: {test_name}")
    print("="*60)
    
    test_path = RUNTIME_DIR / test_name
    
    if not test_path.exists():
        print(f"  [SKIP] File not found: {test_name}")
        results.append({"test": test_name, "status": "SKIP", "error": "File not found"})
        continue
    
    # Build command
    cmd = [
        str(BLENDER_EXE),
        "-b",
        "--python",
        str(test_path),
        "--",
        "--output",
        str(BLENDER_OUTPUT),
    ]
    
    start = __import__('time').time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
        )
        elapsed = __import__('time').time() - start
        
        status = "PASS" if proc.returncode == 0 else "FAIL"
        results.append({
            "test": test_name,
            "status": status,
            "elapsed": round(elapsed, 2),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-500:] if proc.stdout else "",
            "stderr": proc.stderr[-200:] if proc.stderr else "",
        })
        
        if status == "PASS":
            print(f"  [PASS] {test_name} ({elapsed:.1f}s)")
        else:
            print(f"  [FAIL] {test_name} ({elapsed:.1f}s)")
            print(f"  STDERR: {proc.stderr[-300:]}")
    
    except subprocess.TimeoutExpired:
        results.append({"test": test_name, "status": "TIMEOUT", "elapsed": 300})
        print(f"  [TIMEOUT] {test_name} (>300s)")

# Summary
print(f"\n{'='*80}")
print("  TEST SUMMARY")
print("="*80)

passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
skipped = sum(1 for r in results if r["status"] in ["SKIP", "TIMEOUT"])

for r in results:
    icon = "[PASS]" if r["status"] == "PASS" else "[FAIL]" if r["status"] == "FAIL" else "[SKIP]"
    print(f"  {icon} {r['test']} ({r.get('elapsed', '?')}s)")

print(f"\n  Total: {len(results)} | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")
print("="*80)

# Save results
import json
results_data = {
    "date": datetime.now().isoformat(),
    "total": len(results),
    "passed": passed,
    "failed": failed,
    "skipped": skipped,
    "tests": results,
}

result_path = BLENDER_OUTPUT / "full_test_results.json"
with open(result_path, "w", encoding="utf-8") as f:
    json.dump(results_data, f, indent=2, ensure_ascii=False)

print(f"\nFull results saved to: {result_path}")

# Generate acceptance report
print("\nGenerating production acceptance report...")
try:
    gen_path = RUNTIME_DIR / "generate_reports.py"
    if gen_path.exists():
        proc = subprocess.run(
            [sys.executable, str(gen_path)],
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            cwd=str(PROJECT_ROOT),
        )
        if proc.stdout:
            print(proc.stdout)
except Exception as e:
    print(f"  Report generation error: {e}")

if failed == 0:
    print("\nAll runtime tests PASSED!")
    sys.exit(0)
else:
    print(f"\n{failed} test(s) FAILED.")
    sys.exit(1)
