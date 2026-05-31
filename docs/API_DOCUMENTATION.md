# Blender-MCP API Documentation

> Generated: 2026-06-01 | Version: 1.5.5-enh | Target: Blender 5.1.2 / Python 3.13

---

## Module Overview

| Module | Lines | Classes | Methods | Functions | Missing Doc | Unused |
|--------|-------|---------|---------|-----------|-------------|--------|
| check_blender_512_compatibility | 317 | 2 | 22 | 16 | 23 | 0 |
| check_compatibility | 317 | 2 | 14 | 8 | 8 | 0 |
| project_analyzer | 454 | 0 | 5 | 5 | 5 | 0 |
| __init__ | 6 | 0 | 0 | 0 | 0 | 0 |
| advanced_objects | 2204 | 4 | 96 | 0 | 6 | 0 |
| config_new | 223 | 5 | 11 | 0 | 9 | 0 |
| connection_recovery | 426 | 5 | 32 | 1 | 23 | 0 |
| server | 1186 | 1 | 31 | 27 | 2 | 0 |
| telemetry | 342 | 3 | 13 | 5 | 0 | 0 |
| telemetry_decorator | 65 | 0 | 1 | 1 | 0 | 0 |
| __init__ | 1 | 0 | 0 | 0 | 0 | 0 |
| test_advanced_batch_render_import | 485 | 4 | 63 | 1 | 66 | 0 |
| test_advanced_objects | 336 | 5 | 51 | 0 | 56 | 0 |
| test_config | 231 | 5 | 21 | 0 | 25 | 0 |
| test_connection_recovery | 258 | 5 | 25 | 0 | 29 | 0 |

---

## MCP Registered Tools

- `get_scene_info`
- `get_object_info`
- `get_viewport_screenshot`
- `execute_blender_code`
- `get_polyhaven_categories`
- `search_polyhaven_assets`
- `download_polyhaven_asset`
- `set_texture`
- `get_polyhaven_status`
- `get_hyper3d_status`
- `get_sketchfab_status`
- `search_sketchfab_models`
- `get_sketchfab_model_preview`
- `download_sketchfab_model`
- `generate_hyper3d_model_via_text`
- `generate_hyper3d_model_via_images`
- `poll_rodin_job_status`
- `import_generated_asset`
- `get_hunyuan3d_status`
- `generate_hunyuan3d_model`
- `poll_hunyuan_job_status`
- `import_generated_asset_hunyuan`

## Classes and Methods

### `Issue`

**Attributes**:
- `severity`: str
- `category`: str
- `file`: str
- `line`: int
- `code`: str
- `description`: str
- `fix`: str
- `blender_5x_note`: str

### `CompatReport`

**Attributes**:
- `issues`: List[...]

**Methods**:
- `add`(self, severity, category, file, line, code, description, fix, blender_5x_note) (line 37)
- `criticals`(self) (line 41)
- `errors`(self) (line 45)
- `warnings`(self) (line 49)
- `infos`(self) (line 53)
- `summary`(self) (line 56)

### `VersionCheck`

**Attributes**:
- `check_name`: str
- `status`: str
- `message`: str
- `detail`: str

### `CompatibilityReport`

**Attributes**:
- `checks`: List[...]

**Methods**:
- `add`(self, name: str, status: str, message: str, detail: str='') (line 29)
- `passed`(self) -> bool (line 33)
- `failures`(self) -> List[...] (line 37)
- `warnings`(self) -> List[...] (line 41)
- `summary`(self) -> str (line 44)
- `to_dict`(self) -> dict (line 68)

### `BoundingBox`

**Docstring**: Axis-aligned bounding box in Blender world space.

**Attributes**:
- `min_x`: float
- `min_y`: float
- `min_z`: float
- `max_x`: float
- `max_y`: float
- `max_z`: float

**Methods**:
- `width`(self) -> float (line 45)
- `height`(self) -> float (line 49)
- `depth`(self) -> float (line 53)
- `center`(self) -> tuple (line 57)
- `volume`(self) -> float (line 65)

### `MaterialInfo`

**Docstring**: Material information for a Blender object.

**Attributes**:
- `name`: str
- `use_nodes`: bool
- `node_count`: int
- `diffuse_color`: tuple
- `metallic`: float
- `roughness`: float
- `texture_nodes`: List[...]

### `RenderSettings`

**Docstring**: Blender render configuration.

**Attributes**:
- `engine`: str
- `resolution_x`: int
- `resolution_y`: int
- `fps`: int
- `frame_start`: int
- `frame_end`: int
- `samples`: int
- `output_format`: str
- `color_depth`: str
- `transparent`: bool

### `AdvancedObjectOperations`

**Docstring**: High-level Blender object operations.

**Methods**:
- `__init__`(self, blender_connection=None) (line 112)
  > Initialize with an existing BlenderConnection or create one.
- `_next_command_id`(self) -> str (line 122)
- `select_object`(self, object_name: str) -> Dict[...] (line 130)
  > Select a single object in the Blender scene.
- `select_multiple_objects`(self, object_names: List[...]) -> Dict[...] (line 144)
  > Select multiple objects in the Blender scene.
- `deselect_all`(self) -> Dict[...] (line 157)
  > Deselect all objects in the scene.
- `focus_camera_on_object`(self, object_name: str, camera_name: str='Camera') -> Dict[...] (line 162)
  > Align a camera to point at a specific object.
- `focus_camera_isometric`(self, camera_name: str='Camera') -> Dict[...] (line 176)
  > Set camera to isometric (orthographic) view.
- `save_scene`(self, filepath: str, compress: bool=True) -> Dict[...] (line 193)
  > Save the current Blender scene to a .blend file.
- `save_as_scene`(self, filepath: str, compress: bool=True) -> Dict[...] (line 207)
  > Save the current Blender scene as a new file (preserves current file).
- `load_scene`(self, filepath: str, keep_objects: bool=False) -> Dict[...] (line 221)
  > Load a .blend file, optionally keeping existing objects.
- `get_render_settings`(self) -> Dict[...] (line 239)
  > Get current render settings from the Blender scene.
- `set_render_settings`(self, settings: Optional[...]=None, **kwargs) -> Dict[...] (line 244)
  > Configure render settings.
- `render_scene`(self, filepath: Optional[...]=None, frame_range: Optional[...]=None) -> Dict[...] (line 264)
  > Render the current scene.
- `render_animation`(self, filepath: str, frame_start: int=1, frame_end: int=250) -> Dict[...] (line 278)
  > Render a full animation sequence.
- `create_collection`(self, name: str, parent_name: Optional[...]=None) -> Dict[...] (line 301)
  > Create a new collection (Blender's object grouping system).
- `add_to_collection`(self, object_names: List[...], collection_name: str) -> Dict[...] (line 315)
  > Move objects into a collection.
- `remove_from_collection`(self, object_names: List[...], collection_name: str) -> Dict[...] (line 334)
  > Remove objects from a collection (does not delete objects).
- `list_collections`(self) -> Dict[...] (line 348)
  > List all collections and their structure.
- `get_collection_objects`(self, collection_name: str) -> Dict[...] (line 353)
  > Get all objects in a collection.
- `batch_scale`(self, object_names: List[...], factor: float) -> Dict[...] (line 370)
  > Scale multiple objects by a uniform factor.
- `batch_color`(self, object_names: List[...], color: tuple) -> Dict[...] (line 384)
  > Set diffuse color for multiple objects.
- `batch_rotate`(self, object_names: List[...], euler_rotation: tuple) -> Dict[...] (line 398)
  > Rotate multiple objects by specified Euler angles.
- `batch_duplicate`(self, object_names: List[...], offset: tuple=1.0, 0.0, 0.0, copies: int=3) -> Dict[...] (line 412)
  > Create copies of objects with positional offset.
- `get_material`(self, object_name: str) -> Dict[...] (line 432)
  > Get material info for an object.
- `set_material_color`(self, object_name: str, color: tuple) -> Dict[...] (line 445)
  > Set the diffuse color of an object's material.
- `create_material`(self, name: str, color: tuple=0.8, 0.8, 0.8, 1.0, metallic: float=0.0, roughness: float=0.5) -> Dict[...] (line 459)
  > Create a new Principled BSDF material.
- `apply_material_to_object`(self, material_name: str, object_name: str) -> Dict[...] (line 481)
  > Assign a material to an object.
- `set_texture_to_material`(self, material_name: str, texture_slot: str='Base Color', image_path: Optional[...]=None, color_ramp: Optional[...]=None) -> Dict[...] (line 495)
  > Apply a texture image to a material node.
- `get_node_tree`(self, material_name: str) -> Dict[...] (line 522)
  > Get the node tree structure for a material.
- `create_image_texture_node`(self, material_name: str, image_path: str, slot: str='Base Color', tile_x: int=1, tile_y: int=1, repeat: bool=False) -> Dict[...] (line 537)
  > Create an Image Texture node and link it to a Principled BSDF slot.
- `create_procedural_texture`(self, material_name: str, texture_type: str='Checker', slot: str='Base Color', scale: float=5.0, color1: tuple=0.0, 0.0, 0.0, 1.0, color2: tuple=1.0, 1.0, 1.0, 1.0) -> Dict[...] (line 564)
  > Create a procedural texture node and link it.
- `create_color_ramp`(self, material_name: str, slot: str='Base Color', stops: Optional[...]=None) -> Dict[...] (line 601)
  > Create a ColorRamp node and insert it in the material node tree.
- `mix_shaders`(self, material_name: str, shader1: str='Principled BSDF', shader2: str='Principled BSDF', blend_factor: float=0.5, output_material: Optional[...]=None) -> Dict[...] (line 625)
  > Mix two shaders using a Mix Shader node.
- `create_emission_material`(self, name: str, color: tuple=1.0, 1.0, 1.0, 1.0, strength: float=1.0) -> Dict[...] (line 652)
  > Create an emission-only material for self-illuminated surfaces.
- `set_normal_map`(self, material_name: str, texture_path: str, strength: float=1.0, color_ramp: Optional[...]=None) -> Dict[...] (line 674)
  > Create a Normal Map node with a texture and link to BSDF Normal input.
- `set_displacement`(self, material_name: str, texture_path: str, method: str='Bump', displacement_material: str='Material Output') -> Dict[...] (line 697)
  > Set up displacement (Bump or Displacement) node.
- `create_material_group`(self, name: str, node_type: str='Group', inputs: Optional[...]=None) -> Dict[...] (line 720)
  > Create a material node group for reuse across materials.
- `clone_material`(self, source_material_name: str, target_name: str) -> Dict[...] (line 743)
  > Clone a material (copy all nodes and settings).
- `clear_node_tree`(self, material_name: str, keep_bsdf: bool=False) -> Dict[...] (line 761)
  > Clear all nodes from a material's node tree.
- `set_anisotropic`(self, material_name: str, anisotropy: float=0.5, anisotropy_rotation: float=0.0) -> Dict[...] (line 775)
  > Set anisotropic parameters on a Principled BSDF material.
- `set_transparency`(self, material_name: str, alpha: float=1.0, blend_mode: str='OPAQUE') -> Dict[...] (line 796)
  > Set transparency/alpha blending on a material.
- `setup_ior`(self, material_name: str, ior: float=1.45) -> Dict[...] (line 817)
  > Set Index of Refraction (IOR) for transparent/refractive materials.
- `align_to_world_axis`(self, object_name: str, axis: str='Z') -> Dict[...] (line 839)
  > Align an object's rotation to a world axis.
- `snap_to_grid`(self, object_name: str, grid_size: float=0.01) -> Dict[...] (line 853)
  > Snap an object's position to the nearest grid point.
- `center_object_origin`(self, object_name: str) -> Dict[...] (line 867)
  > Move an object's origin to its geometric center.
- `get_bounding_box`(self, object_name: str) -> Dict[...] (line 880)
  > Get the AABB bounding box of an object in world space.
- `set_studio_lighting`(self, preset: str='three_point') -> Dict[...] (line 906)
  > Apply a studio lighting preset to the scene.
- `set_environment_lighting`(self, world_color: tuple=0.05, 0.05, 0.08, 1.0, world_strength: float=1.0, use_texture: bool=False, texture_path: Optional[...]=None) -> Dict[...] (line 931)
  > Configure the scene's world lighting.
- `create_camera`(self, name: str='Camera', location: tuple=5.0, unknown, 3.0, rotation: tuple=unknown, 0.0, 0.3, lens: float=50.0, sensor_width: float=36.0) -> Dict[...] (line 962)
  > Create a new camera with specified position and lens.
- `get_camera_info`(self, camera_name: str='Camera') -> Dict[...] (line 994)
  > Get detailed camera information.
- `get_scene_summary`(self) -> Dict[...] (line 1018)
  > Get a full scene summary including objects, collections, materials, cameras.
- `get_duplicate_objects`(self) -> Dict[...] (line 1035)
  > Find objects with identical names in the scene.
- `clear_unreferenced_data`(self) -> Dict[...] (line 1045)
  > Remove unreferenced data blocks (orphan data).
- `batch_apply_material`(self, object_names: List[...], material_name: str, replace_existing: bool=True) -> Dict[...] (line 1059)
  > Apply the same material to multiple objects in one operation.
- `batch_set_transform`(self, object_names: List[...], location: Optional[...]=None, rotation: Optional[...]=None, scale: Optional[...]=None) -> Dict[...] (line 1085)
  > Set transform (location, rotation, scale) for multiple objects.
- `batch_make_duplicates`(self, object_names: List[...], count_per_object: int=2, offset: tuple=1.0, 0.0, 0.0, randomize: bool=False) -> Dict[...] (line 1114)
  > Create duplicates of objects with configurable spacing and optional randomization.
- `batch_delete`(self, object_names: List[...], also_clearance: bool=False, also_materials: bool=False) -> Dict[...] (line 1144)
  > Delete multiple objects from the scene.
- `batch_set_visibility`(self, object_names: List[...], visible: bool=True, hide_render: bool=False, hide_select: bool=False) -> Dict[...] (line 1170)
  > Set visibility state for multiple objects.
- `batch_make_parent`(self, child_names: List[...], parent_name: str, keep_transform: bool=True) -> Dict[...] (line 1199)
  > Make multiple objects children of a single parent.
- `batch_make_empty_group`(self, object_names: List[...], group_name: str='SelectionGroup', create_collection: bool=False) -> Dict[...] (line 1225)
  > Create an Empty parent for a group of objects and group them.
- `batch_apply_modifiers`(self, object_names: List[...], modifier_names: Optional[...]=None, apply_all: bool=True) -> Dict[...] (line 1251)
  > Apply specified modifiers (or all) on multiple objects.
- `batch_mirror`(self, object_names: List[...], axis: str='X', merge_vertices: bool=True, use_clip: bool=True) -> Dict[...] (line 1277)
  > Apply Mirror modifier to multiple objects (non-destructive).
- `batch_instance_on_points`(self, template_object_names: List[...], points_object_name: str, random_rotation: bool=False, random_scale: bool=False) -> Dict[...] (line 1306)
  > Use geometry nodes to instance objects on points of another object.
- `batch_align_bounding_boxes`(self, object_names: List[...], alignment: str='center', reference: str='world') -> Dict[...] (line 1334)
  > Align bounding box centers of multiple objects.
- `set_render_eevee`(self, samples: int=128, denoise: bool=True, tile_size: int=32, taa_samples: int=128) -> Dict[...] (line 1364)
  > Configure Eevee render engine settings.
- `set_render_cycles`(self, samples: int=1024, denoise: bool=True, engine: str='OPTIX', use_denoising: bool=True) -> Dict[...] (line 1393)
  > Configure Cycles render engine settings.
- `set_render_output`(self, filepath: str, format: str='PNG', color_depth: str='16', compression: int=15, transparent: bool=False, ffmpeg: Optional[...]=None) -> Dict[...] (line 1425)
  > Configure render output path, format, and quality.
- `render_viewport`(self, filepath: str, quality: int=95, resolution_scale: float=1.0, crop_to_bounds: bool=False) -> Dict[...] (line 1462)
  > Render the current viewport (what's visible in the 3D view).
- `render_animation_batch`(self, filepath: str, frame_start: int=1, frame_end: int=250, frame_step: int=1, format: str='FFMPEG', ffmpeg_settings: Optional[...]=None) -> Dict[...] (line 1491)
  > Render a full animation sequence in batch mode.
- `render_multi_view`(self, filepath: str, camera_angles: Optional[...]=None, format: str='PNG') -> Dict[...] (line 1528)
  > Render the scene from multiple camera angles.
- `render_360_panorama`(self, filepath: str, fov: float=180.0, resolution: tuple=4096, 2048, format: str='PNG') -> Dict[...] (line 1563)
  > Render a 360-degree equirectangular panorama.
- `set_render_camera`(self, camera_name: str) -> Dict[...] (line 1592)
  > Set the active render camera.
- `render_preview`(self, filepath: str, resolution_scale: float=0.5, samples: int=64, timeout: int=30) -> Dict[...] (line 1605)
  > Render a low-quality preview image quickly.
- `get_render_info`(self) -> Dict[...] (line 1634)
  > Get the current full render configuration summary.
- `import_fbx`(self, filepath: str, automatic_orientation: bool=True, import_hardware: bool=True, force_connect_children: bool=False) -> Dict[...] (line 1657)
  > Import an FBX file into the Blender scene.
- `import_obj`(self, filepath: str, add_normals: bool=True, split_objects: bool=True, split_groups: bool=True, import_images: bool=True) -> Dict[...] (line 1686)
  > Import an OBJ file into the Blender scene.
- `import_glb`(self, filepath: str, merge_vertices: bool=True, import_shading: str='NORMALS') -> Dict[...] (line 1718)
  > Import a GLB/GLTF file into the Blender scene.
- `import_stl`(self, filepath: str, forward_axis: str='-Z', up_axis: str='Y', scale: float=1.0) -> Dict[...] (line 1744)
  > Import an STL file (typically 3D print meshes).
- `export_fbx`(self, filepath: str, object_names: Optional[...]=None, bake_anim: bool=True, use_selection: bool=False, apply_scale_options: str='FBX') -> Dict[...] (line 1773)
  > Export scene (or selection) as FBX.
- `export_glb`(self, filepath: str, object_names: Optional[...]=None, export_selected: bool=False, export_normals: bool=True, export_materials: bool=True, export_animations: bool=True, compression: bool=True) -> Dict[...] (line 1805)
  > Export scene as GLB (compressed GLTF, self-contained).
- `export_obj`(self, filepath: str, object_names: Optional[...]=None, export_selected: bool=False, export_normals: bool=True, export_uv: bool=True, export_materials: bool=False, use_mesh_modifiers: bool=True, smooth_groups: bool=True) -> Dict[...] (line 1843)
  > Export scene as OBJ (wavefront format).
- `export_stl`(self, filepath: str, object_names: Optional[...]=None, binary_format: bool=True) -> Dict[...] (line 1884)
  > Export as STL (3D print format, no materials/animations).
- `export_blend`(self, filepath: str, relative_paths: bool=True, compress: bool=True) -> Dict[...] (line 1910)
  > Export current scene as a standalone .blend file.
- `export_animation_fbx`(self, filepath: str, object_names: List[...], frame_start: int=1, frame_end: int=250, use_subsets: bool=False, subset_prefix: str='') -> Dict[...] (line 1936)
  > Export only animation data for selected objects as FBX.
- `export_animation_gltf`(self, filepath: str, object_names: List[...], frame_start: int=1, frame_end: int=250, compression: bool=True, export_all_transforms: bool=True) -> Dict[...] (line 1972)
  > Export animation as compressed GLB with animation data.
- `import_scene_blend`(self, filepath: str, append_objects: Optional[...]=None, append_materials: bool=False, link_library: bool=False) -> Dict[...] (line 2008)
  > Append/link objects from another .blend file.
- `import_csv_data`(self, filepath: str, target_object_name: str, position_column: str='x', scale_column: str='scale', object_type: str='Sphere', count: int=100) -> Dict[...] (line 2037)
  > Import CSV data and create objects at specified positions.
- `capture_scene_snapshot`(self, filepath: str, include_rendered: bool=True, resolution: tuple=1920, 1080, format: str='PNG', quality: int=95) -> Dict[...] (line 2075)
  > Capture a full scene snapshot including rendered image + metadata.
- `capture_viewport_snapshot`(self, filepath: str, crop_to_bounds: bool=False, show_objects: bool=True, show_grid: bool=False, show_axes: bool=False, resolution_scale: float=1.0) -> Dict[...] (line 2109)
  > Capture the current viewport as an image (no render).
- `capture_camera_view`(self, camera_name: str, filepath: str, render_pass: str='FINAL', resolution: tuple=1920, 1080) -> Dict[...] (line 2144)
  > Render a specific camera view at a specific render pass.
- `capture_all_cameras`(self, output_dir: str, resolution: tuple=1920, 1080, format: str='PNG', render_pass: str='FINAL') -> Dict[...] (line 2176)
  > Render and save images from all cameras in the scene.

### `ConnectionConfig`

**Docstring**: TCP connection settings for Blender addon communication.

**Attributes**:
- `host`: str
- `port`: int
- `timeout`: float
- `max_retries`: int
- `retry_delay`: float

**Methods**:
- `from_env`(cls) -> 'ConnectionConfig' (class) (line 37)

### `APIKeys`

**Docstring**: API keys for third-party integrations.

**Attributes**:
- `hyper3d_api_key`: str
- `hyper3d_fal_api_key`: str
- `hyper3d_free_trial_key`: str
- `hyper3d_mode`: str
- `hunyuan3d_secret_id`: str
- `hunyuan3d_secret_key`: str
- `hunyuan3d_mode`: str
- `polyhaven_api_key`: str
- `sketchfab_api_key`: str
- `supabase_url`: str
- `supabase_anon_key`: str

**Methods**:
- `has_hyper3d_key`(self) -> bool (line 72)
- `has_hunyuan3d_key`(self) -> bool (line 75)
- `has_sketchfab_key`(self) -> bool (line 78)
- `has_supabase_key`(self) -> bool (line 81)
- `from_env`(cls) -> 'APIKeys' (class) (line 85)

### `TelemetryConfig`

**Docstring**: Telemetry collection settings.

**Attributes**:
- `enabled`: bool
- `max_prompt_length`: int
- `event_queue_maxsize`: int
- `batch_size`: int
- `flush_interval`: float

**Methods**:
- `from_env`(cls) -> 'TelemetryConfig' (class) (line 110)

### `BlenderConfig`

**Docstring**: Feature flags and Blender-specific settings.

**Attributes**:
- `polyhaven_enabled`: bool
- `sketchfab_enabled`: bool
- `telemetry_enabled`: bool
- `addon_version`: str
- `mcp_version`: str
- `log_level`: str

**Methods**:
- `from_env`(cls) -> 'BlenderConfig' (class) (line 135)

### `Config`

**Docstring**: Unified configuration holder. All configs merged from env vars and local file.

**Methods**:
- `__init__`(self) (line 147)
- `_load_local_config`(self) (line 155)
  > Load config from local config.py if it exists.
- `summary`(self) -> dict (line 195)
  > Return a non-sensitive summary of the configuration.

### `CircuitState`

**Bases**: str, Enum

**Docstring**: Circuit breaker states.

**Attributes**:
- `CLOSED`: Any
- `OPEN`: Any
- `HALF_OPEN`: Any

### `CircuitBreaker`

**Docstring**: Circuit breaker to prevent cascading failures.

**Attributes**:
- `failure_threshold`: int
- `recovery_timeout`: float
- `current_state`: CircuitState
- `failure_count`: int
- `last_failure_time`: float

**Methods**:
- `record_success`(self) (line 46)
- `record_failure`(self) (line 50)
- `can_execute`(self) -> bool (line 57)

### `HealthMetrics`

**Docstring**: Tracks connection health statistics.

**Attributes**:
- `total_connections`: int
- `total_failures`: int
- `total_successes`: int
- `total_timeouts`: int
- `total_bytes_sent`: int
- `total_bytes_received`: int
- `avg_response_time_ms`: float
- `_response_times`: list
- `_last_health_check`: float

**Methods**:
- `record_success`(self, response_time_ms: float, bytes_received: int) (line 84)
- `record_failure`(self, reason: str='') (line 92)
- `record_timeout`(self) (line 96)
- `success_rate`(self) -> float (line 101)
- `summary`(self) -> dict (line 105)

### `BlenderConnectionManager`

**Docstring**: Enhanced connection manager with auto-reconnect and circuit breaker.

**Methods**:
- `__init__`(self, host: str='localhost', port: int=9876, timeout: float=180.0, max_retries: int=3, retry_delay: float=1.0, circuit_failure_threshold: int=5, circuit_recovery_timeout: float=30.0) (line 124)
- `is_connected`(self) -> bool (line 150)
- `circuit_state`(self) -> str (line 154)
- `metrics`(self) -> dict (line 158)
- `_validate_circuit`(self) -> bool (line 161)
  > Check if the circuit breaker allows execution.
- `connect`(self) -> bool (async) (line 171)
  > Establish connection to Blender with retry logic.
- `disconnect`(self) (async) (line 224)
  > Close the connection cleanly.
- `send_command`(self, command_type: str, params: Optional[...]=None) -> Dict[...] (async) (line 230)
  > Send a command and receive a response with recovery logic.
- `_receive_full_response`(self, sock: socket.socket, buffer_size: int=8192) -> bytes (async) (line 287)
  > Receive complete JSON response from socket.
- `_close_socket`(self) (line 324)
  > Safely close the socket.
- `health_check`(self) -> dict (async) (line 334)
  > Run a health check against the Blender connection.
- `__enter__`(self) (line 360)
  > Support sync context manager for sync code paths.
- `__exit__`(self, exc_type, exc_val, exc_tb) (line 364)

### `AsyncBlenderConnectionManager`

**Docstring**: Async wrapper around BlenderConnectionManager for asyncio contexts.

**Methods**:
- `__init__`(self, **kwargs) (line 375)
- `is_connected`(self) -> bool (line 379)
- `metrics`(self) -> dict (line 383)
- `circuit_state`(self) -> str (line 387)
- `connect`(self) -> bool (async) (line 390)
- `disconnect`(self) (async) (line 393)
- `send_command`(self, command_type: str, params: Optional[...]=None) -> Dict[...] (async) (line 396)
- `health_check`(self) -> dict (async) (line 399)
- `__aenter__`(self) (async) (line 402)
- `__aexit__`(self, exc_type, exc_val, exc_tb) (async) (line 406)

### `BlenderConnection`

**Attributes**:
- `host`: str
- `port`: int
- `sock`: socket.socket

**Methods**:
- `connect`(self) -> bool (line 35)
  > Connect to the Blender addon socket server
- `disconnect`(self) (line 50)
  > Disconnect from the Blender addon
- `receive_full_response`(self, sock, buffer_size=8192) (line 60)
  > Receive the complete response, potentially in multiple chunks
- `send_command`(self, command_type: str, params: Dict[...]=None) -> Dict[...] (line 116)
  > Send a command to Blender and return the response

### `EventType`

**Bases**: str, Enum

**Docstring**: Types of telemetry events

**Attributes**:
- `STARTUP`: Any
- `TOOL_EXECUTION`: Any
- `PROMPT_SENT`: Any
- `CONNECTION`: Any
- `ERROR`: Any

### `TelemetryEvent`

**Docstring**: Structure for telemetry events

**Attributes**:
- `event_type`: EventType
- `customer_uuid`: str
- `session_id`: str
- `timestamp`: float
- `version`: str
- `platform`: str
- `tool_name`: str | None
- `prompt_text`: str | None
- `success`: bool
- `duration_ms`: float | None
- `error_message`: str | None
- `blender_version`: str | None
- `metadata`: dict[...] | None

### `TelemetryCollector`

**Docstring**: Main telemetry collection class

**Methods**:
- `__init__`(self) (line 87)
  > Initialize telemetry collector
- `_is_disabled`(self) -> bool (line 115)
  > Check if telemetry is disabled via environment variables
- `_get_data_directory`(self) -> Path (line 128)
  > Get directory for storing telemetry data
- `_get_or_create_uuid`(self) -> str (line 141)
  > Get or create anonymous customer UUID
- `_check_user_consent`(self) -> bool (line 165)
  > Check if user has consented to prompt collection via Blender addon
- `record_event`(self, event_type: EventType, tool_name: str | None=None, prompt_text: str | None=None, success: bool=True, duration_ms: float | None=None, error_message: str | None=None, blender_version: str | None=None, metadata: dict[...] | None=None) (line 178)
  > Record a telemetry event (non-blocking)
- `_worker_loop`(self) (line 245)
  > Background worker that sends telemetry
- `_send_event`(self, event: TelemetryEvent) (line 257)
  > Send event to Supabase

### `TestAdvancedBatchOperations`

**Methods**:
- `test_batch_apply_material_default`(self, ops) (line 37)
- `test_batch_apply_material_no_replace`(self, ops) (line 44)
- `test_batch_set_transform_location`(self, ops) (line 49)
- `test_batch_set_transform_all`(self, ops) (line 55)
- `test_batch_set_transform_empty_list`(self, ops) (line 65)
- `test_batch_make_duplicates_default`(self, ops) (line 70)
- `test_batch_make_duplicates_multi_object`(self, ops) (line 76)
- `test_batch_delete_basic`(self, ops) (line 83)
- `test_batch_delete_with_options`(self, ops) (line 89)
- `test_batch_set_visibility_hide`(self, ops) (line 95)
- `test_batch_set_visibility_show`(self, ops) (line 101)
- `test_batch_make_parent_basic`(self, ops) (line 106)
- `test_batch_make_parent_keep_transform_false`(self, ops) (line 112)
- `test_batch_make_empty_group_basic`(self, ops) (line 117)
- `test_batch_apply_modifiers_all`(self, ops) (line 124)
- `test_batch_apply_modifiers_specific`(self, ops) (line 129)
- `test_batch_mirror_basic`(self, ops) (line 134)
- `test_batch_instance_on_points_basic`(self, ops) (line 141)
- `test_batch_align_bounding_boxes_center`(self, ops) (line 148)

### `TestAdvancedRenderAutomation`

**Methods**:
- `test_set_render_eevee_default`(self, ops) (line 162)
- `test_set_render_eevee_custom`(self, ops) (line 169)
- `test_set_render_cycles_default`(self, ops) (line 177)
- `test_set_render_cycles_cpu`(self, ops) (line 184)
- `test_set_render_cycles_invalid_engine`(self, ops) (line 189)
- `test_set_render_output_default`(self, ops) (line 195)
- `test_set_render_output_exr`(self, ops) (line 201)
- `test_set_render_output_invalid_format`(self, ops) (line 206)
- `test_render_viewport_default`(self, ops) (line 211)
- `test_render_viewport_half_res`(self, ops) (line 217)
- `test_render_animation_batch_default`(self, ops) (line 223)
- `test_render_animation_batch_custom`(self, ops) (line 231)
- `test_render_multi_view_default`(self, ops) (line 240)
- `test_render_multi_view_custom`(self, ops) (line 245)
- `test_render_360_panorama_default`(self, ops) (line 253)
- `test_set_render_camera`(self, ops) (line 260)
- `test_render_preview_default`(self, ops) (line 266)
- `test_get_render_info`(self, ops) (line 274)

### `TestAnimationImportExport`

**Methods**:
- `test_import_fbx_default`(self, ops) (line 289)
- `test_import_obj_default`(self, ops) (line 296)
- `test_import_glb_default`(self, ops) (line 303)
- `test_import_stl_default`(self, ops) (line 310)
- `test_export_fbx_default`(self, ops) (line 317)
- `test_export_fbx_selection_only`(self, ops) (line 323)
- `test_export_glb_default`(self, ops) (line 329)
- `test_export_obj_default`(self, ops) (line 336)
- `test_export_stl_binary`(self, ops) (line 343)
- `test_export_stl_ascii`(self, ops) (line 348)
- `test_export_blend_default`(self, ops) (line 353)
- `test_export_animation_fbx`(self, ops) (line 359)
- `test_export_animation_fbx_subsets`(self, ops) (line 370)
- `test_export_animation_gltf`(self, ops) (line 381)
- `test_import_scene_blend_append`(self, ops) (line 392)
- `test_import_scene_blend_link`(self, ops) (line 398)
- `test_import_csv_data_default`(self, ops) (line 403)

### `TestSceneSnapshot`

**Methods**:
- `test_capture_scene_snapshot_default`(self, ops) (line 421)
- `test_capture_scene_snapshot_custom`(self, ops) (line 429)
- `test_capture_viewport_snapshot_default`(self, ops) (line 443)
- `test_capture_viewport_snapshot_with_grid`(self, ops) (line 450)
- `test_capture_camera_view_default`(self, ops) (line 464)
- `test_capture_camera_view_invalid_pass`(self, ops) (line 471)
- `test_capture_camera_view_depth_pass`(self, ops) (line 476)
- `test_capture_all_cameras_default`(self, ops) (line 481)

### `TestBoundingBox`

**Methods**:
- `test_initialization`(self) (line 27)
- `test_dimensions`(self) (line 32)
- `test_volume`(self) (line 38)
- `test_center`(self) (line 42)
- `test_non_zero_origin`(self) (line 49)

### `TestMaterialInfo`

**Methods**:
- `test_initialization`(self) (line 62)
- `test_with_texture_nodes`(self) (line 76)

### `TestRenderSettings`

**Methods**:
- `test_default_values`(self) (line 98)
- `test_custom_values`(self) (line 108)

### `TestAdvancedObjectOperations`

**Methods**:
- `ops`(self) (line 129)
- `test_select_object`(self, ops) (line 133)
- `test_select_multiple_objects`(self, ops) (line 138)
- `test_deselect_all`(self, ops) (line 143)
- `test_focus_camera_on_object`(self, ops) (line 147)
- `test_focus_camera_isometric`(self, ops) (line 152)
- `test_save_scene`(self, ops) (line 157)
- `test_save_as_scene`(self, ops) (line 161)
- `test_load_scene`(self, ops) (line 165)
- `test_get_render_settings`(self, ops) (line 170)
- `test_set_render_settings`(self, ops) (line 174)
- `test_render_scene`(self, ops) (line 178)
- `test_render_animation`(self, ops) (line 182)
- `test_create_collection`(self, ops) (line 187)
- `test_create_nested_collection`(self, ops) (line 192)
- `test_add_to_collection`(self, ops) (line 196)
- `test_remove_from_collection`(self, ops) (line 201)
- `test_list_collections`(self, ops) (line 205)
- `test_get_collection_objects`(self, ops) (line 209)
- `test_batch_scale`(self, ops) (line 214)
- `test_batch_color`(self, ops) (line 219)
- `test_batch_rotate`(self, ops) (line 223)
- `test_batch_duplicate`(self, ops) (line 227)
- `test_get_material`(self, ops) (line 233)
- `test_set_material_color`(self, ops) (line 237)
- `test_create_material`(self, ops) (line 241)
- `test_apply_material_to_object`(self, ops) (line 246)
- `test_set_texture_to_material`(self, ops) (line 250)
- `test_get_node_tree`(self, ops) (line 254)
- `test_align_to_world_axis`(self, ops) (line 259)
- `test_snap_to_grid`(self, ops) (line 263)
- `test_center_object_origin`(self, ops) (line 267)
- `test_get_bounding_box`(self, ops) (line 271)
- `test_set_studio_lighting_three_point`(self, ops) (line 277)
- `test_set_studio_lighting_preset_unknown`(self, ops) (line 281)
- `test_set_environment_lighting`(self, ops) (line 285)
- `test_create_camera`(self, ops) (line 294)
- `test_get_camera_info`(self, ops) (line 304)
- `test_get_scene_summary`(self, ops) (line 310)
- `test_get_duplicate_objects`(self, ops) (line 315)
- `test_clear_unreferenced_data`(self, ops) (line 319)

### `TestCommandCounter`

**Methods**:
- `test_incremental_ids`(self) (line 329)

### `TestConnectionConfig`

**Methods**:
- `test_default_values`(self) (line 29)
- `test_from_env_custom_values`(self) (line 37)
- `test_from_env_fallback_to_defaults`(self) (line 52)

### `TestAPIKeys`

**Methods**:
- `test_empty_keys`(self) (line 69)
- `test_has_hyper3d_key_main`(self) (line 77)
- `test_has_hyper3d_key_fal`(self) (line 81)
- `test_has_hunyuan3d_key`(self) (line 85)
- `test_has_hunyuan3d_key_missing`(self) (line 89)
- `test_has_sketchfab_key`(self) (line 93)
- `test_has_supabase_key`(self) (line 97)
- `test_from_env`(self) (line 101)

### `TestTelemetryConfig`

**Methods**:
- `test_default_values`(self) (line 125)
- `test_from_env_disabled`(self) (line 132)
- `test_from_env_custom_values`(self) (line 137)
- `test_from_env_all_disable_vars`(self) (line 153)

### `TestBlenderConfig`

**Methods**:
- `test_default_values`(self) (line 165)
- `test_from_env_enabled`(self) (line 172)

### `TestConfig`

**Methods**:
- `clean_config`(self) (line 192)
  > Ensure no local config.py or interfering env vars.
- `test_config_singleton`(self, clean_config) (line 197)
- `test_config_summary`(self, clean_config) (line 204)
- `test_config_loaded_from_file_false`(self, clean_config) (line 216)

### `TestCircuitBreaker`

**Methods**:
- `test_initial_state_is_closed`(self) (line 33)
- `test_record_success_resets`(self) (line 38)
- `test_opens_after_threshold`(self) (line 47)
- `test_can_execute_closed`(self) (line 55)
- `test_can_execute_open_exceeded`(self) (line 59)
- `test_can_execute_open_timeout_reaches_half_open`(self) (line 65)
- `test_can_execute_half_open`(self) (line 75)

### `TestHealthMetrics`

**Methods**:
- `test_initial_state`(self) (line 89)
- `test_record_success`(self) (line 95)
- `test_multiple_successes_avg`(self) (line 102)
- `test_record_failure`(self) (line 110)
- `test_record_timeout`(self) (line 115)
- `test_success_rate_all_success`(self) (line 121)
- `test_success_rate_mixed`(self) (line 127)
- `test_success_rate_zero`(self) (line 133)
- `test_summary`(self) (line 137)

### `TestBlenderConnectionManager`

**Methods**:
- `test_create_defaults`(self) (line 155)
- `test_create_custom`(self) (line 164)
- `test_circuit_breaker_prevents_disconnected_exec`(self) (line 178)
- `test_metrics_initial`(self) (line 193)
- `test_create_connection_manager_helper`(self) (line 201)

### `TestBlenderConnectionManagerIntegration`

**Docstring**: Integration tests that actually connect to a real socket server.

**Methods**:
- `test_connect_and_send_command`(self, mock_blender_server) (line 223)
- `test_health_check`(self, mock_blender_server) (line 227)

### `TestAsyncBlenderConnectionManager`

**Methods**:
- `test_create`(self) (line 232)
- `test_wrapper_delegates_to_manager`(self) (line 240)

---

## Usage Examples

### Configuration

```python
from blender_mcp.config import config

summary = config.summary()
print(f'Host: {summary["connection"]["host"]}:{summary["connection"]["port"]}')
print(f'Hyper3D: {summary["api_keys"]["hyper3d"]}')
print(f'Telemetry: {summary["telemetry"]["enabled"]}')
```

### Connection Management

```python
from blender_mcp.connection_recovery import create_connection_manager

manager = create_connection_manager()
health = manager.get_health_status()
print(f'Status: {health["status"]}, Rate: {health["success_rate"]:.2%}')

result = manager.execute('get_scene_info', {})
print(f'Scene: {result}')
```

### Advanced Object Operations (stub)

```python
from blender_mcp.advanced_objects import AdvancedObjectOperations

ops = AdvancedObjectOperations()
# Ops methods: create_collection, create_camera, set_render_eevee_default,
# set_transform, render_viewport, import_gltf, export_fbx,
# capture_viewport_snapshot, batch_scale, batch_color, etc.
```
