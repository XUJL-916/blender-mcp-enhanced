"""
Blender-MCP Comprehensive Project Analyzer v2

Scans all src/blender_mcp modules for interface completeness,
dependency analysis, Python compatibility, and redundancy detection.
Produces: blender_mcp_analysis.json, docs/API_DOCUMENTATION.md
"""

import ast
import json
import re
from pathlib import Path
from dataclasses import asdict

ROOT = Path(r"C:\Users\admin\Desktop\WorkSpcae\blender-mcp-main")
SRC = ROOT / "src" / "blender_mcp"


def type_str(node):
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return type_str(node.value) + "." + node.attr
    if isinstance(node, ast.Subscript):
        base = type_str(node.value)
        if isinstance(node.slice, ast.Constant):
            return f"{base}[{node.slice.value}]"
        return f"{base}[...]"
    if isinstance(node, ast.Tuple):
        return ", ".join(type_str(e) for e in node.elts)
    if isinstance(node, ast.BinOp):
        return f"{type_str(node.left)} | {type_str(node.right)}"
    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Dict):
        return "dict"
    if isinstance(node, ast.Call):
        return type_str(node.func) + "()"
    if isinstance(node, ast.Index):
        return type_str(node.value)
    return "unknown"


def analyze_method(node, class_name=None):
    is_async = isinstance(node, ast.AsyncFunctionDef)
    decorators = node.decorator_list
    is_static = any(
        (isinstance(d, ast.Name) and d.id == "staticmethod") or
        (isinstance(d, ast.Attribute) and d.attr == "staticmethod")
        for d in decorators
    )
    is_cm = any(
        (isinstance(d, ast.Name) and d.id == "classmethod") or
        (isinstance(d, ast.Attribute) and d.attr == "classmethod")
        for d in decorators
    )

    params = []
    args = node.args
    all_args = (getattr(args, "posonlyargs", []) or []) + list(args.args)
    defaults = args.defaults or []
    def_offset = len(all_args) - len(defaults) if defaults else len(all_args)

    for i, arg in enumerate(all_args):
        default = None
        if i >= def_offset and (i - def_offset) < len(defaults):
            default = type_str(defaults[i - def_offset])
        params.append({"name": arg.arg, "type_annotation": type_str(arg.annotation), "default": default})

    if args.vararg:
        params.append({"name": "*" + args.vararg.arg, "type_annotation": type_str(args.vararg.annotation), "default": None})
    for a in (args.kwonlyargs or []):
        d = type_str(getattr(a, 'default', None)) if getattr(a, 'default', None) else None
        params.append({"name": a.arg, "type_annotation": type_str(a.annotation), "default": d})
    if args.kwarg:
        params.append({"name": "**" + args.kwarg.arg, "type_annotation": type_str(args.kwarg.annotation), "default": None})

    ds = ast.get_docstring(node)
    doc = ds.split("\n")[0].strip('"\x27') if ds else None

    return {
        "name": node.name,
        "class_name": class_name,
        "params": params,
        "return_annotation": type_str(node.returns),
        "docstring": doc,
        "line_no": node.lineno,
        "is_async": is_async,
        "is_static": is_static,
        "is_classmethod": is_cm,
        "is_decorated": len(decorators) > 0,
    }


def analyze_module(filepath):
    rel = str(Path(filepath).relative_to(ROOT))
    source = filepath.read_text(encoding="utf-8")
    lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return None

    imports = []
    imported_names = {}
    used_names = set()
    classes_info = []
    functions_info = []
    all_methods = []
    missing_docstrings = []
    issues = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imported_names[name] = alias.name
                imports.append({"type": "import", "module": alias.name, "alias": alias.asname, "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                imported_names[name] = f"{mod}.{alias.name}"
                imports.append({"type": "from", "module": mod, "name": alias.name, "alias": alias.asname, "line": node.lineno})

        if isinstance(node, ast.ClassDef):
            attrs = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    attrs.append({"name": item.target.id, "type": type_str(item.annotation)})
                elif isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name):
                            attrs.append({"name": t.id, "type": None})

            cls_methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m = analyze_method(child, node.name)
                    cls_methods.append(m)
                    all_methods.append(m)
                    used_names.add(child.name)
                    if not m["docstring"]:
                        missing_docstrings.append(f"{node.name}.{child.name} (line {child.lineno})")

            ds = ast.get_docstring(node)
            cls_doc = ds.split("\n")[0].strip('"\x27') if ds else None
            if not cls_doc:
                missing_docstrings.append(f"{node.name} (class, line {node.lineno})")

            classes_info.append({
                "name": node.name,
                "bases": [type_str(b) for b in node.bases],
                "attributes": attrs,
                "methods": cls_methods,
                "docstring": cls_doc,
                "line_no": node.lineno,
            })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m = analyze_method(node)
            functions_info.append(m)
            all_methods.append(m)
            used_names.add(node.name)
            if not m["docstring"]:
                missing_docstrings.append(f"{node.name} (function, line {node.lineno})")

    unused = []
    for name, orig in imported_names.items():
        if name.startswith("_"):
            continue
        found = False
        for line in lines:
            s = line.strip()
            if s.startswith("#"):
                continue
            if re.search(r"\b" + re.escape(name) + r"\b", line):
                found = True
                break
        if not found:
            unused.append({"imported": name, "origin": orig})

    if "datetime.utcfromtimestamp" in source:
        issues.append({
            "severity": "WARNING", "category": "Deprecated API",
            "description": "datetime.utcfromtimestamp() deprecated in Python 3.12+",
            "fix": "Use datetime.fromtimestamp(ts, tz=timezone.utc)",
        })

    return {
        "name": Path(filepath).stem,
        "path": rel,
        "total_lines": len(lines),
        "class_count": len(classes_info),
        "function_count": len(functions_info),
        "method_count": len(all_methods),
        "imports": imports,
        "missing_docstrings": missing_docstrings,
        "unused_imports": unused,
        "issues": issues,
        "_classes": classes_info,
    }


def generate_api_docs(modules):
    lines = []
    lines.append("# Blender-MCP API Documentation")
    lines.append("")
    lines.append("> Generated: 2026-06-01 | Version: 1.5.5-enh | Target: Blender 5.1.2 / Python 3.13")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Module Overview")
    lines.append("")
    lines.append("| Module | Lines | Classes | Methods | Functions | Missing Doc | Unused |")
    lines.append("|--------|-------|---------|---------|-----------|-------------|--------|")

    for name in sorted(modules.keys()):
        m = modules[name]
        lines.append(
            f"| {m['name']} | {m['total_lines']} | {m['class_count']} | {m['method_count']} "
            f"| {m['function_count']} | {len(m['missing_docstrings'])} | {len(m['unused_imports'])} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Extract MCP tool registrations from server.py
    lines.append("## MCP Registered Tools")
    lines.append("")
    server_file = SRC / "server.py"
    if server_file.exists():
        src = server_file.read_text(encoding="utf-8")
        tool_pattern = re.findall(r"(?:@server|@mcp|@fastmcp|\.tool)\(\s*\)\s*\ndef\s+(\w+)", src)
        if not tool_pattern:
            # Try alternate patterns
            tool_pattern = re.findall(r"def\s+(\w+)\s*\(", src)
            # Filter to likely tool names
            tool_pattern = [t for t in tool_pattern if t.startswith("tool_") or t.startswith("handle_") or t.startswith("blender_")]
        for tool in tool_pattern:
            lines.append(f"- `{tool}`")
    lines.append("")

    if not tool_pattern:
        lines.append("*Note: Tool registration pattern could not be auto-detected. Check server.py manually.*")
        lines.append("")

    # Classes and Methods
    lines.append("## Classes and Methods")
    lines.append("")

    for name in sorted(modules.keys()):
        m = modules[name]
        for cls in m.get("_classes", []):
            lines.append(f"### `{cls['name']}`")
            lines.append("")
            if cls.get("bases"):
                lines.append(f"**Bases**: {', '.join(cls['bases'])}")
                lines.append("")
            if cls.get("docstring"):
                lines.append(f"**Docstring**: {cls['docstring']}")
                lines.append("")
            if cls.get("attributes"):
                lines.append("**Attributes**:")
                for a in cls["attributes"]:
                    lines.append(f"- `{a['name']}`: {a.get('type', '') or 'Any'}")
                lines.append("")
            if cls.get("methods"):
                lines.append("**Methods**:")
                for meth in cls["methods"]:
                    params = meth.get("params", [])
                    params_str = ", ".join(
                        f"{p['name']}" + (f": {p['type_annotation']}" if p.get("type_annotation") else "") +
                        (f"={p['default']}" if p.get("default") else "")
                        for p in params
                    )
                    ret = meth.get("return_annotation", "")
                    ret_str = f" -> {ret}" if ret else ""
                    extras = []
                    if meth.get("is_async"):
                        extras.append("async")
                    if meth.get("is_static"):
                        extras.append("static")
                    if meth.get("is_classmethod"):
                        extras.append("class")
                    extra_str = f" ({', '.join(extras)})" if extras else ""
                    line_no = meth.get("line_no", "")
                    line_str = f" (line {line_no})" if line_no else ""
                    doc = meth.get("docstring", "")
                    lines.append(f"- `{meth['name']}`({params_str}){ret_str}{extra_str}{line_str}")
                    if doc:
                        lines.append(f"  > {doc}")
                lines.append("")

    # Usage Examples
    lines.append("---")
    lines.append("")
    lines.append("## Usage Examples")
    lines.append("")
    lines.append("### Configuration")
    lines.append("")
    lines.append("```python")
    lines.append("from blender_mcp.config import config")
    lines.append("")
    lines.append("summary = config.summary()")
    lines.append("print(f'Host: {summary[\"connection\"][\"host\"]}:{summary[\"connection\"][\"port\"]}')")
    lines.append("print(f'Hyper3D: {summary[\"api_keys\"][\"hyper3d\"]}')")
    lines.append("print(f'Telemetry: {summary[\"telemetry\"][\"enabled\"]}')")
    lines.append("```")
    lines.append("")
    lines.append("### Connection Management")
    lines.append("")
    lines.append("```python")
    lines.append("from blender_mcp.connection_recovery import create_connection_manager")
    lines.append("")
    lines.append("manager = create_connection_manager()")
    lines.append("health = manager.get_health_status()")
    lines.append("print(f'Status: {health[\"status\"]}, Rate: {health[\"success_rate\"]:.2%}')")
    lines.append("")
    lines.append("result = manager.execute('get_scene_info', {})")
    lines.append("print(f'Scene: {result}')")
    lines.append("```")
    lines.append("")
    lines.append("### Advanced Object Operations (stub)")
    lines.append("")
    lines.append("```python")
    lines.append("from blender_mcp.advanced_objects import AdvancedObjectOperations")
    lines.append("")
    lines.append("ops = AdvancedObjectOperations()")
    lines.append("# Ops methods: create_collection, create_camera, set_render_eevee_default,")
    lines.append("# set_transform, render_viewport, import_gltf, export_fbx,")
    lines.append("# capture_viewport_snapshot, batch_scale, batch_color, etc.")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    modules = {}

    for d in ["src/blender_mcp", "tests", "scripts"]:
        dirpath = ROOT / d
        if not dirpath.exists():
            continue
        for f in sorted(dirpath.glob("*.py")):
            rel = str(f.relative_to(ROOT))
            report = analyze_module(f)
            if report:
                modules[rel] = report

    total_lines = sum(m["total_lines"] for m in modules.values())
    total_methods = sum(m["method_count"] for m in modules.values())
    total_functions = sum(m["function_count"] for m in modules.values())
    total_classes = sum(m["class_count"] for m in modules.values())
    total_missing_docs = sum(len(m["missing_docstrings"]) for m in modules.values())
    total_unused = sum(len(m["unused_imports"]) for m in modules.values())
    all_issues = []
    for m in modules.values():
        all_issues.extend(m["issues"])

    print("=" * 72)
    print("  Blender-MCP Comprehensive Project Analysis")
    print("  Generated: 2026-06-01  |  Target: Blender 5.1.2 / Python 3.13")
    print("=" * 72)
    print()
    print(f"  Source files scanned: {len(modules)}")
    print(f"  Total lines of code: {total_lines}")
    print(f"  Total methods: {total_methods}")
    print(f"  Total functions: {total_functions}")
    print(f"  Total classes: {total_classes}")
    print(f"  Missing docstrings: {total_missing_docs}")
    print(f"  Potential unused imports: {total_unused}")
    print(f"  Analysis issues: {len(all_issues)}")
    print()

    print("  Per-Module Breakdown:")
    print("  " + "-" * 64)
    for name in sorted(modules.keys()):
        m = modules[name]
        print(f"  {m['name']:25s}  lines={m['total_lines']:5d}  classes={m['class_count']}  "
              f"methods={m['method_count']}  funcs={m['function_count']}  "
              f"missing_doc={len(m['missing_docstrings'])}  unused_imports={len(m['unused_imports'])}  "
              f"issues={len(m['issues'])}")

    print()

    if all_issues:
        print("  Issues Found:")
        print("  " + "-" * 52)
        for issue in all_issues:
            print(f"  [{issue['severity']}] {issue['category']}: {issue['description']}")
            if issue.get("fix"):
                print(f"         FIX: {issue['fix']}")
        print()

    # Generate API docs
    api_docs = generate_api_docs(modules)
    api_doc_path = ROOT / "docs" / "API_DOCUMENTATION.md"
    with open(api_doc_path, "w", encoding="utf-8") as f:
        f.write(api_docs)
    print(f"  API documentation saved to: {api_doc_path}")

    # Save analysis JSON
    analysis_data = {
        "generated": "2026-06-01",
        "target": "Blender 5.1.2 / Python 3.13",
        "summary": {
            "total_files": len(modules),
            "total_lines": total_lines,
            "total_methods": total_methods,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "missing_docstrings": total_missing_docs,
            "unused_imports": total_unused,
            "issues_count": len(all_issues),
        },
        "modules": {},
        "issues": all_issues,
    }

    for name, m in sorted(modules.items()):
        analysis_data["modules"][name] = {
            "name": m["name"],
            "path": m["path"],
            "total_lines": m["total_lines"],
            "class_count": m["class_count"],
            "function_count": m["function_count"],
            "method_count": m["method_count"],
            "missing_docstrings": len(m["missing_docstrings"]),
            "unused_imports": len(m["unused_imports"]),
            "issues": len(m["issues"]),
        }

    analysis_path = ROOT / "blender_mcp_analysis.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)
    print(f"  Analysis JSON saved to: {analysis_path}")

    print()
    print("=" * 72)
    print("  Analysis complete!")
    print("=" * 72)


if __name__ == "__main__":
    main()
