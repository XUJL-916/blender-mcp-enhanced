# ================================================================
#  ================================================================
#  advanced_objects.py
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
#      Advanced object operations — mesh, curve, shape key, particle, volume and modifier manipulation via bpy
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
# ================================================================

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional


# ============================================================
# Data Models
# ============================================================


@dataclass
class BoundingBox:
    """Axis-aligned bounding box in Blender world space."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def depth(self) -> float:
        return self.max_z - self.min_z

    @property
    def center(self) -> tuple:
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2,
        )

    @property
    def volume(self) -> float:
        return self.width * self.height * self.depth


@dataclass
class MaterialInfo:
    """Material information for a Blender object."""

    name: str
    use_nodes: bool
    node_count: int
    diffuse_color: tuple  # RGBA
    metallic: float
    roughness: float
    texture_nodes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RenderSettings:
    """Blender render configuration."""

    engine: str = "EEVEE"  # EEVEE or CYCLES
    resolution_x: int = 1920
    resolution_y: int = 1080
    fps: int = 24
    frame_start: int = 1
    frame_end: int = 1
    samples: int = 128
    output_format: str = "PNG"  # PNG, JPEG, OPEN_EXR, etc.
    color_depth: str = "8"  # 8, 16, 32
    transparent: bool = False


# ============================================================
# AdvancedObjectOperations - Live TCP Implementation
# ============================================================


class AdvancedObjectOperations:
    """Typed advanced operations backed by the live Blender TCP protocol."""

    def __init__(self, blender_connection=None):
        self._conn = blender_connection
        self._command_counter = 0

    def _next_command_id(self) -> str:
        self._command_counter += 1
        return f"cmd_{self._command_counter}"

    @staticmethod
    def _normalize_argument(value: Any) -> Any:
        if is_dataclass(value):
            return {key: AdvancedObjectOperations._normalize_argument(item) for key, item in asdict(value).items()}
        if isinstance(value, dict):
            return {str(key): AdvancedObjectOperations._normalize_argument(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [AdvancedObjectOperations._normalize_argument(item) for item in value]
        return value

    def _send_operation(self, operation: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        connection = self._conn
        if connection is None:
            from .server import get_blender_connection

            connection = get_blender_connection()
        if connection is None or not hasattr(connection, "send_command"):
            raise RuntimeError("A live BlenderConnection is required")
        payload = {
            "operation": operation,
            "arguments": self._normalize_argument(arguments),
            "command_id": self._next_command_id(),
        }
        result = connection.send_command("advanced_operation", payload)
        if not isinstance(result, dict):
            raise TypeError(f"Blender returned a non-object result for {operation}")
        return result

    def _dispatch_bound(self, operation: str, namespace: Dict[str, Any]) -> Dict[str, Any]:
        arguments = {key: value for key, value in namespace.items() if key != "self"}
        return self._send_operation(operation, arguments)

    def select_object(self, object_name: str) -> Dict[str, Any]:
        """Select a single object in the Blender scene."""
        return self._dispatch_bound("select_object", locals())

    def select_multiple_objects(self, object_names: List[str]) -> Dict[str, Any]:
        """Select multiple objects in the Blender scene."""
        return self._dispatch_bound("select_multiple_objects", locals())

    def deselect_all(self) -> Dict[str, Any]:
        """Deselect all objects in the scene."""
        return self._dispatch_bound("deselect_all", locals())

    def focus_camera_on_object(self, object_name: str, camera_name: str = "Camera") -> Dict[str, Any]:
        """Align a camera to point at a specific object."""
        return self._dispatch_bound("focus_camera_on_object", locals())

    def focus_camera_isometric(self, camera_name: str = "Camera") -> Dict[str, Any]:
        """Set camera to isometric (orthographic) view."""
        return self._dispatch_bound("focus_camera_isometric", locals())

    def save_scene(self, filepath: str, compress: bool = True) -> Dict[str, Any]:
        """Save the current Blender scene to a .blend file."""
        return self._dispatch_bound("save_scene", locals())

    def save_as_scene(self, filepath: str, compress: bool = True) -> Dict[str, Any]:
        """Save the current Blender scene as a new file (preserves current file)."""
        return self._dispatch_bound("save_as_scene", locals())

    def load_scene(self, filepath: str, keep_objects: bool = False) -> Dict[str, Any]:
        """Load a .blend file, optionally keeping existing objects."""
        return self._dispatch_bound("load_scene", locals())

    def get_render_settings(self) -> Dict[str, Any]:
        """Get current render settings from the Blender scene."""
        return self._dispatch_bound("get_render_settings", locals())

    def set_render_settings(self, settings: Optional[RenderSettings] = None, **kwargs) -> Dict[str, Any]:
        """Configure render settings."""
        return self._dispatch_bound("set_render_settings", locals())

    def render_scene(self, filepath: Optional[str] = None, frame_range: Optional[tuple] = None) -> Dict[str, Any]:
        """Render the current scene."""
        return self._dispatch_bound("render_scene", locals())

    def render_animation(self, filepath: str, frame_start: int = 1, frame_end: int = 250) -> Dict[str, Any]:
        """Render a full animation sequence."""
        return self._dispatch_bound("render_animation", locals())

    def create_collection(self, name: str, parent_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new collection (Blender's object grouping system)."""
        return self._dispatch_bound("create_collection", locals())

    def add_to_collection(self, object_names: List[str], collection_name: str) -> Dict[str, Any]:
        """Move objects into a collection."""
        return self._dispatch_bound("add_to_collection", locals())

    def remove_from_collection(self, object_names: List[str], collection_name: str) -> Dict[str, Any]:
        """Remove objects from a collection (does not delete objects)."""
        return self._dispatch_bound("remove_from_collection", locals())

    def list_collections(self) -> Dict[str, Any]:
        """List all collections and their structure."""
        return self._dispatch_bound("list_collections", locals())

    def get_collection_objects(self, collection_name: str) -> Dict[str, Any]:
        """Get all objects in a collection."""
        return self._dispatch_bound("get_collection_objects", locals())

    def batch_scale(self, object_names: List[str], factor: float) -> Dict[str, Any]:
        """Scale multiple objects by a uniform factor."""
        return self._dispatch_bound("batch_scale", locals())

    def batch_color(self, object_names: List[str], color: tuple) -> Dict[str, Any]:
        """Set diffuse color for multiple objects."""
        return self._dispatch_bound("batch_color", locals())

    def batch_rotate(self, object_names: List[str], euler_rotation: tuple) -> Dict[str, Any]:
        """Rotate multiple objects by specified Euler angles."""
        return self._dispatch_bound("batch_rotate", locals())

    def batch_duplicate(
        self, object_names: List[str], offset: tuple = (1.0, 0.0, 0.0), copies: int = 3
    ) -> Dict[str, Any]:
        """Create copies of objects with positional offset."""
        return self._dispatch_bound("batch_duplicate", locals())

    def get_material(self, object_name: str) -> Dict[str, Any]:
        """Get material info for an object."""
        return self._dispatch_bound("get_material", locals())

    def set_material_color(self, object_name: str, color: tuple) -> Dict[str, Any]:
        """Set the diffuse color of an object's material."""
        return self._dispatch_bound("set_material_color", locals())

    def create_material(
        self, name: str, color: tuple = (0.8, 0.8, 0.8, 1.0), metallic: float = 0.0, roughness: float = 0.5
    ) -> Dict[str, Any]:
        """Create a new Principled BSDF material."""
        return self._dispatch_bound("create_material", locals())

    def apply_material_to_object(self, material_name: str, object_name: str) -> Dict[str, Any]:
        """Assign a material to an object."""
        return self._dispatch_bound("apply_material_to_object", locals())

    def set_texture_to_material(
        self,
        material_name: str,
        texture_slot: str = "Base Color",
        image_path: Optional[str] = None,
        color_ramp: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """Apply a texture image to a material node."""
        return self._dispatch_bound("set_texture_to_material", locals())

    def get_node_tree(self, material_name: str) -> Dict[str, Any]:
        """Get the node tree structure for a material."""
        return self._dispatch_bound("get_node_tree", locals())

    def create_image_texture_node(
        self,
        material_name: str,
        image_path: str,
        slot: str = "Base Color",
        tile_x: int = 1,
        tile_y: int = 1,
        repeat: bool = False,
    ) -> Dict[str, Any]:
        """Create an Image Texture node and link it to a Principled BSDF slot."""
        return self._dispatch_bound("create_image_texture_node", locals())

    def create_procedural_texture(
        self,
        material_name: str,
        texture_type: str = "Checker",
        slot: str = "Base Color",
        scale: float = 5.0,
        color1: tuple = (0.0, 0.0, 0.0, 1.0),
        color2: tuple = (1.0, 1.0, 1.0, 1.0),
    ) -> Dict[str, Any]:
        """Create a procedural texture node and link it."""
        return self._dispatch_bound("create_procedural_texture", locals())

    def create_color_ramp(
        self, material_name: str, slot: str = "Base Color", stops: Optional[list] = None
    ) -> Dict[str, Any]:
        """Create a ColorRamp node and insert it in the material node tree."""
        return self._dispatch_bound("create_color_ramp", locals())

    def mix_shaders(
        self,
        material_name: str,
        shader1: str = "Principled BSDF",
        shader2: str = "Principled BSDF",
        blend_factor: float = 0.5,
        output_material: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mix two shaders using a Mix Shader node."""
        return self._dispatch_bound("mix_shaders", locals())

    def create_emission_material(
        self, name: str, color: tuple = (1.0, 1.0, 1.0, 1.0), strength: float = 1.0
    ) -> Dict[str, Any]:
        """Create an emission-only material for self-illuminated surfaces."""
        return self._dispatch_bound("create_emission_material", locals())

    def set_normal_map(
        self, material_name: str, texture_path: str, strength: float = 1.0, color_ramp: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """Create a Normal Map node with a texture and link to BSDF Normal input."""
        return self._dispatch_bound("set_normal_map", locals())

    def set_displacement(
        self,
        material_name: str,
        texture_path: str,
        method: str = "Bump",
        displacement_material: str = "Material Output",
    ) -> Dict[str, Any]:
        """Set up displacement (Bump or Displacement) node."""
        return self._dispatch_bound("set_displacement", locals())

    def create_material_group(
        self, name: str, node_type: str = "Group", inputs: Optional[list] = None
    ) -> Dict[str, Any]:
        """Create a material node group for reuse across materials."""
        return self._dispatch_bound("create_material_group", locals())

    def clone_material(self, source_material_name: str, target_name: str) -> Dict[str, Any]:
        """Clone a material (copy all nodes and settings)."""
        return self._dispatch_bound("clone_material", locals())

    def clear_node_tree(self, material_name: str, keep_bsdf: bool = False) -> Dict[str, Any]:
        """Clear all nodes from a material's node tree."""
        return self._dispatch_bound("clear_node_tree", locals())

    def set_anisotropic(
        self, material_name: str, anisotropy: float = 0.5, anisotropy_rotation: float = 0.0
    ) -> Dict[str, Any]:
        """Set anisotropic parameters on a Principled BSDF material."""
        return self._dispatch_bound("set_anisotropic", locals())

    def set_transparency(self, material_name: str, alpha: float = 1.0, blend_mode: str = "OPAQUE") -> Dict[str, Any]:
        """Set transparency/alpha blending on a material."""
        return self._dispatch_bound("set_transparency", locals())

    def setup_ior(self, material_name: str, ior: float = 1.45) -> Dict[str, Any]:
        """Set Index of Refraction (IOR) for transparent/refractive materials."""
        return self._dispatch_bound("setup_ior", locals())

    def align_to_world_axis(self, object_name: str, axis: str = "Z") -> Dict[str, Any]:
        """Align an object's rotation to a world axis."""
        return self._dispatch_bound("align_to_world_axis", locals())

    def snap_to_grid(self, object_name: str, grid_size: float = 0.01) -> Dict[str, Any]:
        """Snap an object's position to the nearest grid point."""
        return self._dispatch_bound("snap_to_grid", locals())

    def center_object_origin(self, object_name: str) -> Dict[str, Any]:
        """Move an object's origin to its geometric center."""
        return self._dispatch_bound("center_object_origin", locals())

    def get_bounding_box(self, object_name: str) -> Dict[str, Any]:
        """Get the AABB bounding box of an object in world space."""
        return self._dispatch_bound("get_bounding_box", locals())

    def set_studio_lighting(self, preset: str = "three_point") -> Dict[str, Any]:
        """Apply a studio lighting preset to the scene."""
        return self._dispatch_bound("set_studio_lighting", locals())

    def set_environment_lighting(
        self,
        world_color: tuple = (0.05, 0.05, 0.08, 1.0),
        world_strength: float = 1.0,
        use_texture: bool = False,
        texture_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure the scene's world lighting."""
        return self._dispatch_bound("set_environment_lighting", locals())

    def create_camera(
        self,
        name: str = "Camera",
        location: tuple = (5.0, -5.0, 3.0),
        rotation: tuple = (-0.5, 0.0, 0.3),
        lens: float = 50.0,
        sensor_width: float = 36.0,
    ) -> Dict[str, Any]:
        """Create a new camera with specified position and lens."""
        return self._dispatch_bound("create_camera", locals())

    def get_camera_info(self, camera_name: str = "Camera") -> Dict[str, Any]:
        """Get detailed camera information."""
        return self._dispatch_bound("get_camera_info", locals())

    def get_scene_summary(self) -> Dict[str, Any]:
        """Get a full scene summary including objects, collections, materials, cameras."""
        return self._dispatch_bound("get_scene_summary", locals())

    def get_duplicate_objects(self) -> Dict[str, Any]:
        """Find objects with identical names in the scene."""
        return self._dispatch_bound("get_duplicate_objects", locals())

    def clear_unreferenced_data(self) -> Dict[str, Any]:
        """Remove unreferenced data blocks (orphan data)."""
        return self._dispatch_bound("clear_unreferenced_data", locals())

    def batch_apply_material(
        self, object_names: List[str], material_name: str, replace_existing: bool = True
    ) -> Dict[str, Any]:
        """Apply the same material to multiple objects in one operation."""
        return self._dispatch_bound("batch_apply_material", locals())

    def batch_set_transform(
        self,
        object_names: List[str],
        location: Optional[tuple] = None,
        rotation: Optional[tuple] = None,
        scale: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """Set transform (location, rotation, scale) for multiple objects."""
        return self._dispatch_bound("batch_set_transform", locals())

    def batch_make_duplicates(
        self,
        object_names: List[str],
        count_per_object: int = 2,
        offset: tuple = (1.0, 0.0, 0.0),
        randomize: bool = False,
    ) -> Dict[str, Any]:
        """Create duplicates of objects with configurable spacing and optional randomization."""
        return self._dispatch_bound("batch_make_duplicates", locals())

    def batch_delete(
        self, object_names: List[str], also_clearance: bool = False, also_materials: bool = False
    ) -> Dict[str, Any]:
        """Delete multiple objects from the scene."""
        return self._dispatch_bound("batch_delete", locals())

    def batch_set_visibility(
        self, object_names: List[str], visible: bool = True, hide_render: bool = False, hide_select: bool = False
    ) -> Dict[str, Any]:
        """Set visibility state for multiple objects."""
        return self._dispatch_bound("batch_set_visibility", locals())

    def batch_make_parent(
        self, child_names: List[str], parent_name: str, keep_transform: bool = True
    ) -> Dict[str, Any]:
        """Make multiple objects children of a single parent."""
        return self._dispatch_bound("batch_make_parent", locals())

    def batch_make_empty_group(
        self, object_names: List[str], group_name: str = "SelectionGroup", create_collection: bool = False
    ) -> Dict[str, Any]:
        """Create an Empty parent for a group of objects and group them."""
        return self._dispatch_bound("batch_make_empty_group", locals())

    def batch_apply_modifiers(
        self, object_names: List[str], modifier_names: Optional[List[str]] = None, apply_all: bool = True
    ) -> Dict[str, Any]:
        """Apply specified modifiers (or all) on multiple objects."""
        return self._dispatch_bound("batch_apply_modifiers", locals())

    def batch_mirror(
        self, object_names: List[str], axis: str = "X", merge_vertices: bool = True, use_clip: bool = True
    ) -> Dict[str, Any]:
        """Apply Mirror modifier to multiple objects (non-destructive)."""
        return self._dispatch_bound("batch_mirror", locals())

    def batch_instance_on_points(
        self,
        template_object_names: List[str],
        points_object_name: str,
        random_rotation: bool = False,
        random_scale: bool = False,
    ) -> Dict[str, Any]:
        """Use geometry nodes to instance objects on points of another object."""
        return self._dispatch_bound("batch_instance_on_points", locals())

    def batch_align_bounding_boxes(
        self, object_names: List[str], alignment: str = "center", reference: str = "world"
    ) -> Dict[str, Any]:
        """Align bounding box centers of multiple objects."""
        return self._dispatch_bound("batch_align_bounding_boxes", locals())

    def set_render_eevee(
        self, samples: int = 128, denoise: bool = True, tile_size: int = 32, taa_samples: int = 128
    ) -> Dict[str, Any]:
        """Configure Eevee render engine settings."""
        return self._dispatch_bound("set_render_eevee", locals())

    def set_render_cycles(
        self, samples: int = 1024, denoise: bool = True, engine: str = "OPTIX", use_denoising: bool = True
    ) -> Dict[str, Any]:
        """Configure Cycles render engine settings."""
        return self._dispatch_bound("set_render_cycles", locals())

    def set_render_output(
        self,
        filepath: str,
        format: str = "PNG",
        color_depth: str = "16",
        compression: int = 15,
        transparent: bool = False,
        ffmpeg: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """Configure render output path, format, and quality."""
        return self._dispatch_bound("set_render_output", locals())

    def render_viewport(
        self, filepath: str, quality: int = 95, resolution_scale: float = 1.0, crop_to_bounds: bool = False
    ) -> Dict[str, Any]:
        """Render the current viewport (what's visible in the 3D view)."""
        return self._dispatch_bound("render_viewport", locals())

    def render_animation_batch(
        self,
        filepath: str,
        frame_start: int = 1,
        frame_end: int = 250,
        frame_step: int = 1,
        format: str = "FFMPEG",
        ffmpeg_settings: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """Render a full animation sequence in batch mode."""
        return self._dispatch_bound("render_animation_batch", locals())

    def render_multi_view(
        self, filepath: str, camera_angles: Optional[list] = None, format: str = "PNG"
    ) -> Dict[str, Any]:
        """Render the scene from multiple camera angles."""
        return self._dispatch_bound("render_multi_view", locals())

    def render_360_panorama(
        self, filepath: str, fov: float = 180.0, resolution: tuple = (4096, 2048), format: str = "PNG"
    ) -> Dict[str, Any]:
        """Render a 360-degree equirectangular panorama."""
        return self._dispatch_bound("render_360_panorama", locals())

    def set_render_camera(self, camera_name: str) -> Dict[str, Any]:
        """Set the active render camera."""
        return self._dispatch_bound("set_render_camera", locals())

    def render_preview(
        self, filepath: str, resolution_scale: float = 0.5, samples: int = 64, timeout: int = 30
    ) -> Dict[str, Any]:
        """Render a low-quality preview image quickly."""
        return self._dispatch_bound("render_preview", locals())

    def get_render_info(self) -> Dict[str, Any]:
        """Get the current full render configuration summary."""
        return self._dispatch_bound("get_render_info", locals())

    def import_fbx(
        self,
        filepath: str,
        automatic_orientation: bool = True,
        import_hardware: bool = True,
        force_connect_children: bool = False,
    ) -> Dict[str, Any]:
        """Import an FBX file into the Blender scene."""
        return self._dispatch_bound("import_fbx", locals())

    def import_obj(
        self,
        filepath: str,
        add_normals: bool = True,
        split_objects: bool = True,
        split_groups: bool = True,
        import_images: bool = True,
    ) -> Dict[str, Any]:
        """Import an OBJ file into the Blender scene."""
        return self._dispatch_bound("import_obj", locals())

    def import_glb(self, filepath: str, merge_vertices: bool = True, import_shading: str = "NORMALS") -> Dict[str, Any]:
        """Import a GLB/GLTF file into the Blender scene."""
        return self._dispatch_bound("import_glb", locals())

    def import_stl(
        self, filepath: str, forward_axis: str = "-Z", up_axis: str = "Y", scale: float = 1.0
    ) -> Dict[str, Any]:
        """Import an STL file (typically 3D print meshes)."""
        return self._dispatch_bound("import_stl", locals())

    def export_fbx(
        self,
        filepath: str,
        object_names: Optional[List[str]] = None,
        bake_anim: bool = True,
        use_selection: bool = False,
        apply_scale_options: str = "FBX",
    ) -> Dict[str, Any]:
        """Export scene (or selection) as FBX."""
        return self._dispatch_bound("export_fbx", locals())

    def export_glb(
        self,
        filepath: str,
        object_names: Optional[List[str]] = None,
        export_selected: bool = False,
        export_normals: bool = True,
        export_materials: bool = True,
        export_animations: bool = True,
        compression: bool = True,
    ) -> Dict[str, Any]:
        """Export scene as GLB (compressed GLTF, self-contained)."""
        return self._dispatch_bound("export_glb", locals())

    def export_obj(
        self,
        filepath: str,
        object_names: Optional[List[str]] = None,
        export_selected: bool = False,
        export_normals: bool = True,
        export_uv: bool = True,
        export_materials: bool = False,
        use_mesh_modifiers: bool = True,
        smooth_groups: bool = True,
    ) -> Dict[str, Any]:
        """Export scene as OBJ (wavefront format)."""
        return self._dispatch_bound("export_obj", locals())

    def export_stl(
        self, filepath: str, object_names: Optional[List[str]] = None, binary_format: bool = True
    ) -> Dict[str, Any]:
        """Export as STL (3D print format, no materials/animations)."""
        return self._dispatch_bound("export_stl", locals())

    def export_blend(self, filepath: str, relative_paths: bool = True, compress: bool = True) -> Dict[str, Any]:
        """Export current scene as a standalone .blend file."""
        return self._dispatch_bound("export_blend", locals())

    def export_animation_fbx(
        self,
        filepath: str,
        object_names: List[str],
        frame_start: int = 1,
        frame_end: int = 250,
        use_subsets: bool = False,
        subset_prefix: str = "",
    ) -> Dict[str, Any]:
        """Export only animation data for selected objects as FBX."""
        return self._dispatch_bound("export_animation_fbx", locals())

    def export_animation_gltf(
        self,
        filepath: str,
        object_names: List[str],
        frame_start: int = 1,
        frame_end: int = 250,
        compression: bool = True,
        export_all_transforms: bool = True,
    ) -> Dict[str, Any]:
        """Export animation as compressed GLB with animation data."""
        return self._dispatch_bound("export_animation_gltf", locals())

    def import_scene_blend(
        self,
        filepath: str,
        append_objects: Optional[List[str]] = None,
        append_materials: bool = False,
        link_library: bool = False,
    ) -> Dict[str, Any]:
        """Append/link objects from another .blend file."""
        return self._dispatch_bound("import_scene_blend", locals())

    def import_csv_data(
        self,
        filepath: str,
        target_object_name: str,
        position_column: str = "x",
        scale_column: str = "scale",
        object_type: str = "Sphere",
        count: int = 100,
    ) -> Dict[str, Any]:
        """Import CSV data and create objects at specified positions."""
        return self._dispatch_bound("import_csv_data", locals())

    def capture_scene_snapshot(
        self,
        filepath: str,
        include_rendered: bool = True,
        resolution: tuple = (1920, 1080),
        format: str = "PNG",
        quality: int = 95,
    ) -> Dict[str, Any]:
        """Capture a full scene snapshot including rendered image + metadata."""
        return self._dispatch_bound("capture_scene_snapshot", locals())

    def capture_viewport_snapshot(
        self,
        filepath: str,
        crop_to_bounds: bool = False,
        show_objects: bool = True,
        show_grid: bool = False,
        show_axes: bool = False,
        resolution_scale: float = 1.0,
    ) -> Dict[str, Any]:
        """Capture the current viewport as an image (no render)."""
        return self._dispatch_bound("capture_viewport_snapshot", locals())

    def capture_camera_view(
        self, camera_name: str, filepath: str, render_pass: str = "FINAL", resolution: tuple = (1920, 1080)
    ) -> Dict[str, Any]:
        """Render a specific camera view at a specific render pass."""
        return self._dispatch_bound("capture_camera_view", locals())

    def capture_all_cameras(
        self, output_dir: str, resolution: tuple = (1920, 1080), format: str = "PNG", render_pass: str = "FINAL"
    ) -> Dict[str, Any]:
        """Render and save images from all cameras in the scene."""
        return self._dispatch_bound("capture_all_cameras", locals())
