"""
Blender Advanced Object Operations API

High-level operations on Blender objects beyond basic mesh creation:
- Object selection/focus
- Scene save/load
- Render output
- Collections (grouping)
- Batch operations
- Material/node editor operations

This module is ADDITIVE — it does not modify existing code.
Import and use alongside the existing server.py tools.

Usage:
    from blender_mcp.advanced_objects import AdvancedObjectOperations

    ops = AdvancedObjectOperations()
    ops.save_scene(filepath="/path/to/file.blend")
    ops.create_collection("Foreground")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger("blender-mcp.advanced_objects")


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
# AdvancedObjectOperations — Stub Implementation
# ============================================================

class AdvancedObjectOperations:
    """
    High-level Blender object operations.

    Each method sends a command to the Blender addon via the existing
    TCP socket protocol. This is a stub — the actual bpy code executes
    inside the Blender addon process.

    This module does NOT modify addon.py. It extends functionality by
    sending new command types that the addon can handle.
    """

    def __init__(self, blender_connection=None):
        """
        Initialize with an existing BlenderConnection or create one.

        Args:
            blender_connection: Optional existing connection instance.
        """
        self._conn = blender_connection
        self._command_counter = 0

    def _next_command_id(self) -> str:
        self._command_counter += 1
        return f"cmd_{self._command_counter}"

    # ------------------------------------------------------------------ #
    # Object Selection & Focus
    # ------------------------------------------------------------------ #

    def select_object(self, object_name: str) -> Dict[str, Any]:
        """
        Select a single object in the Blender scene.

        Args:
            object_name: Name of the object to select.

        Returns:
            Dict with selection result and object info.
        """
        logger.info(f"select_object: {object_name}")
        # TODO: Send command to addon via TCP socket
        return {"selected": object_name, "status": "success"}

    def select_multiple_objects(self, object_names: List[str]) -> Dict[str, Any]:
        """
        Select multiple objects in the Blender scene.

        Args:
            object_names: List of object names to select.

        Returns:
            Dict with list of selected objects and deselected list.
        """
        logger.info(f"select_multiple_objects: {object_names}")
        return {"selected": object_names, "count": len(object_names), "status": "success"}

    def deselect_all(self) -> Dict[str, Any]:
        """Deselect all objects in the scene."""
        logger.info("deselect_all")
        return {"status": "success", "deselected_count": 0}

    def focus_camera_on_object(self, object_name: str, camera_name: str = "Camera") -> Dict[str, Any]:
        """
        Align a camera to point at a specific object.

        Args:
            object_name: Target object to focus on.
            camera_name: Camera to align (default: "Camera").

        Returns:
            Dict with camera transformation update info.
        """
        logger.info(f"focus_camera_on_object: camera={camera_name} -> {object_name}")
        return {"camera": camera_name, "target": object_name, "status": "success"}

    def focus_camera_isometric(self, camera_name: str = "Camera") -> Dict[str, Any]:
        """
        Set camera to isometric (orthographic) view.

        Args:
            camera_name: Camera to modify (default: "Camera").

        Returns:
            Dict with camera type change info.
        """
        logger.info(f"focus_camera_isometric: {camera_name}")
        return {"camera": camera_name, "type": "ORTHO", "status": "success"}

    # ------------------------------------------------------------------ #
    # Scene Save / Load
    # ------------------------------------------------------------------ #

    def save_scene(self, filepath: str, compress: bool = True) -> Dict[str, Any]:
        """
        Save the current Blender scene to a .blend file.

        Args:
            filepath: Target file path.
            compress: Whether to compress the blend file (default: True).

        Returns:
            Dict with save result and file size.
        """
        logger.info(f"save_scene: {filepath} compress={compress}")
        return {"filepath": filepath, "status": "saved"}

    def save_as_scene(self, filepath: str, compress: bool = True) -> Dict[str, Any]:
        """
        Save the current Blender scene as a new file (preserves current file).

        Args:
            filepath: Target file path.
            compress: Whether to compress (default: True).

        Returns:
            Dict with save-as result.
        """
        logger.info(f"save_as_scene: {filepath}")
        return {"filepath": filepath, "status": "saved_as"}

    def load_scene(self, filepath: str, keep_objects: bool = False) -> Dict[str, Any]:
        """
        Load a .blend file, optionally keeping existing objects.

        Args:
            filepath: Source blend file.
            keep_objects: If True, append objects instead of replacing.

        Returns:
            Dict with loaded scene info.
        """
        logger.info(f"load_scene: {filepath} keep={keep_objects}")
        return {"filepath": filepath, "append": keep_objects, "status": "loaded"}

    # ------------------------------------------------------------------ #
    # Render Output
    # ------------------------------------------------------------------ #

    def get_render_settings(self) -> Dict[str, Any]:
        """Get current render settings from the Blender scene."""
        logger.info("get_render_settings")
        return {"engine": "EEVEE", "resolution": [1920, 1080], "status": "success"}

    def set_render_settings(self, settings: Optional[RenderSettings] = None, **kwargs) -> Dict[str, Any]:
        """
        Configure render settings.

        Args:
            settings: RenderSettings dataclass instance (optional).
            **kwargs: Individual settings to override.
                engine: EEVEE or CYCLES
                resolution_x, resolution_y: Output resolution
                fps: Frames per second
                samples: Render samples
                output_format: PNG, JPEG, OPEN_EXR
                transparent: Enable alpha channel

        Returns:
            Dict with updated settings.
        """
        logger.info(f"set_render_settings: {kwargs}")
        return {"engine": kwargs.get("engine", "EEVEE"), "resolution": kwargs.get("resolution_x", 1920), "status": "updated"}

    def render_scene(self, filepath: Optional[str] = None, frame_range: Optional[tuple] = None) -> Dict[str, Any]:
        """
        Render the current scene.

        Args:
            filepath: Output path (default: uses render settings).
            frame_range: (start, end) frames to render (default: current frame).

        Returns:
            Dict with render job ID and expected output path.
        """
        logger.info(f"render_scene: frame_range={frame_range}")
        return {"status": "rendering", "output_path": filepath or "render_output.png"}

    def render_animation(self, filepath: str, frame_start: int = 1, frame_end: int = 250) -> Dict[str, Any]:
        """
        Render a full animation sequence.

        Args:
            filepath: Output directory or file pattern.
            frame_start: First frame (default: 1).
            frame_end: Last frame (default: 250).

        Returns:
            Dict with animation render job info.
        """
        logger.info(f"render_animation: {frame_start}-{frame_end} -> {filepath}")
        return {
            "status": "animating",
            "frames": frame_end - frame_start + 1,
            "output": filepath,
        }

    # ------------------------------------------------------------------ #
    # Collections (Grouping)
    # ------------------------------------------------------------------ #

    def create_collection(self, name: str, parent_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new collection (Blender's object grouping system).

        Args:
            name: Collection name.
            parent_name: Optional parent collection for nesting.

        Returns:
            Dict with created collection info.
        """
        logger.info(f"create_collection: {name} parent={parent_name}")
        return {"name": name, "parent": parent_name, "status": "created"}

    def add_to_collection(self, object_names: List[str], collection_name: str) -> Dict[str, Any]:
        """
        Move objects into a collection.

        Args:
            object_names: Objects to move.
            collection_name: Target collection.

        Returns:
            Dict with move results.
        """
        logger.info(f"add_to_collection: {object_names} -> {collection_name}")
        return {
            "collection": collection_name,
            "moved": object_names,
            "count": len(object_names),
            "status": "moved",
        }

    def remove_from_collection(self, object_names: List[str], collection_name: str) -> Dict[str, Any]:
        """
        Remove objects from a collection (does not delete objects).

        Args:
            object_names: Objects to remove.
            collection_name: Source collection.

        Returns:
            Dict with removal results.
        """
        logger.info(f"remove_from_collection: {object_names} from {collection_name}")
        return {"collection": collection_name, "removed": object_names, "status": "removed"}

    def list_collections(self) -> Dict[str, Any]:
        """List all collections and their structure."""
        logger.info("list_collections")
        return {"collections": [], "count": 0, "status": "success"}

    def get_collection_objects(self, collection_name: str) -> Dict[str, Any]:
        """
        Get all objects in a collection.

        Args:
            collection_name: Collection to query.

        Returns:
            Dict with object list and metadata.
        """
        logger.info(f"get_collection_objects: {collection_name}")
        return {"collection": collection_name, "objects": [], "count": 0, "status": "success"}

    # ------------------------------------------------------------------ #
    # Batch Operations
    # ------------------------------------------------------------------ #

    def batch_scale(self, object_names: List[str], factor: float) -> Dict[str, Any]:
        """
        Scale multiple objects by a uniform factor.

        Args:
            object_names: Objects to scale.
            factor: Scale multiplier (>1 to enlarge, <1 to shrink).

        Returns:
            Dict with per-object scale results.
        """
        logger.info(f"batch_scale: {object_names} x{factor}")
        return {"objects": object_names, "factor": factor, "count": len(object_names), "status": "scaled"}

    def batch_color(self, object_names: List[str], color: tuple) -> Dict[str, Any]:
        """
        Set diffuse color for multiple objects.

        Args:
            object_names: Objects to recolor.
            color: RGBA color tuple (0.0-1.0).

        Returns:
            Dict with per-object color results.
        """
        logger.info(f"batch_color: {object_names} color={color}")
        return {"objects": object_names, "color": color, "count": len(object_names), "status": "colored"}

    def batch_rotate(self, object_names: List[str], euler_rotation: tuple) -> Dict[str, Any]:
        """
        Rotate multiple objects by specified Euler angles.

        Args:
            object_names: Objects to rotate.
            euler_rotation: (X, Y, Z) rotation in radians.

        Returns:
            Dict with rotation results.
        """
        logger.info(f"batch_rotate: {object_names} rotation={euler_rotation}")
        return {"objects": object_names, "rotation": euler_rotation, "count": len(object_names), "status": "rotated"}

    def batch_duplicate(self, object_names: List[str], offset: tuple = (1.0, 0.0, 0.0), copies: int = 3) -> Dict[str, Any]:
        """
        Create copies of objects with positional offset.

        Args:
            object_names: Objects to duplicate.
            offset: (X, Y, Z) offset per copy.
            copies: Number of copies to create.

        Returns:
            Dict with created objects list.
        """
        logger.info(f"batch_duplicate: {object_names} offset={offset} copies={copies}")
        total = len(object_names) * copies
        return {"source": object_names, "copies": copies, "total_created": total, "status": "duplicated"}

    # ------------------------------------------------------------------ #
    # Material / Node Editor
    # ------------------------------------------------------------------ #

    def get_material(self, object_name: str) -> Dict[str, Any]:
        """
        Get material info for an object.

        Args:
            object_name: Object to query.

        Returns:
            Dict with material details.
        """
        logger.info(f"get_material: {object_name}")
        return {"object": object_name, "material": None, "status": "success"}

    def set_material_color(self, object_name: str, color: tuple) -> Dict[str, Any]:
        """
        Set the diffuse color of an object's material.

        Args:
            object_name: Object to update.
            color: RGBA color (0.0-1.0).

        Returns:
            Dict with update result.
        """
        logger.info(f"set_material_color: {object_name} color={color}")
        return {"object": object_name, "color": color, "status": "updated"}

    def create_material(self, name: str, color: tuple = (0.8, 0.8, 0.8, 1.0), metallic: float = 0.0, roughness: float = 0.5) -> Dict[str, Any]:
        """
        Create a new Principled BSDF material.

        Args:
            name: Material name.
            color: Diffuse color (RGBA, 0.0-1.0, default: gray).
            metallic: Metalness (0.0-1.0, default: 0.0).
            roughness: Roughness (0.0-1.0, default: 0.5).

        Returns:
            Dict with created material info.
        """
        logger.info(f"create_material: {name} metallic={metallic} roughness={roughness}")
        return {
            "name": name,
            "color": color,
            "metallic": metallic,
            "roughness": roughness,
            "status": "created",
        }

    def apply_material_to_object(self, material_name: str, object_name: str) -> Dict[str, Any]:
        """
        Assign a material to an object.

        Args:
            material_name: Material to assign.
            object_name: Object to receive the material.

        Returns:
            Dict with assignment result.
        """
        logger.info(f"apply_material_to_object: {material_name} -> {object_name}")
        return {"material": material_name, "object": object_name, "status": "applied"}

    def set_texture_to_material(
        self,
        material_name: str,
        texture_slot: str = "Base Color",
        image_path: Optional[str] = None,
        color_ramp: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        Apply a texture image to a material node.

        Args:
            material_name: Target material.
            texture_slot: Texture node slot (e.g., "Base Color", "Roughness", "Normal").
            image_path: Path to image file.
            color_ramp: Optional (min_color, max_color) for adjustment.

        Returns:
            Dict with texture application result.
        """
        logger.info(f"set_texture_to_material: {material_name} slot={texture_slot} image={image_path}")
        return {
            "material": material_name,
            "slot": texture_slot,
            "image": image_path,
            "status": "applied",
        }

    def get_node_tree(self, material_name: str) -> Dict[str, Any]:
        """
        Get the node tree structure for a material.

        Args:
            material_name: Material to inspect.

        Returns:
            Dict with node names, types, and connections.
        """
        logger.info(f"get_node_tree: {material_name}")
        return {"material": material_name, "nodes": [], "status": "success"}

    # --- Advanced Material/Node Editor ---

    def create_image_texture_node(self, material_name: str, image_path: str, slot: str = "Base Color",
                                   tile_x: int = 1, tile_y: int = 1, repeat: bool = False) -> Dict[str, Any]:
        """
        Create an Image Texture node and link it to a Principled BSDF slot.

        Args:
            material_name: Target material.
            image_path: Path to image file.
            slot: BSDF input slot (Base Color, Roughness, Normal, Metallic, Emission, Displacement).
            tile_x: U tiling (default: 1).
            tile_y: V tiling (default: 1).
            repeat: Whether to repeat texture (default: False).

        Returns:
            Dict with created node info and link.
        """
        logger.info(f"create_image_texture_node: {material_name} image={image_path} slot={slot} tile=({tile_x},{tile_y})")
        return {
            "material": material_name,
            "node_type": "TEX_IMAGE",
            "image": image_path,
            "slot": slot,
            "tile": (tile_x, tile_y),
            "repeat": repeat,
            "status": "created",
        }

    def create_procedural_texture(self, material_name: str, texture_type: str = "Checker",
                                  slot: str = "Base Color", scale: float = 5.0,
                                  color1: tuple = (0.0, 0.0, 0.0, 1.0),
                                  color2: tuple = (1.0, 1.0, 1.0, 1.0)) -> Dict[str, Any]:
        """
        Create a procedural texture node and link it.

        Supported types: Checker, Block, Gradient (Linear/Stairs/Radial),
        Musgrave (Fbm/Multifractal/Multi/Hybrid), Voronoi, Noise, Magic, Cell.

        Args:
            material_name: Target material.
            texture_type: Procedural texture type.
            slot: BSDF input slot.
            scale: Texture scale (default: 5.0).
            color1: First color (for Checker/Block).
            color2: Second color (for Checker/Block).

        Returns:
            Dict with created procedural texture node info.
        """
        supported = ["Checker", "Block", "Gradient", "Musgrave", "Voronoi", "Noise", "Magic", "Cell"]
        if texture_type not in supported:
            logger.warning(f"Unsupported procedural texture type: {texture_type}")
            return {"status": "error", "error": f"Type must be one of {supported}"}
        logger.info(f"create_procedural_texture: {material_name} type={texture_type} scale={scale} slot={slot}")
        return {
            "material": material_name,
            "node_type": "TEX_PROCEDURAL",
            "texture_type": texture_type,
            "scale": scale,
            "color1": color1,
            "color2": color2,
            "slot": slot,
            "status": "created",
        }

    def create_color_ramp(self, material_name: str, slot: str = "Base Color",
                         stops: Optional[list] = None) -> Dict[str, Any]:
        """
        Create a ColorRamp node and insert it in the material node tree.

        Args:
            material_name: Target material.
            slot: The output slot to connect through this ramp.
            stops: List of (factor, color) tuples for ramp stops. Default gradient: black to white.

        Returns:
            Dict with color ramp info.
        """
        if stops is None:
            stops = [(0.0, (0.0, 0.0, 0.0, 1.0)), (1.0, (1.0, 1.0, 1.0, 1.0))]
        logger.info(f"create_color_ramp: {material_name} stops={len(stops)} slot={slot}")
        return {
            "material": material_name,
            "node_type": "COLOR_RAMP",
            "slot": slot,
            "stops": stops,
            "status": "created",
        }

    def mix_shaders(self, material_name: str, shader1: str = "Principled BSDF",
                    shader2: str = "Principled BSDF",
                    blend_factor: float = 0.5, output_material: Optional[str] = None) -> Dict[str, Any]:
        """
        Mix two shaders using a Mix Shader node.

        Args:
            material_name: Target material (or a new one created for the mix).
            shader1: First shader name/type (default: Principled BSDF).
            shader2: Second shader name/type (default: Principled BSDF).
            blend_factor: Mix factor 0.0-1.0 (default: 0.5).
            output_material: Optional output material name (for multi-material).

        Returns:
            Dict with mix shader info.
        """
        logger.info(f"mix_shaders: {material_name} s1={shader1} s2={shader2} factor={blend_factor}")
        return {
            "material": material_name,
            "node_type": "MIX_SHADER",
            "shader1": shader1,
            "shader2": shader2,
            "blend_factor": blend_factor,
            "output_material": output_material,
            "status": "created",
        }

    def create_emission_material(self, name: str, color: tuple = (1.0, 1.0, 1.0, 1.0),
                                 strength: float = 1.0) -> Dict[str, Any]:
        """
        Create an emission-only material for self-illuminated surfaces.

        Args:
            name: Material name.
            color: Emission color (RGB, 0.0-1.0).
            strength: Emission strength multiplier (default: 1.0).

        Returns:
            Dict with created emission material.
        """
        logger.info(f"create_emission_material: {name} color={color} strength={strength}")
        return {
            "name": name,
            "type": "EMISSION",
            "color": color,
            "strength": strength,
            "status": "created",
        }

    def set_normal_map(self, material_name: str, texture_path: str, strength: float = 1.0,
                       color_ramp: Optional[tuple] = None) -> Dict[str, Any]:
        """
        Create a Normal Map node with a texture and link to BSDF Normal input.

        Args:
            material_name: Target material.
            texture_path: Path to normal map image.
            strength: Normal map strength (default: 1.0).
            color_ramp: Optional (min, max) for pre-processing.

        Returns:
            Dict with normal map setup info.
        """
        logger.info(f"set_normal_map: {material_name} texture={texture_path} strength={strength}")
        return {
            "material": material_name,
            "node_type": "NORMAL_MAP",
            "texture": texture_path,
            "strength": strength,
            "status": "applied",
        }

    def set_displacement(self, material_name: str, texture_path: str, method: str = "Bump",
                         displacement_material: str = "Material Output") -> Dict[str, Any]:
        """
        Set up displacement (Bump or Displacement) node.

        Args:
            material_name: Target material.
            texture_path: Displacement height map image path.
            method: "Bump" (approximate) or "Displacement" (real geometry).
            displacement_material: Output material name (default: "Material Output").

        Returns:
            Dict with displacement setup info.
        """
        logger.info(f"set_displacement: {material_name} method={method} texture={texture_path}")
        return {
            "material": material_name,
            "method": method,
            "texture": texture_path,
            "output": displacement_material,
            "status": "applied",
        }

    def create_material_group(self, name: str, node_type: str = "Group",
                              inputs: Optional[list] = None) -> Dict[str, Any]:
        """
        Create a material node group for reuse across materials.

        Args:
            name: Group name.
            node_type: "Group" (generic) or specific type.
            inputs: List of input names for the group interface.

        Returns:
            Dict with group info.
        """
        if inputs is None:
            inputs = ["Color", "Metallic", "Roughness"]
        logger.info(f"create_material_group: {name} type={node_type} inputs={inputs}")
        return {
            "name": name,
            "type": node_type,
            "inputs": inputs,
            "status": "created",
        }

    def clone_material(self, source_material_name: str, target_name: str) -> Dict[str, Any]:
        """
        Clone a material (copy all nodes and settings).

        Args:
            source_material_name: Material to copy from.
            target_name: New material name.

        Returns:
            Dict with clone info.
        """
        logger.info(f"clone_material: {source_material_name} -> {target_name}")
        return {
            "source": source_material_name,
            "target": target_name,
            "status": "cloned",
        }

    def clear_node_tree(self, material_name: str, keep_bsdf: bool = False) -> Dict[str, Any]:
        """
        Clear all nodes from a material's node tree.

        Args:
            material_name: Target material.
            keep_bsdf: If True, keep the Principled BSDF node (default: False).

        Returns:
            Dict with clearing result.
        """
        logger.info(f"clear_node_tree: {material_name} keep_bsdf={keep_bsdf}")
        return {"material": material_name, "kept_bsdf": keep_bsdf, "status": "cleared"}

    def set_anisotropic(self, material_name: str, anisotropy: float = 0.5,
                        anisotropy_rotation: float = 0.0) -> Dict[str, Any]:
        """
        Set anisotropic parameters on a Principled BSDF material.

        Args:
            material_name: Target material.
            anisotropy: Anisotropy amount (0.0 = isotropic, 1.0 = max anisotropic).
            anisotropy_rotation: Anisotropy rotation in radians.

        Returns:
            Dict with anisotropic settings.
        """
        logger.info(f"set_anisotropic: {material_name} aniso={anisotropy} rot={anisotropy_rotation}")
        return {
            "material": material_name,
            "anisotropy": anisotropy,
            "anisotropy_rotation": anisotropy_rotation,
            "status": "updated",
        }

    def set_transparency(self, material_name: str, alpha: float = 1.0,
                         blend_mode: str = "OPAQUE") -> Dict[str, Any]:
        """
        Set transparency/alpha blending on a material.

        Args:
            material_name: Target material.
            alpha: Alpha value (0.0 = fully transparent, 1.0 = opaque).
            blend_mode: "OPAQUE", "CLIP", or "BLEND".

        Returns:
            Dict with transparency settings.
        """
        logger.info(f"set_transparency: {material_name} alpha={alpha} blend={blend_mode}")
        return {
            "material": material_name,
            "alpha": alpha,
            "blend_mode": blend_mode,
            "status": "updated",
        }

    def setup_ior(self, material_name: str, ior: float = 1.45) -> Dict[str, Any]:
        """
        Set Index of Refraction (IOR) for transparent/refractive materials.

        Args:
            material_name: Target material.
            ior: Index of refraction (default: 1.45 = glass).

        Returns:
            Dict with IOR settings.
        """
        logger.info(f"setup_ior: {material_name} ior={ior}")
        return {
            "material": material_name,
            "ior": ior,
            "status": "updated",
        }

    # ------------------------------------------------------------------ #
    # Object Transform & Alignment
    # ------------------------------------------------------------------ #

    def align_to_world_axis(self, object_name: str, axis: str = "Z") -> Dict[str, Any]:
        """
        Align an object's rotation to a world axis.

        Args:
            object_name: Object to align.
            axis: Target axis ("X", "Y", or "Z").

        Returns:
            Dict with rotation update.
        """
        logger.info(f"align_to_world_axis: {object_name} axis={axis}")
        return {"object": object_name, "axis": axis, "status": "aligned"}

    def snap_to_grid(self, object_name: str, grid_size: float = 0.01) -> Dict[str, Any]:
        """
        Snap an object's position to the nearest grid point.

        Args:
            object_name: Object to snap.
            grid_size: Grid precision.

        Returns:
            Dict with old and new position.
        """
        logger.info(f"snap_to_grid: {object_name} grid={grid_size}")
        return {"object": object_name, "grid_size": grid_size, "status": "snapped"}

    def center_object_origin(self, object_name: str) -> Dict[str, Any]:
        """
        Move an object's origin to its geometric center.

        Args:
            object_name: Object to fix.

        Returns:
            Dict with origin relocation info.
        """
        logger.info(f"center_object_origin: {object_name}")
        return {"object": object_name, "origin": "center", "status": "centered"}

    def get_bounding_box(self, object_name: str) -> Dict[str, Any]:
        """
        Get the AABB bounding box of an object in world space.

        Args:
            object_name: Object to inspect.

        Returns:
            Dict with bounding box coordinates and dimensions.
        """
        logger.info(f"get_bounding_box: {object_name}")
        return {
            "object": object_name,
            "bbox": {
                "min": [0.0, 0.0, 0.0],
                "max": [1.0, 1.0, 1.0],
            },
            "dimensions": [1.0, 1.0, 1.0],
            "center": [0.5, 0.5, 0.5],
            "status": "success",
        }

    # ------------------------------------------------------------------ #
    # Lighting & Environment
    # ------------------------------------------------------------------ #

    def set_studio_lighting(self, preset: str = "three_point") -> Dict[str, Any]:
        """
        Apply a studio lighting preset to the scene.

        Args:
            preset: Lighting preset name.
                - "three_point": Key, fill, and back lights
                - "rim_only": Rim/edge lighting only
                - "area_top": Single top area light
                - "sun_only": Single sun light
                - "studio_soft": Soft area light box

        Returns:
            Dict with applied lights list.
        """
        logger.info(f"set_studio_lighting: preset={preset}")
        presets = {
            "three_point": ["Key Light", "Fill Light", "Back Light"],
            "rim_only": ["Rim Light"],
            "area_top": ["Top Area"],
            "sun_only": ["Sun Light"],
            "studio_soft": ["Soft Area"],
        }
        return {"preset": preset, "lights": presets.get(preset, []), "status": "applied"}

    def set_environment_lighting(
        self,
        world_color: tuple = (0.05, 0.05, 0.08, 1.0),
        world_strength: float = 1.0,
        use_texture: bool = False,
        texture_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Configure the scene's world lighting.

        Args:
            world_color: World background color (RGBA).
            world_strength: Light intensity multiplier.
            use_texture: Whether to use an HDRI/world texture.
            texture_path: Path to HDRI image if use_texture=True.

        Returns:
            Dict with world lighting config.
        """
        logger.info(f"set_environment_lighting: texture={use_texture} path={texture_path}")
        return {
            "world_color": world_color,
            "strength": world_strength,
            "use_texture": use_texture,
            "status": "applied",
        }

    # ------------------------------------------------------------------ #
    # Camera Configuration
    # ------------------------------------------------------------------ #

    def create_camera(
        self,
        name: str = "Camera",
        location: tuple = (5.0, -5.0, 3.0),
        rotation: tuple = (-0.5, 0.0, 0.3),
        lens: float = 50.0,
        sensor_width: float = 36.0,
    ) -> Dict[str, Any]:
        """
        Create a new camera with specified position and lens.

        Args:
            name: Camera name.
            location: (X, Y, Z) position.
            rotation: (X, Y, Z) rotation in radians.
            lens: Focal length in mm (default: 50mm).
            sensor_width: Sensor width in mm (default: 36mm).

        Returns:
            Dict with created camera info.
        """
        logger.info(f"create_camera: {name}")
        return {
            "name": name,
            "location": location,
            "rotation": rotation,
            "lens": lens,
            "sensor_width": sensor_width,
            "type": "PERSP",
            "status": "created",
        }

    def get_camera_info(self, camera_name: str = "Camera") -> Dict[str, Any]:
        """
        Get detailed camera information.

        Args:
            camera_name: Camera to inspect.

        Returns:
            Dict with camera type, lens, sensor, resolution.
        """
        logger.info(f"get_camera_info: {camera_name}")
        return {
            "name": camera_name,
            "type": "PERSP",
            "lens": 50.0,
            "sensor_width": 36.0,
            "resolution": [1920, 1080],
            "status": "success",
        }

    # ------------------------------------------------------------------ #
    # Utility / Diagnostics
    # ------------------------------------------------------------------ #

    def get_scene_summary(self) -> Dict[str, Any]:
        """
        Get a full scene summary including objects, collections, materials, cameras.

        Returns:
            Dict with complete scene state.
        """
        logger.info("get_scene_summary")
        return {
            "objects": [],
            "collections": [],
            "materials": [],
            "cameras": [],
            "lights": [],
            "status": "success",
        }

    def get_duplicate_objects(self) -> Dict[str, Any]:
        """
        Find objects with identical names in the scene.

        Returns:
            Dict with duplicate name groups.
        """
        logger.info("get_duplicate_objects")
        return {"duplicates": {}, "unique_count": 0, "status": "success"}

    def clear_unreferenced_data(self) -> Dict[str, Any]:
        """
        Remove unreferenced data blocks (orphan data).

        Returns:
            Dict with freed data count.
        """
        logger.info("clear_unreferenced_data")
        return {"freed_data": 0, "status": "cleared"}

    # ------------------------------------------------------------------ #
    # Advanced Batch Operations
    # ------------------------------------------------------------------ #

    def batch_apply_material(
        self,
        object_names: List[str],
        material_name: str,
        replace_existing: bool = True,
    ) -> Dict[str, Any]:
        """
        Apply the same material to multiple objects in one operation.

        Args:
            object_names: Objects to assign material to.
            material_name: Material to apply.
            replace_existing: If True, replace current material (default: True).

        Returns:
            Dict with per-object material assignment result.
        """
        logger.info(f"batch_apply_material: {object_names} -> {material_name}")
        return {
            "material": material_name,
            "objects": object_names,
            "count": len(object_names),
            "replace_existing": replace_existing,
            "status": "applied",
        }

    def batch_set_transform(
        self,
        object_names: List[str],
        location: Optional[tuple] = None,
        rotation: Optional[tuple] = None,
        scale: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        Set transform (location, rotation, scale) for multiple objects.

        Args:
            object_names: Objects to transform.
            location: (X, Y, Z) position.
            rotation: (X, Y, Z) Euler rotation in radians.
            scale: (X, Y, Z) scale factors.

        Returns:
            Dict with per-object transform update results.
        """
        logger.info(f"batch_set_transform: {object_names} loc={location} rot={rotation} scl={scale}")
        return {
            "objects": object_names,
            "location": location,
            "rotation": rotation,
            "scale": scale,
            "count": len(object_names),
            "status": "transformed",
        }

    def batch_make_duplicates(
        self,
        object_names: List[str],
        count_per_object: int = 2,
        offset: tuple = (1.0, 0.0, 0.0),
        randomize: bool = False,
    ) -> Dict[str, Any]:
        """
        Create duplicates of objects with configurable spacing and optional randomization.

        Args:
            object_names: Objects to duplicate.
            count_per_object: Number of copies per object (default: 2).
            offset: (X, Y, Z) spacing between copies.
            randomize: If True, add random offset to each copy.

        Returns:
            Dict with created objects list and count.
        """
        total = len(object_names) * count_per_object
        logger.info(f"batch_make_duplicates: {object_names} x{count_per_object} offset={offset} random={randomize}")
        return {
            "source": object_names,
            "copies_per_object": count_per_object,
            "total_created": total,
            "offset": offset,
            "randomized": randomize,
            "status": "duplicated",
        }

    def batch_delete(
        self,
        object_names: List[str],
        also_clearance: bool = False,
        also_materials: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete multiple objects from the scene.

        Args:
            object_names: Objects to delete.
            also_clearance: Also remove linked mesh data (default: False).
            also_materials: Also remove assigned materials (default: False).

        Returns:
            Dict with deletion results.
        """
        logger.info(f"batch_delete: {object_names}")
        return {
            "deleted": object_names,
            "count": len(object_names),
            "also_clearance": also_clearance,
            "also_materials": also_materials,
            "status": "deleted",
        }

    def batch_set_visibility(
        self,
        object_names: List[str],
        visible: bool = True,
        hide_render: bool = False,
        hide_select: bool = False,
    ) -> Dict[str, Any]:
        """
        Set visibility state for multiple objects.

        Args:
            object_names: Objects to modify.
            visible: Overall visibility (default: True).
            hide_render: Hide from render (default: False).
            hide_select: Hide from viewport select (default: False).

        Returns:
            Dict with visibility update results.
        """
        logger.info(f"batch_set_visibility: {object_names} visible={visible}")
        return {
            "objects": object_names,
            "count": len(object_names),
            "visible": visible,
            "hide_render": hide_render,
            "hide_select": hide_select,
            "status": "visibility_updated",
        }

    def batch_make_parent(
        self,
        child_names: List[str],
        parent_name: str,
        keep_transform: bool = True,
    ) -> Dict[str, Any]:
        """
        Make multiple objects children of a single parent.

        Args:
            child_names: Objects to parent.
            parent_name: Parent object name.
            keep_transform: If True, keep world transform (default: True).

        Returns:
            Dict with parenting results.
        """
        logger.info(f"batch_make_parent: {child_names} -> {parent_name}")
        return {
            "parent": parent_name,
            "children": child_names,
            "count": len(child_names),
            "keep_transform": keep_transform,
            "status": "parented",
        }

    def batch_make_empty_group(
        self,
        object_names: List[str],
        group_name: str = "SelectionGroup",
        create_collection: bool = False,
    ) -> Dict[str, Any]:
        """
        Create an Empty parent for a group of objects and group them.

        Args:
            object_names: Objects to group.
            group_name: Name of the Empty parent.
            create_collection: Also create a Collection with this name.

        Returns:
            Dict with group creation results.
        """
        logger.info(f"batch_make_empty_group: {object_names} -> {group_name}")
        return {
            "group_name": group_name,
            "members": object_names,
            "count": len(object_names),
            "create_collection": create_collection,
            "status": "grouped",
        }

    def batch_apply_modifiers(
        self,
        object_names: List[str],
        modifier_names: Optional[List[str]] = None,
        apply_all: bool = True,
    ) -> Dict[str, Any]:
        """
        Apply specified modifiers (or all) on multiple objects.

        Args:
            object_names: Objects to apply modifiers on.
            modifier_names: Specific modifier names to apply. If None, applies all.
            apply_all: If True, ignore modifier_names and apply all (default: True).

        Returns:
            Dict with modifier application results.
        """
        logger.info(f"batch_apply_modifiers: {object_names}")
        return {
            "objects": object_names,
            "modifier_names": modifier_names,
            "apply_all": apply_all,
            "count": len(object_names),
            "status": "modifiers_applied",
        }

    def batch_mirror(
        self,
        object_names: List[str],
        axis: str = "X",
        merge_vertices: bool = True,
        use_clip: bool = True,
    ) -> Dict[str, Any]:
        """
        Apply Mirror modifier to multiple objects (non-destructive).

        Args:
            object_names: Objects to mirror.
            axis: Mirror axis ("X", "Y", or "Z", default: "X").
            merge_vertices: Merge vertices at mirror seam (default: True).
            use_clip: Clip geometry at mirror seam (default: True).

        Returns:
            Dict with mirror settings.
        """
        logger.info(f"batch_mirror: {object_names} axis={axis}")
        return {
            "objects": object_names,
            "axis": axis,
            "merge_vertices": merge_vertices,
            "use_clip": use_clip,
            "count": len(object_names),
            "status": "mirrored",
        }

    def batch_instance_on_points(
        self,
        template_object_names: List[str],
        points_object_name: str,
        random_rotation: bool = False,
        random_scale: bool = False,
    ) -> Dict[str, Any]:
        """
        Use geometry nodes to instance objects on points of another object.

        Args:
            template_object_names: Objects to instantiate.
            points_object_name: Object providing the points/curve/mesh.
            random_rotation: Randomize instance rotation (default: False).
            random_scale: Randomize instance scale (default: False).

        Returns:
            Dict with instancing setup results.
        """
        logger.info(f"batch_instance_on_points: {template_object_names} on {points_object_name}")
        return {
            "templates": template_object_names,
            "points_object": points_object_name,
            "random_rotation": random_rotation,
            "random_scale": random_scale,
            "status": "instanced",
        }

    def batch_align_bounding_boxes(
        self,
        object_names: List[str],
        alignment: str = "center",
        reference: str = "world",
    ) -> Dict[str, Any]:
        """
        Align bounding box centers of multiple objects.

        Args:
            object_names: Objects to align.
            alignment: "center", "min", or "max".
            reference: Align to "world" or to first object in list.

        Returns:
            Dict with alignment results.
        """
        logger.info(f"batch_align_bounding_boxes: {object_names} align={alignment}")
        return {
            "objects": object_names,
            "alignment": alignment,
            "reference": reference,
            "count": len(object_names),
            "status": "aligned",
        }

    # ------------------------------------------------------------------ #
    # Advanced Render Automation
    # ------------------------------------------------------------------ #

    def set_render_eevee(
        self,
        samples: int = 128,
        denoise: bool = True,
        tile_size: int = 32,
        taa_samples: int = 128,
    ) -> Dict[str, Any]:
        """
        Configure Eevee render engine settings.

        Args:
            samples: Render samples (default: 128).
            denoise: Enable denoising (default: True).
            tile_size: Tile size for rendering (default: 32).
            taa_samples: TAA samples for motion blur (default: 128).

        Returns:
            Dict with Eevee settings.
        """
        logger.info(f"set_render_eevee: samples={samples} denoise={denoise}")
        return {
            "engine": "EEVEE",
            "samples": samples,
            "denoise": denoise,
            "tile_size": tile_size,
            "taa_samples": taa_samples,
            "status": "configured",
        }

    def set_render_cycles(
        self,
        samples: int = 1024,
        denoise: bool = True,
        engine: str = "OPTIX",
        use_denoising: bool = True,
    ) -> Dict[str, Any]:
        """
        Configure Cycles render engine settings.

        Args:
            samples: Render samples (default: 1024).
            denoise: Enable denoising (default: True).
            engine: Acceleration device ("OPTIX", "CUDA", "HIP", "CPU").
            use_denoising: Use OptiX/CUDA denoiser (default: True).

        Returns:
            Dict with Cycles settings.
        """
        valid_engines = ["OPTIX", "CUDA", "HIP", "CPU", "BLENDER_EEVEE"]
        if engine not in valid_engines:
            return {"status": "error", "error": f"Engine must be one of {valid_engines}"}
        logger.info(f"set_render_cycles: samples={samples} engine={engine}")
        return {
            "engine": "CYCLES",
            "samples": samples,
            "denoise": denoise,
            "acceleration": engine,
            "use_denoising": use_denoising,
            "status": "configured",
        }

    def set_render_output(
        self,
        filepath: str,
        format: str = "PNG",
        color_depth: str = "16",
        compression: int = 15,
        transparent: bool = False,
        ffmpeg: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Configure render output path, format, and quality.

        Args:
            filepath: Output file path or directory.
            format: Image format (PNG, JPEG, OPEN_EXR, TIFF, BMP, SVG).
            color_depth: Color depth (8 or 16 for PNG/JPEG/TIFF, 16/32 for EXR).
            compression: JPEG/PNG compression (0-100, default: 15).
            transparent: Enable alpha channel (default: False).
            ffmpeg: Optional dict for video render settings {codec, quality, fps}.

        Returns:
            Dict with output configuration.
        """
        valid_formats = ["PNG", "JPEG", "OPEN_EXR", "TIFF", "BMP", "SVG", "QTR"]
        if format not in valid_formats:
            return {"status": "error", "error": f"Format must be one of {valid_formats}"}
        logger.info(f"set_render_output: {filepath} format={format} depth={color_depth}")
        return {
            "filepath": filepath,
            "format": format,
            "color_depth": color_depth,
            "compression": compression,
            "transparent": transparent,
            "ffmpeg": ffmpeg,
            "status": "configured",
        }

    def render_viewport(
        self,
        filepath: str,
        quality: int = 95,
        resolution_scale: float = 1.0,
        crop_to_bounds: bool = False,
    ) -> Dict[str, Any]:
        """
        Render the current viewport (what's visible in the 3D view).

        Args:
            filepath: Output file path.
            quality: JPEG quality 1-100 (default: 95). Used for non-PNG formats.
            resolution_scale: Resolution multiplier (0.25 to 1.0, default: 1.0).
            crop_to_bounds: Crop to selected objects only (default: False).

        Returns:
            Dict with render result info.
        """
        logger.info(f"render_viewport: {filepath} quality={quality} scale={resolution_scale}")
        return {
            "filepath": filepath,
            "type": "viewport",
            "quality": quality,
            "resolution_scale": resolution_scale,
            "crop_to_bounds": crop_to_bounds,
            "status": "rendering",
        }

    def render_animation_batch(
        self,
        filepath: str,
        frame_start: int = 1,
        frame_end: int = 250,
        frame_step: int = 1,
        format: str = "FFMPEG",
        ffmpeg_settings: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Render a full animation sequence in batch mode.

        Args:
            filepath: Output directory or video file path.
            frame_start: First frame (default: 1).
            frame_end: Last frame (default: 250).
            frame_step: Render every Nth frame (default: 1).
            format: Output format (PNG sequence, FFMPEG video, etc.).
            ffmpeg_settings: Dict with {codec, quality, fps, audio}.

        Returns:
            Dict with animation render job info.
        """
        num_frames = ((frame_end - frame_start) // frame_step) + 1
        logger.info(f"render_animation_batch: frames {frame_start}-{frame_end} step={frame_step} -> {filepath}")
        return {
            "type": "animation_batch",
            "frame_start": frame_start,
            "frame_end": frame_end,
            "frame_step": frame_step,
            "total_frames": num_frames,
            "format": format,
            "filepath": filepath,
            "ffmpeg_settings": ffmpeg_settings,
            "status": "queued",
        }

    def render_multi_view(
        self,
        filepath: str,
        camera_angles: Optional[list] = None,
        format: str = "PNG",
    ) -> Dict[str, Any]:
        """
        Render the scene from multiple camera angles.

        Args:
            filepath: Output directory.
            camera_angles: List of camera definitions. Each: {name, location, rotation}.
                           If None, renders from 4 cardinal angles.
            format: Output format.

        Returns:
            Dict with multi-view render info.
        """
        default_angles = [
            {"name": "front", "location": (0, -5, 2), "rotation": (0, 0, 0)},
            {"name": "back", "location": (0, 5, 2), "rotation": (0, 3.14159, 0)},
            {"name": "left", "location": (-5, 0, 2), "rotation": (0, 1.5708, 0)},
            {"name": "right", "location": (5, 0, 2), "rotation": (0, -1.5708, 0)},
            {"name": "top", "location": (0, 0, 8), "rotation": (-1.5708, 0, 0)},
        ]
        angles = camera_angles or default_angles
        logger.info(f"render_multi_view: {len(angles)} angles -> {filepath}")
        return {
            "type": "multi_view",
            "angles": angles,
            "format": format,
            "filepath": filepath,
            "status": "queued",
        }

    def render_360_panorama(
        self,
        filepath: str,
        fov: float = 180.0,
        resolution: tuple = (4096, 2048),
        format: str = "PNG",
    ) -> Dict[str, Any]:
        """
        Render a 360-degree equirectangular panorama.

        Args:
            filepath: Output file path (must be .png).
            fov: Field of view (default: 180 degrees).
            resolution: Output resolution (width, height, default: 4096x2048).
            format: Output format (default: PNG).

        Returns:
            Dict with panorama render settings.
        """
        logger.info(f"render_360_panorama: {filepath} fov={fov} resolution={resolution}")
        return {
            "type": "panorama_360",
            "fov": fov,
            "resolution": resolution,
            "format": format,
            "filepath": filepath,
            "status": "queued",
        }

    def set_render_camera(self, camera_name: str) -> Dict[str, Any]:
        """
        Set the active render camera.

        Args:
            camera_name: Name of the camera to use for rendering.

        Returns:
            Dict with camera selection result.
        """
        logger.info(f"set_render_camera: {camera_name}")
        return {"camera": camera_name, "status": "selected"}

    def render_preview(
        self,
        filepath: str,
        resolution_scale: float = 0.5,
        samples: int = 64,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Render a low-quality preview image quickly.

        Args:
            filepath: Output file path.
            resolution_scale: Resolution multiplier (0.5 for half-res, default).
            samples: Render samples for preview (default: 64).
            timeout: Max render time in seconds (default: 30).

        Returns:
            Dict with preview render info.
        """
        logger.info(f"render_preview: {filepath} scale={resolution_scale} samples={samples}")
        return {
            "type": "preview",
            "filepath": filepath,
            "resolution_scale": resolution_scale,
            "samples": samples,
            "timeout": timeout,
            "status": "rendering",
        }

    def get_render_info(self) -> Dict[str, Any]:
        """
        Get the current full render configuration summary.

        Returns:
            Dict with all render settings.
        """
        logger.info("get_render_info")
        return {
            "engine": "EEVEE",
            "samples": 128,
            "resolution": [1920, 1080],
            "output_format": "PNG",
            "fps": 24,
            "frame_range": [1, 250],
            "denoise": True,
            "status": "success",
        }

    # ------------------------------------------------------------------ #
    # Animation Data Import/Export
    # ------------------------------------------------------------------ #

    def import_fbx(
        self,
        filepath: str,
        automatic_orientation: bool = True,
        import_hardware: bool = True,
        force_connect_children: bool = False,
    ) -> Dict[str, Any]:
        """
        Import an FBX file into the Blender scene.

        Args:
            filepath: Path to .fbx file.
            automatic_orientation: Auto-orient to Y-up (default: True).
            import_hardware: Import camera/light objects (default: True).
            force_connect_children: Force connect child objects to parents.

        Returns:
            Dict with import results.
        """
        logger.info(f"import_fbx: {filepath}")
        return {
            "filepath": filepath,
            "format": "FBX",
            "automatic_orientation": automatic_orientation,
            "import_hardware": import_hardware,
            "force_connect_children": force_connect_children,
            "status": "imported",
        }

    def import_obj(
        self,
        filepath: str,
        add_normals: bool = True,
        split_objects: bool = True,
        split_groups: bool = True,
        import_images: bool = True,
    ) -> Dict[str, Any]:
        """
        Import an OBJ file into the Blender scene.

        Args:
            filepath: Path to .obj file.
            add_normals: Import normal data (default: True).
            split_objects: Split OBJ objects into Blender objects (default: True).
            split_groups: Split OBJ groups into Blender collections (default: True).
            import_images: Import linked images (default: True).

        Returns:
            Dict with import results.
        """
        logger.info(f"import_obj: {filepath}")
        return {
            "filepath": filepath,
            "format": "OBJ",
            "add_normals": add_normals,
            "split_objects": split_objects,
            "split_groups": split_groups,
            "import_images": import_images,
            "status": "imported",
        }

    def import_glb(
        self,
        filepath: str,
        merge_vertices: bool = True,
        import_shading: str = "NORMALS",
    ) -> Dict[str, Any]:
        """
        Import a GLB/GLTF file into the Blender scene.

        Args:
            filepath: Path to .glb or .gltf file.
            merge_vertices: Merge duplicate vertices (default: True).
            import_shading: Shading import mode ("NORMALS", "COLOR", "IGNORE").

        Returns:
            Dict with import results.
        """
        logger.info(f"import_glb: {filepath}")
        return {
            "filepath": filepath,
            "format": "GLTF/GLB",
            "merge_vertices": merge_vertices,
            "import_shading": import_shading,
            "status": "imported",
        }

    def import_stl(
        self,
        filepath: str,
        forward_axis: str = "-Z",
        up_axis: str = "Y",
        scale: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Import an STL file (typically 3D print meshes).

        Args:
            filepath: Path to .stl file.
            forward_axis: Forward axis direction (default: "-Z").
            up_axis: Up axis direction (default: "Y").
            scale: Scale factor (default: 1.0).

        Returns:
            Dict with import results.
        """
        logger.info(f"import_stl: {filepath} scale={scale}")
        return {
            "filepath": filepath,
            "format": "STL",
            "forward_axis": forward_axis,
            "up_axis": up_axis,
            "scale": scale,
            "status": "imported",
        }

    def export_fbx(
        self,
        filepath: str,
        object_names: Optional[List[str]] = None,
        bake_anim: bool = True,
        use_selection: bool = False,
        apply_scale_options: str = "FBX",
    ) -> Dict[str, Any]:
        """
        Export scene (or selection) as FBX.

        Args:
            filepath: Output .fbx file path.
            object_names: Specific objects to export. If None, exports active scene.
            bake_anim: Bake animation into FBX (default: True).
            use_selection: Export only selected objects (default: False).
            apply_scale_options: FBX scale mode ("FBX", "METERS", "CENTI").

        Returns:
            Dict with export results.
        """
        logger.info(f"export_fbx: {filepath}")
        return {
            "filepath": filepath,
            "format": "FBX",
            "objects": object_names,
            "bake_anim": bake_anim,
            "use_selection": use_selection,
            "apply_scale_options": apply_scale_options,
            "status": "exported",
        }

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
        """
        Export scene as GLB (compressed GLTF, self-contained).

        Args:
            filepath: Output .glb file path.
            object_names: Specific objects to export.
            export_selected: Export only selected (default: False).
            export_normals: Include normal data (default: True).
            export_materials: Include materials (default: True).
            export_animations: Include animation data (default: True).
            compression: Compress using Draco (default: True).

        Returns:
            Dict with export results.
        """
        logger.info(f"export_glb: {filepath}")
        return {
            "filepath": filepath,
            "format": "GLB",
            "objects": object_names,
            "export_selected": export_selected,
            "export_normals": export_normals,
            "export_materials": export_materials,
            "export_animations": export_animations,
            "compression": compression,
            "status": "exported",
        }

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
        """
        Export scene as OBJ (wavefront format).

        Args:
            filepath: Output .obj file path.
            object_names: Specific objects to export.
            export_selected: Export only selected (default: False).
            export_normals: Include normal data (default: True).
            export_uv: Include UV coordinates (default: True).
            export_materials: Include MTL reference (default: False).
            use_mesh_modifiers: Apply modifiers before export (default: True).
            smooth_groups: Include smooth shading groups (default: True).

        Returns:
            Dict with export results.
        """
        logger.info(f"export_obj: {filepath}")
        return {
            "filepath": filepath,
            "format": "OBJ",
            "objects": object_names,
            "export_selected": export_selected,
            "export_normals": export_normals,
            "export_uv": export_uv,
            "export_materials": export_materials,
            "use_mesh_modifiers": use_mesh_modifiers,
            "smooth_groups": smooth_groups,
            "status": "exported",
        }

    def export_stl(
        self,
        filepath: str,
        object_names: Optional[List[str]] = None,
        binary_format: bool = True,
    ) -> Dict[str, Any]:
        """
        Export as STL (3D print format, no materials/animations).

        Args:
            filepath: Output .stl file path.
            object_names: Specific objects to export.
            binary_format: Binary STL (smaller) vs ASCII (default: True).

        Returns:
            Dict with export results.
        """
        logger.info(f"export_stl: {filepath}")
        return {
            "filepath": filepath,
            "format": "STL",
            "objects": object_names,
            "binary_format": binary_format,
            "status": "exported",
        }

    def export_blend(
        self,
        filepath: str,
        relative_paths: bool = True,
        compress: bool = True,
    ) -> Dict[str, Any]:
        """
        Export current scene as a standalone .blend file.

        Args:
            filepath: Output .blend file path.
            relative_paths: Write relative paths for textures (default: True).
            compress: Compress the blend file (default: True).

        Returns:
            Dict with export results.
        """
        logger.info(f"export_blend: {filepath}")
        return {
            "filepath": filepath,
            "format": "BLEND",
            "relative_paths": relative_paths,
            "compress": compress,
            "status": "exported",
        }

    def export_animation_fbx(
        self,
        filepath: str,
        object_names: List[str],
        frame_start: int = 1,
        frame_end: int = 250,
        use_subsets: bool = False,
        subset_prefix: str = "",
    ) -> Dict[str, Any]:
        """
        Export only animation data for selected objects as FBX.

        Args:
            filepath: Output .fbx file path.
            object_names: Objects whose animation to export.
            frame_start: First frame to bake (default: 1).
            frame_end: Last frame to bake (default: 250).
            use_subsets: Create separate FBX for each object.
            subset_prefix: Prefix for subset filenames.

        Returns:
            Dict with animation export results.
        """
        logger.info(f"export_animation_fbx: {filepath} frames {frame_start}-{frame_end}")
        return {
            "filepath": filepath,
            "format": "FBX_ANIMATION",
            "objects": object_names,
            "frame_start": frame_start,
            "frame_end": frame_end,
            "frame_count": frame_end - frame_start + 1,
            "use_subsets": use_subsets,
            "subset_prefix": subset_prefix,
            "status": "exported",
        }

    def export_animation_gltf(
        self,
        filepath: str,
        object_names: List[str],
        frame_start: int = 1,
        frame_end: int = 250,
        compression: bool = True,
        export_all_transforms: bool = True,
    ) -> Dict[str, Any]:
        """
        Export animation as compressed GLB with animation data.

        Args:
            filepath: Output .glb file path.
            object_names: Objects whose animation to export.
            frame_start: First frame (default: 1).
            frame_end: Last frame (default: 250).
            compression: Use Draco compression (default: True).
            export_all_transforms: Export location/rotation/scale (default: True).

        Returns:
            Dict with GLTF animation export results.
        """
        logger.info(f"export_animation_gltf: {filepath} frames {frame_start}-{frame_end}")
        return {
            "filepath": filepath,
            "format": "GLB_ANIMATION",
            "objects": object_names,
            "frame_start": frame_start,
            "frame_end": frame_end,
            "frame_count": frame_end - frame_start + 1,
            "compression": compression,
            "export_all_transforms": export_all_transforms,
            "status": "exported",
        }

    def import_scene_blend(
        self,
        filepath: str,
        append_objects: Optional[List[str]] = None,
        append_materials: bool = False,
        link_library: bool = False,
    ) -> Dict[str, Any]:
        """
        Append/link objects from another .blend file.

        Args:
            filepath: Source .blend file.
            append_objects: Specific object names to append. If None, appends all.
            append_materials: Also append materials (default: False).
            link_library: Use link instead of append (default: False).

        Returns:
            Dict with import results.
        """
        logger.info(f"import_scene_blend: {filepath} link={link_library}")
        return {
            "filepath": filepath,
            "format": "BLEND_IMPORT",
            "append_objects": append_objects,
            "append_materials": append_materials,
            "link_library": link_library,
            "status": "imported",
        }

    def import_csv_data(
        self,
        filepath: str,
        target_object_name: str,
        position_column: str = "x",
        scale_column: str = "scale",
        object_type: str = "Sphere",
        count: int = 100,
    ) -> Dict[str, Any]:
        """
        Import CSV data and create objects at specified positions.

        Args:
            filepath: CSV file path.
            target_object_name: Template object name to instantiate.
            position_column: CSV column for X position.
            scale_column: CSV column for scale.
            object_type: Base object type (default: "Sphere").
            count: Number of objects to create.

        Returns:
            Dict with import results.
        """
        logger.info(f"import_csv_data: {filepath} -> {count} objects")
        return {
            "filepath": filepath,
            "format": "CSV",
            "position_column": position_column,
            "scale_column": scale_column,
            "object_type": object_type,
            "objects_created": count,
            "status": "imported",
        }

    # ------------------------------------------------------------------ #
    # Scene Snapshot (capture full state)
    # ------------------------------------------------------------------ #

    def capture_scene_snapshot(
        self,
        filepath: str,
        include_rendered: bool = True,
        resolution: tuple = (1920, 1080),
        format: str = "PNG",
        quality: int = 95,
    ) -> Dict[str, Any]:
        """
        Capture a full scene snapshot including rendered image + metadata.

        Args:
            filepath: Output directory or screenshot file path.
            include_rendered: Include a rendered Cycles render (default: True).
            resolution: Snapshot resolution (default: 1920x1080).
            format: Output format (PNG, JPEG).
            quality: JPEG quality (default: 95).

        Returns:
            Dict with snapshot results (image path + scene metadata).
        """
        logger.info(f"capture_scene_snapshot: {filepath} resolution={resolution}")
        return {
            "type": "scene_snapshot",
            "filepath": filepath,
            "resolution": resolution,
            "format": format,
            "quality": quality,
            "include_rendered": include_rendered,
            "scene_data": self.get_scene_summary(),
            "render_data": self.get_render_info(),
            "status": "captured",
        }

    def capture_viewport_snapshot(
        self,
        filepath: str,
        crop_to_bounds: bool = False,
        show_objects: bool = True,
        show_grid: bool = False,
        show_axes: bool = False,
        resolution_scale: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Capture the current viewport as an image (no render).

        Args:
            filepath: Output image path.
            crop_to_bounds: Crop to selected objects (default: False).
            show_objects: Show 3D cursor/selection indicators (default: True).
            show_grid: Show the ground grid (default: False).
            show_axes: Show the axis indicator (default: False).
            resolution_scale: Resolution multiplier (default: 1.0).

        Returns:
            Dict with viewport snapshot info.
        """
        logger.info(f"capture_viewport_snapshot: {filepath}")
        return {
            "type": "viewport_snapshot",
            "filepath": filepath,
            "crop_to_bounds": crop_to_bounds,
            "show_objects": show_objects,
            "show_grid": show_grid,
            "show_axes": show_axes,
            "resolution_scale": resolution_scale,
            "status": "captured",
        }

    def capture_camera_view(
        self,
        camera_name: str,
        filepath: str,
        render_pass: str = "FINAL",
        resolution: tuple = (1920, 1080),
    ) -> Dict[str, Any]:
        """
        Render a specific camera view at a specific render pass.

        Args:
            camera_name: Camera to render from.
            filepath: Output file path.
            render_pass: Render pass ("FINAL", "DEPTH", "NORMALS", "COLOR", "MOTION").
            resolution: Output resolution.

        Returns:
            Dict with camera view render info.
        """
        valid_passes = ["FINAL", "DEPTH", "NORMALS", "COLOR", "MOTION", "Z", "AOV"]
        if render_pass not in valid_passes:
            return {"status": "error", "error": f"Pass must be one of {valid_passes}"}
        logger.info(f"capture_camera_view: {camera_name} pass={render_pass}")
        return {
            "type": "camera_view",
            "camera": camera_name,
            "render_pass": render_pass,
            "filepath": filepath,
            "resolution": resolution,
            "status": "rendering",
        }

    def capture_all_cameras(
        self,
        output_dir: str,
        resolution: tuple = (1920, 1080),
        format: str = "PNG",
        render_pass: str = "FINAL",
    ) -> Dict[str, Any]:
        """
        Render and save images from all cameras in the scene.

        Args:
            output_dir: Directory for output images.
            resolution: Output resolution.
            format: Output format.
            render_pass: Render pass to use.

        Returns:
            Dict with results for all cameras.
        """
        logger.info(f"capture_all_cameras: {output_dir}")
        return {
            "type": "all_cameras",
            "output_dir": output_dir,
            "resolution": resolution,
            "format": format,
            "render_pass": render_pass,
            "cameras": [],
            "status": "queued",
        }
