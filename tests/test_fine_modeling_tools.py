import json
from unittest.mock import MagicMock, patch

import pytest


TOOLS = [
    "mesh_edit",
    "modifier_control",
    "sculpt_refine",
    "mesh_quality",
    "uv_tools",
    "pbr_material",
    "model_checkpoint",
    "modeling_recipe",
]


@pytest.mark.parametrize("tool_name", TOOLS)
def test_fine_modeling_tool_has_schema_and_description(tool_name):
    import blender_mcp.server as server

    tool = getattr(server, tool_name)
    function = tool.__wrapped__
    assert function.__doc__
    assert "ctx" in function.__code__.co_varnames


@pytest.mark.parametrize("tool_name", TOOLS)
def test_fine_modeling_tool_forwards_structured_result(tool_name):
    import blender_mcp.server as server

    connection = MagicMock()
    connection.send_command.return_value = {
        "status": "success",
        "result": {"tool": tool_name, "status": "ok"},
    }
    call_args = {
        "mesh_edit": {"object_name": "Cube", "operation": "bevel"},
        "modifier_control": {"object_name": "Cube"},
        "sculpt_refine": {"object_name": "Cube"},
        "mesh_quality": {"object_name": "Cube"},
        "uv_tools": {"object_name": "Cube"},
        "pbr_material": {"object_name": "Cube"},
        "model_checkpoint": {},
        "modeling_recipe": {"steps": [{"tool": "mesh_quality", "params": {"object_name": "Cube"}}]},
    }

    with patch("blender_mcp.server.get_blender_connection", return_value=connection):
        result = getattr(server, tool_name)(None, **call_args[tool_name])

    payload = json.loads(result)
    assert payload["ok"] is True
    assert payload["command"] == tool_name
    assert payload["result"] == {"tool": tool_name, "status": "ok"}
    assert connection.send_command.call_args.args[0] == tool_name


def test_fine_modeling_command_raises_blender_errors():
    from blender_mcp.server import mesh_quality

    connection = MagicMock()
    connection.send_command.return_value = {"status": "error", "message": "bad mesh"}
    with patch("blender_mcp.server.get_blender_connection", return_value=connection):
        with pytest.raises(RuntimeError, match="bad mesh"):
            mesh_quality(None, object_name="Cube")


def test_addon_registers_all_fine_modeling_handlers():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    for tool_name in TOOLS:
        assert f'"{tool_name}": self._{tool_name}' in source


def test_checkpoint_covers_full_object_state():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    for state_field in (
        '"location": list(obj.location)',
        '"parent": obj.parent.name',
        '"collections": [collection.name',
        '"modifiers": [{"type": modifier.type',
        '"constraints": constraints',
        "copy.animation_data.action = obj.animation_data.action.copy()",
    ):
        assert state_field in source


def test_recipe_removes_new_objects_before_restore():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    cleanup = source.index('if obj.name not in scene_objects_before')
    restore = source.index('self._model_checkpoint("restore", checkpoint_name', cleanup)
    assert cleanup < restore
