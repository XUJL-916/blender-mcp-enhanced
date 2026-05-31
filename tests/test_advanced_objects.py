#================================================================
#  ================================================================
#  test_advanced_objects.py
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

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from blender_mcp.advanced_objects import (
    BoundingBox,
    MaterialInfo,
    RenderSettings,
    AdvancedObjectOperations,
)


# ============================================================
# BoundingBox Tests
# ============================================================

class TestBoundingBox:
    def test_initialization(self):
        bb = BoundingBox(0, 0, 0, 1, 1, 1)
        assert bb.min_x == 0
        assert bb.max_z == 1

    def test_dimensions(self):
        bb = BoundingBox(0, 0, 0, 10, 5, 2)
        assert bb.width == 10
        assert bb.height == 5
        assert bb.depth == 2

    def test_volume(self):
        bb = BoundingBox(0, 0, 0, 2, 3, 4)
        assert bb.volume == 24.0

    def test_center(self):
        bb = BoundingBox(0, 0, 0, 10, 20, 30)
        cx, cy, cz = bb.center
        assert cx == 5.0
        assert cy == 10.0
        assert cz == 15.0

    def test_non_zero_origin(self):
        bb = BoundingBox(-5, -3, -2, 5, 3, 2)
        assert bb.width == 10
        assert bb.height == 6
        assert bb.depth == 4
        assert bb.center == (0.0, 0.0, 0.0)


# ============================================================
# MaterialInfo Tests
# ============================================================

class TestMaterialInfo:
    def test_initialization(self):
        mat = MaterialInfo(
            name="TestMat",
            use_nodes=True,
            node_count=5,
            diffuse_color=(1.0, 0.0, 0.0, 1.0),
            metallic=0.5,
            roughness=0.3,
        )
        assert mat.name == "TestMat"
        assert mat.use_nodes is True
        assert mat.metallic == 0.5
        assert mat.texture_nodes == []

    def test_with_texture_nodes(self):
        mat = MaterialInfo(
            name="TexturedMat",
            use_nodes=True,
            node_count=10,
            diffuse_color=(0.5, 0.5, 0.5, 1.0),
            metallic=0.0,
            roughness=1.0,
            texture_nodes=[
                {"name": "Diffuse", "image": "wood.png"},
                {"name": "Normal", "image": "wood_normal.png"},
            ],
        )
        assert len(mat.texture_nodes) == 2
        assert mat.texture_nodes[0]["image"] == "wood.png"


# ============================================================
# RenderSettings Tests
# ============================================================

class TestRenderSettings:
    def test_default_values(self):
        rs = RenderSettings()
        assert rs.engine == "EEVEE"
        assert rs.resolution_x == 1920
        assert rs.resolution_y == 1080
        assert rs.fps == 24
        assert rs.samples == 128
        assert rs.output_format == "PNG"
        assert rs.transparent is False

    def test_custom_values(self):
        rs = RenderSettings(
            engine="CYCLES",
            resolution_x=3840,
            resolution_y=2160,
            samples=2048,
            output_format="OPEN_EXR",
            transparent=True,
        )
        assert rs.engine == "CYCLES"
        assert rs.resolution_x == 3840
        assert rs.samples == 2048
        assert rs.transparent is True


# ============================================================
# AdvancedObjectOperations — Method Signature Tests
# ============================================================

class TestAdvancedObjectOperations:
    @pytest.fixture
    def ops(self):
        return AdvancedObjectOperations()

    # --- Selection ---
    def test_select_object(self, ops):
        result = ops.select_object("Cube")
        assert result["selected"] == "Cube"
        assert result["status"] == "success"

    def test_select_multiple_objects(self, ops):
        result = ops.select_multiple_objects(["Cube", "Sphere", "Cylinder"])
        assert result["count"] == 3
        assert len(result["selected"]) == 3

    def test_deselect_all(self, ops):
        result = ops.deselect_all()
        assert result["status"] == "success"

    def test_focus_camera_on_object(self, ops):
        result = ops.focus_camera_on_object("Target", "Camera")
        assert result["camera"] == "Camera"
        assert result["target"] == "Target"

    def test_focus_camera_isometric(self, ops):
        result = ops.focus_camera_isometric("Camera2")
        assert result["type"] == "ORTHO"

    # --- Scene Save/Load ---
    def test_save_scene(self, ops):
        result = ops.save_scene("/tmp/test.blend", compress=True)
        assert result["status"] == "saved"

    def test_save_as_scene(self, ops):
        result = ops.save_as_scene("/tmp/test2.blend")
        assert result["status"] == "saved_as"

    def test_load_scene(self, ops):
        result = ops.load_scene("/tmp/test.blend", keep_objects=False)
        assert result["status"] == "loaded"

    # --- Render ---
    def test_get_render_settings(self, ops):
        result = ops.get_render_settings()
        assert result["status"] == "success"

    def test_set_render_settings(self, ops):
        result = ops.set_render_settings(engine="CYCLES", resolution_x=3840)
        assert result["engine"] == "CYCLES"

    def test_render_scene(self, ops):
        result = ops.render_scene(filepath="/tmp/render.png")
        assert result["status"] == "rendering"

    def test_render_animation(self, ops):
        result = ops.render_animation("/tmp/anim", frame_start=1, frame_end=100)
        assert result["frames"] == 100

    # --- Collections ---
    def test_create_collection(self, ops):
        result = ops.create_collection("Foreground")
        assert result["name"] == "Foreground"
        assert result["status"] == "created"

    def test_create_nested_collection(self, ops):
        result = ops.create_collection("Child", parent_name="Parent")
        assert result["parent"] == "Parent"

    def test_add_to_collection(self, ops):
        result = ops.add_to_collection(["Cube", "Sphere"], "Objects")
        assert result["count"] == 2
        assert result["status"] == "moved"

    def test_remove_from_collection(self, ops):
        result = ops.remove_from_collection(["Cube"], "Temp")
        assert result["status"] == "removed"

    def test_list_collections(self, ops):
        result = ops.list_collections()
        assert result["status"] == "success"

    def test_get_collection_objects(self, ops):
        result = ops.get_collection_objects("Main")
        assert result["status"] == "success"

    # --- Batch Operations ---
    def test_batch_scale(self, ops):
        result = ops.batch_scale(["Cube", "Sphere"], factor=2.0)
        assert result["factor"] == 2.0
        assert result["count"] == 2

    def test_batch_color(self, ops):
        result = ops.batch_color(["Cube", "Sphere", "Cylinder"], color=(1.0, 0.0, 0.0, 1.0))
        assert result["count"] == 3

    def test_batch_rotate(self, ops):
        result = ops.batch_rotate(["Cube"], euler_rotation=(0.0, 0.0, 3.14159))
        assert result["status"] == "rotated"

    def test_batch_duplicate(self, ops):
        result = ops.batch_duplicate(["Cube"], offset=(2.0, 0.0, 0.0), copies=5)
        assert result["copies"] == 5
        assert result["total_created"] == 5

    # --- Materials ---
    def test_get_material(self, ops):
        result = ops.get_material("Cube")
        assert result["status"] == "success"

    def test_set_material_color(self, ops):
        result = ops.set_material_color("Cube", color=(0.8, 0.2, 0.1, 1.0))
        assert result["status"] == "updated"

    def test_create_material(self, ops):
        result = ops.create_material("RedMat", color=(1.0, 0.0, 0.0, 1.0), metallic=0.5, roughness=0.3)
        assert result["name"] == "RedMat"
        assert result["metallic"] == 0.5

    def test_apply_material_to_object(self, ops):
        result = ops.apply_material_to_object("RedMat", "Cube")
        assert result["status"] == "applied"

    def test_set_texture_to_material(self, ops):
        result = ops.set_texture_to_material("WoodMat", image_path="/tmp/wood.png")
        assert result["status"] == "applied"

    def test_get_node_tree(self, ops):
        result = ops.get_node_tree("WoodMat")
        assert result["status"] == "success"

    # --- Transform ---
    def test_align_to_world_axis(self, ops):
        result = ops.align_to_world_axis("Cube", axis="Z")
        assert result["axis"] == "Z"

    def test_snap_to_grid(self, ops):
        result = ops.snap_to_grid("Cube", grid_size=0.05)
        assert result["status"] == "snapped"

    def test_center_object_origin(self, ops):
        result = ops.center_object_origin("Cube")
        assert result["status"] == "centered"

    def test_get_bounding_box(self, ops):
        result = ops.get_bounding_box("Cube")
        assert result["status"] == "success"
        assert "bbox" in result

    # --- Lighting ---
    def test_set_studio_lighting_three_point(self, ops):
        result = ops.set_studio_lighting("three_point")
        assert len(result["lights"]) == 3

    def test_set_studio_lighting_preset_unknown(self, ops):
        result = ops.set_studio_lighting("custom_preset")
        assert result["lights"] == []

    def test_set_environment_lighting(self, ops):
        result = ops.set_environment_lighting(
            world_color=(0.1, 0.1, 0.15, 1.0),
            world_strength=0.5,
            use_texture=True,
        )
        assert result["use_texture"] is True

    # --- Camera ---
    def test_create_camera(self, ops):
        result = ops.create_camera(
            name="SideCam",
            location=(0.0, 10.0, 0.0),
            lens=35.0,
        )
        assert result["name"] == "SideCam"
        assert result["lens"] == 35.0
        assert result["type"] == "PERSP"

    def test_get_camera_info(self, ops):
        result = ops.get_camera_info("SideCam")
        assert result["status"] == "success"
        assert result["name"] == "SideCam"

    # --- Diagnostics ---
    def test_get_scene_summary(self, ops):
        result = ops.get_scene_summary()
        assert result["status"] == "success"
        assert "objects" in result

    def test_get_duplicate_objects(self, ops):
        result = ops.get_duplicate_objects()
        assert result["status"] == "success"

    def test_clear_unreferenced_data(self, ops):
        result = ops.clear_unreferenced_data()
        assert result["status"] == "cleared"


# ============================================================
# Command Counter Tests
# ============================================================

class TestCommandCounter:
    def test_incremental_ids(self):
        ops = AdvancedObjectOperations()
        id1 = ops._next_command_id()
        id2 = ops._next_command_id()
        id3 = ops._next_command_id()
        assert id1 == "cmd_1"
        assert id2 == "cmd_2"
        assert id3 == "cmd_3"
