import pytest

from blender_mcp.advanced_objects import AdvancedObjectOperations


class RecordingConnection:
    def __init__(self):
        self.calls = []

    def send_command(self, command, payload):
        self.calls.append((command, payload))
        return {"operation": payload["operation"], "accepted": True}


@pytest.fixture
def connected_ops():
    connection = RecordingConnection()
    return AdvancedObjectOperations(connection), connection


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("batch_apply_material", {"object_names": ["A"], "material_name": "Mat"}),
        ("batch_set_transform", {"object_names": ["A"], "location": (1, 2, 3)}),
        ("batch_make_duplicates", {"object_names": ["A"], "count_per_object": 2}),
        ("batch_delete", {"object_names": ["A"]}),
        ("batch_set_visibility", {"object_names": ["A"], "visible": False}),
        ("batch_make_parent", {"child_names": ["A"], "parent_name": "Root"}),
        ("batch_make_empty_group", {"object_names": ["A"], "group_name": "Group"}),
        ("batch_apply_modifiers", {"object_names": ["A"]}),
        ("batch_mirror", {"object_names": ["A"], "axis": "X"}),
        ("batch_instance_on_points", {"template_object_names": ["Tree"], "points_object_name": "Ground"}),
        ("batch_align_bounding_boxes", {"object_names": ["A", "B"]}),
        ("set_render_eevee", {}),
        ("set_render_cycles", {}),
        ("set_render_output", {"filepath": "render.png"}),
        ("render_viewport", {"filepath": "viewport.png"}),
        ("render_animation_batch", {"filepath": "frames", "frame_start": 1, "frame_end": 3}),
        ("render_multi_view", {"filepath": "views"}),
        ("render_360_panorama", {"filepath": "pano.png"}),
        ("set_render_camera", {"camera_name": "Camera"}),
        ("render_preview", {"filepath": "preview.png"}),
        ("get_render_info", {}),
        ("import_fbx", {"filepath": "model.fbx"}),
        ("import_obj", {"filepath": "model.obj"}),
        ("import_glb", {"filepath": "model.glb"}),
        ("import_stl", {"filepath": "model.stl"}),
        ("export_fbx", {"filepath": "model.fbx"}),
        ("export_glb", {"filepath": "model.glb"}),
        ("export_obj", {"filepath": "model.obj"}),
        ("export_stl", {"filepath": "model.stl"}),
        ("export_blend", {"filepath": "model.blend"}),
        ("export_animation_fbx", {"filepath": "anim.fbx", "object_names": ["Rig"]}),
        ("export_animation_gltf", {"filepath": "anim.glb", "object_names": ["Rig"]}),
        ("import_scene_blend", {"filepath": "library.blend"}),
        ("import_csv_data", {"filepath": "points.csv", "target_object_name": "Dot"}),
        ("capture_scene_snapshot", {"filepath": "scene.png"}),
        ("capture_viewport_snapshot", {"filepath": "viewport.png"}),
        ("capture_camera_view", {"camera_name": "Camera", "filepath": "camera.png"}),
        ("capture_all_cameras", {"output_dir": "cameras"}),
    ],
)
def test_advanced_category_methods_use_live_transport(connected_ops, method, kwargs):
    operations, connection = connected_ops

    result = getattr(operations, method)(**kwargs)

    command, payload = connection.calls[-1]
    assert command == "advanced_operation"
    assert payload["operation"] == method
    assert result == {"operation": method, "accepted": True}


def test_transport_propagates_connection_errors():
    class FailingConnection:
        def send_command(self, command, payload):
            raise ConnectionError("Blender unavailable")

    with pytest.raises(ConnectionError, match="Blender unavailable"):
        AdvancedObjectOperations(FailingConnection()).get_render_info()
