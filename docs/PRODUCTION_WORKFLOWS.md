# Blender MCP Production Workflows

The production toolset complements the modeling tools with scene organization,
rigging, animation, procedural geometry, compositing, and asset preparation.

## Scene management

`scene_manage` supports scene summaries, regex search, selection, collection
creation, moving objects between collections, parenting, and visibility locks.
Mutating actions report both the previous and resulting scene state.

## Character production

`character_rig` can create a 19-bone humanoid armature, bind one or more meshes
with automatic weights, pose individual bones, and add or set shape keys.

`animation_control` inserts keyframes on object properties, creates Blender
constraints, reports animation state, and changes the timeline range.

## Procedural geometry

`geometry_nodes` builds executable Geometry Nodes networks rather than returning
placeholder metadata:

- `linear_array` resamples a line and instances the input geometry along it.
- `scatter_surface` distributes a source object across a target mesh.

## Cameras and compositing

`camera_compositor` creates cameras, adds target tracking, animates camera
location and lens, and configures a Blender 5-compatible compositor graph with
optional denoising and bloom glare.

## Asset preparation

`asset_pipeline` audits polygon counts, UVs, materials, transform state, and
shape keys. It can apply transforms or generate decimated LOD copies. LODs are
created from evaluated meshes, so the source model and its shape keys remain
unchanged.

Use `model_checkpoint` before destructive modeling operations. LOD generation
and scene organization create new data and do not require a checkpoint.

Checkpoints capture object data, local/world transforms, parenting, collection
membership, visibility, modifiers, constraints, material graphs, and animation
actions. Recipe rollback also removes objects created during the failed
transaction and can recreate original objects deleted by an earlier step.

## Measurement and spatial validation

`scene_measure` calculates evaluated vertex/edge/face counts, surface area,
volume, world-space dimensions, point distance, and AABB overlap pairs. Modifier
results are included because measurements use Blender's evaluated dependency graph.

## Batch editing and lighting

`batch_edit` performs validated transforms, renaming, linked or independent
duplication, and deletion across explicit object lists.

`lighting_rig` creates replaceable three-point, product, or sunset rigs in a
dedicated collection and aims each light at a supplied world-space target.

## Simulation and rendering

`simulation_setup` configures rigid-body settings and adds or removes cloth and
collision modifiers. `batch_render` renders a deterministic camera/frame matrix
while restoring the scene's previous camera, frame, output path, format, and
resolution afterward.

## Asynchronous render, bake, and download jobs

`submit_async_job` queues long-running work and returns a job ID immediately.
Render and bake jobs use a temporary snapshot and an independent background
Blender process, so the addon's main TCP connection remains responsive. Download
jobs stream into a `.part` file and atomically rename it after completion.

Submissions accept a priority from -100 to 100, where higher values run first.
They also accept `max_retries` (0 to 10) and `retry_delay`; failures use
exponential backoff and expose the current attempt and next retry time. A fixed
worker pool performs the work, so queued jobs do not create additional threads.

Use `get_async_job` or `list_async_jobs` to inspect queued, running, cancelling,
completed, failed, and cancelled states. Progress, output paths, structured
errors, and a bounded subprocess log tail are retained with each record.
`cancel_async_job` also terminates an active Blender subprocess, while
`cleanup_async_jobs` removes older terminal records.

The queue retains at most 128 records and runs at most two workers by default.
Completed records are evicted oldest-first when capacity is needed; submissions
are rejected if every slot belongs to active work. Override these limits with
`BLENDER_MCP_MAX_ASYNC_JOBS` and `BLENDER_MCP_MAX_ASYNC_WORKERS`. Keep the worker
count conservative because every render or bake worker is a full Blender process.

Queue state is atomically persisted in Blender's user configuration directory.
After an abnormal Blender exit, downloads and snapshot-backed render or bake jobs
are recovered into the queue. A missing snapshot becomes an explicit recovery
failure instead of a false success. `BLENDER_MCP_ASYNC_STATE_PATH` can override
the state file location. This file includes job parameters, so protect it as
local application data when download URLs contain credentials.

### Pause, dependencies, resources, and events

`pause_async_job` moves queued or blocked jobs directly to `paused`. Active
downloads close their HTTP response, while active render or bake subprocesses
are terminated; both approaches release the worker and CPU/GPU resource slot.
`resume_async_job` requeues the work from its durable parameters and snapshot.
Render and bake resume from the beginning of the job rather than from a partial
frame or bake tile.

`depends_on` accepts earlier job IDs and creates a directed acyclic workflow.
Dependent jobs remain `blocked` until every parent completes. A failed or
cancelled parent produces a terminal `DependencyError` in its descendants.
`get_async_job_graph` returns compact nodes and edges for workflow inspection.

Set `resource` to `cpu`, `gpu`, or `auto`. Auto selects GPU only when a render
or bake explicitly requests `params.device="GPU"`; downloads remain CPU work.
Global workers and per-resource limits are independent. Configure them with
`BLENDER_MCP_MAX_ASYNC_WORKERS`, `BLENDER_MCP_MAX_ASYNC_CPU_JOBS`, and
`BLENDER_MCP_MAX_ASYNC_GPU_JOBS`. `get_async_job_resources` reports active,
queued, and configured slots.

`subscribe_async_job_events` reads the durable event journal after an integer
cursor. Save `next_cursor` and pass it as the next `after` value for at-least-once
polling without holding the Blender command connection open. Events include job,
status, attempt, progress, resource, and timestamp. The journal retains 2,000
events by default (`BLENDER_MCP_MAX_ASYNC_EVENTS`). `cursor_expired` signals that
the requested cursor predates the retained window. Pass `clear_events=true` to
`cleanup_async_jobs` when the durable event history should also be discarded.

## Resource packaging

`resource_package(action="audit")` reports file-backed images, packed state,
missing dependencies, current blend path, and dirty state. The `pack` action
refuses to run when dependencies are missing, optionally makes paths relative,
and then packs resources into the blend file.

## Boolean, curves, and typography

`boolean_model` performs exact or fast union, difference, and intersection
operations with optional modifier application and cutter hiding. `curve_create`
builds editable Bezier paths, beveled cables, and extruded text, with optional
conversion to mesh.

## Material graphs and render passes

`material_nodes` inspects complete material graphs and can add nodes, set input
values, create links, or remove nodes. `render_passes` configures supported view
layer passes, Cryptomatte, and transparent film output.

## Scene change tracking and cleanup

`scene_diff` stores compact named snapshots and reports added, removed, and
changed objects. Transform, parenting, visibility, modifiers, materials, and
mesh topology counts participate in comparisons.

`data_cleanup` audits unused datablocks using bounded samples to keep MCP
responses manageable. Its destructive `purge` action is explicit and separate
from auditing.

## Context safety

Structured commands preserve the user's active object, selection, interaction
mode, current frame, 3D cursor transform, and mesh selection mode on both
success and failure. `execute_code` is intentionally unrestricted, while
`scene_manage(action="select")` is the explicit exception that keeps its new
selection result. Context restoration warnings are included in the standard
command envelope instead of being silently discarded.

## Advanced operation compatibility

`AdvancedObjectOperations` keeps its original typed Python API, but every public
method now sends an `advanced_operation` command through the live Blender TCP
connection. The previous placeholder result bodies have been removed. The
Blender addon contains a corresponding handler branch for every public method;
connection failures and invalid parameters propagate as real errors rather than
fabricated success dictionaries.

## Transport protocol

`get_capabilities` negotiates protocol, addon, Blender, feature, envelope, and
advanced-operation information before a workflow starts. Protocol errors and
addon failures use `BlenderProtocolError` and `BlenderCommandError`; the latter
preserves command name, error code, Blender exception type, retriable state, and
execution metadata.

Command logs recursively redact API keys, tokens, secrets, passwords,
authorization headers, cookies, and credentials. Requests default to an 8 MiB
limit and responses to 64 MiB, configurable with
`BLENDER_MCP_MAX_REQUEST_BYTES` and `BLENDER_MCP_MAX_RESPONSE_BYTES`.
`max_retries` means retries after the initial attempt.

The Blender addon independently enforces the same request and response limits,
so direct TCP clients cannot bypass the MCP server guard. Its pending command
queue defaults to 256 entries (`BLENDER_MCP_MAX_COMMAND_QUEUE`); overflow returns
a retriable `COMMAND_QUEUE_FULL` protocol error.
