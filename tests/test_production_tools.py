import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


TOOLS = [
    "scene_manage",
    "character_rig",
    "animation_control",
    "geometry_nodes",
    "camera_compositor",
    "asset_pipeline",
    "scene_measure",
    "batch_edit",
    "lighting_rig",
    "simulation_setup",
    "batch_render",
    "resource_package",
    "boolean_model",
    "curve_create",
    "material_nodes",
    "render_passes",
    "scene_diff",
    "data_cleanup",
]


@pytest.mark.parametrize("tool_name", TOOLS)
def test_production_tool_schema(tool_name):
    import blender_mcp.server as server

    tool = getattr(server, tool_name)
    function = tool.__wrapped__
    assert function.__doc__
    assert "ctx" in function.__code__.co_varnames


@pytest.mark.parametrize("tool_name", TOOLS)
def test_production_tool_forwards_command(tool_name):
    import blender_mcp.server as server

    connection = MagicMock()
    connection.send_command.return_value = {
        "status": "success",
        "result": {"tool": tool_name, "verified": True},
    }
    arguments = {
        "scene_manage": {},
        "character_rig": {},
        "animation_control": {"object_name": "Cube"},
        "geometry_nodes": {"object_name": "Cube"},
        "camera_compositor": {},
        "asset_pipeline": {},
        "scene_measure": {},
        "batch_edit": {"action": "transform", "object_names": ["Cube"]},
        "lighting_rig": {},
        "simulation_setup": {"object_name": "Cube"},
        "batch_render": {"output_dir": "renders"},
        "resource_package": {},
        "boolean_model": {"target_name": "Cube", "cutter_name": "Cutter"},
        "curve_create": {},
        "material_nodes": {"material_name": "Material"},
        "render_passes": {},
        "scene_diff": {},
        "data_cleanup": {},
    }
    with patch("blender_mcp.server.get_blender_connection", return_value=connection):
        result = getattr(server, tool_name)(None, **arguments[tool_name])

    payload = json.loads(result)
    assert payload["ok"] is True
    assert payload["command"] == tool_name
    assert payload["result"]["verified"] is True
    assert connection.send_command.call_args.args[0] == tool_name


def test_addon_registers_production_handlers():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    for tool_name in TOOLS:
        assert f'"{tool_name}": self._{tool_name}' in source


def test_geometry_nodes_tool_exposes_recipe_parameters():
    from blender_mcp.server import geometry_nodes

    variables = geometry_nodes.__wrapped__.__code__.co_varnames
    for name in ("operation", "count", "offset", "source_object", "density", "seed"):
        assert name in variables


def test_partial_command_preserves_protocol_envelope():
    from blender_mcp.server import modeling_recipe

    connection = MagicMock()
    connection.send_command.return_value = {
        "status": "partial", "ok": False, "command": "modeling_recipe",
        "result": {"status": "rolled_back", "completed_steps": []},
        "warnings": ["Changes were rolled back"], "error": None,
        "meta": {"duration_ms": 12.5},
    }
    with patch("blender_mcp.server.get_blender_connection", return_value=connection):
        payload = json.loads(modeling_recipe(None, steps=[{"tool": "mesh_quality"}]))

    assert payload["status"] == "partial"
    assert payload["ok"] is False
    assert payload["result"]["status"] == "rolled_back"
    assert payload["meta"]["duration_ms"] == 12.5


def test_dispatcher_uses_context_guard_with_select_exception():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    assert "def _blender_context_guard(" in source
    assert 'cmd_type == "scene_manage" and params.get("action") == "select"' in source
    assert "self._blender_context_guard(preserve_selection=preserve_selection)" in source


def test_context_guard_captures_user_facing_state():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    for field in ("mesh_select_mode", "cursor_location", "cursor_rotation", '"selected"', '"active"', '"frame"'):
        assert field in source
