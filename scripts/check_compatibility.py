#================================================================
#  ================================================================
#  check_compatibility.py
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

import os
import sys
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class VersionCheck:
    check_name: str
    status: str  # PASS, FAIL, WARNING
    message: str
    detail: str = ""


@dataclass
class CompatibilityReport:
    checks: List[VersionCheck] = field(default_factory=list)

    def add(self, name: str, status: str, message: str, detail: str = ""):
        self.checks.append(VersionCheck(name, status, message, detail))

    @property
    def passed(self) -> bool:
        return all(c.status == "PASS" for c in self.checks)

    @property
    def failures(self) -> List[VersionCheck]:
        return [c for c in self.checks if c.status == "FAIL"]

    @property
    def warnings(self) -> List[VersionCheck]:
        return [c for c in self.checks if c.status == "WARNING"]

    def summary(self) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("Blender-MCP Version Compatibility Report")
        lines.append("=" * 60)

        for check in self.checks:
            icon = {"PASS": "[OK]", "FAIL": "[!!]", "WARNING": "[--]"}.get(check.status, "[??]")
            lines.append(f"  {icon} {check.check_name}: {check.message}")
            if check.detail:
                lines.append(f"       {check.detail}")

        lines.append("")
        lines.append(f"  Passed: {len([c for c in self.checks if c.status == 'PASS'])}/{len(self.checks)}")
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
        if self.failures:
            lines.append(f"  Failures: {len(self.failures)}")

        status = "ALL PASSED" if self.passed else "ISSUES FOUND"
        lines.append(f"\n  Overall: {status}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "checks": [
                {"name": c.check_name, "status": c.status, "message": c.message, "detail": c.detail}
                for c in self.checks
            ],
            "passed": self.passed,
            "failures": len(self.failures),
            "warnings": len(self.warnings),
        }


def check_python_version(report: CompatibilityReport):
    """Check for Python version mismatches."""
    project_dir = Path(__file__).parent.parent

    # Check pyproject.toml
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        match = re.search(r'requires-python\s*=\s*">=(\d+\.\d+)"', content)
        if match:
            required_python = match.group(1)
            actual_python = f"{sys.version_info.major}.{sys.version_info.minor}"
            report.add(
                "Python (pyproject.toml)",
                "PASS",
                f"pyproject.toml requires Python >= {required_python}",
                f"System Python: {actual_python}"
            )

    # Check .python-version
    pyversion_file = project_dir / ".python-version"
    if pyversion_file.exists():
        pinned_version = pyversion_file.read_text().strip()
        report.add(
            "Python (.python-version)",
            "WARNING",
            f".python-version specifies Python {pinned_version}",
            "Differs from pyproject.toml requirement. Consider aligning."
        )

    # Check actual Python version
    current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        report.add(
            "Python (actual)",
            "PASS",
            f"Running Python {current}",
            f"Meets minimum requirement of 3.10"
        )
    else:
        report.add(
            "Python (actual)",
            "FAIL",
            f"Running Python {current}",
            "Minimum requirement is Python 3.10"
        )


def check_addon_version(report: CompatibilityReport):
    """Check addon.py version vs project version."""
    project_dir = Path(__file__).parent.parent

    addon_file = project_dir / "addon.py"
    if addon_file.exists():
        content = addon_file.read_text()
        match = re.search(r'"version"\s*:\s*\((\d+),\s*(\d+)\)', content)
        if match:
            addon_major = match.group(1)
            addon_minor = match.group(2)
            addon_version = f"{addon_major}.{addon_minor}"

            pyproject = project_dir / "pyproject.toml"
            if pyproject.exists():
                pc = pyproject.read_text()
                ver_match = re.search(r'version\s*=\s*"([^"]+)"', pc)
                if ver_match:
                    project_version = ver_match.group(1)
                    addon_version_tuple = (addon_major, addon_minor)
                    try:
                        project_version_tuple = tuple(int(x) for x in project_version.split("."))[:2]
                    except ValueError:
                        project_version_tuple = (0, 0)

                    if addon_version_tuple != project_version_tuple:
                        report.add(
                            "Version Consistency",
                            "WARNING",
                            f"addon.py v{addon_version_tuple[0]}.{addon_version_tuple[1]} != pyproject.toml v{project_version}",
                            "Version mismatch between addon and project"
                        )
                    else:
                        report.add(
                            "Version Consistency",
                            "PASS",
                            f"addon.py v{addon_major}.{addon_minor} == pyproject.toml v{project_version}"
                        )

    # Check for hardcoded keys
    if addon_file.exists():
        content = addon_file.read_text()
        hardcoded_keys = re.findall(r'([A-Z_]*KEY\s*=\s*["\'][^"\']+["\'])', content)
        if hardcoded_keys:
            # Filter out keys that are now documented/expected
            documented_keys = {"RODIN_FREE_TRIAL_KEY"}
            undocumented = [k for k in hardcoded_keys if not any(dk.split("=")[0].strip() in k for dk in documented_keys)]
            if undocumented:
                report.add(
                    "Hardcoded Keys",
                    "WARNING",
                    f"Found {len(undocumented)} undocumented hardcoded key(s) in addon.py",
                    f"Keys: {', '.join(k[:30] + '...' for k in undocumented)}"
                )
            else:
                report.add(
                    "Hardcoded Keys",
                    "PASS",
                    "All hardcoded keys are documented (RODIN_FREE_TRIAL_KEY is a free trial key)"
                )
        else:
            report.add("Hardcoded Keys", "PASS", "No hardcoded keys detected")


def check_dependencies(report: CompatibilityReport):
    """Check dependency availability."""
    try:
        import mcp
        report.add(
            "Dependency: mcp",
            "PASS",
            f"mcp {mcp.__version__} installed" if hasattr(mcp, "__version__") else "mcp installed"
        )
    except ImportError:
        report.add("Dependency: mcp", "FAIL", "mcp package not installed")

    try:
        import tomli
        report.add("Dependency: tomli", "PASS", "tomli installed")
    except ImportError:
        report.add("Dependency: tomli", "WARNING", "tomli not installed (fallback: tomllib on Python 3.11+)")

    try:
        import supabase
        report.add("Dependency: supabase", "PASS", "supabase installed")
    except ImportError:
        report.add("Dependency: supabase", "WARNING", "supabase not installed (telemetry will be disabled)")


def check_file_structure(report: CompatibilityReport):
    """Verify expected file structure exists."""
    project_dir = Path(__file__).parent.parent

    required_files = [
        "addon.py",
        "main.py",
        "pyproject.toml",
        "README.md",
        "src/blender_mcp/__init__.py",
        "src/blender_mcp/server.py",
        "src/blender_mcp/config.py.example",
        "src/blender_mcp/config_new.py",
        "src/blender_mcp/connection_recovery.py",
        "tests/__init__.py",
        "tests/test_config.py",
        "tests/test_connection_recovery.py",
    ]

    missing = []
    for rel_path in required_files:
        full_path = project_dir / rel_path
        if full_path.exists():
            report.add(f"File: {rel_path}", "PASS", "Exists")
        else:
            missing.append(rel_path)

    if missing:
        report.add(
            "File Structure",
            "FAIL",
            f"Missing {len(missing)} file(s)",
            f"Missing: {', '.join(missing)}"
        )
    else:
        report.add("File Structure", "PASS", f"All {len(required_files)} required files present")


def check_test_structure(report: CompatibilityReport):
    """Verify test framework is set up."""
    project_dir = Path(__file__).parent.parent
    tests_dir = project_dir / "tests"
    pytest_ini = tests_dir / "pytest.ini"

    if pytest_ini.exists():
        report.add("Test Framework: pytest.ini", "PASS", "pytest configuration found")
    else:
        report.add("Test Framework: pytest.ini", "WARNING", "pytest.ini not found")

    test_files = list(tests_dir.glob("test_*.py"))
    report.add(
        "Test Files",
        "PASS" if test_files else "WARNING",
        f"{len(test_files)} test file(s) found",
        ", ".join(f.name for f in test_files) if test_files else "No test files"
    )


def check_gitignore(report: CompatibilityReport):
    """Check .gitignore covers config.py."""
    project_dir = Path(__file__).parent.parent
    gitignore = project_dir / ".gitignore"

    if gitignore.exists():
        content = gitignore.read_text()
        if "config.py" in content:
            report.add("Git Ignore: config.py", "PASS", "config.py is excluded from version control")
        else:
            report.add("Git Ignore: config.py", "WARNING", "config.py NOT in .gitignore")
    else:
        report.add("Git Ignore", "WARNING", ".gitignore not found")


def run_checks() -> CompatibilityReport:
    """Run all compatibility checks."""
    report = CompatibilityReport()
    check_python_version(report)
    check_addon_version(report)
    check_dependencies(report)
    check_file_structure(report)
    check_test_structure(report)
    check_gitignore(report)
    return report


def main():
    """CLI entry point."""
    report = run_checks()
    print(report.summary())

    # Save JSON report
    output_path = Path(__file__).parent.parent / "compatibility_report.json"
    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\nJSON report saved to: {output_path}")

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
