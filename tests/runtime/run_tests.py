#================================================================
#  ================================================================
#  run_tests.py
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

# Blender-MCP 真实运行时测试基础设施
# Blender 5.1.2 + bpy 真实执行 + MCP 通信端到端

import os
import subprocess
import sys
import json
import time
import shutil
from pathlib import Path
from datetime import datetime

# Blender 路径
BLENDER_EXE = Path(r"D:/Program Files/blender/blender.exe")
BLENDER_PYTHON = Path(r"D:/Program Files/blender/5.1/python/bin/python.exe")
PROJECT_ROOT = Path(r"C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main")
TESTS_DIR = PROJECT_ROOT / "tests"
RUNTIME_DIR = TESTS_DIR / "runtime"
BLENDER_OUTPUT = PROJECT_ROOT / "blender_test_output"

# 确保目录存在
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
BLENDER_OUTPUT.mkdir(parents=True, exist_ok=True)


def run_blender_script(script_path, extra_args=None):
    """用 Blender headless 模式运行真实 bpy 脚本"""
    cmd = [
        str(BLENDER_EXE),
        "-b",
        "--python",
        str(script_path),
        "--",
        "--output",
        str(BLENDER_OUTPUT),
    ]
    if extra_args:
        cmd.extend(extra_args)
    
    print(f"\n{'='*60}")
    print(f"运行 Blender 真实测试: {script_path.name}")
    print(f"{'='*60}")
    
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - start
        
        print(f"返回码: {result.returncode}")
        print(f"耗时: {elapsed:.1f}s")
        
        if result.stdout:
            print("\n[STDOUT]")
            print(result.stdout)
        if result.stderr:
            print("\n[STDERR]")
            print(result.stderr)
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "elapsed": elapsed,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "error": "超时 (120s)", "elapsed": 120, "success": False}
    except Exception as e:
        return {"returncode": -1, "error": str(e), "success": False}


def main():
    results = {
        "project": "blender-mcp",
        "version": "1.5.5-enh",
        "blender_version": "5.1.2",
        "test_date": datetime.now().isoformat(),
        "blender_exe": str(BLENDER_EXE),
        "python_version": "3.13",
        "test_files": [],
        "overall": {"total": 0, "passed": 0, "failed": 0},
    }
    
    # =====================
    # 第一阶段: Blender Runtime 测试
    # =====================
    print("\n\n" + "=" * 80)
    print("  BLENDER-MCP REAL RUNTIME TESTS")
    print(f"  Blender 5.1.2 + bpy 真实执行 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    test_files = list(RUNTIME_DIR.glob("test_*.py"))
    test_files.sort()
    
    for test_file in test_files:
        r = run_blender_script(test_file)
        test_result = {
            "file": test_file.name,
            "success": r["success"],
            "returncode": r["returncode"],
            "elapsed": round(r["elapsed"], 2),
            "output": r.get("stdout", "")[-500:],  # 最后500字符
        }
        if r.get("error"):
            test_result["error"] = r["error"]
        
        results["test_files"].append(test_result)
        results["overall"]["total"] += 1
        if r["success"]:
            results["overall"]["passed"] += 1
            print(f"\n  [PASS] {test_file.name} ({test_result['elapsed']}s)")
        else:
            results["overall"]["failed"] += 1
            print(f"\n  [FAIL] {test_file.name} (returncode={r['returncode']})")
    
    # 保存结果
    result_path = RUNTIME_DIR / "test_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 汇总
    o = results["overall"]
    print("\n\n" + "=" * 80)
    print(f"  总计: {o['total']} | 通过: {o['passed']} | 失败: {o['failed']}")
    print("=" * 80)
    
    return o["failed"] == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
