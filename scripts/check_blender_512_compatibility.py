#================================================================
#  ================================================================
#  check_blender_512_compatibility.py
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

import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class Issue:
    severity: str
    category: str
    file: str
    line: int
    code: str
    description: str
    fix: str = ""
    blender_5x_note: str = ""


@dataclass
class CompatReport:
    issues: List[Issue] = field(default_factory=list)

    def add(self, *, severity, category, file, line, code, description, fix="", blender_5x_note=""):
        self.issues.append(Issue(severity, category, file, line, code, description, fix, blender_5x_note))

    @property
    def criticals(self):
        return [i for i in self.issues if i.severity == "CRITICAL"]

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == "WARNING"]

    @property
    def infos(self):
        return [i for i in self.issues if i.severity == "INFO"]

    def summary(self):
        lines = []
        lines.append("=" * 72)
        lines.append("  Blender-MCP 5.1.2 Compatibility Report")
        lines.append("  Generated: 2026-06-01  |  Target: Blender 5.1.2")
        lines.append("=" * 72)
        lines.append("")
        for severity in ["CRITICAL", "ERROR", "WARNING", "INFO"]:
            labels = {"CRITICAL": "Critical", "ERROR": "Error", "WARNING": "Warning", "INFO": "Info"}
            icon = {"CRITICAL": "[C!]", "ERROR": "[!!]", "WARNING": "[--]", "INFO": "[..]"}
            group = {"CRITICAL": self.criticals, "ERROR": self.errors,
                     "WARNING": self.warnings, "INFO": self.infos}[severity]
            if not group:
                continue
            lines.append(f"  {severity} ({len(group)}):")
            lines.append("  " + "-" * 52)
            for i in group:
                lines.append(f"    {icon[severity]} {i.file}:{i.line}  {i.code}")
                lines.append(f"       {i.description}")
                if i.fix:
                    lines.append(f"       FIX: {i.fix}")
                if i.blender_5x_note:
                    lines.append(f"       NOTE: {i.blender_5x_note}")
            lines.append("")
        lines.append(f"  Total: {len(self.issues)} issues")
        lines.append(f"  CRITICAL: {len(self.criticals)}  ERROR: {len(self.errors)}")
        lines.append(f"  WARNING: {len(self.warnings)}  INFO: {len(self.infos)}")
        lines.append("=" * 72)
        return "\n".join(lines)


# ============================================================
# Helpers
# ============================================================

def _read_lines(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.readlines()


def _grep(lines, pattern):
    results = []
    regex = re.compile(pattern)
    for i, line in enumerate(lines, 1):
        m = regex.search(line)
        if m:
            results.append((i, line.strip()))
    return results


# ============================================================
# Checks
# ============================================================

def check_operators_panels(lines, report):
    f = "addon.py"
    # bl_region_type = 'UI' deprecated in Blender 4.2+
    for ln, txt in _grep(lines, r"bl_region_type\s*=\s*['\"]UI['\"]"):
        report.add(severity="WARNING", category="Panel Region Type", file=f, line=ln, code=txt[:60],
                   description="bl_region_type = 'UI' is deprecated in Blender 4.2+",
                   blender_5x_note="Use bl_region_type = 'WINDOW' instead. 'UI' still works in 5.1.2 but will be removed.",
                   fix="Change bl_region_type to 'WINDOW'")


def check_shader_nodes(lines, report):
    f = "addon.py"
    removed_nodes = ["ShaderNodeBsdfDiffuse", "ShaderNodeBsdfGlossy", "ShaderNodeBsdfToon"]
    for node in removed_nodes:
        for ln, txt in _grep(lines, rf"type=['\"]{re.escape(node)}['\"]"):
            report.add(severity="ERROR", category="Removed ShaderNode", file=f, line=ln, code=txt[:60],
                       description=f"{node} was removed from Blender",
                       blender_5x_note="Use replacement node instead", fix="Use replacement node")

    # .tree -> .node_tree
    for ln, txt in _grep(lines, r"\.tree\s*="):
        report.add(severity="WARNING", category="Node Tree Attribute", file=f, line=ln, code=txt[:60],
                   description="Use .node_tree instead of .tree",
                   blender_5x_note="In Blender 3.0+, .tree is deprecated. Use .node_tree",
                   fix="Replace .tree with .node_tree")


def check_render_api(lines, report):
    f = "addon.py"
    for ln, txt in _grep(lines, r"scene\.render\.engine\s*=\s*['\"]BLENDER_"):
        report.add(severity="WARNING", category="Deprecated Render Engine", file=f, line=ln, code=txt[:60],
                   description="BLENDER_EEVEE/BLENDER_CYCLES deprecated in Blender 4.0+",
                   blender_5x_note="Use 'EEVEE'/'EEVEE_NEXT' and 'CYCLES' instead",
                   fix="Replace BLENDER_EEVEE with EEVEE or EEVEE_NEXT")


def check_import_export(lines, report):
    f = "addon.py"
    # Old OBJ import operator
    for ln, txt in _grep(lines, r"bpy\.ops\.import_scene\.obj\("):
        report.add(severity="WARNING", category="OBJ Import", file=f, line=ln, code=txt[:60],
                   description="bpy.ops.import_scene.obj deprecated in Blender 4.0+",
                   blender_5x_note="Use bpy.ops.wm.obj_import instead")

    # Version check
    ver_check = _grep(lines, r"bpy\.app\.version.*\(4, 0, 0\)")
    if ver_check:
        report.add(severity="INFO", category="OBJ Import Version Check", file=f, line=ver_check[0][0], code="bpy.app.version check",
                   description="bpy.app.version >= (4,0,0) check found",
                   blender_5x_note="Addon correctly uses bpy.ops.wm.obj_import for Blender 4.0+")
    else:
        report.add(severity="ERROR", category="OBJ Import Version Check", file=f, line=0, code="no version check",
                   description="No version check for OBJ import operator",
                   fix="All OBJ imports should use bpy.ops.wm.obj_import for Blender 4.0+")

    # GLTF imports
    for ln, txt in _grep(lines, r"bpy\.ops\.import_scene\.gltf\("):
        report.add(severity="INFO", category="GLTF Import", file=f, line=ln, code=txt[:60],
                   description="GLTF import — operator path valid in 5.1.2")


def check_screenshot_context(lines, report):
    f = "addon.py"
    for ln, txt in _grep(lines, r"bpy\.context\.temp_override"):
        report.add(severity="INFO", category="Context Override", file=f, line=ln, code=txt[:60],
                   description="bpy.context.temp_override() — correct for Blender 4.1+ / 5.1.2",
                   blender_5x_note="This is the preferred API. No changes needed.")


def check_python_stdlib(lines, report):
    f = "addon.py"
    # datetime.utcfromtimestamp deprecated in Python 3.12+
    for ln, txt in _grep(lines, r"datetime\.utcfromtimestamp"):
        report.add(severity="WARNING", category="utcfromtimestamp", file=f, line=ln, code=txt[:60],
                   description="datetime.utcfromtimestamp() deprecated in Python 3.12+",
                   blender_5x_note="Blender 5.1.2 ships with Python 3.13. Use datetime.fromtimestamp(ts, tz=timezone.utc).",
                   fix="Replace with datetime.fromtimestamp(timestamp, tz=timezone.utc)")

    # tempfile._cleanup() private API
    for ln, txt in _grep(lines, r"tempfile\._cleanup\(\)"):
        report.add(severity="INFO", category="tempfile._cleanup", file=f, line=ln, code=txt[:60],
                   description="tempfile._cleanup() is a private API",
                   blender_5x_note="May break in future Python versions. Consider manual cleanup.",
                   fix="Replace with manual cleanup: os.unlink(tmp_path)")


def check_bpy_props(lines, report):
    f = "addon.py"
    for ln, txt in _grep(lines, r"bpy\.props\.(?:Int|Bool|String|Enum|Float)Property"):
        report.add(severity="INFO", category="bpy.props", file=f, line=ln, code=txt[:60],
                   description="Property type usage — standard API",
                   blender_5x_note="No breaking changes in 5.1.2 for these property types.")


def check_addon_registration(lines, report):
    f = "addon.py"
    prop_del = _grep(lines, r"del bpy\.types\.Scene\.blendermcp_")
    if prop_del:
        report.add(severity="INFO", category="Property Cleanup", file=f, line=prop_del[0][0],
                   code=f"{len(prop_del)} property deletions",
                   description="Properties properly cleaned up in unregister()",
                   blender_5x_note="Standard addon registration pattern.")


def check_image_api(lines, report):
    f = "addon.py"
    for ln, txt in _grep(lines, r"colorspace_settings\.name\s*="):
        report.add(severity="INFO", category="ColorSpace Settings", file=f, line=ln, code=txt[:60],
                   description="colorspace_settings.name assignment",
                   blender_5x_note="Valid in Blender 5.1.2. sRGB and Non-Color are standard.")


def check_mathutils(lines, report):
    f = "addon.py"
    for ln, txt in _grep(lines, r"import mathutils"):
        report.add(severity="INFO", category="mathutils", file=f, line=ln, code=txt[:60],
                   description="import mathutils",
                   blender_5x_note="Valid in Blender 5.1.2 Python environment.")


def check_timers(lines, report):
    f = "addon.py"
    for ln, txt in _grep(lines, r"bpy\.app\.timers\.register"):
        report.add(severity="INFO", category="Timer", file=f, line=ln, code=txt[:60],
                   description="bpy.app.timers.register() usage",
                   blender_5x_note="Standard API, no 5.1.2 changes.")


def check_hunyuan_obj_import(lines, report):
    """Check Hunyuan3D import_generated_asset_hunyuan_ai for OBJ import path."""
    f = "addon.py"
    for ln, txt in _grep(lines, r"bpy\.ops\.wm\.obj_import\("):
        report.add(severity="INFO", category="WM OBJ Import", file=f, line=ln, code=txt[:60],
                   description="bpy.ops.wm.obj_import — correct for Blender 4.0+",
                   blender_5x_note="This is the modern operator path, correct in 5.1.2.")


# ============================================================
# Run
# ============================================================

def run(filepath=None):
    if filepath is None:
        project_root = Path(__file__).parent.parent
        filepath = str(project_root / "addon.py")
    lines = _read_lines(filepath)
    report = CompatReport()
    check_operators_panels(lines, report)
    check_shader_nodes(lines, report)
    check_render_api(lines, report)
    check_import_export(lines, report)
    check_screenshot_context(lines, report)
    check_python_stdlib(lines, report)
    check_bpy_props(lines, report)
    check_addon_registration(lines, report)
    check_image_api(lines, report)
    check_mathutils(lines, report)
    check_timers(lines, report)
    check_hunyuan_obj_import(lines, report)
    return report


def run_all():
    project_root = Path(__file__).parent.parent
    all_issues = []
    for name, subdir in [("addon.py", None), ("server.py", "src/blender_mcp"), ("advanced_objects.py", "src/blender_mcp")]:
        if subdir:
            p = project_root / subdir / name
        else:
            p = project_root / name
        if not p.exists():
            continue
        lines = _read_lines(str(p))
        r = CompatReport()
        check_operators_panels(lines, r)
        check_shader_nodes(lines, r)
        check_import_export(lines, r)
        check_python_stdlib(lines, r)
        check_bpy_props(lines, r)
        all_issues.extend(r.issues)
    combined = CompatReport()
    combined.issues = all_issues
    return combined


if __name__ == "__main__":
    report = run()
    print(report.summary())
    project_root = Path(__file__).parent.parent
    output_path = project_root / "blender_512_compat_report.json"
    data = {
        "generated": "2026-06-01",
        "target": "Blender 5.1.2",
        "total": len(report.issues),
        "criticals": len(report.criticals),
        "errors": len(report.errors),
        "warnings": len(report.warnings),
        "infos": len(report.infos),
        "issues": [
            {"severity": i.severity, "category": i.category, "file": i.file,
             "line": i.line, "code": i.code, "description": i.description,
             "fix": i.fix, "blender_5x_note": i.blender_5x_note}
            for i in report.issues
        ],
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nJSON report saved to: {output_path}")
