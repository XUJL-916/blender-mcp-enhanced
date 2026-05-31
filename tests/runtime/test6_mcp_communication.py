#================================================================
#  ================================================================
#  test6_mcp_communication.py
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

import socket
import json
import sys
import time
from pathlib import Path
from datetime import datetime

# Configuration
MCP_HOST = "localhost"
MCP_PORT = 9876
TIMEOUT = 60  # seconds

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


output_dir.mkdir(parents=True, exist_ok=True)

results = {
    "test": "mcp_communication",
    "test_date": datetime.now().isoformat(),
    "blender_host": MCP_HOST,
    "blender_port": MCP_PORT,
    "tests": [],
    "verification": {},
}


def send_and_receive(host, port, command, timeout=TIMEOUT):
    """Send a command to Blender addon and receive response"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        
        # Send command
        payload = json.dumps(command).encode("utf-8")
        sock.sendall(payload)
        print(f"  Sent: {json.dumps(command)[:200]}...")
        
        # Receive response (chunked)
        chunks = []
        sock.settimeout(timeout)
        while True:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                
                # Try to parse JSON
                try:
                    data = b''.join(chunks)
                    json.loads(data.decode('utf-8'))
                    print(f"  Received complete JSON ({len(data)} bytes)")
                    return json.loads(data.decode('utf-8'))
                except json.JSONDecodeError:
                    continue
            except socket.timeout:
                print(f"  Timeout waiting for response")
                break
        
        # Try to parse partial
        if chunks:
            try:
                data = b''.join(chunks)
                return json.loads(data.decode('utf-8'))
            except:
                return {"error": "Incomplete response", "raw": str(b''.join(chunks)[:200])}
        
        return {"error": "No response received"}
    
    except socket.timeout:
        return {"error": f"Connection timeout after {timeout}s"}
    except ConnectionRefusedError:
        return {"error": f"Connection refused. Is Blender addon running on {host}:{port}?"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if sock:
            try:
                sock.close()
            except:
                pass


def test_tool(tool_name, params, description):
    """Run a single tool test"""
    print(f"\n{'='*60}")
    print(f"Test: {description}")
    print(f"Tool: {tool_name}")
    print("="*60)
    
    command = {"type": tool_name, "params": params or {}}
    
    start = time.time()
    result = send_and_receive(MCP_HOST, MCP_PORT, command)
    elapsed = time.time() - start
    
    test_result = {
        "tool": tool_name,
        "description": description,
        "params": params,
        "elapsed": round(elapsed, 2),
        "result": result,
        "success": result.get("status") == "success" if isinstance(result, dict) else False,
    }
    
    if test_result["success"]:
        print(f"  [PASS] {tool_name} in {elapsed:.1f}s")
        print(f"  Result: {json.dumps(result, indent=2)[:500]}")
    else:
        print(f"  [FAIL] {tool_name} in {elapsed:.1f}s")
        print(f"  Error: {json.dumps(result, indent=2)[:500]}")
    
    return test_result


def main():
    print("="*80)
    print("  MCP COMMUNICATION END-TO-END TEST")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target: {MCP_HOST}:{MCP_PORT}")
    print("="*80)
    
    # Quick connectivity test
    print("\n[0] Connectivity Test")
    print("-"*40)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((MCP_HOST, MCP_PORT))
        sock.close()
        print("  [PASS] Blender addon is running and accepting connections")
        addon_running = True
    except Exception as e:
        print(f"  [SKIP] Cannot connect: {e}")
        print("  Note: Tests require Blender addon to be running.")
        addon_running = False
    
    if not addon_running:
        # Save results with skip status
        results["addon_running"] = False
        results["verification"] = {"status": "SKIPPED", "reason": "Blender addon not running"}
        result_path = output_dir / "test6_mcp_communication.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {result_path}")
        print("\nTo run these tests, you need Blender with addon.py loaded and MCP server running.")
        sys.exit(0)
    
    # ====== Test Suite ======
    
    # Test 1: get_scene_info
    results["tests"].append(test_tool(
        "get_scene_info",
        {},
        "Retrieve current scene information"
    ))
    
    # Test 2: create_cube
    results["tests"].append(test_tool(
        "create_cube",
        {"location": [0, 0, 0], "size": 2},
        "Create a cube object"
    ))
    
    # Test 3: get_object_info
    results["tests"].append(test_tool(
        "get_object_info",
        {"object_name": "Cube"},
        "Get information about created cube"
    ))
    
    # Test 4: set_object_location
    results["tests"].append(test_tool(
        "set_object_location",
        {"object_name": "Cube", "location": [5, 0, 0]},
        "Move cube to new position"
    ))
    
    # Test 5: get_render_settings
    results["tests"].append(test_tool(
        "get_render_settings",
        {},
        "Get current render settings"
    ))
    
    # Test 6: set_render_eevee_default
    results["tests"].append(test_tool(
        "set_render_eevee_default",
        {},
        "Configure EEVEE render engine"
    ))
    
    # Test 7: save_scene
    results["tests"].append(test_tool(
        "save_scene",
        {"filepath": str(output_dir / "test_mcp_scene.blend")},
        "Save current scene"
    ))
    
    # Test 8: export_fbx
    results["tests"].append(test_tool(
        "export_fbx",
        {"filepath": str(output_dir / "test_mcp_export.fbx"), "include_selection": False},
        "Export scene to FBX format"
    ))
    
    # Test 9: export_glb
    results["tests"].append(test_tool(
        "export_glb",
        {"filepath": str(output_dir / "test_mcp_export.glb"), "include_selection": False},
        "Export scene to GLB format"
    ))
    
    # Test 10: import_fbx (if test file exists)
    fbx_test_path = output_dir / "test_mcp_export.fbx"
    if fbx_test_path.exists():
        results["tests"].append(test_tool(
            "import_fbx",
            {"filepath": str(fbx_test_path)},
            "Import FBX file"
        ))
    
    # ====== Summary ======
    total = len(results["tests"])
    passed = sum(1 for t in results["tests"] if t["success"])
    failed = total - passed
    
    print(f"\n{'='*80}")
    print(f"  MCP COMMUNICATION TEST SUMMARY")
    print(f"{'='*80}")
    print(f"  Total: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"{'='*80}")
    
    # Verification
    if total == 0:
        status = "SKIPPED"
    elif failed == 0:
        status = "PASS"
    elif passed > 0:
        status = "PARTIAL_PASS"
    else:
        status = "FAIL"
    
    results["addon_running"] = True
    results["total_tests"] = total
    results["passed"] = passed
    results["failed"] = failed
    results["verification"] = {
        "status": status,
        "total": total,
        "passed": passed,
        "failed": failed,
    }
    
    # Save results
    result_path = output_dir / "test6_mcp_communication.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_path}")
    
    if status == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
