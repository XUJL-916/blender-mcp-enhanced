import inspect
from pathlib import Path

import pytest

from blender_mcp.advanced_objects import (
    AdvancedObjectOperations,
    BoundingBox,
    MaterialInfo,
    RenderSettings,
)


class RecordingConnection:
    def __init__(self, result=None):
        self.calls = []
        self.result = result

    def send_command(self, command, payload):
        self.calls.append((command, payload))
        return self.result or {
            "executed": payload["operation"],
            "arguments": payload["arguments"],
            "command_id": payload["command_id"],
        }


def test_bounding_box_properties():
    bounds = BoundingBox(-5, -3, -2, 5, 3, 2)
    assert (bounds.width, bounds.height, bounds.depth) == (10, 6, 4)
    assert bounds.center == (0.0, 0.0, 0.0)
    assert bounds.volume == 240


def test_material_info_defaults():
    material = MaterialInfo("Mat", True, 2, (1, 1, 1, 1), 0.2, 0.4)
    assert material.texture_nodes == []


def test_render_settings_defaults():
    settings = RenderSettings()
    assert settings.engine == "EEVEE"
    assert settings.resolution_x == 1920
    assert settings.samples == 128


def test_every_public_operation_is_live_transport():
    public = {
        name: method for name, method in vars(AdvancedObjectOperations).items()
        if not name.startswith("_") and callable(method)
    }
    assert len(public) >= 80
    for name, method in public.items():
        assert "_dispatch_bound" in method.__code__.co_names, f"{name} still uses a placeholder body"


@pytest.mark.parametrize(
    ("method", "args", "kwargs", "expected"),
    [
        ("select_object", ("Cube",), {}, {"object_name": "Cube"}),
        ("create_collection", ("Props",), {"parent_name": "Scene"},
         {"name": "Props", "parent_name": "Scene"}),
        ("batch_scale", (["A", "B"], 2.0), {},
         {"object_names": ["A", "B"], "factor": 2.0}),
        ("create_material", ("Metal",), {"color": (1, 0, 0, 1), "metallic": 0.8},
         {"name": "Metal", "color": [1, 0, 0, 1], "metallic": 0.8, "roughness": 0.5}),
        ("capture_all_cameras", ("renders",), {},
         {"output_dir": "renders", "resolution": [1920, 1080],
          "format": "PNG", "render_pass": "FINAL"}),
    ],
)
def test_operation_forwards_bound_arguments(method, args, kwargs, expected):
    connection = RecordingConnection()
    operations = AdvancedObjectOperations(connection)

    result = getattr(operations, method)(*args, **kwargs)

    command, payload = connection.calls[-1]
    assert command == "advanced_operation"
    assert payload["operation"] == method
    for key, value in expected.items():
        assert payload["arguments"][key] == value
    assert result["executed"] == method


def test_dataclass_arguments_are_serialized():
    connection = RecordingConnection()
    operations = AdvancedObjectOperations(connection)
    operations.set_render_settings(RenderSettings(engine="CYCLES", samples=64))

    payload = connection.calls[-1][1]
    assert payload["arguments"]["settings"]["engine"] == "CYCLES"
    assert payload["arguments"]["settings"]["samples"] == 64


def test_command_ids_are_incremental():
    connection = RecordingConnection()
    operations = AdvancedObjectOperations(connection)
    operations.deselect_all()
    operations.get_scene_summary()
    assert [call[1]["command_id"] for call in connection.calls] == ["cmd_1", "cmd_2"]


def test_connection_result_is_returned_without_fabrication():
    expected = {"status": "partial", "reason": "render cancelled"}
    operations = AdvancedObjectOperations(RecordingConnection(expected))
    assert operations.render_preview("preview.png") is expected


def test_missing_connection_fails_explicitly(monkeypatch):
    import blender_mcp.server as server

    monkeypatch.setattr(server, "get_blender_connection", lambda: None)
    with pytest.raises(RuntimeError, match="live BlenderConnection"):
        AdvancedObjectOperations().select_object("Cube")


def test_public_signatures_are_preserved():
    signature = inspect.signature(AdvancedObjectOperations.batch_duplicate)
    assert list(signature.parameters)[:3] == ["self", "object_names", "offset"]
    assert signature.parameters["copies"].default == 3


def test_addon_has_a_branch_for_every_advanced_operation():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    handler = source[source.index("def _advanced_operation("):source.index("def get_scene_info(")]
    public_names = [
        name for name, method in vars(AdvancedObjectOperations).items()
        if not name.startswith("_") and callable(method)
    ]
    missing = [name for name in public_names if f'"{name}"' not in handler]
    assert missing == []


def test_advanced_module_contains_no_fake_success_results():
    source = (Path(__file__).parents[1] / "src" / "blender_mcp" / "advanced_objects.py").read_text(encoding="utf-8")
    assert '"status": "success"' not in source
    assert '"status": "queued"' not in source
    assert "TODO: Send command" not in source
