"""
Phase 4: Regression Test Runner
Runs all runtime tests, detects regressions, generates report.
Designed to run on every commit.
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main")
RUNTIME_DIR = PROJECT_ROOT / "tests" / "runtime"
BLENDER_OUTPUT = PROJECT_ROOT / "blender_test_output"
REPORT_DIR = PROJECT_ROOT / "docs"

# Ensure directories
BLENDER_OUTPUT.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("  BLENDER-MCP REGRESSION TEST SUITE")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Find all test scripts
test_scripts = sorted(RUNTIME_DIR.glob("test_*.py"))
test_scripts = [t for t in test_scripts if t.name != "run_tests.py" and t.name != "test6_mcp_communication.py"]

print(f"\nFound {len(test_scripts)} runtime tests:")
for t in test_scripts:
    print(f"  - {t.name}")

# Run each test
overall_results = []
total_start = time.time()

for test_script in test_scripts:
    print(f"\n{'='*60}")
    print(f"Running: {test_script.name}")
    print("="*60)
    
    cmd = [
        str(PROJECT_ROOT / "blender_test_output" / "blender.exe"),
        "-b",
        "--python",
        str(test_script),
        "--",
        "--output",
        str(BLENDER_OUTPUT),
    ]
    
    # Check if we need to use the actual blender.exe path
    blender_exe = Path(r"D:\Program Files\blender\blender.exe")
    cmd = [
        str(blender_exe),
        "-b",
        "--python",
        str(test_script),
        "--",
        "--output",
        str(BLENDER_OUTPUT),
    ]
    
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - start
        
        # Find JSON result file
        test_name = test_script.stem.replace("test_", "")
        result_json = BLENDER_OUTPUT / f"{test_name}.json"
        
        test_result = {
            "test": test_script.name,
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "returncode": result.returncode,
            "elapsed": round(elapsed, 2),
            "result_json": str(result_json) if result_json.exists() else None,
        }
        
        if result.stdout:
            # Print last 20 lines of output for debugging
            lines = result.stdout.strip().split('\n')
            print('\n'.join(lines[-20:]))
        
        if result.returncode != 0 and result.stderr:
            lines = result.stderr.strip().split('\n')
            print('\n[STDERR]')
            print('\n'.join(lines[-10:]))
        
        overall_results.append(test_result)
        
    except subprocess.TimeoutExpired:
        overall_results.append({
            "test": test_script.name,
            "status": "TIMEOUT",
            "elapsed": 180,
            "error": "Test timed out after 180s",
        })
        print(f"  [TIMEOUT] {test_script.name}")
    except Exception as e:
        overall_results.append({
            "test": test_script.name,
            "status": "ERROR",
            "error": str(e),
        })
        print(f"  [ERROR] {test_script.name}: {e}")

total_elapsed = time.time() - total_start

# Summary
passed = sum(1 for r in overall_results if r["status"] == "PASS")
failed = sum(1 for r in overall_results if r["status"] == "FAIL")
timed_out = sum(1 for r in overall_results if r["status"] == "TIMEOUT")
errors = sum(1 for r in overall_results if r["status"] == "ERROR")

print(f"\n{'='*80}")
print("  REGRESSION TEST SUMMARY")
print("="*80)
print(f"  Total: {len(overall_results)}")
print(f"  PASS:  {passed} ({passed/len(overall_results)*100:.0f}%)")
print(f"  FAIL:  {failed}")
print(f"  TIMEOUT: {timed_out}")
print(f"  ERROR: {errors}")
print(f"  Total time: {total_elapsed:.1f}s")
print("="*80)

# Generate report
report = {
    "test": "regression_suite",
    "date": datetime.now().isoformat(),
    "total": len(overall_results),
    "passed": passed,
    "failed": failed,
    "timed_out": timed_out,
    "errors": errors,
    "total_time_sec": round(total_elapsed, 2),
    "tests": overall_results,
    "pass_rate": round(passed / len(overall_results) * 100, 1) if overall_results else 0,
}

# Save JSON
report_path = REPORT_DIR / "REGRESSION_REPORT.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# Save text summary
summary_path = REPORT_DIR / "REGRESSION_SUMMARY.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write(f"Blender-MCP Regression Test Summary\n")
    f.write(f"Date: {report['date']}\n")
    f.write(f"Total: {report['total']} | PASS: {report['passed']} | FAIL: {report['failed']} | TIMEOUT: {report['timed_out']} | ERROR: {report['errors']}\n")
    f.write(f"Pass Rate: {report['pass_rate']}%\n")
    f.write(f"Total Time: {report['total_time_sec']}s\n\n")
    for t in overall_results:
        status_icon = "[PASS]" if t["status"] == "PASS" else "[FAIL]" if t["status"] == "FAIL" else "[TIMEOUT]" if t["status"] == "TIMEOUT" else "[ERROR]"
        f.write(f"  {status_icon} {t['test']} ({t['elapsed']}s)\n")
        if "error" in t:
            f.write(f"    Error: {t['error']}\n")

print(f"\nJSON report: {report_path}")
print(f"Text summary: {summary_path}")

if failed > 0 or timed_out > 0 or errors > 0:
    sys.exit(1)
