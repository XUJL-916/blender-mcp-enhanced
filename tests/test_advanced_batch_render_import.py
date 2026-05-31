"""
Tests for Advanced Batch Operations, Render Automation,
Animation Import/Export, and Scene Snapshot modules.

This file targets ONLY the NEW methods appended to advanced_objects.py
and does not modify any existing code or tests.

Run: .venv/Scripts/python.exe -m pytest tests/test_advanced_batch_render_import.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from blender_mcp.advanced_objects import AdvancedObjectOperations


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def ops():
    """Create a fresh AdvancedObjectOperations instance for each test."""
    return AdvancedObjectOperations()


# ============================================================
# Advanced Batch Operations Tests (11 methods)
# ============================================================

class TestAdvancedBatchOperations:

    # --- batch_apply_material ---
    def test_batch_apply_material_default(self, ops):
        result = ops.batch_apply_material(["Cube", "Sphere"], "Metal_Mat")
        assert result["status"] == "applied"
        assert result["material"] == "Metal_Mat"
        assert result["count"] == 2
        assert result["replace_existing"] is True

    def test_batch_apply_material_no_replace(self, ops):
        result = ops.batch_apply_material(["Cube"], "Plastic", replace_existing=False)
        assert result["replace_existing"] is False

    # --- batch_set_transform ---
    def test_batch_set_transform_location(self, ops):
        result = ops.batch_set_transform(["A", "B"], location=(1, 2, 3))
        assert result["status"] == "transformed"
        assert result["location"] == (1, 2, 3)
        assert result["count"] == 2

    def test_batch_set_transform_all(self, ops):
        result = ops.batch_set_transform(
            ["Obj1"],
            location=(0, 0, 0),
            rotation=(0, 0, 0),
            scale=(2, 2, 2),
        )
        assert result["rotation"] == (0, 0, 0)
        assert result["scale"] == (2, 2, 2)

    def test_batch_set_transform_empty_list(self, ops):
        result = ops.batch_set_transform([], location=(1, 1, 1))
        assert result["count"] == 0

    # --- batch_make_duplicates ---
    def test_batch_make_duplicates_default(self, ops):
        result = ops.batch_make_duplicates(["Cube"], count_per_object=3)
        assert result["status"] == "duplicated"
        assert result["total_created"] == 3
        assert result["copies_per_object"] == 3

    def test_batch_make_duplicates_multi_object(self, ops):
        result = ops.batch_make_duplicates(["A", "B", "C"], count_per_object=2, offset=(0.5, 0, 0))
        assert result["total_created"] == 6
        assert result["offset"] == (0.5, 0, 0)
        assert result["randomized"] is False

    # --- batch_delete ---
    def test_batch_delete_basic(self, ops):
        result = ops.batch_delete(["Obj1", "Obj2", "Obj3"])
        assert result["status"] == "deleted"
        assert result["count"] == 3
        assert result["deleted"] == ["Obj1", "Obj2", "Obj3"]

    def test_batch_delete_with_options(self, ops):
        result = ops.batch_delete(["Obj1"], also_clearance=True, also_materials=True)
        assert result["also_clearance"] is True
        assert result["also_materials"] is True

    # --- batch_set_visibility ---
    def test_batch_set_visibility_hide(self, ops):
        result = ops.batch_set_visibility(["A", "B"], visible=False, hide_render=True)
        assert result["visible"] is False
        assert result["hide_render"] is True
        assert result["count"] == 2

    def test_batch_set_visibility_show(self, ops):
        result = ops.batch_set_visibility(["X"], visible=True)
        assert result["status"] == "visibility_updated"

    # --- batch_make_parent ---
    def test_batch_make_parent_basic(self, ops):
        result = ops.batch_make_parent(["Leg1", "Leg2", "Leg3"], "Body")
        assert result["parent"] == "Body"
        assert result["count"] == 3
        assert result["status"] == "parented"

    def test_batch_make_parent_keep_transform_false(self, ops):
        result = ops.batch_make_parent(["A"], "B", keep_transform=False)
        assert result["keep_transform"] is False

    # --- batch_make_empty_group ---
    def test_batch_make_empty_group_basic(self, ops):
        result = ops.batch_make_empty_group(["Obj1", "Obj2"], "MyGroup")
        assert result["group_name"] == "MyGroup"
        assert result["count"] == 2
        assert result["status"] == "grouped"

    # --- batch_apply_modifiers ---
    def test_batch_apply_modifiers_all(self, ops):
        result = ops.batch_apply_modifiers(["A", "B"], apply_all=True)
        assert result["apply_all"] is True
        assert result["count"] == 2

    def test_batch_apply_modifiers_specific(self, ops):
        result = ops.batch_apply_modifiers(["Mesh"], modifier_names=["Subdivision", "Boolean"])
        assert result["modifier_names"] == ["Subdivision", "Boolean"]

    # --- batch_mirror ---
    def test_batch_mirror_basic(self, ops):
        result = ops.batch_mirror(["Mesh1"], axis="X")
        assert result["axis"] == "X"
        assert result["merge_vertices"] is True
        assert result["count"] == 1

    # --- batch_instance_on_points ---
    def test_batch_instance_on_points_basic(self, ops):
        result = ops.batch_instance_on_points(["Tree"], "Ground", random_rotation=True)
        assert result["templates"] == ["Tree"]
        assert result["points_object"] == "Ground"
        assert result["random_rotation"] is True

    # --- batch_align_bounding_boxes ---
    def test_batch_align_bounding_boxes_center(self, ops):
        result = ops.batch_align_bounding_boxes(["A", "B", "C"], alignment="center")
        assert result["alignment"] == "center"
        assert result["reference"] == "world"
        assert result["count"] == 3


# ============================================================
# Advanced Render Automation Tests (10 methods)
# ============================================================

class TestAdvancedRenderAutomation:

    # --- set_render_eevee ---
    def test_set_render_eevee_default(self, ops):
        result = ops.set_render_eevee()
        assert result["status"] == "configured"
        assert result["engine"] == "EEVEE"
        assert result["samples"] == 128
        assert result["denoise"] is True

    def test_set_render_eevee_custom(self, ops):
        result = ops.set_render_eevee(samples=512, denoise=False, tile_size=64, taa_samples=256)
        assert result["samples"] == 512
        assert result["denoise"] is False
        assert result["tile_size"] == 64
        assert result["taa_samples"] == 256

    # --- set_render_cycles ---
    def test_set_render_cycles_default(self, ops):
        result = ops.set_render_cycles()
        assert result["status"] == "configured"
        assert result["engine"] == "CYCLES"
        assert result["samples"] == 1024
        assert result["acceleration"] == "OPTIX"

    def test_set_render_cycles_cpu(self, ops):
        result = ops.set_render_cycles(samples=2048, engine="CPU")
        assert result["acceleration"] == "CPU"
        assert result["samples"] == 2048

    def test_set_render_cycles_invalid_engine(self, ops):
        result = ops.set_render_cycles(engine="INVALID")
        assert result["status"] == "error"
        assert "Engine must be" in result["error"]

    # --- set_render_output ---
    def test_set_render_output_default(self, ops):
        result = ops.set_render_output("/tmp/render.png")
        assert result["status"] == "configured"
        assert result["format"] == "PNG"
        assert result["color_depth"] == "16"

    def test_set_render_output_exr(self, ops):
        result = ops.set_render_output("/tmp/exr/output", format="OPEN_EXR", color_depth="32")
        assert result["format"] == "OPEN_EXR"
        assert result["color_depth"] == "32"

    def test_set_render_output_invalid_format(self, ops):
        result = ops.set_render_output("/tmp/test", format="INVALID")
        assert result["status"] == "error"

    # --- render_viewport ---
    def test_render_viewport_default(self, ops):
        result = ops.render_viewport("/tmp/viewport.png")
        assert result["type"] == "viewport"
        assert result["status"] == "rendering"
        assert result["quality"] == 95

    def test_render_viewport_half_res(self, ops):
        result = ops.render_viewport("/tmp/half.png", resolution_scale=0.5, crop_to_bounds=True)
        assert result["resolution_scale"] == 0.5
        assert result["crop_to_bounds"] is True

    # --- render_animation_batch ---
    def test_render_animation_batch_default(self, ops):
        result = ops.render_animation_batch("/tmp/anim")
        assert result["type"] == "animation_batch"
        assert result["frame_start"] == 1
        assert result["frame_end"] == 250
        assert result["total_frames"] == 250
        assert result["status"] == "queued"

    def test_render_animation_batch_custom(self, ops):
        result = ops.render_animation_batch(
            "/tmp/seq", frame_start=10, frame_end=60, frame_step=2, format="PNG"
        )
        assert result["frame_step"] == 2
        assert result["total_frames"] == 26  # (60-10)//2 + 1
        assert result["format"] == "PNG"

    # --- render_multi_view ---
    def test_render_multi_view_default(self, ops):
        result = ops.render_multi_view("/tmp/multiview")
        assert result["type"] == "multi_view"
        assert len(result["angles"]) == 5  # default: front, back, left, right, top

    def test_render_multi_view_custom(self, ops):
        result = ops.render_multi_view(
            "/tmp/cv",
            camera_angles=[{"name": "front", "location": (0, -5, 2), "rotation": (0, 0, 0)}],
        )
        assert len(result["angles"]) == 1

    # --- render_360_panorama ---
    def test_render_360_panorama_default(self, ops):
        result = ops.render_360_panorama("/tmp/pano.png")
        assert result["type"] == "panorama_360"
        assert result["fov"] == 180.0
        assert result["resolution"] == (4096, 2048)

    # --- set_render_camera ---
    def test_set_render_camera(self, ops):
        result = ops.set_render_camera("MainCamera")
        assert result["camera"] == "MainCamera"
        assert result["status"] == "selected"

    # --- render_preview ---
    def test_render_preview_default(self, ops):
        result = ops.render_preview("/tmp/preview.png")
        assert result["type"] == "preview"
        assert result["resolution_scale"] == 0.5
        assert result["samples"] == 64
        assert result["timeout"] == 30

    # --- get_render_info ---
    def test_get_render_info(self, ops):
        result = ops.get_render_info()
        assert result["status"] == "success"
        assert result["engine"] == "EEVEE"
        assert result["resolution"] == [1920, 1080]
        assert result["denoise"] is True


# ============================================================
# Animation Data Import/Export Tests (13 methods)
# ============================================================

class TestAnimationImportExport:

    # --- import_fbx ---
    def test_import_fbx_default(self, ops):
        result = ops.import_fbx("/models/character.fbx")
        assert result["status"] == "imported"
        assert result["format"] == "FBX"
        assert result["automatic_orientation"] is True

    # --- import_obj ---
    def test_import_obj_default(self, ops):
        result = ops.import_obj("/models/rock.obj")
        assert result["status"] == "imported"
        assert result["format"] == "OBJ"
        assert result["split_objects"] is True

    # --- import_glb ---
    def test_import_glb_default(self, ops):
        result = ops.import_glb("/models/scene.glb")
        assert result["status"] == "imported"
        assert result["format"] == "GLTF/GLB"
        assert result["merge_vertices"] is True

    # --- import_stl ---
    def test_import_stl_default(self, ops):
        result = ops.import_stl("/models/part.stl")
        assert result["status"] == "imported"
        assert result["format"] == "STL"
        assert result["scale"] == 1.0

    # --- export_fbx ---
    def test_export_fbx_default(self, ops):
        result = ops.export_fbx("/export/character.fbx")
        assert result["status"] == "exported"
        assert result["format"] == "FBX"
        assert result["bake_anim"] is True

    def test_export_fbx_selection_only(self, ops):
        result = ops.export_fbx("/export/hand.fbx", object_names=["Hand_L"], use_selection=True)
        assert result["objects"] == ["Hand_L"]
        assert result["use_selection"] is True

    # --- export_glb ---
    def test_export_glb_default(self, ops):
        result = ops.export_glb("/export/scene.glb")
        assert result["status"] == "exported"
        assert result["format"] == "GLB"
        assert result["compression"] is True

    # --- export_obj ---
    def test_export_obj_default(self, ops):
        result = ops.export_obj("/export/mesh.obj")
        assert result["status"] == "exported"
        assert result["format"] == "OBJ"
        assert result["export_uv"] is True

    # --- export_stl ---
    def test_export_stl_binary(self, ops):
        result = ops.export_stl("/export/part.stl")
        assert result["status"] == "exported"
        assert result["binary_format"] is True

    def test_export_stl_ascii(self, ops):
        result = ops.export_stl("/export/part_ascii.stl", binary_format=False)
        assert result["binary_format"] is False

    # --- export_blend ---
    def test_export_blend_default(self, ops):
        result = ops.export_blend("/backup/scene.blend")
        assert result["status"] == "exported"
        assert result["compress"] is True

    # --- export_animation_fbx ---
    def test_export_animation_fbx(self, ops):
        result = ops.export_animation_fbx(
            "/export/anim.fbx",
            object_names=["Armature"],
            frame_start=1,
            frame_end=120,
        )
        assert result["status"] == "exported"
        assert result["format"] == "FBX_ANIMATION"
        assert result["frame_count"] == 120

    def test_export_animation_fbx_subsets(self, ops):
        result = ops.export_animation_fbx(
            "/export/anim",
            object_names=["A", "B"],
            use_subsets=True,
            subset_prefix="char",
        )
        assert result["use_subsets"] is True
        assert result["subset_prefix"] == "char"

    # --- export_animation_gltf ---
    def test_export_animation_gltf(self, ops):
        result = ops.export_animation_gltf(
            "/export/anim.glb",
            object_names=["Armature"],
            compression=False,
        )
        assert result["status"] == "exported"
        assert result["format"] == "GLB_ANIMATION"
        assert result["compression"] is False

    # --- import_scene_blend ---
    def test_import_scene_blend_append(self, ops):
        result = ops.import_scene_blend("/models/props.blend", append_materials=True)
        assert result["status"] == "imported"
        assert result["append_materials"] is True
        assert result["link_library"] is False

    def test_import_scene_blend_link(self, ops):
        result = ops.import_scene_blend("/models/props.blend", link_library=True)
        assert result["link_library"] is True

    # --- import_csv_data ---
    def test_import_csv_data_default(self, ops):
        result = ops.import_csv_data(
            "/data/positions.csv",
            target_object_name="Sphere",
            count=200,
        )
        assert result["status"] == "imported"
        assert result["objects_created"] == 200
        assert result["format"] == "CSV"


# ============================================================
# Scene Snapshot Tests (4 methods)
# ============================================================

class TestSceneSnapshot:

    # --- capture_scene_snapshot ---
    def test_capture_scene_snapshot_default(self, ops):
        result = ops.capture_scene_snapshot("/tmp/snapshot.png")
        assert result["status"] == "captured"
        assert result["type"] == "scene_snapshot"
        assert result["include_rendered"] is True
        assert "scene_data" in result
        assert "render_data" in result

    def test_capture_scene_snapshot_custom(self, ops):
        result = ops.capture_scene_snapshot(
            "/tmp/rendered.png",
            include_rendered=False,
            resolution=(3840, 2160),
            format="JPEG",
            quality=90,
        )
        assert result["resolution"] == (3840, 2160)
        assert result["format"] == "JPEG"
        assert result["quality"] == 90
        assert result["include_rendered"] is False

    # --- capture_viewport_snapshot ---
    def test_capture_viewport_snapshot_default(self, ops):
        result = ops.capture_viewport_snapshot("/tmp/viewport.png")
        assert result["status"] == "captured"
        assert result["type"] == "viewport_snapshot"
        assert result["show_objects"] is True
        assert result["show_grid"] is False

    def test_capture_viewport_snapshot_with_grid(self, ops):
        result = ops.capture_viewport_snapshot(
            "/tmp/grid.png",
            show_grid=True,
            show_axes=True,
            resolution_scale=0.5,
            crop_to_bounds=True,
        )
        assert result["show_grid"] is True
        assert result["show_axes"] is True
        assert result["resolution_scale"] == 0.5
        assert result["crop_to_bounds"] is True

    # --- capture_camera_view ---
    def test_capture_camera_view_default(self, ops):
        result = ops.capture_camera_view("MainCamera", "/tmp/cam.png")
        assert result["type"] == "camera_view"
        assert result["camera"] == "MainCamera"
        assert result["render_pass"] == "FINAL"
        assert result["status"] == "rendering"

    def test_capture_camera_view_invalid_pass(self, ops):
        result = ops.capture_camera_view("Cam", "/tmp/x.png", render_pass="INVALID")
        assert result["status"] == "error"
        assert "Pass must be" in result["error"]

    def test_capture_camera_view_depth_pass(self, ops):
        result = ops.capture_camera_view("DepthCam", "/tmp/depth.png", render_pass="DEPTH")
        assert result["render_pass"] == "DEPTH"

    # --- capture_all_cameras ---
    def test_capture_all_cameras_default(self, ops):
        result = ops.capture_all_cameras("/tmp/all_cams")
        assert result["type"] == "all_cameras"
        assert result["status"] == "queued"
        assert result["format"] == "PNG"
