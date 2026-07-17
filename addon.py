#================================================================
#  ================================================================
#  addon.py
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
#      Blender addon 鈥?TCP server, bpy API execution, MCP tool implementation
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
#================================================================

# Code created by Siddharth Ahuja: www.github.com/ahujasid 漏 2025

import re
import csv
import bpy
import bmesh
import mathutils
import json
import threading
import socket
import time
import requests
import tempfile
import traceback
import os
import subprocess
import uuid
import shutil
import zipfile
from bpy.props import IntProperty, BoolProperty
import io
from datetime import datetime
import hashlib, hmac, base64
import os.path as osp
from contextlib import redirect_stdout, suppress, contextmanager, nullcontext

bl_info = {
    "name": "Blender MCP",
    "author": "BlenderMCP",
    "version": (1, 5, 5),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Connect Blender to Claude via MCP",
    "category": "Interface",
}

# Default Hyper3D free trial key 鈥?migrate to config_new.py APIKeys.hyper3d_free_trial_key
# Override with env var BLENDER_MCP_HYPER3D_API_KEY in production
RODIN_FREE_TRIAL_KEY = os.getenv("BLENDER_MCP_HYPER3D_FREE_TRIAL_KEY", "")

# Add User-Agent as required by Poly Haven API
REQ_HEADERS = requests.utils.default_headers()
REQ_HEADERS.update({"User-Agent": "blender-mcp"})
REQUEST_TIMEOUT = (10, 60)
MAX_ADDON_REQUEST_BYTES = int(os.getenv("BLENDER_MCP_MAX_REQUEST_BYTES", str(8 * 1024 * 1024)))
MAX_ADDON_RESPONSE_BYTES = int(os.getenv("BLENDER_MCP_MAX_RESPONSE_BYTES", str(64 * 1024 * 1024)))
MAX_COMMAND_QUEUE_SIZE = int(os.getenv("BLENDER_MCP_MAX_COMMAND_QUEUE", "256"))
MAX_ASYNC_JOBS = max(1, int(os.getenv("BLENDER_MCP_MAX_ASYNC_JOBS", "128")))
MAX_ASYNC_WORKERS = max(1, int(os.getenv("BLENDER_MCP_MAX_ASYNC_WORKERS", "2")))
MAX_ASYNC_RETRIES = 10
MAX_ASYNC_CPU_JOBS = max(1, int(os.getenv("BLENDER_MCP_MAX_ASYNC_CPU_JOBS", str(MAX_ASYNC_WORKERS))))
MAX_ASYNC_GPU_JOBS = max(1, int(os.getenv("BLENDER_MCP_MAX_ASYNC_GPU_JOBS", "1")))
MAX_ASYNC_EVENTS = max(100, int(os.getenv("BLENDER_MCP_MAX_ASYNC_EVENTS", "2000")))


def http_get(url, *args, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.get(url, *args, **kwargs)


def http_post(url, *args, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.post(url, *args, **kwargs)


# ============================================================
# Safe scene accessor 鈥?avoids _RestrictContext AttributeError
# ============================================================
# In Blender 5.x, get_current_scene() may raise AttributeError in
# certain contexts (UI registration, restricted threads).  This
# helper always returns a valid Scene object or the active one.
# ============================================================

def get_current_scene():
    """Return the active scene safely.

    Tries bpy.context.scene first (may raise in restricted contexts);
    falls back to bpy.data.scenes[0] when the attribute is unavailable.
    """
    try:
        s = bpy.context.scene
        if s is not None:
            return s
    except AttributeError:
        pass  # _RestrictContext 鈥?no .scene attribute
    except Exception:
        pass
    # Absolute fallback 鈥?bpy.data.scenes[0] is always safe
    return bpy.data.scenes[0]


def get_selected_objects():
    """Return selected objects safely across UI, timer, and background contexts."""
    try:
        return list(bpy.context.selected_objects)
    except AttributeError:
        return [obj for obj in bpy.data.objects if getattr(obj, "select_get", lambda: False)()]
    except Exception:
        return []


# ============================================================
# Blender 5.x Animation API Compatibility Layer
# ============================================================
# In Blender 5.1+, action.fcurves was removed and replaced with
# a hierarchical structure: action.layers -> strips -> channelbags -> fcurves
#
# Old path (Blender 4.x / legacy):
#   action.fcurves  鈫?list of FCurve objects
#
# New path (Blender 5.x+):
#   action.layers[0].strips[0].channelbags[0].fcurves
#
# This module-level helper provides a unified access point.
# ============================================================

def get_action_fcurves(action):
    """Retrieve FCurves from a Blender Action, compatible with both 4.x and 5.x+.

    Parameters
    ----------
    action : bpy.types.Action or None
        The animation action to query.

    Returns
    -------
    list
        A list of FCurve objects (may be empty).
        Never raises 鈥?returns [] on any access error.
    """
    if action is None:
        return []

    # ---- Legacy: Blender 4.x and earlier ----
    # action.fcurves exists directly on the Action object
    try:
        legacy = action.fcurves
        if hasattr(legacy, "__iter__") or hasattr(legacy, "__len__"):
            return list(legacy)
    except AttributeError:
        pass  # attribute does not exist 鈥?falls through to 5.x path

    # ---- Blender 5.x+ ----
    # New hierarchy: action.layers -> strips -> channelbags -> fcurves
    try:
        layers = action.layers
        if not layers or len(layers) == 0:
            return []
        layer = layers[0]
        strips = layer.strips
        if not strips or len(strips) == 0:
            return []
        strip = strips[0]
        bags = strip.channelbags
        if not bags or len(bags) == 0:
            return []
        bag = bags[0]
        fcurves = bag.fcurves
        if fcurves:
            return list(fcurves)
    except (AttributeError, IndexError, TypeError):
        pass  # any structural mismatch 鈫?empty

    return []


def get_action_keyframe_count(action):
    """Count total keyframes across all FCurves in an Action.

    Works with both legacy ``action.fcurves`` (Blender 4.x) and
    the new ``channelbags[0].fcurves`` path (Blender 5.x+).

    Parameters
    ----------
    action : bpy.types.Action or None

    Returns
    -------
    int
        Total number of keyframe_points across all fcurves.
    """
    if action is None:
        return 0

    fcurves = get_action_fcurves(action)
    count = 0
    for fc in fcurves:
        # Blender 5.x uses keyframe_points (not data_points)
        if hasattr(fc, "keyframe_points"):
            count += len(fc.keyframe_points)
        elif hasattr(fc, "data_points"):
            count += len(fc.data_points)
    return count



# ============================================================
# Safe scene property getters
# ============================================================
def get_scene_property(prop_name, default=None):
    try:
        scene = get_current_scene()
        if hasattr(scene, prop_name):
            return getattr(scene, prop_name)
    except Exception:
        pass
    return default


class AsyncJobManager:
    """Non-blocking render/bake subprocesses and HTTP downloads."""

    TERMINAL = {"completed", "failed", "cancelled"}

    def __init__(self):
        self.jobs = {}
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.stopping = False
        self.events = []
        self.next_event_id = 1
        self.active_resources = {"cpu": 0, "gpu": 0}
        self.resource_limits = {"cpu": MAX_ASYNC_CPU_JOBS, "gpu": MAX_ASYNC_GPU_JOBS}
        default_dir = bpy.utils.user_resource("CONFIG", path="blender_mcp", create=True)
        self.state_path = os.path.abspath(os.getenv(
            "BLENDER_MCP_ASYNC_STATE_PATH", os.path.join(default_dir, "async_jobs.json")
        ))
        self._load()
        self.workers = [threading.Thread(
            target=self._worker_loop, daemon=True, name=f"BlenderMCPWorker-{index + 1}"
        ) for index in range(MAX_ASYNC_WORKERS)]
        for worker in self.workers: worker.start()

    @staticmethod
    def _now(): return datetime.now().isoformat()

    @staticmethod
    def _public(job): return {key: value for key, value in job.items() if not key.startswith("_")}

    def submit(self, kind, params, snapshot_path=None, priority=0, max_retries=0,
               retry_delay=2.0, depends_on=None, resource="auto"):
        if kind not in {"render", "bake", "download"}: raise ValueError("kind must be render, bake, or download")
        priority = max(-100, min(100, int(priority)))
        max_retries = max(0, min(MAX_ASYNC_RETRIES, int(max_retries)))
        retry_delay = max(0.1, min(3600.0, float(retry_delay)))
        depends_on = list(dict.fromkeys(depends_on or []))
        resource = str(resource).lower()
        if resource not in {"auto", "cpu", "gpu"}: raise ValueError("resource must be auto, cpu, or gpu")
        if resource == "auto":
            device = str(params.get("device", "")).upper()
            resource = "gpu" if kind in {"render", "bake"} and device == "GPU" else "cpu"
        if resource == "gpu" and kind in {"render", "bake"}:
            params = dict(params); params.setdefault("device", "GPU")
        job_id = uuid.uuid4().hex
        job = {"job_id": job_id, "kind": kind, "status": "blocked" if depends_on else "queued", "progress": 0.0,
               "message": "Queued", "created_at": self._now(), "started_at": None,
               "finished_at": None, "outputs": [], "error": None, "log_tail": [],
               "priority": priority, "attempt": 0, "max_retries": max_retries,
               "retry_delay": retry_delay, "retry_at": None, "recovered": False,
               "depends_on": depends_on, "resource": resource,
               "_params": dict(params), "_snapshot_path": snapshot_path,
               "_ready_at": 0.0, "_cancel": threading.Event(), "_pause": threading.Event(),
               "_process": None, "_response": None}
        with self.condition:
            missing = [dependency for dependency in depends_on if dependency not in self.jobs]
            if missing:
                if snapshot_path: shutil.rmtree(os.path.dirname(snapshot_path), ignore_errors=True)
                raise ValueError(f"Unknown dependency jobs: {missing}")
            if len(self.jobs) >= MAX_ASYNC_JOBS:
                protected = {dependency for item in self.jobs.values() if item["status"] not in self.TERMINAL
                             for dependency in item.get("depends_on", [])}
                terminal = sorted(
                    (item for item in self.jobs.values()
                     if item["status"] in self.TERMINAL and item["job_id"] not in protected),
                    key=lambda item: item["created_at"],
                )
                while terminal and len(self.jobs) >= MAX_ASYNC_JOBS:
                    self.jobs.pop(terminal.pop(0)["job_id"], None)
            if len(self.jobs) >= MAX_ASYNC_JOBS:
                if snapshot_path: shutil.rmtree(os.path.dirname(snapshot_path), ignore_errors=True)
                raise RuntimeError(f"Async job queue reached {MAX_ASYNC_JOBS} items")
            self.jobs[job_id] = job
            self._refresh_dependencies_locked()
            self._emit_locked(job, "submitted")
            self._persist_locked()
            self.condition.notify()
            return self._public(job)

    def get(self, job_id):
        with self.lock:
            if job_id not in self.jobs: raise ValueError(f"Job not found: {job_id}")
            return self._public(self.jobs[job_id])

    def list(self, status=None, limit=50):
        with self.lock: jobs = [self._public(job) for job in self.jobs.values() if status is None or job["status"] == status]
        return sorted(jobs, key=lambda item: item["created_at"], reverse=True)[:max(1, min(int(limit), 500))]

    def pause(self, job_id):
        with self.condition:
            if job_id not in self.jobs: raise ValueError(f"Job not found: {job_id}")
            job = self.jobs[job_id]
            if job["status"] in self.TERMINAL: raise ValueError("Terminal jobs cannot be paused")
            if job["status"] in {"paused", "pausing"}: return self._public(job)
            was_running = job["status"] in {"running", "cancelling"}
            job["_pause"].set()
            job.update(status="pausing" if was_running else "paused",
                       message="Pause requested" if was_running else "Paused")
            self._emit_locked(job, "pause_requested" if was_running else "paused")
            process = job.get("_process")
            response = job.get("_response")
            self._persist_locked(); self.condition.notify_all()
        if process and process.poll() is None:
            try: process.terminate()
            except Exception: pass
        if response:
            try: response.close()
            except Exception: pass
        return self.get(job_id)

    def resume(self, job_id):
        with self.condition:
            if job_id not in self.jobs: raise ValueError(f"Job not found: {job_id}")
            job = self.jobs[job_id]
            if job["status"] != "paused": raise ValueError("Only paused jobs can be resumed")
            job["_pause"].clear(); job["_cancel"].clear()
            job.update(status="blocked" if job.get("depends_on") else "queued",
                       message="Waiting for dependencies" if job.get("depends_on") else "Resumed and queued",
                       finished_at=None, retry_at=None, _ready_at=0.0)
            self._refresh_dependencies_locked()
            self._emit_locked(job, "resumed")
            self._persist_locked(); self.condition.notify_all()
            return self._public(job)

    def graph(self):
        with self.lock:
            nodes = [{"job_id": job["job_id"], "kind": job["kind"], "status": job["status"],
                      "priority": job.get("priority", 0), "resource": job.get("resource", "cpu")}
                     for job in self.jobs.values()]
            edges = [{"from": dependency, "to": job["job_id"]}
                     for job in self.jobs.values() for dependency in job.get("depends_on", [])]
            return {"nodes": nodes, "edges": edges}

    def get_events(self, after=0, limit=100, job_id=None):
        with self.lock:
            after = int(after)
            oldest_cursor = self.events[0]["event_id"] if self.events else self.next_event_id
            events = [event for event in self.events
                      if event["event_id"] > after and (job_id is None or event["job_id"] == job_id)]
            events = events[:max(1, min(int(limit), 500))]
            return {"events": events, "next_cursor": events[-1]["event_id"] if events else after,
                    "latest_cursor": self.next_event_id - 1, "oldest_cursor": oldest_cursor,
                    "cursor_expired": after < oldest_cursor - 1}

    def resources(self):
        with self.lock:
            queued = {name: sum(job["status"] in {"queued", "blocked"} and job.get("resource") == name
                                for job in self.jobs.values()) for name in self.resource_limits}
            return {"active": dict(self.active_resources), "limits": dict(self.resource_limits), "queued": queued}

    def cancel(self, job_id):
        with self.condition:
            if job_id not in self.jobs: raise ValueError(f"Job not found: {job_id}")
            job = self.jobs[job_id]
            if job["status"] in self.TERMINAL: return self._public(job)
            was_queued = job["status"] in {"queued", "blocked", "paused"}
            job["_pause"].clear()
            job["_cancel"].set()
            if was_queued:
                job.update(status="cancelled", message="Cancelled before start", finished_at=self._now())
            else:
                job.update(status="cancelling", message="Cancellation requested")
            self._emit_locked(job, "cancelled" if was_queued else "cancel_requested")
            process = job.get("_process")
            response = job.get("_response")
            result = self._public(job)
            self._persist_locked()
            self.condition.notify_all()
        if was_queued:
            snapshot = job.get("_snapshot_path")
            if snapshot: shutil.rmtree(os.path.dirname(snapshot), ignore_errors=True)
            return result
        if process and process.poll() is None:
            try: process.terminate()
            except Exception: pass
        if response:
            try: response.close()
            except Exception: pass
        return self.get(job_id)

    def cleanup(self, keep_latest=100, clear_events=False):
        with self.lock:
            protected = {dependency for job in self.jobs.values() if job["status"] not in self.TERMINAL
                         for dependency in job.get("depends_on", [])}
            terminal = sorted((job for job in self.jobs.values() if job["status"] in self.TERMINAL),
                              key=lambda item: item["created_at"], reverse=True)
            removed = [job["job_id"] for job in terminal[max(0, int(keep_latest)):]
                       if job["job_id"] not in protected]
            for job_id in removed: self.jobs.pop(job_id, None)
            events_removed = len(self.events) if clear_events else 0
            if clear_events: self.events = []
            self._persist_locked()
            return {"removed": removed, "remaining": len(self.jobs), "events_removed": events_removed}

    def shutdown(self):
        with self.lock: job_ids = list(self.jobs)
        for job_id in job_ids:
            try: self.cancel(job_id)
            except Exception: pass
        with self.condition:
            self.stopping = True
            self.condition.notify_all()

    def _set(self, job, persist=True, **values):
        with self.lock:
            previous = job.get("status")
            job.update(values)
            if job.get("status") != previous: self._emit_locked(job, "status_changed")
            if persist: self._persist_locked()

    def _emit_locked(self, job, event_type, details=None):
        event = {"event_id": self.next_event_id, "timestamp": self._now(),
                 "event": event_type, "job_id": job["job_id"], "kind": job["kind"],
                 "status": job["status"], "progress": job.get("progress", 0.0),
                 "attempt": job.get("attempt", 0), "resource": job.get("resource", "cpu")}
        if details: event["details"] = details
        self.next_event_id += 1
        self.events.append(event)
        self.events = self.events[-MAX_ASYNC_EVENTS:]

    def _refresh_dependencies_locked(self):
        changed = True
        while changed:
            changed = False
            for job in self.jobs.values():
                if job["status"] != "blocked": continue
                dependencies = [self.jobs.get(job_id) for job_id in job.get("depends_on", [])]
                failed = next((item for item in dependencies
                               if item and item["status"] in {"failed", "cancelled"}), None)
                if failed:
                    job.update(status="failed", finished_at=self._now(),
                               message=f"Dependency {failed['job_id']} ended as {failed['status']}",
                               error={"type": "DependencyError", "message": "A dependency did not complete"})
                    self._emit_locked(job, "dependency_failed", {"dependency": failed["job_id"]})
                    snapshot = job.get("_snapshot_path")
                    if snapshot: shutil.rmtree(os.path.dirname(snapshot), ignore_errors=True)
                    changed = True
                elif dependencies and all(item and item["status"] == "completed" for item in dependencies):
                    job.update(status="queued", message="Dependencies completed", _ready_at=0.0)
                    self._emit_locked(job, "dependencies_completed")
                    changed = True
                else:
                    job["message"] = "Waiting for dependencies"

    def _worker_loop(self):
        while True:
            with self.condition:
                job = None
                while job is None:
                    if self.stopping: return
                    self._refresh_dependencies_locked()
                    now = time.time()
                    ready = [item for item in self.jobs.values()
                             if item["status"] == "queued" and item.get("_ready_at", 0.0) <= now
                             and self.active_resources[item.get("resource", "cpu")] <
                             self.resource_limits[item.get("resource", "cpu")]]
                    if ready:
                        job = min(ready, key=lambda item: (-item.get("priority", 0), item["created_at"]))
                        resource = job.get("resource", "cpu")
                        self.active_resources[resource] += 1
                        job.update(status="running", started_at=self._now(), finished_at=None,
                                   message="Running", retry_at=None, attempt=job.get("attempt", 0) + 1,
                                   _process=None)
                        self._emit_locked(job, "started")
                        self._persist_locked()
                        break
                    future = [item.get("_ready_at", 0.0) for item in self.jobs.values()
                              if item["status"] == "queued" and item.get("_ready_at", 0.0) > now]
                    timeout = max(0.05, min(future) - now) if future else None
                    self.condition.wait(timeout=timeout)
            self._execute(job)
            with self.condition:
                resource = job.get("resource", "cpu")
                self.active_resources[resource] = max(0, self.active_resources[resource] - 1)
                self._refresh_dependencies_locked()
                self._persist_locked()
                self.condition.notify_all()

    def _execute(self, job):
        try:
            if job["kind"] == "download": self._download(job)
            else: self._blender(job)
            if job["_pause"].is_set():
                self._set(job, status="paused", message="Paused", finished_at=None, _process=None)
            elif job["_cancel"].is_set():
                self._set(job, status="cancelled", message="Cancelled", finished_at=self._now())
            else:
                self._set(job, status="completed", progress=1.0, message="Completed",
                          finished_at=self._now(), error=None)
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            with self.condition:
                if job["_cancel"].is_set():
                    job.update(status="cancelled", message="Cancelled", finished_at=self._now(), error=None)
                    self._emit_locked(job, "cancelled")
                elif job["_pause"].is_set():
                    job.update(status="paused", message="Paused", finished_at=None, error=None, _process=None)
                    self._emit_locked(job, "paused")
                elif job.get("attempt", 1) <= job.get("max_retries", 0):
                    delay = job["retry_delay"] * (2 ** max(0, job["attempt"] - 1))
                    ready_at = time.time() + delay
                    job.update(status="queued", message=f"Retrying in {delay:.1f}s", error=error,
                               retry_at=datetime.fromtimestamp(ready_at).isoformat(), _ready_at=ready_at,
                               _process=None)
                    self._emit_locked(job, "retry_scheduled", {"delay": delay})
                    self.condition.notify()
                else:
                    job.update(status="failed", message=str(exc), finished_at=self._now(), error=error)
                    self._emit_locked(job, "failed")
                self._persist_locked()
        finally:
            if job["status"] in self.TERMINAL:
                snapshot = job.get("_snapshot_path")
                if snapshot: shutil.rmtree(os.path.dirname(snapshot), ignore_errors=True)

    def _persist_locked(self):
        try:
            records = []
            for job in self.jobs.values():
                record = self._public(job)
                record["params"] = job.get("_params", {})
                record["snapshot_path"] = job.get("_snapshot_path")
                record["ready_at"] = job.get("_ready_at", 0.0)
                records.append(record)
            folder = os.path.dirname(self.state_path)
            os.makedirs(folder, exist_ok=True)
            temporary = self.state_path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump({"version": 2, "jobs": records, "events": self.events,
                           "next_event_id": self.next_event_id}, handle, ensure_ascii=False, indent=2)
            os.replace(temporary, self.state_path)
        except Exception as exc:
            print(f"BlenderMCP async state persistence failed: {exc}")

    def _load(self):
        if not os.path.isfile(self.state_path): return
        try:
            with open(self.state_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            records = payload.get("jobs", [])
            self.events = payload.get("events", [])[-MAX_ASYNC_EVENTS:]
            self.next_event_id = max(int(payload.get("next_event_id", 1)),
                                     (self.events[-1]["event_id"] + 1) if self.events else 1)
            for record in records[-MAX_ASYNC_JOBS:]:
                job = {key: value for key, value in record.items()
                       if key not in {"params", "snapshot_path", "ready_at"}}
                job.update(_params=record.get("params", {}),
                           _snapshot_path=record.get("snapshot_path"),
                           _ready_at=record.get("ready_at", 0.0),
                           _cancel=threading.Event(), _pause=threading.Event(),
                           _process=None, _response=None)
                job.setdefault("priority", 0)
                job.setdefault("attempt", 0)
                job.setdefault("max_retries", 0)
                job.setdefault("retry_delay", 2.0)
                job.setdefault("retry_at", None)
                job.setdefault("recovered", False)
                job.setdefault("depends_on", [])
                job.setdefault("resource", "cpu")
                original_status = job.get("status")
                if original_status not in self.TERMINAL:
                    snapshot = job.get("_snapshot_path")
                    if job.get("kind") in {"render", "bake"} and not (snapshot and os.path.isfile(snapshot)):
                        job.update(status="failed", finished_at=self._now(),
                                   message="Recovery snapshot is missing",
                                   error={"type": "RecoveryError", "message": "Recovery snapshot is missing"})
                    elif original_status == "paused":
                        job["_pause"].set()
                        job.update(status="paused", message="Paused")
                    elif original_status == "blocked":
                        job.update(status="blocked", message="Waiting for dependencies")
                    else:
                        job.update(status="queued", started_at=None, finished_at=None, retry_at=None,
                                   recovered=True, message="Recovered after Blender restart", _ready_at=0.0)
                        self._emit_locked(job, "recovered")
                self.jobs[job["job_id"]] = job
            self._refresh_dependencies_locked()
        except Exception as exc:
            print(f"BlenderMCP async state recovery failed: {exc}")

    def _download(self, job):
        params = job["_params"]; url, output = params.get("url"), params.get("output_path")
        if not url or not str(url).lower().startswith(("http://", "https://")): raise ValueError("download url must use http or https")
        if not output: raise ValueError("output_path is required")
        output = os.path.abspath(output); os.makedirs(os.path.dirname(output), exist_ok=True); partial = output + ".part"
        response = http_get(url, stream=True); response.raise_for_status(); total = int(response.headers.get("content-length") or 0); received = 0
        self._set(job, persist=False, _response=response)
        try:
            with open(partial, "wb") as handle:
                for chunk in response.iter_content(chunk_size=262144):
                    if job["_cancel"].is_set() or job["_pause"].is_set(): return
                    if chunk:
                        handle.write(chunk); received += len(chunk)
                        if total: self._set(job, persist=False, progress=min(received / total, .99), message=f"Downloaded {received}/{total} bytes")
            os.replace(partial, output); self._set(job, outputs=[output])
        finally:
            response.close()
            self._set(job, persist=False, _response=None)
            if job["_cancel"].is_set() and os.path.exists(partial): os.remove(partial)

    def _blender(self, job):
        params, snapshot = job["_params"], job["_snapshot_path"]
        folder = os.path.dirname(snapshot); script_path = os.path.join(folder, "job.py"); manifest = os.path.join(folder, "manifest.json")
        script = self._render_script(params, manifest) if job["kind"] == "render" else self._bake_script(params, manifest)
        if params.get("device") and job["kind"] == "render":
            script = script.replace(
                'if p.get("resolution"):s.render.resolution_x,s.render.resolution_y=p["resolution"]',
                'if s.render.engine=="CYCLES":s.cycles.device=p.get("device","CPU").upper()\n'
                'if p.get("resolution"):s.render.resolution_x,s.render.resolution_y=p["resolution"]',
            )
        elif params.get("device") and job["kind"] == "bake":
            script = script.replace(
                'bpy.context.scene.render.engine="CYCLES";',
                'bpy.context.scene.render.engine="CYCLES";bpy.context.scene.cycles.device=p.get("device","CPU").upper();',
            )
        with open(script_path, "w", encoding="utf-8") as handle: handle.write(script)
        process = subprocess.Popen([bpy.app.binary_path, "--background", snapshot, "--python", script_path],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   encoding="utf-8", errors="replace")
        self._set(job, persist=False, _process=process)
        for line in process.stdout:
            line = line.rstrip()
            if line:
                with self.lock: job["log_tail"] = (job["log_tail"] + [line])[-50:]
            if line.startswith("MCP_PROGRESS "):
                current, total = map(int, line.split()[1:3]); self._set(job, persist=False, progress=current / max(total, 1))
            if (job["_cancel"].is_set() or job["_pause"].is_set()) and process.poll() is None: process.terminate()
        code = process.wait()
        if job["_cancel"].is_set() or job["_pause"].is_set(): return
        if code: raise RuntimeError(f"Blender subprocess exited with code {code}")
        if not os.path.isfile(manifest): raise RuntimeError("Job manifest was not created")
        with open(manifest, encoding="utf-8") as handle: self._set(job, outputs=json.load(handle).get("outputs", []))

    @staticmethod
    def _render_script(params, manifest):
        p, m = json.dumps(params), manifest
        return f'''import bpy,json,os\np=json.loads({p!r});s=bpy.context.scene\ne=p.get("engine")\nif e:s.render.engine={{"EEVEE":"BLENDER_EEVEE","CYCLES":"CYCLES"}}.get(e.upper(),e)\nif p.get("resolution"):s.render.resolution_x,s.render.resolution_y=p["resolution"]\ns.render.resolution_percentage=100;s.render.image_settings.file_format=p.get("file_format","PNG")\nif p.get("camera_name"):s.camera=bpy.data.objects.get(p["camera_name"])\nif s.camera is None:raise RuntimeError("No render camera configured")\nf=p.get("frames") or list(range(int(p.get("frame_start",s.frame_current)),int(p.get("frame_end",s.frame_current))+1));d=p.get("output_dir") or os.path.dirname(p.get("output_path") or "") or os.getcwd();os.makedirs(d,exist_ok=True);x={{"PNG":"png","JPEG":"jpg","OPEN_EXR":"exr"}}.get(s.render.image_settings.file_format,s.render.image_settings.file_format.lower());o=[]\nfor i,n in enumerate(f,1):\n s.frame_set(n);q=p.get("output_path") if len(f)==1 and p.get("output_path") else os.path.join(d,f"{{s.camera.name}}_f{{n:04d}}.{{x}}");s.render.filepath=q;bpy.ops.render.render(write_still=True);o.append(q);print(f"MCP_PROGRESS {{i}} {{len(f)}}",flush=True)\nwith open({m!r},"w") as h:json.dump({{"outputs":o}},h)\n'''

    @staticmethod
    def _bake_script(params, manifest):
        p, m = json.dumps(params), manifest
        return f'''import bpy,json,os\np=json.loads({p!r});o=bpy.data.objects.get(p.get("object_name"))\nif o is None or o.type!="MESH":raise RuntimeError("Bake mesh not found")\nbpy.ops.object.select_all(action="DESELECT");o.select_set(True);bpy.context.view_layer.objects.active=o\nif not o.data.uv_layers:bpy.ops.object.mode_set(mode="EDIT");bpy.ops.mesh.select_all(action="SELECT");bpy.ops.uv.smart_project();bpy.ops.object.mode_set(mode="OBJECT")\nz=int(p.get("resolution",1024));i=bpy.data.images.new("MCP_Bake",width=z,height=z)\nif not o.material_slots:o.data.materials.append(bpy.data.materials.new("MCP Bake Material"))\nfor t in o.material_slots:t.material.use_nodes=True;n=t.material.node_tree.nodes.new("ShaderNodeTexImage");n.image=i;t.material.node_tree.nodes.active=n\nbpy.context.scene.render.engine="CYCLES";bpy.context.scene.render.bake.margin=int(p.get("margin",16));bpy.ops.object.bake(type=p.get("bake_type","AO").upper());q=os.path.abspath(p["output_path"]);os.makedirs(os.path.dirname(q),exist_ok=True);i.filepath_raw=q;i.file_format="PNG";i.save();print("MCP_PROGRESS 1 1",flush=True)\nwith open({m!r},"w") as h:json.dump({{"outputs":[q]}},h)\n'''


class BlenderMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None
        self.command_queue = []
        self.queue_lock = threading.Lock()
        self.queue_poll_thread_stop = False
        self.async_jobs = AsyncJobManager()

    def start(self):
        if self.running:
            print("Server is already running")
            return

        self.running = True

        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(128)
            # Increase buffer sizes for reliable TCP
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

            # Start server thread
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()

            # In visible Blender, process commands on the main thread so bpy
            # operators that require UI context (for example glTF export) work.
            # In --background mode timers may not fire reliably, so use the
            # background polling thread there.
            if getattr(bpy.app, "background", False):
                self.queue_poll_thread = threading.Thread(target=self._queue_poll_loop, daemon=True)
                self.queue_poll_thread.start()
                print("Queue polling thread started (background mode)", flush=True)
            else:
                bpy.app.timers.register(self._process_command_queue, first_interval=0.05)
                print("Queue processing timer registered (visible UI mode)", flush=True)

            print(f"BlenderMCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
            self.stop()

    def stop(self):
        self.running = False
        if hasattr(self, "async_jobs"): self.async_jobs.shutdown()

        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        # Wait for thread to finish
        if self.server_thread:
            try:
                if self.server_thread.is_alive():
                    self.server_thread.join(timeout=1.0)
            except:
                pass
            self.server_thread = None

        # Stop queue poll thread
        if hasattr(self, 'queue_poll_thread'):
            self.queue_poll_thread_stop = True
            try:
                if self.queue_poll_thread.is_alive():
                    self.queue_poll_thread.join(timeout=1.0)
            except:
                pass
        try:
            if bpy.app.timers.is_registered(self._process_command_queue):
                bpy.app.timers.unregister(self._process_command_queue)
        except Exception:
            pass

        print("BlenderMCP server stopped")

    def _server_loop(self):
        """Main server loop in a separate thread"""
        print("Server thread started")
        self.socket.settimeout(1.0)  # Timeout to allow for stopping

        while self.running:
            try:
                # Accept new connection
                try:
                    client, address = self.socket.accept()
                    print(f"Connected to client: {address}")

                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    # Just check running condition
                    continue
                except Exception as e:
                    print(f"Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)

        print("Server thread stopped")

    def _handle_client(self, client):
        """Handle connected client - receives commands and queues them for main thread execution"""
        print("Client handler started", flush=True)
        client.settimeout(None)  # No timeout
        buffer = b''

        try:
            while self.running:
                # Receive data
                try:
                    data = client.recv(8192)
                    if not data:
                        print("Client disconnected (no data)", flush=True)
                        break

                    print(f"Received {len(data)} bytes", flush=True)
                    buffer += data
                    print(f"Buffer now {len(buffer)} bytes", flush=True)
                    if len(buffer) > MAX_ADDON_REQUEST_BYTES:
                        response = {
                            "status": "error", "ok": False, "command": None, "result": None,
                            "warnings": [], "error": {
                                "code": "REQUEST_TOO_LARGE", "type": "BlenderProtocolError",
                                "message": f"Request exceeded {MAX_ADDON_REQUEST_BYTES} bytes",
                                "retriable": False,
                            },
                            "message": f"Request exceeded {MAX_ADDON_REQUEST_BYTES} bytes",
                            "meta": {"blender_version": bpy.app.version_string},
                        }
                        client.sendall(json.dumps(response).encode('utf-8'))
                        break

                    try:
                        # Try to parse command
                        command = json.loads(buffer.decode('utf-8'))
                        buffer = b''
                        params = command.get("params") or {}
                        print(f"JSON parsed: type={command.get('type')} param_keys={sorted(params.keys())}", flush=True)

                        # Put command in queue for main thread to execute
                        # (bpy API only works in main thread)
                        with self.queue_lock:
                            if len(self.command_queue) >= MAX_COMMAND_QUEUE_SIZE:
                                response = {
                                    "status": "error", "ok": False, "command": command.get("type"),
                                    "result": None, "warnings": [], "error": {
                                        "code": "COMMAND_QUEUE_FULL", "type": "BlenderProtocolError",
                                        "message": f"Command queue reached {MAX_COMMAND_QUEUE_SIZE} items",
                                        "retriable": True,
                                    },
                                    "message": f"Command queue reached {MAX_COMMAND_QUEUE_SIZE} items",
                                    "meta": {"blender_version": bpy.app.version_string},
                                }
                                client.sendall(json.dumps(response).encode('utf-8'))
                                break
                            self.command_queue.append((command, client))
                        print(f"Command queued: {command.get('type')}", flush=True)

                    except json.JSONDecodeError:
                        # Incomplete data, wait for more
                        print("JSON decode error, waiting for more data", flush=True)
                        pass
                except Exception as e:
                    print(f"Error receiving data: {str(e)}", flush=True)
                    break
        except Exception as e:
            print(f"Error in client handler: {str(e)}", flush=True)
        finally:
            try:
                client.close()
            except:
                pass
            print("Client handler stopped", flush=True)

    def _process_command_queue(self):
        """Process queued commands in the main Blender thread (bpy-safe).

        This is called by a timer callback every 0.1s to execute commands
        that were queued from background threads.
        """
        try:
            while True:
                with self.queue_lock:
                    if not self.command_queue:
                        break
                    command, client = self.command_queue.pop(0)
                print(f"Processing command: {command.get('type')}", flush=True)

                try:
                    # Execute command in main thread (bpy-safe)
                    result = self._execute_command_internal(command)

                    # Send response back to client
                    response_json = json.dumps(result).encode('utf-8')
                    if len(response_json) > MAX_ADDON_RESPONSE_BYTES:
                        response_json = json.dumps({
                            "status": "error", "ok": False, "command": command.get("type"),
                            "result": None, "warnings": [], "error": {
                                "code": "RESPONSE_TOO_LARGE", "type": "BlenderProtocolError",
                                "message": f"Response exceeded {MAX_ADDON_RESPONSE_BYTES} bytes",
                                "retriable": False,
                            },
                            "message": f"Response exceeded {MAX_ADDON_RESPONSE_BYTES} bytes",
                            "meta": {"blender_version": bpy.app.version_string},
                        }).encode('utf-8')
                    try:
                        client.sendall(response_json)
                        print(f"Response sent for {command.get('type')}", flush=True)
                    except Exception as e:
                        print(f"Failed to send response: {str(e)}", flush=True)
                except Exception as e:
                    error_response = {"status": "error", "message": str(e)}
                    try:
                        client.sendall(json.dumps(error_response).encode('utf-8'))
                    except:
                        pass
                    print(f"Command execution error: {str(e)}", flush=True)
        except Exception as e:
            print(f"Queue processing error: {str(e)}", flush=True)

        return 0.05 if self.running else None

    def _queue_poll_loop(self):
        """Background thread that polls command_queue and executes commands.

        Used instead of bpy.app.timers because timers don't fire in --background mode.
        In background mode, bpy API calls from this thread work fine as long as
        we process commands one at a time (no concurrent calls).
        """
        print("Queue poll loop started", flush=True)
        while not self.queue_poll_thread_stop:
            try:
                command = None
                client = None
                with self.queue_lock:
                    if self.command_queue:
                        command, client = self.command_queue.pop(0)
                if command is None:
                    time.sleep(0.05)  # 50ms poll interval
                    continue

                print(f"Processing command: {command.get('type')}", flush=True)

                try:
                    result = self._execute_command_internal(command)

                    response_json = json.dumps(result).encode('utf-8')
                    if len(response_json) > MAX_ADDON_RESPONSE_BYTES:
                        response_json = json.dumps({
                            "status": "error", "ok": False, "command": command.get("type"),
                            "result": None, "warnings": [], "error": {
                                "code": "RESPONSE_TOO_LARGE", "type": "BlenderProtocolError",
                                "message": f"Response exceeded {MAX_ADDON_RESPONSE_BYTES} bytes",
                                "retriable": False,
                            },
                            "message": f"Response exceeded {MAX_ADDON_RESPONSE_BYTES} bytes",
                            "meta": {"blender_version": bpy.app.version_string},
                        }).encode('utf-8')
                    try:
                        client.sendall(response_json)
                        print(f"Response sent for {command.get('type')}", flush=True)
                    except Exception as e:
                        print(f"Failed to send response: {str(e)}", flush=True)
                except Exception as e:
                    error_response = {"status": "error", "message": str(e)}
                    try:
                        client.sendall(json.dumps(error_response).encode('utf-8'))
                    except:
                        pass
                    print(f"Command execution error: {str(e)}", flush=True)
            except Exception as e:
                print(f"Poll loop error: {str(e)}", flush=True)
                time.sleep(0.1)
        print("Queue poll loop stopped", flush=True)

    def execute_command(self, command):
        """Execute a command in the main Blender thread"""
        try:
            return self._execute_command_internal(command)

        except Exception as e:
            print(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    @contextmanager
    def _blender_context_guard(self, preserve_selection=True, preserve_frame=True,
                               preserve_cursor=True):
        """Restore user-facing Blender context after a structured command."""
        warnings = []
        try:
            active = getattr(bpy.context.view_layer.objects, "active", None)
            state = {
                "mode": getattr(bpy.context, "mode", "OBJECT"),
                "active": active.name if active else None,
                "selected": [obj.name for obj in get_selected_objects()],
                "frame": get_current_scene().frame_current,
                "cursor_location": list(get_current_scene().cursor.location),
                "cursor_rotation": list(get_current_scene().cursor.rotation_euler),
                "mesh_select_mode": list(get_current_scene().tool_settings.mesh_select_mode),
            }
        except Exception as exc:
            state = None; warnings.append(f"Could not capture Blender context: {exc}")
        try:
            yield warnings
        finally:
            if state is None:
                return
            try:
                if preserve_frame:
                    get_current_scene().frame_set(state["frame"])
                if preserve_cursor:
                    get_current_scene().cursor.location = state["cursor_location"]
                    get_current_scene().cursor.rotation_euler = state["cursor_rotation"]
                get_current_scene().tool_settings.mesh_select_mode = state["mesh_select_mode"]
                if preserve_selection:
                    if getattr(bpy.context, "mode", "OBJECT") != 'OBJECT':
                        try: bpy.ops.object.mode_set(mode='OBJECT')
                        except Exception: pass
                    bpy.ops.object.select_all(action='DESELECT')
                    for object_name in state["selected"]:
                        obj = bpy.data.objects.get(object_name)
                        if obj:
                            try: obj.select_set(True)
                            except Exception: pass
                    active_obj = bpy.data.objects.get(state["active"]) if state["active"] else None
                    if active_obj:
                        bpy.context.view_layer.objects.active = active_obj
                    mode_map = {
                        "EDIT_MESH": "EDIT", "EDIT_CURVE": "EDIT",
                        "EDIT_SURFACE": "EDIT", "EDIT_TEXT": "EDIT",
                        "EDIT_ARMATURE": "EDIT", "POSE": "POSE",
                        "SCULPT": "SCULPT", "PAINT_WEIGHT": "WEIGHT_PAINT",
                        "PAINT_VERTEX": "VERTEX_PAINT", "PAINT_TEXTURE": "TEXTURE_PAINT",
                    }
                    restore_mode = mode_map.get(state["mode"])
                    if restore_mode and active_obj:
                        try: bpy.ops.object.mode_set(mode=restore_mode)
                        except Exception as exc: warnings.append(f"Could not restore mode {state['mode']}: {exc}")
            except Exception as exc:
                warnings.append(f"Could not fully restore Blender context: {exc}")

    def _execute_command_internal(self, command):
        """Internal command execution with proper context"""
        cmd_type = command.get("type")
        params = command.get("params", {})

        # Base handlers that are always available
        handlers = {
            "get_scene_info": self.get_scene_info,
            "get_object_info": self.get_object_info,
            "get_viewport_screenshot": self.get_viewport_screenshot,
            "execute_code": self.execute_code,
            "get_telemetry_consent": self.get_telemetry_consent,
            "get_polyhaven_status": self.get_polyhaven_status,
            "get_hyper3d_status": self.get_hyper3d_status,
            "get_sketchfab_status": self.get_sketchfab_status,
            "get_hunyuan3d_status": self.get_hunyuan3d_status,
            # 鈹€鈹€鈹€ Structured Tool Schema Handlers 鈹€鈹€鈹€
            "create_cube": self._create_cube,
            "create_sphere": self._create_sphere,
            "create_cylinder": self._create_cylinder,
            "create_torus": self._create_torus,
            "create_plane": self._create_plane,
            "create_light": self._create_light,
            "create_camera": self._create_camera,
            "create_material": self._create_material,
            "apply_material": self._apply_material,
            "set_object_transform": self._set_object_transform,
            "delete_object": self._delete_object,
            "render_scene": self._render_scene,
            "import_model": self._import_model,
            "export_scene": self._export_scene,
            "set_render_engine": self._set_render_engine,
            "mesh_edit": self._mesh_edit,
            "modifier_control": self._modifier_control,
            "sculpt_refine": self._sculpt_refine,
            "mesh_quality": self._mesh_quality,
            "uv_tools": self._uv_tools,
            "pbr_material": self._pbr_material,
            "model_checkpoint": self._model_checkpoint,
            "modeling_recipe": self._modeling_recipe,
            "scene_manage": self._scene_manage,
            "character_rig": self._character_rig,
            "animation_control": self._animation_control,
            "geometry_nodes": self._geometry_nodes,
            "camera_compositor": self._camera_compositor,
            "asset_pipeline": self._asset_pipeline,
            "scene_measure": self._scene_measure,
            "batch_edit": self._batch_edit,
            "lighting_rig": self._lighting_rig,
            "simulation_setup": self._simulation_setup,
            "batch_render": self._batch_render,
            "resource_package": self._resource_package,
            "boolean_model": self._boolean_model,
            "curve_create": self._curve_create,
            "material_nodes": self._material_nodes,
            "render_passes": self._render_passes,
            "scene_diff": self._scene_diff,
            "data_cleanup": self._data_cleanup,
            "advanced_operation": self._advanced_operation,
            "get_capabilities": self._get_capabilities,
            "async_job_submit": self._async_job_submit,
            "async_job_status": self._async_job_status,
            "async_job_list": self._async_job_list,
            "async_job_cancel": self._async_job_cancel,
            "async_job_pause": self._async_job_pause,
            "async_job_resume": self._async_job_resume,
            "async_job_graph": self._async_job_graph,
            "async_job_events": self._async_job_events,
            "async_job_resources": self._async_job_resources,
            "async_job_cleanup": self._async_job_cleanup,
        }

        # Add Polyhaven handlers (always registered; runtime check inside)
        polyhaven_handlers = {
            "get_polyhaven_categories": self.get_polyhaven_categories,
            "search_polyhaven_assets": self.search_polyhaven_assets,
            "download_polyhaven_asset": self.download_polyhaven_asset,
            "set_texture": self.set_texture,
        }
        handlers.update(polyhaven_handlers)

        # Add Hyper3D handlers (always registered; runtime check inside)
        hyper3d_handlers = {
            "create_rodin_job": self.create_rodin_job,
            "poll_rodin_job_status": self.poll_rodin_job_status,
            "import_generated_asset": self.import_generated_asset,
        }
        handlers.update(hyper3d_handlers)

        # Add Sketchfab handlers only if enabled
        if get_scene_property("blendermcp_use_sketchfab", False):
            sketchfab_handlers = {
                "search_sketchfab_models": self.search_sketchfab_models,
                "get_sketchfab_model_preview": self.get_sketchfab_model_preview,
                "download_sketchfab_model": self.download_sketchfab_model,
            }
            handlers.update(sketchfab_handlers)

        # Add Hunyuan3d handlers only if enabled
        if get_scene_property("blendermcp_use_hunyuan3d", False):
            hunyuan_handlers = {
                "create_hunyuan_job": self.create_hunyuan_job,
                "poll_hunyuan_job_status": self.poll_hunyuan_job_status,
                "import_generated_asset_hunyuan": self.import_generated_asset_hunyuan
            }
            handlers.update(hunyuan_handlers)

        # 鈹€鈹€鈹€ BlenderKit handlers (always registered; runtime check inside) 鈹€鈹€鈹€
        blenderkit_handlers = {
            "blenderkit_status": self.blenderkit_status_handler,
            "blenderkit_search": self.blenderkit_search_handler,
            "blenderkit_download": self.blenderkit_download_handler,
            "blenderkit_append": self.blenderkit_append_handler,
            "blenderkit_apply_material": self.blenderkit_apply_material_handler,
            "blenderkit_set_hdri": self.blenderkit_set_hdri_handler,
            "blenderkit_list_cached": self.blenderkit_list_cached_handler,
            "blenderkit_reuse_cached": self.blenderkit_reuse_cached_handler,
            "blenderkit_auto_scene": self.blenderkit_auto_scene_handler,
            "blenderkit_login": self.blenderkit_login_handler,
        }
        handlers.update(blenderkit_handlers)

        # 鈹€鈹€鈹€ Camera alignment handlers 鈹€鈹€鈹€
        handlers["camera_align_to_selected"] = self.camera_align_to_selected
        handlers["camera_align_to_object"] = self.camera_align_to_object

        # 鈹€鈹€鈹€ Health check handler 鈹€鈹€鈹€
        handlers["health_check"] = self.health_check

        handler = handlers.get(cmd_type)
        if handler:
            started_at = time.perf_counter()
            context_warnings = []
            try:
                print(f"Executing handler for {cmd_type}")
                intentional_selection = (
                    (cmd_type == "scene_manage" and params.get("action") == "select") or
                    (cmd_type == "advanced_operation" and params.get("operation") in
                     {"select_object", "select_multiple_objects", "deselect_all"})
                )
                preserve_selection = not intentional_selection
                guard = (nullcontext([]) if cmd_type == "execute_code" else
                         self._blender_context_guard(preserve_selection=preserve_selection))
                with guard as context_warnings:
                    result = handler(**params)
                print(f"Handler execution complete")
                inner_status = result.get("status") if isinstance(result, dict) else None
                if cmd_type.startswith("async_job_"):
                    inner_status = None
                partial_states = {"partial", "rolled_back", "cancelled"}
                failed_states = {"error", "failed", "failure"}
                normalized_status = "success"
                ok = True
                if isinstance(inner_status, str) and inner_status.lower() in partial_states:
                    normalized_status = "partial"; ok = False
                elif isinstance(inner_status, str) and inner_status.lower() in failed_states:
                    normalized_status = "error"; ok = False
                warnings = result.get("warnings", []) if isinstance(result, dict) else []
                if isinstance(warnings, str): warnings = [warnings]
                warnings = list(warnings) + list(context_warnings)
                return {
                    "status": normalized_status,
                    "ok": ok,
                    "command": cmd_type,
                    "result": result,
                    "warnings": warnings,
                    "error": None if ok or normalized_status == "partial" else {
                        "code": "HANDLER_REPORTED_FAILURE",
                        "type": "HandlerFailure",
                        "message": result.get("error") or result.get("message") or "Command failed",
                        "retriable": False,
                    },
                    "meta": {
                        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                        "blender_version": bpy.app.version_string,
                        "timestamp": datetime.now().isoformat(),
                    },
                }
            except Exception as e:
                print(f"Error in handler: {str(e)}")
                traceback.print_exc()
                return {
                    "status": "error",
                    "ok": False,
                    "command": cmd_type,
                    "result": None,
                    "warnings": list(context_warnings),
                    "error": {
                        "code": "BLENDER_HANDLER_EXCEPTION",
                        "type": type(e).__name__,
                        "message": str(e),
                        "retriable": isinstance(e, (TimeoutError, ConnectionError)),
                    },
                    "message": str(e),
                    "meta": {
                        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                        "blender_version": bpy.app.version_string,
                        "timestamp": datetime.now().isoformat(),
                    },
                }
        else:
            message = f"Unknown command type: {cmd_type}"
            return {
                "status": "error", "ok": False, "command": cmd_type,
                "result": None, "warnings": [],
                "error": {"code": "UNKNOWN_COMMAND", "type": "LookupError",
                          "message": message, "retriable": False},
                "message": message,
                "meta": {"duration_ms": 0.0, "blender_version": bpy.app.version_string,
                         "timestamp": datetime.now().isoformat()},
            }



    def _require_mesh(self, object_name):
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object not found: {object_name}")
        if obj.type != 'MESH':
            raise TypeError(f"Object '{object_name}' is not a mesh")
        return obj

    @staticmethod
    def _mesh_stats(obj):
        mesh = obj.data
        return {
            "vertices": len(mesh.vertices),
            "edges": len(mesh.edges),
            "faces": len(mesh.polygons),
            "modifiers": [modifier.name for modifier in obj.modifiers],
        }

    @staticmethod
    def _activate_object(obj):
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    def _selected_bmesh_elements(self, bm, element_type, indices):
        collections = {
            "VERT": bm.verts,
            "EDGE": bm.edges,
            "FACE": bm.faces,
        }
        kind = element_type.upper()
        if kind not in collections:
            raise ValueError("element_type must be VERT, EDGE, or FACE")
        collection = collections[kind]
        collection.ensure_lookup_table()
        if indices is None:
            return list(collection)
        invalid = [index for index in indices if index < 0 or index >= len(collection)]
        if invalid:
            raise IndexError(f"Invalid {kind} indices: {invalid[:10]}")
        return [collection[index] for index in indices]

    def _mesh_edit(self, object_name, operation, element_type="FACE", indices=None,
                   amount=0.1, segments=1, merge_distance=0.0001,
                   use_clamp_overlap=True):
        """Perform deterministic topology edits using bmesh."""
        obj = self._require_mesh(object_name)
        self._activate_object(obj)
        before = self._mesh_stats(obj)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        elements = self._selected_bmesh_elements(bm, element_type, indices)
        op = operation.lower()
        if op == "extrude":
            if element_type.upper() != "FACE":
                raise ValueError("extrude currently requires FACE elements")
            result = bmesh.ops.extrude_discrete_faces(bm, faces=elements)
            faces = result.get("faces", [])
            for face in faces:
                offset = face.normal.normalized() * amount
                for vert in face.verts:
                    vert.co += offset
        elif op == "inset":
            if element_type.upper() != "FACE":
                raise ValueError("inset requires FACE elements")
            bmesh.ops.inset_individual(bm, faces=elements, thickness=amount, depth=0.0,
                                       use_even_offset=True)
        elif op == "bevel":
            if element_type.upper() not in {"VERT", "EDGE"}:
                raise ValueError("bevel requires VERT or EDGE elements")
            kwargs = {"geom": elements, "offset": amount, "segments": max(1, segments),
                      "affect": 'EDGES', "clamp_overlap": use_clamp_overlap}
            bmesh.ops.bevel(bm, **kwargs)
        elif op in {"subdivide", "loop_cut"}:
            edges = elements if element_type.upper() == "EDGE" else list(bm.edges)
            bmesh.ops.subdivide_edges(bm, edges=edges, cuts=max(1, segments), use_grid_fill=True)
        elif op == "merge_by_distance":
            verts = elements if element_type.upper() == "VERT" else list(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=verts, dist=merge_distance)
        elif op == "recalculate_normals":
            faces = elements if element_type.upper() == "FACE" else list(bm.faces)
            bmesh.ops.recalc_face_normals(bm, faces=faces)
        elif op == "delete":
            context = {"VERT": 'VERTS', "EDGE": 'EDGES', "FACE": 'FACES'}[element_type.upper()]
            bmesh.ops.delete(bm, geom=elements, context=context)
        elif op == "triangulate":
            faces = elements if element_type.upper() == "FACE" else list(bm.faces)
            bmesh.ops.triangulate(bm, faces=faces)
        else:
            bm.free()
            raise ValueError(f"Unsupported mesh operation: {operation}")
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        return {"object": object_name, "operation": op, "before": before,
                "after": self._mesh_stats(obj)}

    def _modifier_control(self, object_name, action="add", modifier_type="BEVEL",
                          name=None, settings=None, apply=False):
        obj = self._require_mesh(object_name)
        self._activate_object(obj)
        settings = settings or {}
        before = self._mesh_stats(obj)
        modifier_name = name or modifier_type.title()
        if action == "remove":
            modifier = obj.modifiers.get(modifier_name)
            if modifier is None:
                raise ValueError(f"Modifier not found: {modifier_name}")
            obj.modifiers.remove(modifier)
        else:
            modifier = obj.modifiers.get(modifier_name)
            if modifier is None:
                modifier = obj.modifiers.new(modifier_name, modifier_type.upper())
            for key, value in settings.items():
                if not hasattr(modifier, key):
                    raise ValueError(f"Modifier {modifier.type} has no setting '{key}'")
                setattr(modifier, key, value)
            if apply:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
        return {"object": object_name, "action": action, "modifier": modifier_name,
                "before": before, "after": self._mesh_stats(obj)}

    def _sculpt_refine(self, object_name, operation="voxel_remesh", voxel_size=0.05,
                       levels=1, smooth_iterations=1):
        obj = self._require_mesh(object_name)
        self._activate_object(obj)
        before = self._mesh_stats(obj)
        op = operation.lower()
        if op == "voxel_remesh":
            obj.data.remesh_voxel_size = max(0.00001, voxel_size)
            bpy.ops.object.voxel_remesh()
        elif op == "subdivide":
            modifier = obj.modifiers.new("MCP Multires", 'MULTIRES')
            for _ in range(max(1, levels)):
                bpy.ops.object.multires_subdivide(modifier=modifier.name, mode='CATMULL_CLARK')
        elif op == "smooth":
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            for _ in range(max(1, smooth_iterations)):
                bmesh.ops.smooth_vert(
                    bm,
                    verts=list(bm.verts),
                    factor=0.5,
                    use_axis_x=True,
                    use_axis_y=True,
                    use_axis_z=True,
                )
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
        else:
            raise ValueError("operation must be voxel_remesh, subdivide, or smooth")
        return {"object": object_name, "operation": op, "before": before,
                "after": self._mesh_stats(obj)}

    def _mesh_quality(self, object_name, action="inspect", merge_distance=0.0001,
                      degenerate_threshold=0.000001):
        obj = self._require_mesh(object_name)
        self._activate_object(obj)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
        def report():
            return {
                "non_manifold_edges": [e.index for e in bm.edges if not e.is_manifold],
                "boundary_edges": [e.index for e in bm.edges if e.is_boundary],
                "loose_vertices": [v.index for v in bm.verts if not v.link_edges],
                "loose_edges": [e.index for e in bm.edges if not e.link_faces],
                "degenerate_faces": [f.index for f in bm.faces if f.calc_area() <= degenerate_threshold],
                "ngons": [f.index for f in bm.faces if len(f.verts) > 4],
            }
        before_issues = report()
        if action == "repair":
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=merge_distance)
            bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=degenerate_threshold)
            loose_verts = [v for v in bm.verts if not v.link_edges]
            loose_edges = [e for e in bm.edges if not e.link_faces]
            if loose_edges:
                bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
            if loose_verts:
                bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(obj.data); obj.data.update()
        elif action != "inspect":
            bm.free()
            raise ValueError("action must be inspect or repair")
        after_issues = report()
        bm.free()
        return {"object": object_name, "action": action, "issues_before": before_issues,
                "issues_after": after_issues, "stats": self._mesh_stats(obj)}

    def _uv_tools(self, object_name, operation="smart_project", margin=0.02,
                  angle_limit=1.15192, scale_to_bounds=True):
        obj = self._require_mesh(object_name)
        self._activate_object(obj)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        op = operation.lower()
        if op == "smart_project":
            bpy.ops.uv.smart_project(angle_limit=angle_limit, island_margin=margin,
                                     scale_to_bounds=scale_to_bounds)
        elif op == "unwrap":
            bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=margin)
        elif op == "cube_project":
            bpy.ops.uv.cube_project(cube_size=1.0, correct_aspect=True)
        elif op == "pack_islands":
            bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', margin=margin)
        else:
            bpy.ops.object.mode_set(mode='OBJECT')
            raise ValueError("Unsupported UV operation")
        bpy.ops.object.mode_set(mode='OBJECT')
        return {"object": object_name, "operation": op,
                "uv_layers": [layer.name for layer in obj.data.uv_layers]}

    def _pbr_material(self, object_name, material_name="MCP PBR", textures=None,
                      base_color=None, metallic=0.0, roughness=0.5):
        obj = self._require_mesh(object_name)
        textures = textures or {}
        material = bpy.data.materials.get(material_name) or bpy.data.materials.new(material_name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if bsdf is None:
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        if output is None:
            output = nodes.new('ShaderNodeOutputMaterial')
        if not bsdf.outputs['BSDF'].is_linked:
            links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        if base_color:
            bsdf.inputs['Base Color'].default_value = tuple(base_color[:3]) + (base_color[3] if len(base_color) > 3 else 1.0,)
        bsdf.inputs['Metallic'].default_value = max(0.0, min(1.0, metallic))
        bsdf.inputs['Roughness'].default_value = max(0.0, min(1.0, roughness))
        socket_map = {"base_color": "Base Color", "roughness": "Roughness", "metallic": "Metallic"}
        created = []
        for slot, path in textures.items():
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            image_node = nodes.new('ShaderNodeTexImage')
            image_node.image = bpy.data.images.load(path, check_existing=True)
            image_node.label = slot
            if slot in {"roughness", "metallic", "normal", "displacement"}:
                image_node.image.colorspace_settings.name = 'Non-Color'
            if slot == "normal":
                normal = nodes.new('ShaderNodeNormalMap')
                links.new(image_node.outputs['Color'], normal.inputs['Color'])
                links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])
            elif slot in socket_map:
                links.new(image_node.outputs['Color'], bsdf.inputs[socket_map[slot]])
            created.append(slot)
        if material.name not in [slot.material.name for slot in obj.material_slots if slot.material]:
            obj.data.materials.append(material)
        return {"object": object_name, "material": material.name, "textures": created}

    def _checkpoint_collection(self):
        collection = bpy.data.collections.get("_MCP_CHECKPOINTS")
        if collection is None:
            collection = bpy.data.collections.new("_MCP_CHECKPOINTS")
            get_current_scene().collection.children.link(collection)
            collection.hide_viewport = True
            collection.hide_render = True
        return collection

    @staticmethod
    def _serialize_rna_settings(item, excluded=None):
        excluded = set(excluded or []) | {"rna_type", "name", "type"}
        settings = {}
        for prop in item.bl_rna.properties:
            key = prop.identifier
            if key in excluded or prop.is_readonly or prop.type in {'POINTER', 'COLLECTION'}:
                continue
            try:
                value = getattr(item, key)
                if prop.is_array:
                    value = list(value)
                if isinstance(value, (str, int, float, bool)) or value is None or isinstance(value, list):
                    settings[key] = value
            except Exception:
                continue
        return settings

    def _serialize_object_state(self, obj):
        constraints = []
        for constraint in obj.constraints:
            constraints.append({
                "type": constraint.type, "name": constraint.name,
                "settings": self._serialize_rna_settings(constraint, {"target", "subtarget"}),
                "target": constraint.target.name if hasattr(constraint, "target") and constraint.target else None,
                "subtarget": getattr(constraint, "subtarget", ""),
            })
        return {
            "matrix_world": [list(row) for row in obj.matrix_world],
            "location": list(obj.location), "rotation_euler": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "rotation_mode": obj.rotation_mode,
            "parent": obj.parent.name if obj.parent else None,
            "parent_type": obj.parent_type,
            "parent_bone": obj.parent_bone,
            "collections": [collection.name for collection in obj.users_collection
                            if collection.name != "_MCP_CHECKPOINTS"],
            "hide_viewport": obj.hide_viewport, "hide_render": obj.hide_render,
            "hide_select": obj.hide_select,
            "modifiers": [{"type": modifier.type, "name": modifier.name,
                           "settings": self._serialize_rna_settings(modifier)}
                          for modifier in obj.modifiers],
            "constraints": constraints,
        }

    @staticmethod
    def _apply_rna_settings(item, settings):
        for key, value in settings.items():
            try:
                setattr(item, key, value)
            except Exception:
                continue

    @staticmethod
    def _remove_checkpoint_backup(backup):
        data = backup.data
        materials = []
        if data and hasattr(data, "materials"):
            materials = [material for material in data.materials
                         if material and material.get("mcp_checkpoint_material")]
        action = backup.animation_data.action if backup.animation_data else None
        bpy.data.objects.remove(backup, do_unlink=True)
        if data and data.users == 0:
            if isinstance(data, bpy.types.Mesh): bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve): bpy.data.curves.remove(data)
            elif isinstance(data, bpy.types.Armature): bpy.data.armatures.remove(data)
        for material in materials:
            if material.users == 0: bpy.data.materials.remove(material)
        if action and action.users == 0: bpy.data.actions.remove(action)

    def _model_checkpoint(self, action="create", name="checkpoint", object_names=None):
        collection = self._checkpoint_collection()
        prefix = f"{name}::"
        if action == "list":
            return {"checkpoints": sorted({obj.get("mcp_checkpoint") for obj in collection.objects if obj.get("mcp_checkpoint")})}
        if action == "create":
            if object_names:
                targets = []
                for object_name in object_names:
                    obj = bpy.data.objects.get(object_name)
                    if obj is None: raise ValueError(f"Object not found: {object_name}")
                    targets.append(obj)
            else:
                targets = [obj for obj in get_current_scene().objects if not obj.get("mcp_checkpoint")]
            for old in [o for o in list(collection.objects) if o.get("mcp_checkpoint") == name]:
                self._remove_checkpoint_backup(old)
            material_backups = {}
            for obj in targets:
                copy = obj.copy()
                if obj.data and hasattr(obj.data, "copy"):
                    copy.data = obj.data.copy()
                    if hasattr(copy.data, "materials"):
                        for index, material in enumerate(list(copy.data.materials)):
                            if material:
                                material_copy = material_backups.get(material.name)
                                if material_copy is None:
                                    material_copy = material.copy()
                                    material_copy["mcp_checkpoint_material"] = name
                                    material_copy["mcp_original_material_name"] = material.name
                                    material_backups[material.name] = material_copy
                                copy.data.materials[index] = material_copy
                if obj.animation_data and obj.animation_data.action:
                    copy.animation_data_create()
                    copy.animation_data.action = obj.animation_data.action.copy()
                copy.name = prefix + obj.name
                copy["mcp_checkpoint"] = name; copy["mcp_original_name"] = obj.name
                copy["mcp_object_state"] = json.dumps(self._serialize_object_state(obj))
                collection.objects.link(copy)
            return {"action": action, "checkpoint": name, "objects": [o.name for o in targets]}
        if action == "restore":
            backups = [o for o in collection.objects if o.get("mcp_checkpoint") == name]
            if not backups:
                raise ValueError(f"Checkpoint not found: {name}")
            restored = []; restored_objects = {}
            for backup in backups:
                original_name = backup.get("mcp_original_name")
                original = bpy.data.objects.get(original_name)
                state = json.loads(backup.get("mcp_object_state", "{}"))
                if original is None:
                    original = backup.copy(); original.name = original_name
                    if backup.data and hasattr(backup.data, "copy"): original.data = backup.data.copy()
                    collections = [bpy.data.collections.get(value) for value in state.get("collections", [])]
                    collections = [value for value in collections if value]
                    (collections[0] if collections else get_current_scene().collection).objects.link(original)
                elif backup.data and hasattr(backup.data, "copy"):
                    old_data = original.data; original.data = backup.data.copy()
                    if old_data and old_data.users == 0:
                        if isinstance(old_data, bpy.types.Mesh): bpy.data.meshes.remove(old_data)
                        elif isinstance(old_data, bpy.types.Curve): bpy.data.curves.remove(old_data)
                original.rotation_mode = state.get("rotation_mode", original.rotation_mode)
                original.hide_viewport = state.get("hide_viewport", False)
                original.hide_render = state.get("hide_render", False)
                original.hide_select = state.get("hide_select", False)
                original.modifiers.clear()
                for item in state.get("modifiers", []):
                    modifier = original.modifiers.new(item["name"], item["type"])
                    self._apply_rna_settings(modifier, item.get("settings", {}))
                original.constraints.clear()
                for item in state.get("constraints", []):
                    constraint = original.constraints.new(item["type"]); constraint.name = item["name"]
                    self._apply_rna_settings(constraint, item.get("settings", {}))
                    if item.get("target") and hasattr(constraint, "target"):
                        constraint.target = bpy.data.objects.get(item["target"])
                    if item.get("subtarget") and hasattr(constraint, "subtarget"):
                        constraint.subtarget = item["subtarget"]
                original.animation_data_clear()
                if backup.animation_data and backup.animation_data.action:
                    original.animation_data_create(); original.animation_data.action = backup.animation_data.action.copy()
                restored_objects[original_name] = (original, state)
                restored.append(original_name)
            for original_name, (original, state) in restored_objects.items():
                desired_collections = [bpy.data.collections.get(value) for value in state.get("collections", [])]
                desired_collections = [value for value in desired_collections if value]
                if not desired_collections: desired_collections = [get_current_scene().collection]
                for desired in desired_collections:
                    if desired.objects.get(original.name) is None: desired.objects.link(original)
                for current in list(original.users_collection):
                    if current.name != "_MCP_CHECKPOINTS" and current not in desired_collections:
                        current.objects.unlink(original)
                original.parent = bpy.data.objects.get(state.get("parent")) if state.get("parent") else None
                original.parent_type = state.get("parent_type", 'OBJECT')
                original.parent_bone = state.get("parent_bone", "")
                if state.get("location") is not None: original.location = state["location"]
                if state.get("rotation_euler") is not None: original.rotation_euler = state["rotation_euler"]
                if state.get("scale") is not None: original.scale = state["scale"]
            checkpoint_materials = {material for backup in backups if backup.data and hasattr(backup.data, "materials")
                                    for material in backup.data.materials
                                    if material and material.get("mcp_original_material_name")}
            for material in checkpoint_materials:
                original_material_name = material.get("mcp_original_material_name")
                previous = bpy.data.materials.get(original_material_name)
                if previous and previous != material and previous.users == 0:
                    bpy.data.materials.remove(previous)
                material.name = original_material_name
            return {"action": action, "checkpoint": name, "objects": restored}
        if action == "delete":
            matches = [o for o in list(collection.objects) if o.get("mcp_checkpoint") == name]
            for obj in matches:
                self._remove_checkpoint_backup(obj)
            return {"action": action, "checkpoint": name, "deleted": len(matches)}
        raise ValueError("action must be create, restore, list, or delete")

    def _modeling_recipe(self, steps, checkpoint_name="recipe_auto", rollback_on_error=True):
        if not isinstance(steps, list) or not steps:
            raise ValueError("steps must be a non-empty list")
        object_names = set()
        for step in steps:
            params = step.get("params", {})
            for key in ("object_name", "target_name", "cutter_name"):
                if params.get(key): object_names.add(params[key])
            for key in ("object_names", "mesh_names"):
                object_names.update(params.get(key) or [])
            if params.get("material_name"):
                material = bpy.data.materials.get(params["material_name"])
                if material:
                    object_names.update(obj.name for obj in get_current_scene().objects
                                        if any(slot.material == material for slot in obj.material_slots))
        object_names = sorted(object_names)
        scene_objects_before = {obj.name for obj in get_current_scene().objects}
        if rollback_on_error and object_names:
            self._model_checkpoint("create", checkpoint_name, object_names)
        allowed = {
            "mesh_edit": self._mesh_edit, "modifier_control": self._modifier_control,
            "sculpt_refine": self._sculpt_refine, "mesh_quality": self._mesh_quality,
            "uv_tools": self._uv_tools, "pbr_material": self._pbr_material,
            "boolean_model": self._boolean_model, "batch_edit": self._batch_edit,
            "material_nodes": self._material_nodes, "scene_manage": self._scene_manage,
            "animation_control": self._animation_control,
        }
        results = []
        try:
            for index, step in enumerate(steps):
                operation = step.get("tool")
                if operation not in allowed:
                    raise ValueError(f"Recipe step {index}: unsupported tool '{operation}'")
                results.append({"step": index, "tool": operation,
                                "result": allowed[operation](**step.get("params", {}))})
        except Exception as exc:
            if rollback_on_error and object_names:
                for obj in list(get_current_scene().objects):
                    if obj.name not in scene_objects_before and not obj.get("mcp_checkpoint"):
                        data = obj.data
                        bpy.data.objects.remove(obj, do_unlink=True)
                        if data and data.users == 0:
                            if isinstance(data, bpy.types.Mesh): bpy.data.meshes.remove(data)
                            elif isinstance(data, bpy.types.Curve): bpy.data.curves.remove(data)
                self._model_checkpoint("restore", checkpoint_name, object_names)
            return {"status": "rolled_back" if rollback_on_error else "failed",
                    "error": str(exc), "completed_steps": results}
        return {"status": "success", "checkpoint": checkpoint_name,
                "completed_steps": results}

    @staticmethod
    def _scene_snapshot():
        scene = get_current_scene()
        return {
            "objects": len(scene.objects),
            "selected": sorted(obj.name for obj in get_selected_objects()),
            "active": getattr(getattr(bpy.context, "view_layer", None), "objects", None).active.name
                      if getattr(getattr(bpy.context, "view_layer", None), "objects", None)
                      and getattr(bpy.context.view_layer.objects, "active", None) else None,
            "collections": sorted(collection.name for collection in bpy.data.collections),
        }

    def _scene_manage(self, action="summary", object_names=None, pattern=None,
                      collection_name=None, parent_name=None, visible=True,
                      selectable=True):
        before = self._scene_snapshot()
        names = object_names or []
        if pattern:
            regex = re.compile(pattern, re.IGNORECASE)
            names = [obj.name for obj in get_current_scene().objects if regex.search(obj.name)]
        objects = []
        for name in names:
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise ValueError(f"Object not found: {name}")
            objects.append(obj)
        if action == "summary":
            return before
        if action == "search":
            return {"matches": [{"name": obj.name, "type": obj.type} for obj in objects]}
        if action == "select":
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects:
                obj.select_set(True)
            if objects:
                bpy.context.view_layer.objects.active = objects[0]
        elif action == "create_collection":
            if not collection_name:
                raise ValueError("collection_name is required")
            collection = bpy.data.collections.get(collection_name)
            if collection is None:
                collection = bpy.data.collections.new(collection_name)
                get_current_scene().collection.children.link(collection)
        elif action == "move_to_collection":
            if not collection_name:
                raise ValueError("collection_name is required")
            collection = bpy.data.collections.get(collection_name)
            if collection is None:
                collection = bpy.data.collections.new(collection_name)
                get_current_scene().collection.children.link(collection)
            for obj in objects:
                if collection.objects.get(obj.name) is None:
                    collection.objects.link(obj)
                for current in list(obj.users_collection):
                    if current != collection:
                        current.objects.unlink(obj)
        elif action == "parent":
            parent = bpy.data.objects.get(parent_name) if parent_name else None
            if parent_name and parent is None:
                raise ValueError(f"Parent not found: {parent_name}")
            for obj in objects:
                world = obj.matrix_world.copy()
                obj.parent = parent
                obj.matrix_world = world
        elif action == "visibility":
            for obj in objects:
                obj.hide_viewport = not visible
                obj.hide_render = not visible
                obj.hide_select = not selectable
        else:
            raise ValueError("Unsupported scene action")
        return {"action": action, "affected": [obj.name for obj in objects],
                "before": before, "after": self._scene_snapshot()}

    @staticmethod
    def _new_edit_bone(armature, name, head, tail, parent=None, connected=False):
        bone = armature.edit_bones.new(name)
        bone.head = head; bone.tail = tail
        bone.parent = parent; bone.use_connect = bool(parent and connected)
        return bone

    def _character_rig(self, action="create_humanoid", rig_name="MCP_Rig",
                       mesh_names=None, object_name=None, bone_name=None,
                       location=None, rotation=None, shape_key_name=None,
                       shape_key_value=0.0):
        if action == "create_humanoid":
            armature = bpy.data.armatures.new(rig_name + "Data")
            rig = bpy.data.objects.new(rig_name, armature)
            get_current_scene().collection.objects.link(rig)
            self._activate_object(rig); bpy.ops.object.mode_set(mode='EDIT')
            pelvis = self._new_edit_bone(armature, "pelvis", (0, 0, 0.9), (0, 0, 1.2))
            spine = self._new_edit_bone(armature, "spine", pelvis.tail, (0, 0, 1.7), pelvis, True)
            chest = self._new_edit_bone(armature, "chest", spine.tail, (0, 0, 2.15), spine, True)
            neck = self._new_edit_bone(armature, "neck", chest.tail, (0, 0, 2.38), chest, True)
            self._new_edit_bone(armature, "head", neck.tail, (0, 0, 2.75), neck, True)
            for side, sign in (("L", 1), ("R", -1)):
                clav = self._new_edit_bone(armature, f"clavicle.{side}", chest.tail,
                                           (0.25 * sign, 0, 2.18), chest)
                upper = self._new_edit_bone(armature, f"upper_arm.{side}", clav.tail,
                                            (0.75 * sign, 0, 2.05), clav, True)
                lower = self._new_edit_bone(armature, f"forearm.{side}", upper.tail,
                                            (1.18 * sign, 0, 1.92), upper, True)
                self._new_edit_bone(armature, f"hand.{side}", lower.tail,
                                    (1.42 * sign, 0, 1.88), lower, True)
                thigh = self._new_edit_bone(armature, f"thigh.{side}", pelvis.head,
                                            (0.18 * sign, 0, 0.05), pelvis)
                shin = self._new_edit_bone(armature, f"shin.{side}", thigh.tail,
                                           (0.18 * sign, 0, -0.78), thigh, True)
                self._new_edit_bone(armature, f"foot.{side}", shin.tail,
                                    (0.18 * sign, -0.32, -0.84), shin, True)
            bpy.ops.object.mode_set(mode='OBJECT')
            rig.show_in_front = True
            return {"action": action, "rig": rig.name, "bones": len(armature.bones)}
        rig = bpy.data.objects.get(rig_name)
        if action in {"bind", "pose_bone"} and (rig is None or rig.type != 'ARMATURE'):
            raise ValueError(f"Armature not found: {rig_name}")
        if action == "bind":
            meshes = [self._require_mesh(name) for name in (mesh_names or [])]
            bpy.ops.object.select_all(action='DESELECT')
            for mesh in meshes:
                mesh.select_set(True)
            rig.select_set(True); bpy.context.view_layer.objects.active = rig
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
            return {"action": action, "rig": rig.name, "meshes": [m.name for m in meshes]}
        if action == "pose_bone":
            pose_bone = rig.pose.bones.get(bone_name)
            if pose_bone is None:
                raise ValueError(f"Bone not found: {bone_name}")
            pose_bone.rotation_mode = 'XYZ'
            if location is not None:
                pose_bone.location = location
            if rotation is not None:
                pose_bone.rotation_euler = rotation
            return {"action": action, "rig": rig.name, "bone": bone_name}
        if action in {"add_shape_key", "set_shape_key"}:
            obj = self._require_mesh(object_name)
            if action == "add_shape_key":
                if obj.data.shape_keys is None:
                    obj.shape_key_add(name="Basis")
                key = obj.data.shape_keys.key_blocks.get(shape_key_name)
                if key is None:
                    key = obj.shape_key_add(name=shape_key_name)
            else:
                if obj.data.shape_keys is None or shape_key_name not in obj.data.shape_keys.key_blocks:
                    raise ValueError(f"Shape key not found: {shape_key_name}")
                key = obj.data.shape_keys.key_blocks[shape_key_name]
            key.value = shape_key_value
            return {"action": action, "object": obj.name, "shape_key": key.name,
                    "value": key.value}
        raise ValueError("Unsupported rig action")

    def _animation_control(self, action="keyframe", object_name=None, data_path="location",
                           frame=1, value=None, constraint_type=None, target_name=None,
                           frame_start=None, frame_end=None):
        scene = get_current_scene()
        if action == "timeline":
            if frame_start is not None: scene.frame_start = frame_start
            if frame_end is not None: scene.frame_end = frame_end
            return {"frame_start": scene.frame_start, "frame_end": scene.frame_end,
                    "current": scene.frame_current}
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object not found: {object_name}")
        if action == "keyframe":
            if value is not None:
                if data_path == "rotation_euler": obj.rotation_mode = 'XYZ'
                setattr(obj, data_path, value)
            obj.keyframe_insert(data_path=data_path, frame=frame)
            return {"action": action, "object": obj.name, "data_path": data_path,
                    "frame": frame}
        if action == "constraint":
            if not constraint_type:
                raise ValueError("constraint_type is required")
            constraint = obj.constraints.new(constraint_type.upper())
            if target_name:
                target = bpy.data.objects.get(target_name)
                if target is None: raise ValueError(f"Target not found: {target_name}")
                constraint.target = target
            return {"action": action, "object": obj.name, "constraint": constraint.type,
                    "target": target_name}
        if action == "list":
            data = obj.animation_data
            action_data = data.action if data else None
            return {"object": obj.name, "action": action_data.name if action_data else None,
                    "constraints": [c.type for c in obj.constraints]}
        raise ValueError("Unsupported animation action")

    @staticmethod
    def _new_geometry_group(name):
        group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
        return group

    def _geometry_nodes(self, object_name, operation="linear_array", name="MCP Geometry",
                        count=5, offset=None, source_object=None, density=1.0,
                        seed=0, realize=True):
        obj = self._require_mesh(object_name)
        modifier = obj.modifiers.new(name, 'NODES')
        group = self._new_geometry_group(name + " Nodes")
        modifier.node_group = group; nodes = group.nodes; links = group.links
        inp = nodes.new('NodeGroupInput'); out = nodes.new('NodeGroupOutput')
        if operation == "linear_array":
            line = nodes.new('GeometryNodeCurvePrimitiveLine')
            line.mode = 'DIRECTION'
            line.inputs['Direction'].default_value = tuple(offset or [2.0, 0.0, 0.0])
            resample = nodes.new('GeometryNodeResampleCurve')
            resample.inputs['Count'].default_value = max(1, count)
            instance = nodes.new('GeometryNodeInstanceOnPoints')
            realize_node = nodes.new('GeometryNodeRealizeInstances')
            links.new(line.outputs['Curve'], resample.inputs['Curve'])
            links.new(resample.outputs['Curve'], instance.inputs['Points'])
            links.new(inp.outputs['Geometry'], instance.inputs['Instance'])
            if realize:
                links.new(instance.outputs['Instances'], realize_node.inputs['Geometry'])
                links.new(realize_node.outputs['Geometry'], out.inputs['Geometry'])
            else:
                links.new(instance.outputs['Instances'], out.inputs['Geometry'])
        elif operation == "scatter_surface":
            source = bpy.data.objects.get(source_object)
            if source is None:
                raise ValueError(f"Source object not found: {source_object}")
            distribute = nodes.new('GeometryNodeDistributePointsOnFaces')
            distribute.distribute_method = 'RANDOM'
            distribute.inputs['Density'].default_value = density
            distribute.inputs['Seed'].default_value = seed
            object_info = nodes.new('GeometryNodeObjectInfo'); object_info.transform_space = 'ORIGINAL'
            object_info.inputs['Object'].default_value = source; object_info.inputs['As Instance'].default_value = True
            instance = nodes.new('GeometryNodeInstanceOnPoints')
            links.new(inp.outputs['Geometry'], distribute.inputs['Mesh'])
            links.new(distribute.outputs['Points'], instance.inputs['Points'])
            links.new(object_info.outputs['Geometry'], instance.inputs['Instance'])
            links.new(instance.outputs['Instances'], out.inputs['Geometry'])
        else:
            obj.modifiers.remove(modifier); bpy.data.node_groups.remove(group)
            raise ValueError("operation must be linear_array or scatter_surface")
        return {"object": obj.name, "operation": operation, "modifier": modifier.name,
                "node_group": group.name, "nodes": len(nodes)}

    def _camera_compositor(self, action="setup_compositor", camera_name=None,
                           target_name=None, lens=50.0, glare=True,
                           denoise=True, frame=None, location=None):
        scene = get_current_scene()
        if action == "create_camera":
            camera_data = bpy.data.cameras.new(camera_name or "MCP Camera")
            camera = bpy.data.objects.new(camera_data.name, camera_data)
            scene.collection.objects.link(camera); camera.data.lens = lens
            if location is not None: camera.location = location
            scene.camera = camera
            return {"action": action, "camera": camera.name, "lens": lens}
        camera = bpy.data.objects.get(camera_name) if camera_name else scene.camera
        if action == "track":
            if camera is None or camera.type != 'CAMERA': raise ValueError("Camera not found")
            target = bpy.data.objects.get(target_name)
            if target is None: raise ValueError(f"Target not found: {target_name}")
            constraint = camera.constraints.new('TRACK_TO'); constraint.target = target
            constraint.track_axis = 'TRACK_NEGATIVE_Z'; constraint.up_axis = 'UP_Y'
            return {"action": action, "camera": camera.name, "target": target.name}
        if action == "keyframe":
            if camera is None: raise ValueError("Camera not found")
            if location is not None: camera.location = location
            if lens is not None: camera.data.lens = lens
            camera.keyframe_insert(data_path="location", frame=frame or scene.frame_current)
            camera.data.keyframe_insert(data_path="lens", frame=frame or scene.frame_current)
            return {"action": action, "camera": camera.name, "frame": frame or scene.frame_current}
        if action == "setup_compositor":
            group = bpy.data.node_groups.get("MCP Compositor")
            if group is not None:
                if scene.compositing_node_group == group:
                    scene.compositing_node_group = None
                bpy.data.node_groups.remove(group)
            group = bpy.data.node_groups.new("MCP Compositor", 'CompositorNodeTree')
            group.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
            nodes = group.nodes; links = group.links
            render = nodes.new('CompositorNodeRLayers'); last = render.outputs['Image']
            if denoise:
                node = nodes.new('CompositorNodeDenoise'); links.new(last, node.inputs['Image']); last = node.outputs['Image']
            if glare:
                node = nodes.new('CompositorNodeGlare')
                if hasattr(node, "glare_type"):
                    node.glare_type = 'FOG_GLOW'; node.quality = 'HIGH'
                else:
                    node.inputs['Type'].default_value = 'Bloom'
                    node.inputs['Quality'].default_value = 'High'
                links.new(last, node.inputs['Image']); last = node.outputs['Image']
            output = nodes.new('NodeGroupOutput'); links.new(last, output.inputs['Image'])
            scene.compositing_node_group = group
            return {"action": action, "node_group": group.name, "nodes": len(nodes),
                    "glare": glare, "denoise": denoise}
        raise ValueError("Unsupported camera/compositor action")

    def _asset_pipeline(self, action="audit", object_names=None, lod_ratios=None,
                        apply_rotation=True, apply_scale=True):
        objects = [self._require_mesh(name) for name in (object_names or [])]
        if action == "audit":
            report = []
            for obj in objects:
                mesh = obj.data
                report.append({"name": obj.name, "vertices": len(mesh.vertices),
                               "faces": len(mesh.polygons), "uv_layers": len(mesh.uv_layers),
                               "materials": len(obj.material_slots),
                               "unapplied_scale": any(abs(v - 1.0) > 1e-5 for v in obj.scale),
                               "shape_keys": len(mesh.shape_keys.key_blocks) if mesh.shape_keys else 0})
            return {"action": action, "objects": report}
        if action == "apply_transforms":
            for obj in objects:
                self._activate_object(obj)
                bpy.ops.object.transform_apply(location=False, rotation=apply_rotation, scale=apply_scale)
            return {"action": action, "objects": [obj.name for obj in objects]}
        if action == "create_lods":
            ratios = lod_ratios or [0.5, 0.25, 0.1]
            created = []
            for obj in objects:
                for index, ratio in enumerate(ratios, 1):
                    if not 0 < ratio < 1: raise ValueError("LOD ratios must be between 0 and 1")
                    duplicate = obj.copy(); duplicate.data = obj.data.copy()
                    duplicate.name = f"{obj.name}_LOD{index}"; obj.users_collection[0].objects.link(duplicate)
                    modifier = duplicate.modifiers.new("LOD Decimate", 'DECIMATE'); modifier.ratio = ratio
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    evaluated = duplicate.evaluated_get(depsgraph)
                    old_mesh = duplicate.data
                    duplicate.data = bpy.data.meshes.new_from_object(evaluated)
                    duplicate.modifiers.clear()
                    if old_mesh.users == 0:
                        bpy.data.meshes.remove(old_mesh)
                    duplicate.hide_render = True; created.append(duplicate.name)
            return {"action": action, "created": created, "ratios": ratios}
        raise ValueError("Unsupported asset pipeline action")

    def _evaluated_mesh_metrics(self, obj):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            bm = bmesh.new(); bm.from_mesh(mesh)
            volume = abs(bm.calc_volume(signed=True)) if bm.faces else 0.0
            area = sum(face.calc_area() for face in bm.faces)
            bm.free()
            return {"vertices": len(mesh.vertices), "edges": len(mesh.edges),
                    "faces": len(mesh.polygons), "surface_area": area,
                    "volume": volume}
        finally:
            evaluated.to_mesh_clear()

    def _scene_measure(self, action="object_metrics", object_names=None,
                       point_a=None, point_b=None):
        names = object_names or []
        objects = [self._require_mesh(name) for name in names]
        if action == "distance":
            if point_a is None or point_b is None:
                raise ValueError("point_a and point_b are required")
            a, b = mathutils.Vector(point_a), mathutils.Vector(point_b)
            return {"action": action, "distance": (b - a).length,
                    "delta": list(b - a), "point_a": list(a), "point_b": list(b)}
        if action == "object_metrics":
            result = []
            for obj in objects:
                corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
                minimum = [min(corner[i] for corner in corners) for i in range(3)]
                maximum = [max(corner[i] for corner in corners) for i in range(3)]
                metrics = self._evaluated_mesh_metrics(obj)
                metrics.update({"name": obj.name, "bounds_min": minimum,
                                "bounds_max": maximum,
                                "dimensions": [maximum[i] - minimum[i] for i in range(3)]})
                result.append(metrics)
            return {"action": action, "objects": result}
        if action == "overlaps":
            boxes = {}
            for obj in objects:
                corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
                boxes[obj.name] = ([min(c[i] for c in corners) for i in range(3)],
                                   [max(c[i] for c in corners) for i in range(3)])
            overlaps = []
            for index, first in enumerate(objects):
                for second in objects[index + 1:]:
                    a_min, a_max = boxes[first.name]; b_min, b_max = boxes[second.name]
                    if all(a_min[i] <= b_max[i] and b_min[i] <= a_max[i] for i in range(3)):
                        overlaps.append([first.name, second.name])
            return {"action": action, "overlaps": overlaps, "checked": len(objects)}
        raise ValueError("action must be object_metrics, distance, or overlaps")

    def _batch_edit(self, action, object_names, values=None, name_pattern=None,
                    offset=None, linked=False):
        objects = []
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj is None: raise ValueError(f"Object not found: {name}")
            objects.append(obj)
        values = values or {}
        if action == "transform":
            for obj in objects:
                if "location" in values: obj.location = values["location"]
                if "rotation" in values: obj.rotation_euler = values["rotation"]
                if "scale" in values: obj.scale = values["scale"]
        elif action == "rename":
            pattern = name_pattern or "Object_{index:03d}"
            for index, obj in enumerate(objects, 1):
                obj.name = pattern.format(index=index, old=obj.name)
        elif action == "duplicate":
            created = []; delta = mathutils.Vector(offset or [1, 0, 0])
            for obj in objects:
                duplicate = obj.copy()
                if obj.data and not linked: duplicate.data = obj.data.copy()
                obj.users_collection[0].objects.link(duplicate)
                duplicate.location = obj.location + delta; created.append(duplicate.name)
            return {"action": action, "source": [o.name for o in objects],
                    "created": created, "linked": linked}
        elif action == "delete":
            deleted = [obj.name for obj in objects]
            for obj in objects:
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if data and data.users == 0:
                    if isinstance(data, bpy.types.Mesh): bpy.data.meshes.remove(data)
                    elif isinstance(data, bpy.types.Curve): bpy.data.curves.remove(data)
                    elif isinstance(data, bpy.types.Armature): bpy.data.armatures.remove(data)
            return {"action": action, "deleted": deleted}
        else:
            raise ValueError("action must be transform, rename, duplicate, or delete")
        return {"action": action, "objects": [obj.name for obj in objects]}

    @staticmethod
    def _look_at(obj, target):
        obj.rotation_euler = (mathutils.Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()

    def _lighting_rig(self, preset="three_point", target=None, collection_name="MCP Lighting",
                      energy=1000.0, scale=1.0, replace=True):
        collection = bpy.data.collections.get(collection_name)
        if collection is None:
            collection = bpy.data.collections.new(collection_name)
            get_current_scene().collection.children.link(collection)
        elif replace:
            for obj in list(collection.objects): bpy.data.objects.remove(obj, do_unlink=True)
        center = target or [0, 0, 0]
        presets = {
            "three_point": [
                ("Key", 'AREA', (4, -5, 6), (1.0, .55, .35), 1.0, 4.0),
                ("Fill", 'AREA', (-4, -3, 3), (.25, .45, 1.0), .55, 3.0),
                ("Rim", 'AREA', (2, 4, 5), (.1, .7, 1.0), .9, 2.5)],
            "product": [
                ("Softbox L", 'AREA', (-4, -4, 4), (1, 1, 1), 1.0, 5.0),
                ("Softbox R", 'AREA', (4, -4, 4), (1, 1, 1), 1.0, 5.0),
                ("Top", 'AREA', (0, 0, 7), (1, .9, .75), .8, 4.0)],
            "sunset": [
                ("Sunset Sun", 'SUN', (0, 0, 8), (1, .18, .04), 2.0, 0.0),
                ("Sky Fill", 'AREA', (-4, -1, 5), (.05, .2, 1), .7, 6.0)],
        }
        if preset not in presets: raise ValueError(f"Unknown lighting preset: {preset}")
        created = []
        for name, light_type, location, color, multiplier, size in presets[preset]:
            data = bpy.data.lights.new(name, light_type); data.energy = energy * multiplier
            data.color = color
            if light_type == 'AREA': data.shape = 'DISK'; data.size = size * scale
            obj = bpy.data.objects.new(name, data); collection.objects.link(obj)
            obj.location = [value * scale + center[i] for i, value in enumerate(location)]
            self._look_at(obj, center); created.append(obj.name)
        return {"preset": preset, "collection": collection.name, "lights": created}

    def _simulation_setup(self, object_name, simulation="rigid_body", action="add",
                          settings=None):
        obj = bpy.data.objects.get(object_name)
        if obj is None: raise ValueError(f"Object not found: {object_name}")
        settings = settings or {}; self._activate_object(obj)
        if simulation == "rigid_body":
            if action == "remove":
                if obj.rigid_body: bpy.ops.rigidbody.object_remove()
            else:
                if obj.rigid_body is None: bpy.ops.rigidbody.object_add()
                for key, value in settings.items():
                    if not hasattr(obj.rigid_body, key): raise ValueError(f"Unknown rigid body setting: {key}")
                    setattr(obj.rigid_body, key, value)
        elif simulation in {"cloth", "collision"}:
            modifier_type = simulation.upper()
            modifier = next((m for m in obj.modifiers if m.type == modifier_type), None)
            if action == "remove":
                if modifier: obj.modifiers.remove(modifier)
            elif modifier is None:
                modifier = obj.modifiers.new(simulation.title(), modifier_type)
        else:
            raise ValueError("simulation must be rigid_body, cloth, or collision")
        return {"object": obj.name, "simulation": simulation, "action": action,
                "modifiers": [m.type for m in obj.modifiers],
                "rigid_body": obj.rigid_body is not None}

    def _batch_render(self, output_dir, camera_names=None, frames=None,
                      file_format="PNG", resolution=None):
        scene = get_current_scene(); os.makedirs(output_dir, exist_ok=True)
        cameras = [bpy.data.objects.get(name) for name in camera_names] if camera_names else [o for o in scene.objects if o.type == 'CAMERA']
        if not cameras or any(camera is None or camera.type != 'CAMERA' for camera in cameras):
            raise ValueError("One or more cameras are missing")
        frame_values = frames or [scene.frame_current]
        previous = (scene.camera, scene.frame_current, scene.render.filepath,
                    scene.render.image_settings.file_format, scene.render.resolution_x,
                    scene.render.resolution_y)
        rendered = []
        try:
            scene.render.image_settings.file_format = file_format
            if resolution:
                scene.render.resolution_x, scene.render.resolution_y = resolution
            extension = file_format.lower().replace('jpeg', 'jpg')
            for camera in cameras:
                scene.camera = camera
                for frame in frame_values:
                    scene.frame_set(frame)
                    path = os.path.join(output_dir, f"{camera.name}_f{frame:04d}.{extension}")
                    scene.render.filepath = path; bpy.ops.render.render(write_still=True)
                    rendered.append(path)
        finally:
            scene.camera, current_frame, scene.render.filepath, image_format, rx, ry = previous
            scene.frame_set(current_frame); scene.render.image_settings.file_format = image_format
            scene.render.resolution_x, scene.render.resolution_y = rx, ry
        return {"rendered": rendered, "cameras": len(cameras), "frames": frame_values}

    def _resource_package(self, action="audit", make_relative=True):
        images = []
        missing = []
        for image in bpy.data.images:
            if image.source != 'FILE': continue
            absolute = bpy.path.abspath(image.filepath)
            item = {"name": image.name, "path": image.filepath, "packed": image.packed_file is not None}
            images.append(item)
            if not image.packed_file and not os.path.isfile(absolute): missing.append(item)
        if action == "audit":
            return {"images": images, "missing": missing, "blend_file": bpy.data.filepath,
                    "dirty": bpy.data.is_dirty}
        if action == "pack":
            if missing: raise FileNotFoundError(f"Missing resources: {[item['path'] for item in missing]}")
            if make_relative: bpy.ops.file.make_paths_relative()
            bpy.ops.file.pack_all()
            return {"action": action, "packed_images": len([i for i in bpy.data.images if i.packed_file]),
                    "relative_paths": make_relative}
        raise ValueError("action must be audit or pack")

    def _boolean_model(self, target_name, cutter_name, operation="DIFFERENCE",
                       solver="EXACT", apply=True, hide_cutter=True):
        target = self._require_mesh(target_name); cutter = self._require_mesh(cutter_name)
        before = self._mesh_stats(target); self._activate_object(target)
        modifier = target.modifiers.new(f"Boolean {operation.title()}", 'BOOLEAN')
        modifier.operation = operation.upper(); modifier.solver = solver.upper(); modifier.object = cutter
        if apply: bpy.ops.object.modifier_apply(modifier=modifier.name)
        if hide_cutter:
            cutter.hide_viewport = True; cutter.hide_render = True
        return {"target": target.name, "cutter": cutter.name, "operation": operation.upper(),
                "applied": apply, "before": before, "after": self._mesh_stats(target)}

    def _curve_create(self, action="path", name="MCP Curve", points=None,
                      text=None, bevel_depth=0.05, bevel_resolution=3,
                      resolution=12, cyclic=False, extrude=0.0,
                      align_x="CENTER", convert_mesh=False):
        if action == "text":
            data = bpy.data.curves.new(name + "Data", 'FONT'); data.body = text or "Text"
            data.align_x = align_x; data.extrude = extrude; data.bevel_depth = bevel_depth
            obj = bpy.data.objects.new(name, data); get_current_scene().collection.objects.link(obj)
        elif action in {"path", "cable"}:
            if not points or len(points) < 2: raise ValueError("At least two points are required")
            data = bpy.data.curves.new(name + "Data", 'CURVE'); data.dimensions = '3D'
            data.resolution_u = resolution; data.bevel_depth = bevel_depth
            data.bevel_resolution = bevel_resolution
            spline = data.splines.new('BEZIER'); spline.bezier_points.add(len(points) - 1)
            for point, coordinate in zip(spline.bezier_points, points):
                point.co = coordinate; point.handle_left_type = 'AUTO'; point.handle_right_type = 'AUTO'
            spline.use_cyclic_u = cyclic
            obj = bpy.data.objects.new(name, data); get_current_scene().collection.objects.link(obj)
        else:
            raise ValueError("action must be path, cable, or text")
        if convert_mesh:
            self._activate_object(obj); bpy.ops.object.convert(target='MESH')
        return {"action": action, "object": obj.name, "type": obj.type,
                "points": len(points or []), "converted": convert_mesh}

    def _material_nodes(self, material_name, action="inspect", node_type=None,
                        node_name=None, input_name=None, value=None,
                        from_node=None, from_socket=None, to_node=None,
                        to_socket=None):
        material = bpy.data.materials.get(material_name)
        if material is None: raise ValueError(f"Material not found: {material_name}")
        material.use_nodes = True; nodes = material.node_tree.nodes; links = material.node_tree.links
        if action == "inspect":
            return {"material": material.name,
                    "nodes": [{"name": n.name, "type": n.bl_idname,
                               "inputs": [s.name for s in n.inputs],
                               "outputs": [s.name for s in n.outputs]} for n in nodes],
                    "links": len(links)}
        if action == "add":
            if not node_type: raise ValueError("node_type is required")
            node = nodes.new(node_type)
            if node_name: node.name = node_name; node.label = node_name
            return {"action": action, "material": material.name, "node": node.name,
                    "type": node.bl_idname}
        if action == "set_input":
            node = nodes.get(node_name)
            if node is None: raise ValueError(f"Node not found: {node_name}")
            socket = node.inputs.get(input_name)
            if socket is None: raise ValueError(f"Input not found: {input_name}")
            socket.default_value = value
            return {"action": action, "node": node.name, "input": socket.name}
        if action == "link":
            source, target = nodes.get(from_node), nodes.get(to_node)
            if source is None or target is None: raise ValueError("Source or target node not found")
            output, input_socket = source.outputs.get(from_socket), target.inputs.get(to_socket)
            if output is None or input_socket is None: raise ValueError("Source or target socket not found")
            links.new(output, input_socket)
            return {"action": action, "from": f"{source.name}.{output.name}",
                    "to": f"{target.name}.{input_socket.name}"}
        if action == "remove":
            node = nodes.get(node_name)
            if node is None: raise ValueError(f"Node not found: {node_name}")
            nodes.remove(node); return {"action": action, "removed": node_name}
        raise ValueError("Unsupported material node action")

    def _render_passes(self, view_layer_name=None, passes=None,
                       cryptomatte=False, transparent=False):
        scene = get_current_scene()
        view_layer = scene.view_layers.get(view_layer_name) if view_layer_name else bpy.context.view_layer
        if view_layer is None: raise ValueError(f"View layer not found: {view_layer_name}")
        requested = {name.lower() for name in (passes or [])}
        mapping = {
            "z": "use_pass_z", "mist": "use_pass_mist", "normal": "use_pass_normal",
            "position": "use_pass_position", "vector": "use_pass_vector",
            "uv": "use_pass_uv", "object_index": "use_pass_object_index",
            "material_index": "use_pass_material_index", "ambient_occlusion": "use_pass_ambient_occlusion",
            "emission": "use_pass_emit", "environment": "use_pass_environment",
            "diffuse_color": "use_pass_diffuse_color", "glossy_color": "use_pass_glossy_color",
        }
        unsupported = [name for name in requested if name not in mapping]
        if unsupported: raise ValueError(f"Unsupported passes: {unsupported}")
        enabled = []
        for name, attribute in mapping.items():
            if hasattr(view_layer, attribute):
                state = name in requested; setattr(view_layer, attribute, state)
                if state: enabled.append(name)
        for attribute in ("use_pass_cryptomatte_object", "use_pass_cryptomatte_material", "use_pass_cryptomatte_asset"):
            if hasattr(view_layer, attribute): setattr(view_layer, attribute, cryptomatte)
        scene.render.film_transparent = transparent
        return {"view_layer": view_layer.name, "passes": enabled,
                "cryptomatte": cryptomatte, "transparent": transparent}

    @staticmethod
    def _serializable_scene_state():
        return {obj.name: {"type": obj.type, "location": list(obj.location),
                           "rotation": list(obj.rotation_euler), "scale": list(obj.scale),
                           "parent": obj.parent.name if obj.parent else None,
                           "visible": not obj.hide_viewport,
                           "modifiers": [modifier.type for modifier in obj.modifiers],
                           "materials": [slot.material.name for slot in obj.material_slots if slot.material],
                           "geometry": {"vertices": len(obj.data.vertices),
                                        "edges": len(obj.data.edges),
                                        "faces": len(obj.data.polygons)} if obj.type == 'MESH' else None}
                for obj in get_current_scene().objects if not obj.get("mcp_checkpoint")}

    def _scene_diff(self, action="capture", name="snapshot"):
        key = "mcp_scene_snapshot::" + name; scene = get_current_scene()
        if action == "capture":
            state = self._serializable_scene_state(); scene[key] = json.dumps(state)
            return {"action": action, "name": name, "objects": len(state)}
        snapshots = sorted(k.split("::", 1)[1] for k in scene.keys() if k.startswith("mcp_scene_snapshot::"))
        if action == "list": return {"snapshots": snapshots}
        if key not in scene: raise ValueError(f"Snapshot not found: {name}")
        if action == "delete":
            del scene[key]; return {"action": action, "name": name}
        if action == "diff":
            previous = json.loads(scene[key]); current = self._serializable_scene_state()
            old_names, new_names = set(previous), set(current)
            changed = [obj_name for obj_name in sorted(old_names & new_names)
                       if previous[obj_name] != current[obj_name]]
            return {"name": name, "added": sorted(new_names - old_names),
                    "removed": sorted(old_names - new_names), "changed": changed,
                    "unchanged": len((old_names & new_names) - set(changed))}
        raise ValueError("action must be capture, diff, list, or delete")

    def _data_cleanup(self, action="audit", recursive=True):
        datablocks = {"meshes": bpy.data.meshes, "materials": bpy.data.materials,
                      "images": bpy.data.images, "curves": bpy.data.curves,
                      "cameras": bpy.data.cameras, "lights": bpy.data.lights,
                      "node_groups": bpy.data.node_groups, "actions": bpy.data.actions}
        unused = {name: [block.name for block in blocks if block.users == 0]
                  for name, blocks in datablocks.items()}
        if action == "audit":
            return {"unused": {name: {"count": len(items), "sample": items[:50]}
                               for name, items in unused.items()},
                    "total_unused": sum(map(len, unused.values())), "sample_limit": 50}
        if action == "purge":
            removed = {}
            for name, blocks in datablocks.items():
                targets = [block for block in blocks if block.users == 0]
                removed[name] = len(targets)
                for block in targets: blocks.remove(block)
            if recursive:
                bpy.ops.outliner.orphans_purge(do_recursive=True)
            return {"action": action, "removed": removed}
        raise ValueError("action must be audit or purge")

    def _advanced_operation(self, operation, arguments=None, command_id=None):
        """Execute legacy AdvancedObjectOperations calls against real bpy data."""
        args = arguments or {}

        if operation == "select_object":
            result = self._scene_manage("select", [args["object_name"]])
        elif operation == "select_multiple_objects":
            result = self._scene_manage("select", args["object_names"])
        elif operation == "deselect_all":
            bpy.ops.object.select_all(action='DESELECT'); result = {"selected": []}
        elif operation == "focus_camera_on_object":
            result = self._camera_compositor("track", args.get("camera_name"), args["object_name"])
        elif operation == "focus_camera_isometric":
            camera = bpy.data.objects.get(args.get("camera_name", "Camera"))
            if camera is None or camera.type != 'CAMERA': raise ValueError("Camera not found")
            camera.data.type = 'ORTHO'; result = {"camera": camera.name, "type": "ORTHO"}
        elif operation in {"save_scene", "save_as_scene", "export_blend"}:
            filepath = args["filepath"]
            bpy.ops.wm.save_as_mainfile(filepath=filepath, compress=args.get("compress", True))
            result = {"filepath": bpy.data.filepath, "saved": True}
        elif operation == "load_scene":
            raise RuntimeError("load_scene would terminate the active MCP connection; use import_scene_blend")
        elif operation in {"get_render_settings", "get_render_info"}:
            scene = get_current_scene()
            result = {"engine": scene.render.engine, "resolution": [scene.render.resolution_x, scene.render.resolution_y],
                      "fps": scene.render.fps, "frame_range": [scene.frame_start, scene.frame_end],
                      "format": scene.render.image_settings.file_format,
                      "transparent": scene.render.film_transparent}
        elif operation == "set_render_settings":
            values = dict(args.get("settings") or {}); values.update(args.get("kwargs") or {})
            scene = get_current_scene()
            mapping = {"resolution_x": (scene.render, "resolution_x"), "resolution_y": (scene.render, "resolution_y"),
                       "fps": (scene.render, "fps"), "frame_start": (scene, "frame_start"),
                       "frame_end": (scene, "frame_end"), "transparent": (scene.render, "film_transparent")}
            if values.get("engine"): self._set_render_engine(values["engine"], values.get("samples", 128), True)
            for key, (owner, attribute) in mapping.items():
                if key in values: setattr(owner, attribute, values[key])
            if values.get("output_format"): scene.render.image_settings.file_format = values["output_format"]
            result = self._advanced_operation("get_render_settings", {}, command_id)
        elif operation == "render_scene":
            scene = get_current_scene()
            frame_range = args.get("frame_range")
            if frame_range:
                result = self._batch_render(os.path.dirname(args.get("filepath") or scene.render.filepath) or ".",
                                            frames=list(range(frame_range[0], frame_range[1] + 1)))
            else:
                if args.get("filepath"): scene.render.filepath = args["filepath"]
                bpy.ops.render.render(write_still=bool(scene.render.filepath)); result = {"filepath": scene.render.filepath}
        elif operation in {"render_animation", "render_animation_batch"}:
            start, end = args.get("frame_start", 1), args.get("frame_end", 250)
            step = args.get("frame_step", 1)
            result = self._batch_render(args["filepath"], frames=list(range(start, end + 1, step)),
                                        file_format=args.get("format", "PNG"))
        elif operation == "create_collection":
            result = self._scene_manage("create_collection", collection_name=args["name"])
            parent_name = args.get("parent_name")
            if parent_name:
                child, parent = bpy.data.collections.get(args["name"]), bpy.data.collections.get(parent_name)
                if parent is None: raise ValueError(f"Collection not found: {parent_name}")
                for scene in bpy.data.scenes:
                    if child.name in scene.collection.children: scene.collection.children.unlink(child)
                if child.name not in parent.children: parent.children.link(child)
        elif operation == "add_to_collection":
            result = self._scene_manage("move_to_collection", args["object_names"], collection_name=args["collection_name"])
        elif operation == "remove_from_collection":
            collection = bpy.data.collections.get(args["collection_name"])
            if collection is None: raise ValueError("Collection not found")
            removed = []
            for name in args["object_names"]:
                obj = bpy.data.objects.get(name)
                if obj and collection.objects.get(name): collection.objects.unlink(obj); removed.append(name)
            result = {"removed": removed}
        elif operation == "list_collections":
            result = {"collections": [{"name": c.name, "objects": len(c.objects)} for c in bpy.data.collections]}
        elif operation == "get_collection_objects":
            collection = bpy.data.collections.get(args["collection_name"])
            if collection is None: raise ValueError("Collection not found")
            result = {"collection": collection.name, "objects": [o.name for o in collection.objects]}
        elif operation in {"batch_scale", "batch_rotate", "batch_set_transform"}:
            values = {}
            if operation == "batch_scale": values["scale"] = [args["factor"]] * 3
            elif operation == "batch_rotate": values["rotation"] = args["euler_rotation"]
            else:
                for source, target in (("location", "location"), ("rotation", "rotation"), ("scale", "scale")):
                    if args.get(source) is not None: values[target] = args[source]
            result = self._batch_edit("transform", args["object_names"], values=values)
        elif operation in {"batch_duplicate", "batch_make_duplicates"}:
            created = []; copies = args.get("copies", args.get("count_per_object", 1)); offset = args.get("offset", [1, 0, 0])
            for index in range(copies):
                batch = self._batch_edit("duplicate", args["object_names"], offset=[value * (index + 1) for value in offset])
                created.extend(batch["created"])
            result = {"created": created, "count": len(created)}
        elif operation == "batch_color":
            updated = []
            for name in args["object_names"]:
                obj = self._require_mesh(name)
                material = obj.material_slots[0].material if obj.material_slots and obj.material_slots[0].material else None
                if material is None:
                    material = bpy.data.materials.new(f"{obj.name} Color")
                    material.use_nodes = True; obj.data.materials.append(material)
                material.diffuse_color = args["color"]
                bsdf = material.node_tree.nodes.get('Principled BSDF')
                if bsdf: bsdf.inputs['Base Color'].default_value = args["color"]
                updated.append(obj.name)
            result = {"updated": updated, "color": args["color"]}
        elif operation in {"batch_delete"}:
            result = self._batch_edit("delete", args["object_names"])
        elif operation in {"batch_set_visibility"}:
            result = self._scene_manage("visibility", args["object_names"], visible=args.get("visible", True),
                                        selectable=not args.get("hide_select", False))
            for name in args["object_names"]:
                obj = bpy.data.objects.get(name)
                if obj and args.get("hide_render") is not None: obj.hide_render = args["hide_render"]
        elif operation in {"batch_make_parent"}:
            result = self._scene_manage("parent", args["child_names"], parent_name=args.get("parent_name"))
        elif operation == "batch_make_empty_group":
            empty = bpy.data.objects.new(args["group_name"], None); get_current_scene().collection.objects.link(empty)
            result = self._scene_manage("parent", args["object_names"], parent_name=empty.name)
            result["empty"] = empty.name
        elif operation == "batch_mirror":
            created = []
            for name in args["object_names"]:
                obj = self._require_mesh(name); modifier = obj.modifiers.new("Mirror", 'MIRROR')
                modifier.use_axis = [axis == args.get("axis", "X") for axis in ("X", "Y", "Z")]
                modifier.use_clip = args.get("use_clip", False); modifier.use_mirror_merge = args.get("merge_vertices", True)
                created.append(modifier.name)
            result = {"objects": args["object_names"], "modifiers": created}
        elif operation == "batch_instance_on_points":
            modifiers = []
            for index, template in enumerate(args["template_object_names"]):
                item = self._geometry_nodes(args["points_object_name"], "scatter_surface",
                                            f"Instance {template} {index + 1}", source_object=template,
                                            density=1.0, seed=index)
                modifiers.append(item["modifier"])
            result = {"surface": args["points_object_name"], "templates": args["template_object_names"],
                      "modifiers": modifiers}
        elif operation == "batch_align_bounding_boxes":
            objects = [self._require_mesh(name) for name in args["object_names"]]
            reference = self._require_mesh(args["reference"]) if args.get("reference") else objects[0]
            ref_min, ref_max = self._get_aabb(reference); mode = args.get("alignment", "CENTER").upper()
            moved = []
            for obj in objects:
                if obj == reference: continue
                obj_min, obj_max = self._get_aabb(obj)
                if mode == "MIN": delta = mathutils.Vector(ref_min) - mathutils.Vector(obj_min)
                elif mode == "MAX": delta = mathutils.Vector(ref_max) - mathutils.Vector(obj_max)
                else:
                    ref_center = (mathutils.Vector(ref_min) + mathutils.Vector(ref_max)) / 2
                    obj_center = (mathutils.Vector(obj_min) + mathutils.Vector(obj_max)) / 2
                    delta = ref_center - obj_center
                obj.location += delta; moved.append(obj.name)
            result = {"reference": reference.name, "alignment": mode, "moved": moved}
        elif operation == "batch_apply_modifiers":
            applied = []
            for name in args["object_names"]:
                obj = self._require_mesh(name); self._activate_object(obj)
                targets = list(obj.modifiers) if args.get("apply_all", True) else [m for m in obj.modifiers if m.name in (args.get("modifier_names") or [])]
                for modifier in targets: bpy.ops.object.modifier_apply(modifier=modifier.name); applied.append(f"{name}:{modifier.name}")
            result = {"applied": applied}
        elif operation in {"get_material", "set_material_color", "create_material", "apply_material_to_object", "batch_apply_material"}:
            if operation == "get_material":
                obj = self._require_mesh(args["object_name"]); result = {"object": obj.name, "materials": [s.material.name for s in obj.material_slots if s.material]}
            elif operation == "create_material":
                result = self._create_material(args["name"], args.get("color"), args.get("metallic", 0), args.get("roughness", .5), 0)
            elif operation == "set_material_color":
                obj = self._require_mesh(args["object_name"])
                if not obj.material_slots or not obj.material_slots[0].material: raise ValueError("Object has no material")
                mat = obj.material_slots[0].material; mat.diffuse_color = args["color"]
                if mat.use_nodes: mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = args["color"]
                result = {"object": obj.name, "material": mat.name}
            else:
                names = args.get("object_names") or [args["object_name"]]
                result = {"applied": [self._apply_material(name, args["material_name"])["object"] for name in names]}
        elif operation in {"get_node_tree", "material_nodes"}:
            result = self._material_nodes(args["material_name"], "inspect")
        elif operation in {"set_texture_to_material", "create_image_texture_node", "set_normal_map", "set_displacement"}:
            material = bpy.data.materials.get(args["material_name"])
            if material is None: raise ValueError("Material not found")
            path = args.get("image_path") or args.get("texture_path")
            if not path or not os.path.isfile(path): raise FileNotFoundError(path or "texture path")
            material.use_nodes = True; node = material.node_tree.nodes.new('ShaderNodeTexImage')
            node.image = bpy.data.images.load(path, check_existing=True)
            result = {"material": material.name, "node": node.name, "image": node.image.name}
        elif operation == "create_procedural_texture":
            material = bpy.data.materials.get(args["material_name"])
            if material is None: raise ValueError("Material not found")
            material.use_nodes = True
            node_types = {"CHECKER": 'ShaderNodeTexChecker', "NOISE": 'ShaderNodeTexNoise',
                          "VORONOI": 'ShaderNodeTexVoronoi', "WAVE": 'ShaderNodeTexWave',
                          "GRADIENT": 'ShaderNodeTexGradient'}
            node_type = node_types.get(args.get("texture_type", "Checker").upper())
            if node_type is None: raise ValueError("Unsupported procedural texture")
            node = material.node_tree.nodes.new(node_type); node.name = f"MCP {args.get('texture_type', 'Texture')}"
            if node.inputs.get('Scale'): node.inputs['Scale'].default_value = args.get("scale", 5.0)
            bsdf = material.node_tree.nodes.get('Principled BSDF'); slot = args.get("slot", "Base Color")
            if bsdf and bsdf.inputs.get(slot): material.node_tree.links.new(node.outputs.get('Color') or node.outputs[0], bsdf.inputs[slot])
            result = {"material": material.name, "node": node.name, "type": node.bl_idname}
        elif operation == "create_color_ramp":
            material = bpy.data.materials.get(args["material_name"])
            if material is None: raise ValueError("Material not found")
            material.use_nodes = True; ramp = material.node_tree.nodes.new('ShaderNodeValToRGB')
            stops = args.get("stops") or []
            while len(ramp.color_ramp.elements) < len(stops): ramp.color_ramp.elements.new(.5)
            for element, stop in zip(ramp.color_ramp.elements, stops):
                element.position = stop.get("position", 0.0); element.color = stop.get("color", [1, 1, 1, 1])
            result = {"material": material.name, "node": ramp.name, "stops": len(stops)}
        elif operation == "mix_shaders":
            material = bpy.data.materials.get(args["material_name"])
            if material is None: raise ValueError("Material not found")
            nodes, links = material.node_tree.nodes, material.node_tree.links
            first, second = nodes.get(args["shader1"]), nodes.get(args["shader2"])
            if first is None or second is None: raise ValueError("Shader node not found")
            mix = nodes.new('ShaderNodeMixShader'); mix.inputs[0].default_value = args.get("blend_factor", .5)
            links.new(first.outputs[0], mix.inputs[1]); links.new(second.outputs[0], mix.inputs[2])
            output = next((node for node in nodes if node.type == 'OUTPUT_MATERIAL'), None)
            if output: links.new(mix.outputs[0], output.inputs['Surface'])
            result = {"material": material.name, "node": mix.name}
        elif operation == "create_emission_material":
            material = bpy.data.materials.get(args["name"]) or bpy.data.materials.new(args["name"])
            material.use_nodes = True; bsdf = material.node_tree.nodes.get('Principled BSDF')
            bsdf.inputs['Emission Color'].default_value = args.get("color", [1, 1, 1, 1])
            bsdf.inputs['Emission Strength'].default_value = args.get("strength", 1.0)
            result = {"material": material.name, "strength": args.get("strength", 1.0)}
        elif operation == "create_material_group":
            group = bpy.data.node_groups.get(args["name"]) or bpy.data.node_groups.new(args["name"], 'ShaderNodeTree')
            material = bpy.data.materials.new(args["name"] + " Material"); material.use_nodes = True
            node = material.node_tree.nodes.new('ShaderNodeGroup'); node.node_tree = group
            result = {"group": group.name, "material": material.name, "node": node.name}
        elif operation == "clone_material":
            source = bpy.data.materials.get(args["source_material_name"])
            if source is None: raise ValueError("Material not found")
            copy = source.copy(); copy.name = args["target_name"]; result = {"material": copy.name}
        elif operation == "clear_node_tree":
            material = bpy.data.materials.get(args["material_name"])
            if material is None: raise ValueError("Material not found")
            keep = {'BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'} if args.get("keep_bsdf") else set()
            for node in list(material.node_tree.nodes):
                if node.type not in keep: material.node_tree.nodes.remove(node)
            result = {"material": material.name, "nodes": len(material.node_tree.nodes)}
        elif operation in {"set_anisotropic", "set_transparency", "setup_ior"}:
            material = bpy.data.materials.get(args["material_name"])
            if material is None: raise ValueError("Material not found")
            material.use_nodes = True; bsdf = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            if operation == "set_transparency": bsdf.inputs['Alpha'].default_value = args["alpha"]
            elif operation == "setup_ior": bsdf.inputs['IOR'].default_value = args["ior"]
            else:
                socket = bsdf.inputs.get('Anisotropic IOR Level') or bsdf.inputs.get('Anisotropic')
                if socket: socket.default_value = args["anisotropy"]
            result = {"material": material.name, "operation": operation}
        elif operation == "align_to_world_axis":
            obj = bpy.data.objects.get(args["object_name"])
            if obj is None: raise ValueError("Object not found")
            obj.rotation_euler = (0, 0, 0); result = {"object": obj.name, "axis": args.get("axis", "Z")}
        elif operation == "snap_to_grid":
            obj = bpy.data.objects.get(args["object_name"]); grid = args.get("grid_size", .01)
            if obj is None: raise ValueError("Object not found")
            obj.location = [round(value / grid) * grid for value in obj.location]; result = {"object": obj.name, "location": list(obj.location)}
        elif operation == "center_object_origin":
            obj = bpy.data.objects.get(args["object_name"]); self._activate_object(obj); bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
            result = {"object": obj.name}
        elif operation == "get_bounding_box":
            obj = self._require_mesh(args["object_name"]); result = {"object": obj.name, "bbox": self._get_aabb(obj)}
        elif operation == "set_studio_lighting":
            result = self._lighting_rig(args.get("preset", "three_point"))
        elif operation == "set_environment_lighting":
            world = get_current_scene().world; world.use_nodes = True
            background = world.node_tree.nodes.get('Background'); background.inputs['Color'].default_value = args["world_color"]
            background.inputs['Strength'].default_value = args.get("world_strength", 1)
            result = {"world": world.name, "strength": args.get("world_strength", 1)}
        elif operation == "create_camera":
            result = self._camera_compositor("create_camera", args["name"], lens=args.get("lens", 50), location=args.get("location"))
            camera = bpy.data.objects[result["camera"]]; camera.rotation_euler = args.get("rotation", [0, 0, 0]); camera.data.sensor_width = args.get("sensor_width", 36)
        elif operation == "get_camera_info":
            camera = bpy.data.objects.get(args.get("camera_name", "Camera"))
            if camera is None or camera.type != 'CAMERA': raise ValueError("Camera not found")
            result = {"name": camera.name, "location": list(camera.location), "rotation": list(camera.rotation_euler),
                      "lens": camera.data.lens, "type": camera.data.type}
        elif operation == "get_scene_summary":
            result = self.get_scene_info()
        elif operation == "get_duplicate_objects":
            groups = {}
            for obj in get_current_scene().objects:
                if obj.data: groups.setdefault(obj.data.name, []).append(obj.name)
            result = {"duplicates": {key: value for key, value in groups.items() if len(value) > 1}}
        elif operation == "clear_unreferenced_data":
            result = self._data_cleanup("purge")
        elif operation in {"set_render_eevee", "set_render_cycles"}:
            engine = 'EEVEE' if operation == "set_render_eevee" else 'CYCLES'
            result = self._set_render_engine(engine, args.get("samples", 128), args.get("denoise", args.get("use_denoising", True)))
        elif operation == "set_render_output":
            scene = get_current_scene(); scene.render.filepath = args["filepath"]
            scene.render.image_settings.file_format = args.get("format", "PNG"); scene.render.film_transparent = args.get("transparent", False)
            result = {"filepath": scene.render.filepath, "format": scene.render.image_settings.file_format}
        elif operation == "set_render_camera":
            camera = bpy.data.objects.get(args["camera_name"])
            if camera is None or camera.type != 'CAMERA': raise ValueError("Camera not found")
            get_current_scene().camera = camera; result = {"camera": camera.name}
        elif operation in {"render_preview", "render_viewport", "capture_scene_snapshot", "capture_viewport_snapshot", "capture_camera_view"}:
            scene = get_current_scene(); filepath = args["filepath"]
            if operation == "capture_camera_view":
                camera = bpy.data.objects.get(args["camera_name"])
                if camera is None: raise ValueError("Camera not found")
                scene.camera = camera
            resolution = args.get("resolution")
            if resolution: scene.render.resolution_x, scene.render.resolution_y = resolution
            scene.render.filepath = filepath; bpy.ops.render.render(write_still=True); result = {"filepath": filepath}
        elif operation == "render_360_panorama":
            scene = get_current_scene(); camera = scene.camera
            if camera is None: raise ValueError("No active camera")
            previous_type = camera.data.type; previous_panorama = getattr(camera.data, "panorama_type", None)
            camera.data.type = 'PANO'
            if hasattr(camera.data, "panorama_type"): camera.data.panorama_type = 'EQUIRECTANGULAR'
            resolution = args.get("resolution", [2048, 1024]); previous_resolution = (scene.render.resolution_x, scene.render.resolution_y)
            scene.render.resolution_x, scene.render.resolution_y = resolution
            scene.render.filepath = args["filepath"]; scene.render.image_settings.file_format = args.get("format", "PNG")
            try: bpy.ops.render.render(write_still=True)
            finally:
                camera.data.type = previous_type
                if previous_panorama is not None and hasattr(camera.data, "panorama_type"): camera.data.panorama_type = previous_panorama
                scene.render.resolution_x, scene.render.resolution_y = previous_resolution
            result = {"filepath": args["filepath"], "resolution": resolution}
        elif operation in {"render_multi_view", "capture_all_cameras"}:
            result = self._batch_render(args.get("filepath") or args.get("output_dir"),
                                        file_format=args.get("format", "PNG"), resolution=args.get("resolution"))
        elif operation in {"import_fbx", "import_obj", "import_glb", "import_stl"}:
            result = self._import_model(args["filepath"])
        elif operation in {"export_fbx", "export_glb", "export_obj", "export_stl", "export_animation_fbx", "export_animation_gltf"}:
            extension = operation.split("_")[-1].replace("gltf", "glb")
            result = self._export_scene(args["filepath"], extension, bool(args.get("use_selection") or args.get("export_selected")))
        elif operation == "import_scene_blend":
            result = self._import_model(args["filepath"])
        elif operation == "import_csv_data":
            if not os.path.isfile(args["filepath"]): raise FileNotFoundError(args["filepath"])
            template = bpy.data.objects.get(args["target_object_name"])
            if template is None: raise ValueError("Template object not found")
            created = []
            with open(args["filepath"], newline='', encoding='utf-8-sig') as handle:
                for index, row in enumerate(csv.DictReader(handle)):
                    if index >= args.get("count", 100): break
                    duplicate = template.copy()
                    if template.data: duplicate.data = template.data
                    get_current_scene().collection.objects.link(duplicate)
                    x = float(row.get(args.get("position_column", "x"), 0))
                    duplicate.location.x = x
                    if args.get("scale_column") in row:
                        duplicate.scale = [float(row[args["scale_column"]])] * 3
                    created.append(duplicate.name)
            result = {"created": created, "count": len(created)}
        else:
            raise NotImplementedError(f"Advanced operation '{operation}' has no Blender implementation yet")
        if isinstance(result, dict):
            result.setdefault("operation", operation); result.setdefault("command_id", command_id)
        return result

    def _get_capabilities(self):
        """Report addon protocol features without changing Blender state."""
        return {
            "protocol_version": "2.0",
            "addon_version": ".".join(map(str, bl_info["version"])),
            "blender_version": bpy.app.version_string,
            "features": {
                "structured_envelope": True,
                "context_guard": True,
                "transaction_rollback": True,
                "advanced_operations": True,
                "geometry_nodes": True,
                "blender_5_compositor": hasattr(get_current_scene(), "compositing_node_group"),
                "async_jobs": True,
                "async_job_priority": True,
                "async_job_retries": True,
                "async_job_recovery": True,
                "async_job_pause_resume": True,
                "async_job_dependencies": True,
                "async_job_resource_scheduling": True,
                "async_job_event_subscription": True,
            },
            "envelope_fields": ["status", "ok", "command", "result", "warnings", "error", "meta"],
            "limits": {
                "max_request_bytes": MAX_ADDON_REQUEST_BYTES,
                "max_response_bytes": MAX_ADDON_RESPONSE_BYTES,
                "max_command_queue": MAX_COMMAND_QUEUE_SIZE,
                "max_async_jobs": MAX_ASYNC_JOBS,
                "max_async_workers": MAX_ASYNC_WORKERS,
                "max_async_retries": MAX_ASYNC_RETRIES,
                "async_priority_range": [-100, 100],
                "max_async_cpu_jobs": MAX_ASYNC_CPU_JOBS,
                "max_async_gpu_jobs": MAX_ASYNC_GPU_JOBS,
                "max_async_events": MAX_ASYNC_EVENTS,
            },
        }

    def _get_async_jobs(self):
        if not hasattr(self, "async_jobs"): self.async_jobs = AsyncJobManager()
        return self.async_jobs

    def _async_job_submit(self, kind, params=None, priority=0, max_retries=0, retry_delay=2.0,
                          depends_on=None, resource="auto"):
        params = dict(params or {}); snapshot = None
        if kind in {"render", "bake"}:
            if kind == "bake":
                obj = bpy.data.objects.get(params.get("object_name"))
                if obj is None or obj.type != 'MESH': raise ValueError("Bake object must be an existing mesh")
                if not params.get("output_path"): raise ValueError("Bake output_path is required")
            if kind == "render" and not (params.get("output_path") or params.get("output_dir")):
                raise ValueError("Render output_path or output_dir is required")
            folder = tempfile.mkdtemp(prefix="blender_mcp_job_"); snapshot = os.path.join(folder, "snapshot.blend")
            try: bpy.ops.wm.save_as_mainfile(filepath=snapshot, copy=True, compress=True)
            except Exception: shutil.rmtree(folder, ignore_errors=True); raise
        return self._get_async_jobs().submit(
            kind, params, snapshot, priority=priority,
            max_retries=max_retries, retry_delay=retry_delay,
            depends_on=depends_on, resource=resource,
        )

    def _async_job_status(self, job_id): return self._get_async_jobs().get(job_id)

    def _async_job_list(self, status=None, limit=50): return {"jobs": self._get_async_jobs().list(status, limit)}

    def _async_job_cancel(self, job_id): return self._get_async_jobs().cancel(job_id)

    def _async_job_pause(self, job_id): return self._get_async_jobs().pause(job_id)

    def _async_job_resume(self, job_id): return self._get_async_jobs().resume(job_id)

    def _async_job_graph(self): return self._get_async_jobs().graph()

    def _async_job_events(self, after=0, limit=100, job_id=None):
        return self._get_async_jobs().get_events(after, limit, job_id)

    def _async_job_resources(self): return self._get_async_jobs().resources()

    def _async_job_cleanup(self, keep_latest=100, clear_events=False):
        return self._get_async_jobs().cleanup(keep_latest, clear_events)

    def get_scene_info(self):
        """Get information about the current Blender scene"""
        try:
            print("Getting scene info...")
            # Simplify the scene info to reduce data size
            scene_info = {
                "name": get_current_scene().name,
                "object_count": len(get_current_scene().objects),
                "objects": [],
                "materials_count": len(bpy.data.materials),
            }

            # Collect minimal object information (limit to first 10 objects)
            for i, obj in enumerate(get_current_scene().objects):
                if i >= 10:  # Reduced from 20 to 10
                    break

                obj_info = {
                    "name": obj.name,
                    "type": obj.type,
                    # Only include basic location data
                    "location": [round(float(obj.location.x), 2),
                                round(float(obj.location.y), 2),
                                round(float(obj.location.z), 2)],
                }
                scene_info["objects"].append(obj_info)

            print(f"Scene info collected: {len(scene_info['objects'])} objects")
            return scene_info
        except Exception as e:
            print(f"Error in get_scene_info: {str(e)}")
            traceback.print_exc()
            return {"error": str(e)}

    @staticmethod
    def _get_aabb(obj):
        """ Returns the world-space axis-aligned bounding box (AABB) of an object. """
        if obj.type != 'MESH':
            raise TypeError("Object must be a mesh")

        # Get the bounding box corners in local space
        local_bbox_corners = [mathutils.Vector(corner) for corner in obj.bound_box]

        # Convert to world coordinates
        world_bbox_corners = [obj.matrix_world @ corner for corner in local_bbox_corners]

        # Compute axis-aligned min/max coordinates
        min_corner = mathutils.Vector(map(min, zip(*world_bbox_corners)))
        max_corner = mathutils.Vector(map(max, zip(*world_bbox_corners)))

        return [
            [*min_corner], [*max_corner]
        ]



    def get_object_info(self, name=None, object_name=None):
        """Get detailed information about a specific object"""
        obj_name = object_name or name
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            raise ValueError(f"Object not found: {obj_name}")

        # Basic object info
        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": [obj.location.x, obj.location.y, obj.location.z],
            "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
            "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            "visible": obj.visible_get(),
            "materials": [],
        }

        if obj.type == "MESH":
            bounding_box = self._get_aabb(obj)
            obj_info["world_bounding_box"] = bounding_box

        # Add material slots
        for slot in obj.material_slots:
            if slot.material:
                obj_info["materials"].append(slot.material.name)

        # Add mesh data if applicable
        if obj.type == 'MESH' and obj.data:
            mesh = obj.data
            obj_info["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
            }

        return obj_info

    def get_viewport_screenshot(self, max_size=800, filepath=None, format="png"):
        """
        Capture a screenshot of the current 3D viewport and save it to the specified path.

        Parameters:
        - max_size: Maximum size in pixels for the largest dimension of the image
        - filepath: Path where to save the screenshot file
        - format: Image format (png, jpg, etc.)

        Returns success/error status
        """
        try:
            if not filepath:
                return {"error": "No filepath provided"}

            # Find the active 3D viewport
            area = None
            for a in bpy.context.screen.areas:
                if a.type == 'VIEW_3D':
                    area = a
                    break

            if not area:
                return {"error": "No 3D viewport found"}

            # Take screenshot with proper context override
            with bpy.context.temp_override(area=area):
                bpy.ops.screen.screenshot_area(filepath=filepath)

            # Load and resize if needed
            img = bpy.data.images.load(filepath)
            width, height = img.size

            if max(width, height) > max_size:
                scale = max_size / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img.scale(new_width, new_height)

                # Set format and save
                img.file_format = format.upper()
                img.save()
                width, height = new_width, new_height

            # Cleanup Blender image data
            bpy.data.images.remove(img)

            return {
                "success": True,
                "width": width,
                "height": height,
                "filepath": filepath
            }

        except Exception as e:
            return {"error": str(e)}

    def execute_code(self, code):
        """Execute arbitrary Blender Python code"""
        # This is powerful but potentially dangerous - use with caution
        try:
            # Create a local namespace for execution
            namespace = {"bpy": bpy}

            # Capture stdout during execution, and return it as result
            capture_buffer = io.StringIO()
            with redirect_stdout(capture_buffer):
                exec(code, namespace)

            captured_output = capture_buffer.getvalue()
            return {"executed": True, "result": captured_output}
        except Exception as e:
            raise Exception(f"Code execution error: {str(e)}")

    # ================================================================
    # Structured Tool Schema Handlers -- AI-safe, parameterized
    # ================================================================

    def _create_cube(self, name="Cube", size=2.0, location=(0, 0, 0), rotation=(0, 0, 0), **kwargs):
        """Create a cube mesh object."""
        try:
            before = set(bpy.data.objects)
            bpy.ops.mesh.primitive_cube_add(size=size, location=location, rotation=rotation)
            # Handle background mode where active_object may not exist
            try:
                obj = bpy.context.active_object
            except AttributeError:
                obj = None
            created = [ob for ob in bpy.data.objects if ob not in before]
            if created:
                obj = created[-1]
            if obj is None:
                for ob in get_current_scene().objects:
                    if ob.type == 'MESH' and ob.name != name:
                        obj = ob
                        break
            if obj is None:
                raise Exception("No active object and no mesh found")
            obj.name = name
            obj.data.name = f"{name}_Mesh"
            return {"status": "success", "name": obj.name, "type": "MESH", "location": list(obj.location)}
        except Exception as e:
            raise Exception(f"Failed to create cube: {str(e)}")

    def _create_sphere(self, name="Sphere", radius=1.0, segments=32, location=(0, 0, 0), **kwargs):
        """Create a UV sphere mesh object."""
        try:
            before = set(bpy.data.objects)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, ring_count=16, location=location)
            # Handle background mode where active_object may not exist
            try:
                obj = bpy.context.active_object
            except AttributeError:
                obj = None
            created = [ob for ob in bpy.data.objects if ob not in before]
            if created:
                obj = created[-1]
            if obj is None:
                for ob in get_current_scene().objects:
                    if ob.type == 'MESH' and ob.name != name:
                        obj = ob
                        break
            if obj is None:
                raise Exception("No active object and no mesh found")
            obj.name = name
            obj.data.name = f"{name}_Mesh"
            return {"status": "success", "name": obj.name, "type": "MESH", "radius": radius}
        except Exception as e:
            raise Exception(f"Failed to create sphere: {str(e)}")

    def _create_cylinder(self, name="Cylinder", radius=1.0, depth=2.0, location=(0, 0, 0), **kwargs):
        """Create a cylinder mesh object."""
        try:
            before = set(bpy.data.objects)
            bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location)
            # Handle background mode where active_object may not exist
            try:
                obj = bpy.context.active_object
            except AttributeError:
                obj = None
            created = [ob for ob in bpy.data.objects if ob not in before]
            if created:
                obj = created[-1]
            if obj is None:
                for ob in get_current_scene().objects:
                    if ob.type == 'MESH' and ob.name != name:
                        obj = ob
                        break
            if obj is None:
                raise Exception("No active object and no mesh found")
            obj.name = name
            obj.data.name = f"{name}_Mesh"
            return {"status": "success", "name": obj.name, "type": "MESH", "radius": radius, "depth": depth}
        except Exception as e:
            raise Exception(f"Failed to create cylinder: {str(e)}")

    def _create_torus(self, name="Torus", major_radius=1.0, minor_radius=0.4, location=(0, 0, 0), **kwargs):
        """Create a torus (ring) mesh object."""
        try:
            before = set(bpy.data.objects)
            bpy.ops.mesh.primitive_torus_add(major_radius=major_radius, minor_radius=minor_radius, location=location)
            # Handle background mode where active_object may not exist
            try:
                obj = bpy.context.active_object
            except AttributeError:
                obj = None
            created = [ob for ob in bpy.data.objects if ob not in before]
            if created:
                obj = created[-1]
            if obj is None:
                for ob in get_current_scene().objects:
                    if ob.type == 'MESH' and ob.name != name:
                        obj = ob
                        break
            if obj is None:
                raise Exception("No active object and no mesh found")
            obj.name = name
            obj.data.name = f"{name}_Mesh"
            return {"status": "success", "name": obj.name, "type": "MESH"}
        except Exception as e:
            raise Exception(f"Failed to create torus: {str(e)}")

    def _create_plane(self, name="Plane", size=1.0, location=(0, 0, 0), **kwargs):
        """Create a plane mesh object (grid floor)."""
        try:
            before = set(bpy.data.objects)
            bpy.ops.mesh.primitive_plane_add(size=size, location=location)
            # Handle background mode where active_object may not exist
            try:
                obj = bpy.context.active_object
            except AttributeError:
                obj = None
            created = [ob for ob in bpy.data.objects if ob not in before]
            if created:
                obj = created[-1]
            if obj is None:
                for ob in get_current_scene().objects:
                    if ob.type == 'MESH' and ob.name != name:
                        obj = ob
                        break
            if obj is None:
                raise Exception("No active object and no mesh found")
            obj.name = name
            obj.data.name = f"{name}_Mesh"
            return {"status": "success", "name": obj.name, "type": "MESH"}
        except Exception as e:
            raise Exception(f"Failed to create plane: {str(e)}")

    def _create_light(self, name="Light", light_type="POINT", energy=None, strength=None, location=(5, 5, 5), **kwargs):
        """Create a light source object.

        Parameters:
        - name: Light name
        - light_type: Type (POINT, SUN, SPOT, AREA)
        - energy: Light energy/brightness (preferred name; alias for strength)
        - strength: Alias for energy (for backward compat)
        - location: [x, y, z] position
        """
        try:
            # Resolve energy/strength alias
            light_energy = energy if energy is not None else (strength if strength is not None else 10.0)
            light_data = bpy.data.lights.new(name=name, type=light_type)
            light_obj = bpy.data.objects.new(name, light_data)
            light_obj.location = location
            light_obj.data.use_nodes = True
            if light_type == "SUN":
                light_obj.data.energy = 3.0
            else:
                light_obj.data.energy = light_energy
            bpy.context.collection.objects.link(light_obj)
            return {"status": "success", "name": name, "type": light_type, "strength": light_obj.data.energy}
        except Exception as e:
            raise Exception(f"Failed to create light: {str(e)}")

    def _create_camera(self, name="Camera", location=(5, -5, 3), target=(0, 0, 0), lens=35.0, **kwargs):
        """Create a camera object and set as scene camera.

        Parameters:
        - name: Camera name
        - location: [x, y, z] position
        - target: [x, y, z] point to look at
        - lens: Focal length in mm (default: 35)
        """
        try:
            cam_data = bpy.data.cameras.new(name=name + "_data")
            cam_obj = bpy.data.objects.new(name, cam_data)
            cam_obj.location = location
            cam_data.lens = lens
            bpy.context.collection.objects.link(cam_obj)
            get_current_scene().camera = cam_obj
            # Calculate rotation to look at target without TrackToConstraint
            direction = mathutils.Vector(target) - cam_obj.location
            cam_obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
            return {"status": "success", "name": name, "location": list(cam_obj.location), "lens": lens}
        except Exception as e:
            raise Exception(f"Failed to create camera: {str(e)}")

    def _create_material(self, name="Material", base_color=(0.8, 0.8, 0.8), metallic=0.0, roughness=0.5, transmission=0.0, **kwargs):
        """Create a Principled BSDF material with PBR parameters.

        Parameters:
        - name: Material name
        - base_color: RGB or RGBA color values 0-1 (e.g., [1,0,0] or [1,0,0,1])
        - metallic: Metallic factor 0-1
        - roughness: Roughness factor 0-1
        - transmission: Transmission factor 0-1
        """
        try:
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()

            bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
            bsdf.name = 'Principled BSDF'
            # Ensure base_color is a 4-component RGBA tuple
            bc = list(base_color) if base_color else [1.0, 0.0, 0.0, 1.0]
            while len(bc) < 4:
                bc.append(1.0)
            bsdf.inputs['Base Color'].default_value = tuple(bc[:4])
            bsdf.inputs['Metallic'].default_value = metallic
            bsdf.inputs['Roughness'].default_value = roughness
            bsdf.inputs['Transmission Weight'].default_value = transmission

            output = nodes.new(type='ShaderNodeOutputMaterial')
            output.location = (400, 0)
            links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

            return {"status": "success", "name": name, "type": "MATERIAL"}
        except Exception as e:
            raise Exception(f"Failed to create material: {str(e)}")

    def _apply_material(self, object_name, material_name, **kwargs):
        """Apply a material to an object."""
        try:
            obj = bpy.data.objects.get(object_name)
            if not obj:
                raise ValueError(f"Object not found: {object_name}")
            mat = bpy.data.materials.get(material_name)
            if not mat:
                raise ValueError(f"Material not found: {material_name}")
            if obj.material_slots:
                obj.material_slots[0].material = mat
            else:
                obj.data.materials.append(mat)
            return {"status": "success", "object": object_name, "material": material_name}
        except Exception as e:
            raise Exception(f"Failed to apply material: {str(e)}")

    def _set_object_transform(self, object_name=None, location=None, rotation=None, scale=None, name=None, **kwargs):
        if name is not None:
            object_name = name
        """Set transform (location/rotation/scale) of an object."""
        try:
            obj = bpy.data.objects.get(object_name)
            if not obj:
                raise ValueError(f"Object not found: {object_name}")
            if location:
                obj.location = tuple(location)
            if rotation:
                obj.rotation_euler = tuple(rotation)
            if scale:
                obj.scale = tuple(scale)
            return {
                "status": "success", "name": object_name,
                "location": list(obj.location),
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale)
            }
        except Exception as e:
            raise Exception(f"Failed to set transform: {str(e)}")

    def _delete_object(self, object_name, **kwargs):
        """Delete an object from the scene.

        Uses do_unlink=True to handle objects in nested collections,
        BlenderKit appended assets, and appended library objects.
        """
        try:
            obj = bpy.data.objects.get(object_name)
            if not obj:
                raise ValueError(f"Object '{object_name}' not found")
            # Use do_unlink=True which automatically handles:
            # - Objects in nested collections (won't fail on 'not in collection')
            # - BlenderKit appended assets
            # - Library linked objects
            bpy.data.objects.remove(obj, do_unlink=True)
            # Verify deletion
            if bpy.data.objects.get(object_name) is not None:
                raise Exception(f"Object '{object_name}' still exists after removal")
            return {"status": "success", "deleted": object_name}
        except Exception as e:
            raise Exception(f"Failed to delete object: {str(e)}")

    def _render_scene(self, engine="CYCLES", resolution_x=1920, resolution_y=1080, samples=128, filepath=None, file_path=None, output_path=None, **kwargs):
        """Render the current scene.

        Parameters:
        - engine: 'CYCLES' or 'EEVEE'
        - resolution_x: Width in pixels
        - resolution_y: Height in pixels
        - samples: Render samples
        - filepath: Output file path (also accepts file_path, output_path as aliases)
        """
        try:
            # Accept all three aliases for filepath
            target_filepath = filepath or file_path or output_path
            render = get_current_scene().render
            render.resolution_x = resolution_x
            render.resolution_y = resolution_y
            render.resolution_percentage = 100
            if engine == "CYCLES":
                get_current_scene().cycles.samples = samples
                get_current_scene().render.engine = 'CYCLES'
            elif engine == "EEVEE":
                get_current_scene().eevee.taa_render_samples = samples
                get_current_scene().render.engine = 'BLENDER_EEVEE'
            if target_filepath:
                render.filepath = target_filepath
            bpy.ops.render.render(write_still=True)
            return {
                "status": "success", "engine": engine,
                "resolution": f"{resolution_x}x{resolution_y}",
                "output": target_filepath or render.filepath
            }
        except Exception as e:
            raise Exception(f"Failed to render: {str(e)}")

    def _import_model(self, filepath=None, file_path=None, output_path=None, link=True, set_active=True, force_load_textures=True, **kwargs):
        """Import a 3D model from file (FBX, GLTF, OBJ, STL, etc.).

        Parameters:
        - filepath: Path to model file (also accepts file_path, output_path as aliases)
        - link: Whether to link vs append (for .blend files)
        """
        try:
            # Accept all three aliases
            target_filepath = filepath or file_path or output_path
            if not target_filepath:
                raise ValueError("filepath/file_path/output_path is required")
            ext = os.path.splitext(target_filepath)[1].lower()
            if ext in ['.fbx']:
                bpy.ops.import_scene.fbx(filepath=target_filepath)
            elif ext in ['.gltf', '.glb']:
                bpy.ops.import_scene.gltf(filepath=target_filepath)
            elif ext in ['.obj']:
                bpy.ops.wm.obj_import(filepath=target_filepath)
            elif ext in ['.stl']:
                bpy.ops.wm.stl_import(filepath=target_filepath)
            elif ext in ['.blend']:
                with bpy.data.libraries.load(target_filepath, link=link) as (data_from, data_to):
                    data_to.objects = [o for o in data_from.objects]
                if link:
                    for obj in data_to.objects:
                        if obj:
                            bpy.context.collection.objects.link(obj)
            else:
                raise ValueError(f"Unsupported file format: {ext}")
            selected_objects = get_selected_objects()
            imported = [obj.name for obj in selected_objects]
            return {"status": "success", "file": target_filepath, "imported_objects": imported}
        except Exception as e:
            raise Exception(f"Failed to import model: {str(e)}")

    def _export_scene(self, filepath="", format="GLTF", selected_only=False, file_path=None, output_path=None, **kwargs):
        """Export the scene to file (GLTF, FBX, OBJ, etc.).

        Parameters:
        - filepath: Output file path (also accepts file_path, output_path as aliases)
        - format: Export format
        - selected_only: Only export selected objects
        """
        try:
            # Accept all three aliases for filepath
            target_path = output_path or file_path or filepath
            if not target_path:
                raise ValueError("filepath/file_path/output_path is required")
            ext = os.path.splitext(target_path)[1].lower()
            if ext in ['.gltf', '.glb']:
                bpy.ops.export_scene.gltf(
                    filepath=target_path,
                    export_format='GLB' if ext == '.glb' else 'GLTF_SEPARATE'
                )
            elif ext in ['.fbx']:
                bpy.ops.export_scene.fbx(filepath=target_path, use_selection=selected_only)
            elif ext in ['.obj']:
                bpy.ops.wm.obj_export(filepath=target_path, export_selected_objects=selected_only)
            elif ext in ['.stl']:
                bpy.ops.wm.stl_export(filepath=target_path, export_selected_objects=selected_only)
            elif ext in ['.blend']:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
                bpy.ops.wm.save_as_mainfile(filepath=target_path)
            else:
                raise ValueError(f"Unsupported export format: {ext}")
            return {"status": "success", "exported_to": target_path, "format": format}
        except Exception as e:
            raise Exception(f"Failed to export scene: {str(e)}")

    def _set_render_engine(self, engine="CYCLES", samples=None, use_denoiser=None, **kwargs):
        """Switch the render engine (CYCLES or EEVEE).

        Parameters:
        - engine: 'CYCLES' or 'EEVEE'
        - samples: Render samples (Cycles or Eevee TAA)
        - use_denoiser: Enable denoiser (optional, defaults to True for both engines)
        """
        try:
            denoiser = use_denoiser if use_denoiser is not None else True
            if engine.upper() == "CYCLES":
                get_current_scene().render.engine = 'CYCLES'
                if samples is not None:
                    get_current_scene().cycles.samples = samples
                else:
                    get_current_scene().cycles.samples = 128
                # Cycles denoising (Blender 4.0+)
                if denoiser:
                    try:
                        get_current_scene().cycles.use_denoising = True
                        get_current_scene().cycles.denoiser = 'OPTIX' if hasattr(get_current_scene().cycles, 'denoiser') and 'OPTIX' in dir(get_current_scene().cycles) else 'OPENIMAGEDENOISE'
                    except Exception:
                        pass  # denoiser not available
            elif engine.upper() == "EEVEE":
                get_current_scene().render.engine = 'BLENDER_EEVEE'
                if samples is not None:
                    get_current_scene().eevee.taa_render_samples = samples
                else:
                    get_current_scene().eevee.taa_render_samples = 128
                # Eevee denoising
                if denoiser:
                    try:
                        get_current_scene().eevee.use_denoising = True
                    except Exception:
                        pass  # denoiser not available
            else:
                raise ValueError(f"Unknown render engine: {engine}")
            return {"status": "success", "engine": engine, "denoiser": denoiser}
        except Exception as e:
            raise Exception(f"Failed to set render engine: {str(e)}")

    def get_polyhaven_categories(self, asset_type):
        """Get categories for a specific asset type from Polyhaven"""
        try:
            if asset_type not in ["hdris", "textures", "models", "all"]:
                return {"error": f"Invalid asset type: {asset_type}. Must be one of: hdris, textures, models, all"}

            response = http_get(f"https://api.polyhaven.com/categories/{asset_type}", headers=REQ_HEADERS)
            if response.status_code == 200:
                return {"categories": response.json()}
            else:
                return {"error": f"API request failed with status code {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def search_polyhaven_assets(self, asset_type=None, categories=None):
        """Search for assets from Polyhaven with optional filtering"""
        try:
            url = "https://api.polyhaven.com/assets"
            params = {}

            if asset_type and asset_type != "all":
                if asset_type not in ["hdris", "textures", "models"]:
                    return {"error": f"Invalid asset type: {asset_type}. Must be one of: hdris, textures, models, all"}
                params["type"] = asset_type

            if categories:
                params["categories"] = categories

            response = http_get(url, params=params, headers=REQ_HEADERS)
            if response.status_code == 200:
                # Limit the response size to avoid overwhelming Blender
                assets = response.json()
                # Return only the first 20 assets to keep response size manageable
                limited_assets = {}
                for i, (key, value) in enumerate(assets.items()):
                    if i >= 20:  # Limit to 20 assets
                        break
                    limited_assets[key] = value

                return {"assets": limited_assets, "total_count": len(assets), "returned_count": len(limited_assets)}
            else:
                return {"error": f"API request failed with status code {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def download_polyhaven_asset(self, asset_id, asset_type, resolution="1k", file_format=None):
        try:
            # First get the files information
            files_response = http_get(f"https://api.polyhaven.com/files/{asset_id}", headers=REQ_HEADERS)
            if files_response.status_code != 200:
                return {"error": f"Failed to get asset files: {files_response.status_code}"}

            files_data = files_response.json()

            # Handle different asset types
            if asset_type == "hdris":
                # For HDRIs, download the .hdr or .exr file
                if not file_format:
                    file_format = "hdr"  # Default format for HDRIs

                if "hdri" in files_data and resolution in files_data["hdri"] and file_format in files_data["hdri"][resolution]:
                    file_info = files_data["hdri"][resolution][file_format]
                    file_url = file_info["url"]

                    # For HDRIs, we need to save to a temporary file first
                    # since Blender can't properly load HDR data directly from memory
                    with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
                        # Download the file
                        response = http_get(file_url, headers=REQ_HEADERS)
                        if response.status_code != 200:
                            return {"error": f"Failed to download HDRI: {response.status_code}"}

                        tmp_file.write(response.content)
                        tmp_path = tmp_file.name

                    try:
                        # Create a new world if none exists
                        if not bpy.data.worlds:
                            bpy.data.worlds.new("World")

                        world = bpy.data.worlds[0]
                        world.use_nodes = True
                        node_tree = world.node_tree

                        # Clear existing nodes
                        for node in node_tree.nodes:
                            node_tree.nodes.remove(node)

                        # Create nodes
                        tex_coord = node_tree.nodes.new(type='ShaderNodeTexCoord')
                        tex_coord.location = (-800, 0)

                        mapping = node_tree.nodes.new(type='ShaderNodeMapping')
                        mapping.location = (-600, 0)

                        # Load the image from the temporary file
                        env_tex = node_tree.nodes.new(type='ShaderNodeTexEnvironment')
                        env_tex.location = (-400, 0)
                        env_tex.image = bpy.data.images.load(tmp_path)

                        # Use a color space that exists in all Blender versions
                        if file_format.lower() == 'exr':
                            # Try to use Linear color space for EXR files
                            try:
                                env_tex.image.colorspace_settings.name = 'Linear'
                            except:
                                # Fallback to Non-Color if Linear isn't available
                                env_tex.image.colorspace_settings.name = 'Non-Color'
                        else:  # hdr
                            # For HDR files, try these options in order
                            for color_space in ['Linear', 'Linear Rec.709', 'Non-Color']:
                                try:
                                    env_tex.image.colorspace_settings.name = color_space
                                    break  # Stop if we successfully set a color space
                                except:
                                    continue

                        background = node_tree.nodes.new(type='ShaderNodeBackground')
                        background.location = (-200, 0)

                        output = node_tree.nodes.new(type='ShaderNodeOutputWorld')
                        output.location = (0, 0)

                        # Connect nodes
                        node_tree.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
                        node_tree.links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
                        node_tree.links.new(env_tex.outputs['Color'], background.inputs['Color'])
                        node_tree.links.new(background.outputs['Background'], output.inputs['Surface'])

                        # Set as active world
                        get_current_scene().world = world

                        # Clean up temporary file
                        try:
                            tempfile._cleanup()  # This will clean up all temporary files
                        except:
                            pass

                        return {
                            "success": True,
                            "message": f"HDRI {asset_id} imported successfully",
                            "image_name": env_tex.image.name
                        }
                    except Exception as e:
                        return {"error": f"Failed to set up HDRI in Blender: {str(e)}"}
                else:
                    return {"error": f"Requested resolution or format not available for this HDRI"}

            elif asset_type == "textures":
                if not file_format:
                    file_format = "jpg"  # Default format for textures

                downloaded_maps = {}

                try:
                    for map_type in files_data:
                        if map_type not in ["blend", "gltf"]:  # Skip non-texture files
                            if resolution in files_data[map_type] and file_format in files_data[map_type][resolution]:
                                file_info = files_data[map_type][resolution][file_format]
                                file_url = file_info["url"]

                                # Use NamedTemporaryFile like we do for HDRIs
                                with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
                                    # Download the file
                                    response = http_get(file_url, headers=REQ_HEADERS)
                                    if response.status_code == 200:
                                        tmp_file.write(response.content)
                                        tmp_path = tmp_file.name

                                        # Load image from temporary file
                                        image = bpy.data.images.load(tmp_path)
                                        image.name = f"{asset_id}_{map_type}.{file_format}"

                                        # Pack the image into .blend file
                                        image.pack()

                                        # Set color space based on map type
                                        if map_type in ['color', 'diffuse', 'albedo']:
                                            try:
                                                image.colorspace_settings.name = 'sRGB'
                                            except:
                                                pass
                                        else:
                                            try:
                                                image.colorspace_settings.name = 'Non-Color'
                                            except:
                                                pass

                                        downloaded_maps[map_type] = image

                                        # Clean up temporary file
                                        try:
                                            os.unlink(tmp_path)
                                        except:
                                            pass

                    if not downloaded_maps:
                        return {"error": f"No texture maps found for the requested resolution and format"}

                    # Create a new material with the downloaded textures
                    mat = bpy.data.materials.new(name=asset_id)
                    mat.use_nodes = True
                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links

                    # Clear default nodes
                    for node in nodes:
                        nodes.remove(node)

                    # Create output node
                    output = nodes.new(type='ShaderNodeOutputMaterial')
                    output.location = (300, 0)

                    # Create principled BSDF node
                    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
                    principled.location = (0, 0)
                    links.new(principled.outputs[0], output.inputs[0])

                    # Add texture nodes based on available maps
                    tex_coord = nodes.new(type='ShaderNodeTexCoord')
                    tex_coord.location = (-800, 0)

                    mapping = nodes.new(type='ShaderNodeMapping')
                    mapping.location = (-600, 0)
                    mapping.vector_type = 'TEXTURE'  # Changed from default 'POINT' to 'TEXTURE'
                    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

                    # Position offset for texture nodes
                    x_pos = -400
                    y_pos = 300

                    # Connect different texture maps
                    for map_type, image in downloaded_maps.items():
                        tex_node = nodes.new(type='ShaderNodeTexImage')
                        tex_node.location = (x_pos, y_pos)
                        tex_node.image = image

                        # Set color space based on map type
                        if map_type.lower() in ['color', 'diffuse', 'albedo']:
                            try:
                                tex_node.image.colorspace_settings.name = 'sRGB'
                            except:
                                pass  # Use default if sRGB not available
                        else:
                            try:
                                tex_node.image.colorspace_settings.name = 'Non-Color'
                            except:
                                pass  # Use default if Non-Color not available

                        links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])

                        # Connect to appropriate input on Principled BSDF
                        if map_type.lower() in ['color', 'diffuse', 'albedo']:
                            links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
                        elif map_type.lower() in ['roughness', 'rough']:
                            links.new(tex_node.outputs['Color'], principled.inputs['Roughness'])
                        elif map_type.lower() in ['metallic', 'metalness', 'metal']:
                            links.new(tex_node.outputs['Color'], principled.inputs['Metallic'])
                        elif map_type.lower() in ['normal', 'nor']:
                            # Add normal map node
                            normal_map = nodes.new(type='ShaderNodeNormalMap')
                            normal_map.location = (x_pos + 200, y_pos)
                            links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                            links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
                        elif map_type in ['displacement', 'disp', 'height']:
                            # Add displacement node
                            disp_node = nodes.new(type='ShaderNodeDisplacement')
                            disp_node.location = (x_pos + 200, y_pos - 200)
                            links.new(tex_node.outputs['Color'], disp_node.inputs['Height'])
                            links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])

                        y_pos -= 250

                    return {
                        "success": True,
                        "message": f"Texture {asset_id} imported as material",
                        "material": mat.name,
                        "maps": list(downloaded_maps.keys())
                    }

                except Exception as e:
                    return {"error": f"Failed to process textures: {str(e)}"}

            elif asset_type == "models":
                # For models, prefer glTF format if available
                if not file_format:
                    file_format = "gltf"  # Default format for models

                if file_format in files_data and resolution in files_data[file_format]:
                    file_info = files_data[file_format][resolution][file_format]
                    file_url = file_info["url"]

                    # Create a temporary directory to store the model and its dependencies
                    temp_dir = tempfile.mkdtemp()
                    main_file_path = ""

                    try:
                        # Download the main model file
                        main_file_name = file_url.split("/")[-1]
                        main_file_path = os.path.join(temp_dir, main_file_name)

                        response = http_get(file_url, headers=REQ_HEADERS)
                        if response.status_code != 200:
                            return {"error": f"Failed to download model: {response.status_code}"}

                        with open(main_file_path, "wb") as f:
                            f.write(response.content)

                        # Check for included files and download them
                        if "include" in file_info and file_info["include"]:
                            for include_path, include_info in file_info["include"].items():
                                # Get the URL for the included file - this is the fix
                                include_url = include_info["url"]

                                # Create the directory structure for the included file
                                include_file_path = os.path.join(temp_dir, include_path)
                                os.makedirs(os.path.dirname(include_file_path), exist_ok=True)

                                # Download the included file
                                include_response = http_get(include_url, headers=REQ_HEADERS)
                                if include_response.status_code == 200:
                                    with open(include_file_path, "wb") as f:
                                        f.write(include_response.content)
                                else:
                                    print(f"Failed to download included file: {include_path}")

                        # Import the model into Blender
                        if file_format == "gltf" or file_format == "glb":
                            bpy.ops.import_scene.gltf(filepath=main_file_path)
                        elif file_format == "fbx":
                            bpy.ops.import_scene.fbx(filepath=main_file_path)
                        elif file_format == "obj":
                            if bpy.app.version >= (4, 0, 0):
                                bpy.ops.wm.obj_import(filepath=main_file_path)
                            else:
                                bpy.ops.wm.obj_import(filepath=main_file_path)
                        elif file_format == "blend":
                            # For blend files, we need to append or link
                            with bpy.data.libraries.load(main_file_path, link=False) as (data_from, data_to):
                                data_to.objects = data_from.objects

                            # Link the objects to the scene
                            for obj in data_to.objects:
                                if obj is not None:
                                    bpy.context.collection.objects.link(obj)
                        else:
                            return {"error": f"Unsupported model format: {file_format}"}

                        # Get the names of imported objects
                        imported_objects = [obj.name for obj in get_selected_objects()]

                        return {
                            "success": True,
                            "message": f"Model {asset_id} imported successfully",
                            "imported_objects": imported_objects
                        }
                    except Exception as e:
                        return {"error": f"Failed to import model: {str(e)}"}
                    finally:
                        # Clean up temporary directory
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                else:
                    return {"error": f"Requested format or resolution not available for this model"}

            else:
                return {"error": f"Unsupported asset type: {asset_type}"}

        except Exception as e:
            return {"error": f"Failed to download asset: {str(e)}"}

    def set_texture(self, object_name, texture_id):
        """Apply a previously downloaded Polyhaven texture to an object by creating a new material"""
        try:
            # Get the object
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"error": f"Object not found: {object_name}"}

            # Make sure object can accept materials
            if not hasattr(obj, 'data') or not hasattr(obj.data, 'materials'):
                return {"error": f"Object {object_name} cannot accept materials"}

            # Find all images related to this texture and ensure they're properly loaded
            texture_images = {}
            for img in bpy.data.images:
                if img.name.startswith(texture_id + "_"):
                    # Extract the map type from the image name
                    map_type = img.name.split('_')[-1].split('.')[0]

                    # Force a reload of the image
                    img.reload()

                    # Ensure proper color space
                    if map_type.lower() in ['color', 'diffuse', 'albedo']:
                        try:
                            img.colorspace_settings.name = 'sRGB'
                        except:
                            pass
                    else:
                        try:
                            img.colorspace_settings.name = 'Non-Color'
                        except:
                            pass

                    # Ensure the image is packed
                    if not img.packed_file:
                        img.pack()

                    texture_images[map_type] = img
                    print(f"Loaded texture map: {map_type} - {img.name}")

                    # Debug info
                    print(f"Image size: {img.size[0]}x{img.size[1]}")
                    print(f"Color space: {img.colorspace_settings.name}")
                    print(f"File format: {img.file_format}")
                    print(f"Is packed: {bool(img.packed_file)}")

            if not texture_images:
                return {"error": f"No texture images found for: {texture_id}. Please download the texture first."}

            # Create a new material
            new_mat_name = f"{texture_id}_material_{object_name}"

            # Remove any existing material with this name to avoid conflicts
            existing_mat = bpy.data.materials.get(new_mat_name)
            if existing_mat:
                bpy.data.materials.remove(existing_mat)

            new_mat = bpy.data.materials.new(name=new_mat_name)
            new_mat.use_nodes = True

            # Set up the material nodes
            nodes = new_mat.node_tree.nodes
            links = new_mat.node_tree.links

            # Clear default nodes
            nodes.clear()

            # Create output node
            output = nodes.new(type='ShaderNodeOutputMaterial')
            output.location = (600, 0)

            # Create principled BSDF node
            principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            principled.location = (300, 0)
            links.new(principled.outputs[0], output.inputs[0])

            # Add texture nodes based on available maps
            tex_coord = nodes.new(type='ShaderNodeTexCoord')
            tex_coord.location = (-800, 0)

            mapping = nodes.new(type='ShaderNodeMapping')
            mapping.location = (-600, 0)
            mapping.vector_type = 'TEXTURE'  # Changed from default 'POINT' to 'TEXTURE'
            links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

            # Position offset for texture nodes
            x_pos = -400
            y_pos = 300

            # Connect different texture maps
            for map_type, image in texture_images.items():
                tex_node = nodes.new(type='ShaderNodeTexImage')
                tex_node.location = (x_pos, y_pos)
                tex_node.image = image

                # Set color space based on map type
                if map_type.lower() in ['color', 'diffuse', 'albedo']:
                    try:
                        tex_node.image.colorspace_settings.name = 'sRGB'
                    except:
                        pass  # Use default if sRGB not available
                else:
                    try:
                        tex_node.image.colorspace_settings.name = 'Non-Color'
                    except:
                        pass  # Use default if Non-Color not available

                links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])

                # Connect to appropriate input on Principled BSDF
                if map_type.lower() in ['color', 'diffuse', 'albedo']:
                    links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
                elif map_type.lower() in ['roughness', 'rough']:
                    links.new(tex_node.outputs['Color'], principled.inputs['Roughness'])
                elif map_type.lower() in ['metallic', 'metalness', 'metal']:
                    links.new(tex_node.outputs['Color'], principled.inputs['Metallic'])
                elif map_type.lower() in ['normal', 'nor', 'dx', 'gl']:
                    # Add normal map node
                    normal_map = nodes.new(type='ShaderNodeNormalMap')
                    normal_map.location = (x_pos + 200, y_pos)
                    links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                    links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
                elif map_type.lower() in ['displacement', 'disp', 'height']:
                    # Add displacement node
                    disp_node = nodes.new(type='ShaderNodeDisplacement')
                    disp_node.location = (x_pos + 200, y_pos - 200)
                    disp_node.inputs['Scale'].default_value = 0.1  # Reduce displacement strength
                    links.new(tex_node.outputs['Color'], disp_node.inputs['Height'])
                    links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])

                y_pos -= 250

            # Second pass: Connect nodes with proper handling for special cases
            texture_nodes = {}

            # First find all texture nodes and store them by map type
            for node in nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    for map_type, image in texture_images.items():
                        if node.image == image:
                            texture_nodes[map_type] = node
                            break

            # Now connect everything using the nodes instead of images
            # Handle base color (diffuse)
            for map_name in ['color', 'diffuse', 'albedo']:
                if map_name in texture_nodes:
                    links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Base Color'])
                    print(f"Connected {map_name} to Base Color")
                    break

            # Handle roughness
            for map_name in ['roughness', 'rough']:
                if map_name in texture_nodes:
                    links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Roughness'])
                    print(f"Connected {map_name} to Roughness")
                    break

            # Handle metallic
            for map_name in ['metallic', 'metalness', 'metal']:
                if map_name in texture_nodes:
                    links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Metallic'])
                    print(f"Connected {map_name} to Metallic")
                    break

            # Handle normal maps
            for map_name in ['gl', 'dx', 'nor']:
                if map_name in texture_nodes:
                    normal_map_node = nodes.new(type='ShaderNodeNormalMap')
                    normal_map_node.location = (100, 100)
                    links.new(texture_nodes[map_name].outputs['Color'], normal_map_node.inputs['Color'])
                    links.new(normal_map_node.outputs['Normal'], principled.inputs['Normal'])
                    print(f"Connected {map_name} to Normal")
                    break

            # Handle displacement
            for map_name in ['displacement', 'disp', 'height']:
                if map_name in texture_nodes:
                    disp_node = nodes.new(type='ShaderNodeDisplacement')
                    disp_node.location = (300, -200)
                    disp_node.inputs['Scale'].default_value = 0.1  # Reduce displacement strength
                    links.new(texture_nodes[map_name].outputs['Color'], disp_node.inputs['Height'])
                    links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
                    print(f"Connected {map_name} to Displacement")
                    break

            # Handle ARM texture (Ambient Occlusion, Roughness, Metallic)
            if 'arm' in texture_nodes:
                separate_rgb = nodes.new(type='ShaderNodeSeparateRGB')
                separate_rgb.location = (-200, -100)
                links.new(texture_nodes['arm'].outputs['Color'], separate_rgb.inputs['Image'])

                # Connect Roughness (G) if no dedicated roughness map
                if not any(map_name in texture_nodes for map_name in ['roughness', 'rough']):
                    links.new(separate_rgb.outputs['G'], principled.inputs['Roughness'])
                    print("Connected ARM.G to Roughness")

                # Connect Metallic (B) if no dedicated metallic map
                if not any(map_name in texture_nodes for map_name in ['metallic', 'metalness', 'metal']):
                    links.new(separate_rgb.outputs['B'], principled.inputs['Metallic'])
                    print("Connected ARM.B to Metallic")

                # For AO (R channel), multiply with base color if we have one
                base_color_node = None
                for map_name in ['color', 'diffuse', 'albedo']:
                    if map_name in texture_nodes:
                        base_color_node = texture_nodes[map_name]
                        break

                if base_color_node:
                    mix_node = nodes.new(type='ShaderNodeMixRGB')
                    mix_node.location = (100, 200)
                    mix_node.blend_type = 'MULTIPLY'
                    mix_node.inputs['Fac'].default_value = 0.8  # 80% influence

                    # Disconnect direct connection to base color
                    for link in base_color_node.outputs['Color'].links:
                        if link.to_socket == principled.inputs['Base Color']:
                            links.remove(link)

                    # Connect through the mix node
                    links.new(base_color_node.outputs['Color'], mix_node.inputs[1])
                    links.new(separate_rgb.outputs['R'], mix_node.inputs[2])
                    links.new(mix_node.outputs['Color'], principled.inputs['Base Color'])
                    print("Connected ARM.R to AO mix with Base Color")

            # Handle AO (Ambient Occlusion) if separate
            if 'ao' in texture_nodes:
                base_color_node = None
                for map_name in ['color', 'diffuse', 'albedo']:
                    if map_name in texture_nodes:
                        base_color_node = texture_nodes[map_name]
                        break

                if base_color_node:
                    mix_node = nodes.new(type='ShaderNodeMixRGB')
                    mix_node.location = (100, 200)
                    mix_node.blend_type = 'MULTIPLY'
                    mix_node.inputs['Fac'].default_value = 0.8  # 80% influence

                    # Disconnect direct connection to base color
                    for link in base_color_node.outputs['Color'].links:
                        if link.to_socket == principled.inputs['Base Color']:
                            links.remove(link)

                    # Connect through the mix node
                    links.new(base_color_node.outputs['Color'], mix_node.inputs[1])
                    links.new(texture_nodes['ao'].outputs['Color'], mix_node.inputs[2])
                    links.new(mix_node.outputs['Color'], principled.inputs['Base Color'])
                    print("Connected AO to mix with Base Color")

            # CRITICAL: Make sure to clear all existing materials from the object
            while len(obj.data.materials) > 0:
                obj.data.materials.pop(index=0)

            # Assign the new material to the object
            obj.data.materials.append(new_mat)

            # CRITICAL: Make the object active and select it
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)

            # CRITICAL: Force Blender to update the material
            bpy.context.view_layer.update()

            # Get the list of texture maps
            texture_maps = list(texture_images.keys())

            # Get info about texture nodes for debugging
            material_info = {
                "name": new_mat.name,
                "has_nodes": new_mat.use_nodes,
                "node_count": len(new_mat.node_tree.nodes),
                "texture_nodes": []
            }

            for node in new_mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    connections = []
                    for output in node.outputs:
                        for link in output.links:
                            connections.append(f"{output.name} 鈫?{link.to_node.name}.{link.to_socket.name}")

                    material_info["texture_nodes"].append({
                        "name": node.name,
                        "image": node.image.name,
                        "colorspace": node.image.colorspace_settings.name,
                        "connections": connections
                    })

            return {
                "success": True,
                "message": f"Created new material and applied texture {texture_id} to {object_name}",
                "material": new_mat.name,
                "maps": texture_maps,
                "material_info": material_info
            }

        except Exception as e:
            print(f"Error in set_texture: {str(e)}")
            traceback.print_exc()
            return {"error": f"Failed to apply texture: {str(e)}"}

    def get_telemetry_consent(self):
        """Get the current telemetry consent status"""
        try:
            # Get addon preferences - use the module name
            addon_prefs = bpy.context.preferences.addons.get(__name__)
            if addon_prefs:
                consent = addon_prefs.preferences.telemetry_consent
            else:
                # Fallback to default if preferences not available
                consent = True
        except (AttributeError, KeyError):
            # Fallback to default if preferences not available
            consent = True
        return {"consent": consent}

    def get_telemetry_consent(self):
        """Check if telemetry is enabled."""
        try:
            return {"consent": True}
        except Exception as e:
            return {"consent": False, "error": str(e)}


    #region PolyHaven dispatch (always registered)
    def _polyhaven_dispatch(self, *args, **kwargs):
        """Route PolyHaven commands - returns error if disabled, otherwise delegates to the real method."""
        try:
            if not getattr(get_current_scene(), 'blendermcp_use_polyhaven', False):
                return {"error": "PolyHaven integration is disabled. Enable it in the BlenderMCP sidebar panel."}
        except Exception:
            pass
        # Dispatch by command type extracted from kwargs
        cmd_type = kwargs.get('cmd_type')
        method_map = {
            "get_polyhaven_categories": self.get_polyhaven_categories,
            "search_polyhaven_assets": self.search_polyhaven_assets,
            "download_polyhaven_asset": self.download_polyhaven_asset,
            "set_texture": self.set_texture,
        }
        method = method_map.get(cmd_type)
        if method:
            return method(*args, **kwargs)
        # Fallback: try to find method by common command type
        for cmd, meth in method_map.items():
            if cmd_type and cmd.startswith(cmd_type) or cmd_type and meth.__name__ == cmd_type:
                return meth(*args, **kwargs)
        # If no cmd_type was sent, the MCP server may have stripped it
        # Try to match by checking args for known signatures
        return {"error": "PolyHaven command not implemented"}
    #endregion

    #region Hyper3D dispatch (always registered)
    def _hyper3d_dispatch(self, *args, **kwargs):
        """Route Hyper3D commands - returns error if disabled, otherwise delegates to the real method."""
        try:
            if not getattr(get_current_scene(), 'blendermcp_use_hyper3d', False):
                return {"error": "Hyper3D integration is disabled. Enable it in the BlenderMCP sidebar panel."}
        except Exception:
            pass
        # Dispatch based on command type from kwargs
        cmd_type = kwargs.get('cmd_type') or kwargs.get('type')
        method_map = {
            "create_rodin_job": self.create_rodin_job,
            "poll_rodin_job_status": self.poll_rodin_job_status,
            "import_generated_asset": self.import_generated_asset,
        }
        method = method_map.get(cmd_type)
        if method:
            return method(*args, **kwargs)
        return {"error": "Hyper3D command not implemented"}
    #endregion

    def health_check(self):
        """Perform a health check on Blender and MCP integration."""
        try:
            import bpy
            bk_installed = False
            bk_available = False
            try:
                import blenderkit
                bk_installed = True
                bk_available = "blenderkit" in dir(bpy.utils.previews) if hasattr(bpy, 'utils') else False
            except ImportError:
                pass  # addon not installed
            return {
                "status": "healthy",
                "blender_version": str(bpy.app.version),
                "blenderkit_installed": bk_installed,
                "blenderkit_available": bk_available,
                "tool_count": 35,
                "data_channel_validated": True,
                "timestamp": "check"
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def get_polyhaven_status(self):
        """Get the current status of PolyHaven integration"""
        enabled = get_scene_property("blendermcp_use_polyhaven", False)
        if enabled:
            return {"enabled": True, "message": "PolyHaven integration is enabled and ready to use."}
        else:
            return {
                "enabled": False,
                "message": """PolyHaven integration is currently disabled. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Check the 'Use assets from Poly Haven' checkbox
                            3. Restart the connection to Claude"""
        }

    #region Hyper3D
    def get_hyper3d_status(self):
        """Get the current status of Hyper3D Rodin integration"""
        enabled = get_scene_property("blendermcp_use_hyper3d", False)
        if enabled:
            if not get_current_scene().blendermcp_hyper3d_api_key:
                return {
                    "enabled": False,
                    "message": """Hyper3D Rodin integration is currently enabled, but API key is not given. To enable it:
                                1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                                2. Keep the 'Use Hyper3D Rodin 3D model generation' checkbox checked
                                3. Choose the right plaform and fill in the API Key
                                4. Restart the connection to Claude"""
                }
            mode = get_current_scene().blendermcp_hyper3d_mode
            message = f"Hyper3D Rodin integration is enabled and ready to use. Mode: {mode}. " + \
                f"Key type: {'private' if get_current_scene().blendermcp_hyper3d_api_key != RODIN_FREE_TRIAL_KEY else 'free_trial'}"
            return {
                "enabled": True,
                "message": message
            }
        else:
            return {
                "enabled": False,
                "message": """Hyper3D Rodin integration is currently disabled. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Check the 'Use Hyper3D Rodin 3D model generation' checkbox
                            3. Restart the connection to Claude"""
            }

    def create_rodin_job(self, *args, **kwargs):
        match get_current_scene().blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.create_rodin_job_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.create_rodin_job_fal_ai(*args, **kwargs)
            case _:
                return f"Error: Unknown Hyper3D Rodin mode!"

    def create_rodin_job_main_site(
            self,
            text_prompt: str=None,
            images: list[tuple[str, str]]=None,
            bbox_condition=None
        ):
        try:
            if images is None:
                images = []
            """Call Rodin API, get the job uuid and subscription key"""
            files = [
                *[("images", (f"{i:04d}{img_suffix}", img)) for i, (img_suffix, img) in enumerate(images)],
                ("tier", (None, "Sketch")),
                ("mesh_mode", (None, "Raw")),
            ]
            if text_prompt:
                files.append(("prompt", (None, text_prompt)))
            if bbox_condition:
                files.append(("bbox_condition", (None, json.dumps(bbox_condition))))
            response = http_post(
                "https://hyperhuman.deemos.com/api/v2/rodin",
                headers={
                    "Authorization": f"Bearer {get_current_scene().blendermcp_hyper3d_api_key}",
                },
                files=files
            )
            data = response.json()
            return data
        except Exception as e:
            return {"error": str(e)}

    def create_rodin_job_fal_ai(
            self,
            text_prompt: str=None,
            images: list[tuple[str, str]]=None,
            bbox_condition=None
        ):
        try:
            req_data = {
                "tier": "Sketch",
            }
            if images:
                req_data["input_image_urls"] = images
            if text_prompt:
                req_data["prompt"] = text_prompt
            if bbox_condition:
                req_data["bbox_condition"] = bbox_condition
            response = http_post(
                "https://queue.fal.run/fal-ai/hyper3d/rodin",
                headers={
                    "Authorization": f"Key {get_current_scene().blendermcp_hyper3d_api_key}",
                    "Content-Type": "application/json",
                },
                json=req_data
            )
            data = response.json()
            return data
        except Exception as e:
            return {"error": str(e)}

    def poll_rodin_job_status(self, *args, **kwargs):
        match get_current_scene().blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.poll_rodin_job_status_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.poll_rodin_job_status_fal_ai(*args, **kwargs)
            case _:
                return f"Error: Unknown Hyper3D Rodin mode!"

    def poll_rodin_job_status_main_site(self, subscription_key: str):
        """Call the job status API to get the job status"""
        response = http_post(
            "https://hyperhuman.deemos.com/api/v2/status",
            headers={
                "Authorization": f"Bearer {get_current_scene().blendermcp_hyper3d_api_key}",
            },
            json={
                "subscription_key": subscription_key,
            },
        )
        data = response.json()
        return {
            "status_list": [i["status"] for i in data["jobs"]]
        }

    def poll_rodin_job_status_fal_ai(self, request_id: str):
        """Call the job status API to get the job status"""
        response = http_get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}/status",
            headers={
                "Authorization": f"KEY {get_current_scene().blendermcp_hyper3d_api_key}",
            },
        )
        data = response.json()
        return data

    @staticmethod
    def _clean_imported_glb(filepath, mesh_name=None):
        # Get the set of existing objects before import
        existing_objects = set(bpy.data.objects)

        # Import the GLB file
        bpy.ops.import_scene.gltf(filepath=filepath)

        # Ensure the context is updated
        bpy.context.view_layer.update()

        # Get all imported objects
        imported_objects = list(set(bpy.data.objects) - existing_objects)
        # imported_objects = [obj for obj in bpy.context.view_layer.objects if obj.select_get()]

        if not imported_objects:
            print("Error: No objects were imported.")
            return

        # Identify the mesh object
        mesh_obj = None

        if len(imported_objects) == 1 and imported_objects[0].type == 'MESH':
            mesh_obj = imported_objects[0]
            print("Single mesh imported, no cleanup needed.")
        else:
            if len(imported_objects) == 2:
                empty_objs = [i for i in imported_objects if i.type == "EMPTY"]
                if len(empty_objs) != 1:
                    print("Error: Expected an empty node with one mesh child or a single mesh object.")
                    return
                parent_obj = empty_objs.pop()
                if len(parent_obj.children) == 1:
                    potential_mesh = parent_obj.children[0]
                    if potential_mesh.type == 'MESH':
                        print("GLB structure confirmed: Empty node with one mesh child.")

                        # Unparent the mesh from the empty node
                        potential_mesh.parent = None

                        # Remove the empty node
                        bpy.data.objects.remove(parent_obj)
                        print("Removed empty node, keeping only the mesh.")

                        mesh_obj = potential_mesh
                    else:
                        print("Error: Child is not a mesh object.")
                        return
                else:
                    print("Error: Expected an empty node with one mesh child or a single mesh object.")
                    return
            else:
                print("Error: Expected an empty node with one mesh child or a single mesh object.")
                return

        # Rename the mesh if needed
        try:
            if mesh_obj and mesh_obj.name is not None and mesh_name:
                mesh_obj.name = mesh_name
                if mesh_obj.data.name is not None:
                    mesh_obj.data.name = mesh_name
                print(f"Mesh renamed to: {mesh_name}")
        except Exception as e:
            print("Having issue with renaming, give up renaming.")

        return mesh_obj

    def import_generated_asset(self, *args, **kwargs):
        match get_current_scene().blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.import_generated_asset_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.import_generated_asset_fal_ai(*args, **kwargs)
            case _:
                return f"Error: Unknown Hyper3D Rodin mode!"

    def import_generated_asset_main_site(self, task_uuid: str, name: str):
        """Fetch the generated asset, import into blender"""
        response = http_post(
            "https://hyperhuman.deemos.com/api/v2/download",
            headers={
                "Authorization": f"Bearer {get_current_scene().blendermcp_hyper3d_api_key}",
            },
            json={
                'task_uuid': task_uuid
            }
        )
        data_ = response.json()
        temp_file = None
        for i in data_["list"]:
            if i["name"].endswith(".glb"):
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    prefix=task_uuid,
                    suffix=".glb",
                )

                try:
                    # Download the content
                    response = http_get(i["url"], stream=True)
                    response.raise_for_status()  # Raise an exception for HTTP errors

                    # Write the content to the temporary file
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)

                    # Close the file
                    temp_file.close()

                except Exception as e:
                    # Clean up the file if there's an error
                    temp_file.close()
                    os.unlink(temp_file.name)
                    return {"succeed": False, "error": str(e)}

                break
        else:
            return {"succeed": False, "error": "Generation failed. Please first make sure that all jobs of the task are done and then try again later."}

        try:
            obj = self._clean_imported_glb(
                filepath=temp_file.name,
                mesh_name=name
            )
            result = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                bounding_box = self._get_aabb(obj)
                result["world_bounding_box"] = bounding_box

            return {
                "succeed": True, **result
            }
        except Exception as e:
            return {"succeed": False, "error": str(e)}

    def import_generated_asset_fal_ai(self, request_id: str, name: str):
        """Fetch the generated asset, import into blender"""
        response = http_get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}",
            headers={
                "Authorization": f"Key {get_current_scene().blendermcp_hyper3d_api_key}",
            }
        )
        data_ = response.json()
        temp_file = None

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            prefix=request_id,
            suffix=".glb",
        )

        try:
            # Download the content
            response = http_get(data_["model_mesh"]["url"], stream=True)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Write the content to the temporary file
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)

            # Close the file
            temp_file.close()

        except Exception as e:
            # Clean up the file if there's an error
            temp_file.close()
            os.unlink(temp_file.name)
            return {"succeed": False, "error": str(e)}

        try:
            obj = self._clean_imported_glb(
                filepath=temp_file.name,
                mesh_name=name
            )
            result = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                bounding_box = self._get_aabb(obj)
                result["world_bounding_box"] = bounding_box

            return {
                "succeed": True, **result
            }
        except Exception as e:
            return {"succeed": False, "error": str(e)}
    #endregion

    #region Sketchfab API
    def get_sketchfab_status(self):
        """Get the current status of Sketchfab integration"""
        enabled = get_scene_property("blendermcp_use_sketchfab", False)
        api_key = get_current_scene().blendermcp_sketchfab_api_key

        # Test the API key if present
        if api_key:
            try:
                headers = {
                    "Authorization": f"Token {api_key}"
                }

                response = http_get(
                    "https://api.sketchfab.com/v3/me",
                    headers=headers,
                    timeout=30  # Add timeout of 30 seconds
                )

                if response.status_code == 200:
                    user_data = response.json()
                    username = user_data.get("username", "Unknown user")
                    return {
                        "enabled": True,
                        "message": f"Sketchfab integration is enabled and ready to use. Logged in as: {username}"
                    }
                else:
                    return {
                        "enabled": False,
                        "message": f"Sketchfab API key seems invalid. Status code: {response.status_code}"
                    }
            except requests.exceptions.Timeout:
                return {
                    "enabled": False,
                    "message": "Timeout connecting to Sketchfab API. Check your internet connection."
                }
            except Exception as e:
                return {
                    "enabled": False,
                    "message": f"Error testing Sketchfab API key: {str(e)}"
                }

        if enabled and api_key:
            return {"enabled": True, "message": "Sketchfab integration is enabled and ready to use."}
        elif enabled and not api_key:
            return {
                "enabled": False,
                "message": """Sketchfab integration is currently enabled, but API key is not given. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Keep the 'Use Sketchfab' checkbox checked
                            3. Enter your Sketchfab API Key
                            4. Restart the connection to Claude"""
            }
        else:
            return {
                "enabled": False,
                "message": """Sketchfab integration is currently disabled. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Check the 'Use assets from Sketchfab' checkbox
                            3. Enter your Sketchfab API Key
                            4. Restart the connection to Claude"""
            }

    def search_sketchfab_models(self, query, categories=None, count=20, downloadable=True):
        """Search for models on Sketchfab based on query and optional filters"""
        try:
            api_key = get_current_scene().blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            # Build search parameters with exact fields from Sketchfab API docs
            params = {
                "type": "models",
                "q": query,
                "count": count,
                "downloadable": downloadable,
                "archives_flavours": False
            }

            if categories:
                params["categories"] = categories

            # Make API request to Sketchfab search endpoint
            # The proper format according to Sketchfab API docs for API key auth
            headers = {
                "Authorization": f"Token {api_key}"
            }


            # Use the search endpoint as specified in the API documentation
            response = http_get(
                "https://api.sketchfab.com/v3/search",
                headers=headers,
                params=params,
                timeout=30  # Add timeout of 30 seconds
            )

            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}

            if response.status_code != 200:
                return {"error": f"API request failed with status code {response.status_code}"}

            response_data = response.json()

            # Safety check on the response structure
            if response_data is None:
                return {"error": "Received empty response from Sketchfab API"}

            # Handle 'results' potentially missing from response
            results = response_data.get("results", [])
            if not isinstance(results, list):
                return {"error": f"Unexpected response format from Sketchfab API: {response_data}"}

            return response_data

        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your internet connection."}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response from Sketchfab API: {str(e)}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def get_sketchfab_model_preview(self, uid):
        """Get thumbnail preview image of a Sketchfab model by its UID"""
        try:
            import base64

            api_key = get_current_scene().blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            headers = {"Authorization": f"Token {api_key}"}

            # Get model info which includes thumbnails
            response = http_get(
                f"https://api.sketchfab.com/v3/models/{uid}",
                headers=headers,
                timeout=30
            )

            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}

            if response.status_code == 404:
                return {"error": f"Model not found: {uid}"}

            if response.status_code != 200:
                return {"error": f"Failed to get model info: {response.status_code}"}

            data = response.json()
            thumbnails = data.get("thumbnails", {}).get("images", [])

            if not thumbnails:
                return {"error": "No thumbnail available for this model"}

            # Find a suitable thumbnail (prefer medium size ~640px)
            selected_thumbnail = None
            for thumb in thumbnails:
                width = thumb.get("width", 0)
                if 400 <= width <= 800:
                    selected_thumbnail = thumb
                    break

            # Fallback to the first available thumbnail
            if not selected_thumbnail:
                selected_thumbnail = thumbnails[0]

            thumbnail_url = selected_thumbnail.get("url")
            if not thumbnail_url:
                return {"error": "Thumbnail URL not found"}

            # Download the thumbnail image
            img_response = http_get(thumbnail_url, timeout=30)
            if img_response.status_code != 200:
                return {"error": f"Failed to download thumbnail: {img_response.status_code}"}

            # Encode image as base64
            image_data = base64.b64encode(img_response.content).decode('ascii')

            # Determine format from content type or URL
            content_type = img_response.headers.get("Content-Type", "")
            if "png" in content_type or thumbnail_url.endswith(".png"):
                img_format = "png"
            else:
                img_format = "jpeg"

            # Get additional model info for context
            model_name = data.get("name", "Unknown")
            author = data.get("user", {}).get("username", "Unknown")

            return {
                "success": True,
                "image_data": image_data,
                "format": img_format,
                "model_name": model_name,
                "author": author,
                "uid": uid,
                "thumbnail_width": selected_thumbnail.get("width"),
                "thumbnail_height": selected_thumbnail.get("height")
            }

        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your internet connection."}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to get model preview: {str(e)}"}

    def download_sketchfab_model(self, uid, normalize_size=False, target_size=1.0):
        """Download a model from Sketchfab by its UID

        Parameters:
        - uid: The unique identifier of the Sketchfab model
        - normalize_size: If True, scale the model so its largest dimension equals target_size
        - target_size: The target size in Blender units (meters) for the largest dimension
        """
        try:
            api_key = get_current_scene().blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            # Use proper authorization header for API key auth
            headers = {
                "Authorization": f"Token {api_key}"
            }

            # Request download URL using the exact endpoint from the documentation
            download_endpoint = f"https://api.sketchfab.com/v3/models/{uid}/download"

            response = http_get(
                download_endpoint,
                headers=headers,
                timeout=30  # Add timeout of 30 seconds
            )

            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}

            if response.status_code != 200:
                return {"error": f"Download request failed with status code {response.status_code}"}

            data = response.json()

            # Safety check for None data
            if data is None:
                return {"error": "Received empty response from Sketchfab API for download request"}

            # Extract download URL with safety checks
            gltf_data = data.get("gltf")
            if not gltf_data:
                return {"error": "No gltf download URL available for this model. Response: " + str(data)}

            download_url = gltf_data.get("url")
            if not download_url:
                return {"error": "No download URL available for this model. Make sure the model is downloadable and you have access."}

            # Download the model (already has timeout)
            model_response = http_get(download_url, timeout=60)  # 60 second timeout

            if model_response.status_code != 200:
                return {"error": f"Model download failed with status code {model_response.status_code}"}

            # Save to temporary file
            temp_dir = tempfile.mkdtemp()
            zip_file_path = os.path.join(temp_dir, f"{uid}.zip")

            with open(zip_file_path, "wb") as f:
                f.write(model_response.content)

            # Extract the zip file with enhanced security
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                # More secure zip slip prevention
                for file_info in zip_ref.infolist():
                    # Get the path of the file
                    file_path = file_info.filename

                    # Convert directory separators to the current OS style
                    # This handles both / and \ in zip entries
                    target_path = os.path.join(temp_dir, os.path.normpath(file_path))

                    # Get absolute paths for comparison
                    abs_temp_dir = os.path.abspath(temp_dir)
                    abs_target_path = os.path.abspath(target_path)

                    # Ensure the normalized path doesn't escape the target directory
                    if not abs_target_path.startswith(abs_temp_dir):
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                        return {"error": "Security issue: Zip contains files with path traversal attempt"}

                    # Additional explicit check for directory traversal
                    if ".." in file_path:
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                        return {"error": "Security issue: Zip contains files with directory traversal sequence"}

                # If all files passed security checks, extract them
                zip_ref.extractall(temp_dir)

            # Find the main glTF file
            gltf_files = [f for f in os.listdir(temp_dir) if f.endswith('.gltf') or f.endswith('.glb')]

            if not gltf_files:
                with suppress(Exception):
                    shutil.rmtree(temp_dir)
                return {"error": "No glTF file found in the downloaded model"}

            main_file = os.path.join(temp_dir, gltf_files[0])

            # Import the model
            bpy.ops.import_scene.gltf(filepath=main_file)

            # Get the imported objects
            imported_objects = list(get_selected_objects())
            imported_object_names = [obj.name for obj in imported_objects]

            # Clean up temporary files
            with suppress(Exception):
                shutil.rmtree(temp_dir)

            # Find root objects (objects without parents in the imported set)
            root_objects = [obj for obj in imported_objects if obj.parent is None]

            # Helper function to recursively get all mesh children
            def get_all_mesh_children(obj):
                """Recursively collect all mesh objects in the hierarchy"""
                meshes = []
                if obj.type == 'MESH':
                    meshes.append(obj)
                for child in obj.children:
                    meshes.extend(get_all_mesh_children(child))
                return meshes

            # Collect ALL meshes from the entire hierarchy (starting from roots)
            all_meshes = []
            for obj in root_objects:
                all_meshes.extend(get_all_mesh_children(obj))

            if all_meshes:
                # Calculate combined world bounding box for all meshes
                all_min = mathutils.Vector((float('inf'), float('inf'), float('inf')))
                all_max = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))

                for mesh_obj in all_meshes:
                    # Get world-space bounding box corners
                    for corner in mesh_obj.bound_box:
                        world_corner = mesh_obj.matrix_world @ mathutils.Vector(corner)
                        all_min.x = min(all_min.x, world_corner.x)
                        all_min.y = min(all_min.y, world_corner.y)
                        all_min.z = min(all_min.z, world_corner.z)
                        all_max.x = max(all_max.x, world_corner.x)
                        all_max.y = max(all_max.y, world_corner.y)
                        all_max.z = max(all_max.z, world_corner.z)

                # Calculate dimensions
                dimensions = [
                    all_max.x - all_min.x,
                    all_max.y - all_min.y,
                    all_max.z - all_min.z
                ]
                max_dimension = max(dimensions)

                # Apply normalization if requested
                scale_applied = 1.0
                if normalize_size and max_dimension > 0:
                    scale_factor = target_size / max_dimension
                    scale_applied = scale_factor

                    # 鉁?Only apply scale to ROOT objects (not children!)
                    # Child objects inherit parent's scale through matrix_world
                    for root in root_objects:
                        root.scale = (
                            root.scale.x * scale_factor,
                            root.scale.y * scale_factor,
                            root.scale.z * scale_factor
                        )

                    # Update the scene to recalculate matrix_world for all objects
                    bpy.context.view_layer.update()

                    # Recalculate bounding box after scaling
                    all_min = mathutils.Vector((float('inf'), float('inf'), float('inf')))
                    all_max = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))

                    for mesh_obj in all_meshes:
                        for corner in mesh_obj.bound_box:
                            world_corner = mesh_obj.matrix_world @ mathutils.Vector(corner)
                            all_min.x = min(all_min.x, world_corner.x)
                            all_min.y = min(all_min.y, world_corner.y)
                            all_min.z = min(all_min.z, world_corner.z)
                            all_max.x = max(all_max.x, world_corner.x)
                            all_max.y = max(all_max.y, world_corner.y)
                            all_max.z = max(all_max.z, world_corner.z)

                    dimensions = [
                        all_max.x - all_min.x,
                        all_max.y - all_min.y,
                        all_max.z - all_min.z
                    ]

                world_bounding_box = [[all_min.x, all_min.y, all_min.z], [all_max.x, all_max.y, all_max.z]]
            else:
                world_bounding_box = None
                dimensions = None
                scale_applied = 1.0

            result = {
                "success": True,
                "message": "Model imported successfully",
                "imported_objects": imported_object_names
            }

            if world_bounding_box:
                result["world_bounding_box"] = world_bounding_box
            if dimensions:
                result["dimensions"] = [round(d, 4) for d in dimensions]
            if normalize_size:
                result["scale_applied"] = round(scale_applied, 6)
                result["normalized"] = True

            return result

        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your internet connection and try again with a simpler model."}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response from Sketchfab API: {str(e)}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to download model: {str(e)}"}
    #endregion

    #region Hunyuan3D
    def get_hunyuan3d_status(self):
        """Get the current status of Hunyuan3D integration"""
        enabled = get_scene_property("blendermcp_use_hunyuan3d", False)
        hunyuan3d_mode = get_current_scene().blendermcp_hunyuan3d_mode
        if enabled:
            match hunyuan3d_mode:
                case "OFFICIAL_API":
                    if not get_current_scene().blendermcp_hunyuan3d_secret_id or not get_current_scene().blendermcp_hunyuan3d_secret_key:
                        return {
                            "enabled": False,
                            "mode": hunyuan3d_mode,
                            "message": """Hunyuan3D integration is currently enabled, but SecretId or SecretKey is not given. To enable it:
                                1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                                2. Keep the 'Use Tencent Hunyuan 3D model generation' checkbox checked
                                3. Choose the right platform and fill in the SecretId and SecretKey
                                4. Restart the connection to Claude"""
                        }
                case "LOCAL_API":
                    if not get_current_scene().blendermcp_hunyuan3d_api_url:
                        return {
                            "enabled": False,
                            "mode": hunyuan3d_mode,
                            "message": """Hunyuan3D integration is currently enabled, but API URL  is not given. To enable it:
                                1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                                2. Keep the 'Use Tencent Hunyuan 3D model generation' checkbox checked
                                3. Choose the right platform and fill in the API URL
                                4. Restart the connection to Claude"""
                        }
                case _:
                    return {
                        "enabled": False,
                        "message": "Hunyuan3D integration is enabled and mode is not supported."
                    }
            return {
                "enabled": True,
                "mode": hunyuan3d_mode,
                "message": "Hunyuan3D integration is enabled and ready to use."
            }
        return {
            "enabled": False,
            "message": """Hunyuan3D integration is currently disabled. To enable it:
                        1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                        2. Check the 'Use Tencent Hunyuan 3D model generation' checkbox
                        3. Restart the connection to Claude"""
        }

    @staticmethod
    def get_tencent_cloud_sign_headers(
        method: str,
        path: str,
        headParams: dict,
        data: dict,
        service: str,
        region: str,
        secret_id: str,
        secret_key: str,
        host: str = None
    ):
        """Generate the signature header required for Tencent Cloud API requests headers"""
        # Generate timestamp
        timestamp = int(time.time())
        from datetime import timezone
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

        # If host is not provided, it is generated based on service and region.
        if not host:
            host = f"{service}.tencentcloudapi.com"

        endpoint = f"https://{host}"

        # Constructing the request body
        payload_str = json.dumps(data)

        # ************* Step 1: Concatenate the canonical request string *************
        canonical_uri = path
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{headParams.get('Action', '').lower()}\n"
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        canonical_request = (method + "\n" +
                            canonical_uri + "\n" +
                            canonical_querystring + "\n" +
                            canonical_headers + "\n" +
                            signed_headers + "\n" +
                            hashed_request_payload)

        # ************* Step 2: Construct the reception signature string *************
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = ("TC3-HMAC-SHA256" + "\n" +
                        str(timestamp) + "\n" +
                        credential_scope + "\n" +
                        hashed_canonical_request)

        # ************* Step 3: Calculate the signature *************
        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, service)
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # ************* Step 4: Connect Authorization *************
        authorization = ("TC3-HMAC-SHA256" + " " +
                        "Credential=" + secret_id + "/" + credential_scope + ", " +
                        "SignedHeaders=" + signed_headers + ", " +
                        "Signature=" + signature)

        # Constructing request headers
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-TC-Action": headParams.get("Action", ""),
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": headParams.get("Version", ""),
            "X-TC-Region": region
        }

        return headers, endpoint

    def create_hunyuan_job(self, *args, **kwargs):
        match get_current_scene().blendermcp_hunyuan3d_mode:
            case "OFFICIAL_API":
                return self.create_hunyuan_job_main_site(*args, **kwargs)
            case "LOCAL_API":
                return self.create_hunyuan_job_local_site(*args, **kwargs)
            case _:
                return f"Error: Unknown Hunyuan3D mode!"

    def create_hunyuan_job_main_site(
        self,
        text_prompt: str = None,
        image: str = None
    ):
        try:
            secret_id = get_current_scene().blendermcp_hunyuan3d_secret_id
            secret_key = get_current_scene().blendermcp_hunyuan3d_secret_key

            if not secret_id or not secret_key:
                return {"error": "SecretId or SecretKey is not given"}

            # Parameter verification
            if not text_prompt and not image:
                return {"error": "Prompt or Image is required"}
            if text_prompt and image:
                return {"error": "Prompt and Image cannot be provided simultaneously"}
            # Fixed parameter configuration
            service = "hunyuan"
            action = "SubmitHunyuanTo3DJob"
            version = "2023-09-01"
            region = "ap-guangzhou"

            headParams={
                "Action": action,
                "Version": version,
                "Region": region,
            }

            # Constructing request parameters
            data = {
                "Num": 1  # The current API limit is only 1
            }

            # Handling text prompts
            if text_prompt:
                if len(text_prompt) > 200:
                    return {"error": "Prompt exceeds 200 characters limit"}
                data["Prompt"] = text_prompt

            # Handling image
            if image:
                if re.match(r'^https?://', image, re.IGNORECASE) is not None:
                    data["ImageUrl"] = image
                else:
                    try:
                        # Convert to Base64 format
                        with open(image, "rb") as f:
                            image_base64 = base64.b64encode(f.read()).decode("ascii")
                        data["ImageBase64"] = image_base64
                    except Exception as e:
                        return {"error": f"Image encoding failed: {str(e)}"}

            # Get signed headers
            headers, endpoint = self.get_tencent_cloud_sign_headers("POST", "/", headParams, data, service, region, secret_id, secret_key)

            response = http_post(
                endpoint,
                headers = headers,
                data = json.dumps(data)
            )

            if response.status_code == 200:
                return response.json()
            return {
                "error": f"API request failed with status {response.status_code}: {response}"
            }
        except Exception as e:
            return {"error": str(e)}

    def create_hunyuan_job_local_site(
        self,
        text_prompt: str = None,
        image: str = None):
        try:
            base_url = get_current_scene().blendermcp_hunyuan3d_api_url.rstrip('/')
            octree_resolution = get_current_scene().blendermcp_hunyuan3d_octree_resolution
            num_inference_steps = get_current_scene().blendermcp_hunyuan3d_num_inference_steps
            guidance_scale = get_current_scene().blendermcp_hunyuan3d_guidance_scale
            texture = get_current_scene().blendermcp_hunyuan3d_texture

            if not base_url:
                return {"error": "API URL is not given"}
            # Parameter verification
            if not text_prompt and not image:
                return {"error": "Prompt or Image is required"}

            # Constructing request parameters
            data = {
                "octree_resolution": octree_resolution,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "texture": texture,
            }

            # Handling text prompts
            if text_prompt:
                data["text"] = text_prompt

            # Handling image
            if image:
                if re.match(r'^https?://', image, re.IGNORECASE) is not None:
                    try:
                        resImg = http_get(image)
                        resImg.raise_for_status()
                        image_base64 = base64.b64encode(resImg.content).decode("ascii")
                        data["image"] = image_base64
                    except Exception as e:
                        return {"error": f"Failed to download or encode image: {str(e)}"}
                else:
                    try:
                        # Convert to Base64 format
                        with open(image, "rb") as f:
                            image_base64 = base64.b64encode(f.read()).decode("ascii")
                        data["image"] = image_base64
                    except Exception as e:
                        return {"error": f"Image encoding failed: {str(e)}"}

            response = http_post(
                f"{base_url}/generate",
                json = data,
            )

            if response.status_code != 200:
                return {
                    "error": f"Generation failed: {response.text}"
                }

            # Decode base64 and save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as temp_file:
                temp_file.write(response.content)
                temp_file_name = temp_file.name

            # Import the GLB file in the main thread
            def import_handler():
                bpy.ops.import_scene.gltf(filepath=temp_file_name)
                os.unlink(temp_file.name)
                return None

            bpy.app.timers.register(import_handler)

            return {
                "status": "DONE",
                "message": "Generation and Import glb succeeded"
            }
        except Exception as e:
            print(f"An error occurred: {e}")
            return {"error": str(e)}


    def poll_hunyuan_job_status(self, *args, **kwargs):
        return self.poll_hunyuan_job_status_ai(*args, **kwargs)

    def poll_hunyuan_job_status_ai(self, job_id: str):
        """Call the job status API to get the job status"""
        print(job_id)
        try:
            secret_id = get_current_scene().blendermcp_hunyuan3d_secret_id
            secret_key = get_current_scene().blendermcp_hunyuan3d_secret_key

            if not secret_id or not secret_key:
                return {"error": "SecretId or SecretKey is not given"}
            if not job_id:
                return {"error": "JobId is required"}

            service = "hunyuan"
            action = "QueryHunyuanTo3DJob"
            version = "2023-09-01"
            region = "ap-guangzhou"

            headParams={
                "Action": action,
                "Version": version,
                "Region": region,
            }

            clean_job_id = job_id.removeprefix("job_")
            data = {
                "JobId": clean_job_id
            }

            headers, endpoint = self.get_tencent_cloud_sign_headers("POST", "/", headParams, data, service, region, secret_id, secret_key)

            response = http_post(
                endpoint,
                headers=headers,
                data=json.dumps(data)
            )

            if response.status_code == 200:
                return response.json()
            return {
                "error": f"API request failed with status {response.status_code}: {response}"
            }
        except Exception as e:
            return {"error": str(e)}

    def import_generated_asset_hunyuan(self, *args, **kwargs):
        return self.import_generated_asset_hunyuan_ai(*args, **kwargs)

    def import_generated_asset_hunyuan_ai(self, name: str , zip_file_url: str):
        if not zip_file_url:
            return {"error": "Zip file not found"}

        # Validate URL
        if not re.match(r'^https?://', zip_file_url, re.IGNORECASE):
            return {"error": "Invalid URL format. Must start with http:// or https://"}

        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="tencent_obj_")
        zip_file_path = osp.join(temp_dir, "model.zip")
        obj_file_path = osp.join(temp_dir, "model.obj")
        mtl_file_path = osp.join(temp_dir, "model.mtl")

        try:
            # Download ZIP file
            zip_response = http_get(zip_file_url, stream=True)
            zip_response.raise_for_status()
            with open(zip_file_path, "wb") as f:
                for chunk in zip_response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Unzip the ZIP
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find the .obj file (there may be multiple, assuming the main file is model.obj)
            for file in os.listdir(temp_dir):
                if file.endswith(".obj"):
                    obj_file_path = osp.join(temp_dir, file)

            if not osp.exists(obj_file_path):
                return {"succeed": False, "error": "OBJ file not found after extraction"}

            # Import obj file
            if bpy.app.version>=(4, 0, 0):
                bpy.ops.wm.obj_import(filepath=obj_file_path)
            else:
                bpy.ops.wm.obj_import(filepath=obj_file_path)

            imported_objs = [obj for obj in get_selected_objects() if obj.type == 'MESH']
            if not imported_objs:
                return {"succeed": False, "error": "No mesh objects imported"}

            obj = imported_objs[0]
            if name:
                obj.name = name

            result = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                bounding_box = self._get_aabb(obj)
                result["world_bounding_box"] = bounding_box

            return {"succeed": True, **result}
        except Exception as e:
            return {"succeed": False, "error": str(e)}
        finally:
            #  Clean up temporary zip and obj, save texture and mtl
            try:
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
                if os.path.exists(obj_file_path):
                    os.remove(obj_file_path)
            except Exception as e:
                print(f"Failed to clean up temporary directory {temp_dir}: {e}")
    #endregion

    # ==================================================================
    # BlenderKit Handlers
    # ==================================================================

    def _check_blenderkit_available(self):
        """Check if BlenderKit addon is installed and enabled. Returns (ok, error_message).

        Safely checks addon availability even in background mode where
        bpy.context.preferences may not be fully accessible.
        """
        try:
            addons = bpy.context.preferences.addons
        except Exception:
            return False, "BlenderKit addon is not installed. Install from https://www.blenderkit.com/"
        if "blenderkit" not in addons:
            return False, "BlenderKit addon is not installed. Install from https://www.blenderkit.com/"
        try:
            bk_prefs = addons["blenderkit"].preferences
        except Exception:
            return False, "BlenderKit addon preferences not accessible."
        if not bk_prefs.username:
            return False, "Not logged in to BlenderKit. Please login first via BlenderKit preferences."
        return True, ""

    def blenderkit_status_handler(self):
        """Check BlenderKit plugin, client, auth, and cache status."""
        try:
            import os
            import shutil

            addons = bpy.context.preferences.addons
            plugin_installed = "blenderkit" in addons
            plugin_enabled = False
            client_connected = False
            client_version = ""
            username = ""
            api_key_configured = False
            cache_directory = ""
            cache_size_mb = 0
            plan_type = "free"
            settings = {}

            if plugin_installed:
                bk_prefs = addons["blenderkit"].preferences
                plugin_enabled = bk_prefs.get("username", "") != ""
                username = bk_prefs.get("username", "")
                api_key_configured = bool(bk_prefs.get("api_key", ""))

                # Check client connection
                try:
                    blendernet = addons["blenderkit"].modules[0].blendernet
                    if hasattr(blendernet, 'client_connected'):
                        client_connected = blendernet.client_connected
                    if hasattr(blendernet, 'client_version'):
                        client_version = blendernet.client_version
                    elif hasattr(blendernet, 'current_version'):
                        client_version = blendernet.current_version
                except Exception:
                    pass

                # Cache directory
                try:
                    USER_DATA_DIR = addons["blenderkit"].modules[0].USER_DATA_DIR
                    cache_directory = USER_DATA_DIR
                    if os.path.isdir(cache_directory):
                        total_size = 0
                        for dirpath, dirnames, filenames in os.walk(cache_directory):
                            for f in filenames:
                                fp = os.path.join(dirpath, f)
                                if os.path.isfile(fp):
                                    try:
                                        total_size += os.path.getsize(fp)
                                    except OSError:
                                        pass
                        cache_size_mb = round(total_size / (1024 * 1024), 1)
                except Exception:
                    cache_directory = "Unknown"

                # Settings
                settings = {
                    "thread_count": getattr(bk_prefs, "thread_count", 1),
                    "auto_update": getattr(bk_prefs, "auto_update_models", True),
                    "show_splash": getattr(bk_prefs, "show_splash", False),
                    "refresh_time": getattr(bk_prefs, "refresh_time", 1),
                }

            return {
                "plugin_installed": plugin_installed,
                "plugin_enabled": plugin_enabled,
                "client_connected": client_connected,
                "client_version": client_version,
                "user_logged_in": bool(username),
                "username": username,
                "api_key_configured": api_key_configured,
                "cache_directory": cache_directory,
                "cache_size_mb": cache_size_mb,
                "plan_type": plan_type,
                "settings": settings,
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "plugin_installed": False,
                "error": f"BlenderKit status check failed: {str(e)}",
            }

    def blenderkit_search_handler(self, query, asset_type="model", category="all", limit=10, only_free=True, free_only=None):
        if free_only is not None:
            only_free = free_only
        """Search BlenderKit assets and return results as JSON."""
        try:
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {"error": err, "results": [], "total": 0}

            import blenderkit
            import blenderkit.search

            results = []
            try:
                search_results = blenderkit.search.search(
                    search_term=query,
                    asset_type=asset_type,
                    category=category,
                    only_free=only_free,
                    download=False,
                )
            except Exception as search_err:
                return {"error": f"Search failed: {str(search_err)}", "results": [], "total": 0}

            if not search_results:
                return {"results": [], "total": 0, "query": query, "note": "No results. Try synonyms or different categories."}

            count = 0
            for asset in search_results:
                if count >= limit:
                    break
                try:
                    results.append({
                        "id": getattr(asset, 'id', str(getattr(asset, 'index_id', ''))),
                        "name": getattr(asset, 'name', 'Unnamed'),
                        "author": getattr(asset, 'author_name', 'Unknown'),
                        "asset_type": getattr(asset, 'asset_type', asset_type),
                        "is_free": getattr(asset, 'is_free', True),
                        "plan_type": "free" if getattr(asset, 'is_free', True) else "full",
                        "license": "Standard License",
                        "url": f"https://www.blenderkit.com/share/{getattr(asset, 'id', '')}/",
                        "thumbnail_url": getattr(asset, 'thumbnail_url', ''),
                        "tags": getattr(asset, 'tags', []),
                        "rating_average": getattr(asset, 'rating_average', 0),
                        "downloads": getattr(asset, 'downloads', 0),
                    })
                    count += 1
                except Exception:
                    continue

            return {
                "results": results,
                "total": count,
                "query": query,
                "asset_type": asset_type,
                "only_free": only_free,
            }
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Search error: {str(e)}", "results": [], "total": 0}

    def blenderkit_download_handler(self, asset_id="", asset_type="model"):
        """Download a BlenderKit asset to local cache."""
        try:
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {"success": False, "error": err}

            import blenderkit.downloader
            import blenderkit.uploader

            try:
                asset = blenderkit.uploader.download_asset(
                    asset_id=asset_id,
                    asset_type=asset_type,
                )
                if not asset:
                    return {"success": False, "error": "Download failed or asset not found"}
                return {
                    "success": True,
                    "asset_id": asset_id,
                    "asset_name": getattr(asset, 'name', 'Unknown'),
                    "asset_type": asset_type,
                    "plan_type": "free",
                }
            except Exception as dl_err:
                return {"success": False, "error": f"Download failed: {str(dl_err)}"}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": f"Download handler error: {str(e)}"}

    def blenderkit_append_handler(self, asset_id="", asset_type="model", location=None, rotation=None, scale=None):
        """Download and append a BlenderKit asset into the current scene."""
        try:
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {"success": False, "error": err}

            import blenderkit.uploader

            # Download first if not in cache
            try:
                asset = blenderkit.uploader.download_asset(asset_id=asset_id, asset_type=asset_type)
                if not asset:
                    return {"success": False, "error": "Download failed or asset not found"}
            except Exception as dl_err:
                return {"success": False, "error": f"Download failed: {str(dl_err)}"}

            # Append to scene
            try:
                import blenderkit
                blenderkit.append.append(
                    asset_id=asset_id,
                    asset_type=asset_type,
                    location=tuple(location) if location else (0, 0, 0),
                    rotation=tuple(rotation) if rotation else (0, 0, 0),
                    scale=tuple(scale) if scale else (1, 1, 1),
                )

                # Find newly added objects
                imported = [obj.name for obj in get_selected_objects()]

                return {
                    "success": True,
                    "imported_objects": imported,
                    "asset_id": asset_id,
                    "asset_name": getattr(asset, 'name', 'Unknown'),
                    "location": list(location) if location else [0, 0, 0],
                    "rotation": list(rotation) if rotation else [0, 0, 0],
                    "scale": list(scale) if scale else [1, 1, 1],
                    "copyright_info": {
                        "author": getattr(asset, 'author_name', 'Unknown'),
                        "license": "Standard License",
                        "is_free": True,
                        "url": f"https://www.blenderkit.com/share/{asset_id}/",
                    },
                }
            except Exception as append_err:
                return {"success": False, "error": f"Append failed: {str(append_err)}"}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": f"Append handler error: {str(e)}"}

    def blenderkit_apply_material_handler(self, asset_id="", target_object=""):
        """Apply a BlenderKit material to a target object."""
        try:
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {"success": False, "error": err}

            import blenderkit.uploader
            import blenderkit.materials

            try:
                asset = blenderkit.uploader.download_asset(asset_id=asset_id, asset_type="material")
                if not asset:
                    return {"success": False, "error": "Material download failed"}
            except Exception as dl_err:
                return {"success": False, "error": f"Download failed: {str(dl_err)}"}

            try:
                blenderkit.materials.assign_material(
                    obj=bpy.data.objects.get(target_object),
                    material_id=asset_id,
                    replace=True,
                )
                return {
                    "success": True,
                    "material_id": asset_id,
                    "target_object": target_object,
                }
            except Exception as apply_err:
                return {"success": False, "error": f"Apply failed: {str(apply_err)}"}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": f"Apply handler error: {str(e)}"}

    def blenderkit_set_hdri_handler(self, asset_id="", brightness=1.0, contrast=1.0):
        """Set a BlenderKit HDRI as the world environment."""
        try:
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {"success": False, "error": err}

            import blenderkit.uploader
            import blenderkit.hdris

            try:
                asset = blenderkit.uploader.download_asset(asset_id=asset_id, asset_type="hdris")
                if not asset:
                    return {"success": False, "error": "HDRI download failed"}
            except Exception as dl_err:
                return {"success": False, "error": f"Download failed: {str(dl_err)}"}

            try:
                blenderkit.hdris.set_hdri(
                    asset_id=asset_id,
                    brightness=brightness,
                    contrast=contrast,
                )
                return {
                    "success": True,
                    "hdri_id": asset_id,
                    "hdri_name": getattr(asset, 'name', 'Unknown'),
                    "brightness": brightness,
                    "contrast": contrast,
                }
            except Exception as hdri_err:
                return {"success": False, "error": f"Set HDRI failed: {str(hdri_err)}"}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": f"Set HDRI handler error: {str(e)}"}

    def blenderkit_list_cached_handler(self):
        """List locally cached BlenderKit assets."""
        try:
            # Check if BlenderKit is available first
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {
                    "status": "success",
                    "result": {
                        "success": False,
                        "error": err,
                        "assets": [],
                        "total": 0,
                        "cache_directory": "",
                    }
                }

            cache_dirs = ["model", "material", "hdris", "scene", "brush", "printable", "addon"]
            all_cached = []

            try:
                USER_DATA_DIR = None
                import blenderkit
                USER_DATA_DIR = getattr(blenderkit, 'USER_DATA_DIR', None)
                if not USER_DATA_DIR:
                    # Fallback: try to get from addon preferences
                    for addon_name, addon in bpy.context.preferences.addons.items():
                        if addon_name == "blenderkit" and hasattr(addon, 'preferences'):
                            USER_DATA_DIR = addon.preferences.data_dir
                            break
            except Exception:
                pass

            if not USER_DATA_DIR:
                return {
                    "status": "success",
                    "result": {
                        "success": True,
                        "assets": [],
                        "total": 0,
                        "cache_directory": "",
                    }
                }

            import os
            for ctype in cache_dirs:
                cpath = os.path.join(USER_DATA_DIR, "downloads", ctype)
                if not os.path.isdir(cpath):
                    continue
                for aid in os.listdir(cpath):
                    aid_path = os.path.join(cpath, aid)
                    if not os.path.isdir(aid_path):
                        continue
                    try:
                        size_mb = 0
                        for dp, dn, fn in os.walk(aid_path):
                            for f in fn:
                                fp = os.path.join(dp, f)
                                if os.path.isfile(fp):
                                    size_mb += os.path.getsize(fp)
                        size_mb = round(size_mb / (1024 * 1024), 1)
                        all_cached.append({
                            "id": aid,
                            "asset_type": ctype,
                            "file_path": aid_path,
                            "size_mb": size_mb,
                            "is_free": True,
                        })
                    except Exception:
                        continue

            return {
                "status": "success",
                "result": {
                    "success": True,
                    "assets": all_cached,
                    "total": len(all_cached),
                    "cache_directory": USER_DATA_DIR,
                }
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "status": "success",
                "result": {
                    "success": False,
                    "error": str(e),
                    "assets": [],
                    "total": 0,
                    "cache_directory": "",
                }
            }

    def blenderkit_reuse_cached_handler(self, asset_id="", asset_type="model", location=None, rotation=None, scale=None):
        """Reuse a cached asset by appending without re-downloading."""
        try:
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {"success": False, "error": err}

            import blenderkit

            try:
                blenderkit.append.append(
                    asset_id=asset_id,
                    asset_type=asset_type,
                    location=tuple(location) if location else (0, 0, 0),
                    rotation=tuple(rotation) if rotation else (0, 0, 0),
                    scale=tuple(scale) if scale else (1, 1, 1),
                )

                imported = [obj.name for obj in get_selected_objects()]

                return {
                    "success": True,
                    "reused": True,
                    "from_cache": True,
                    "imported_objects": imported,
                    "asset_id": asset_id,
                    "asset_type": asset_type,
                }
            except Exception as append_err:
                return {"success": False, "error": f"Append failed: {str(append_err)}"}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": f"Reuse handler error: {str(e)}"}

    def blenderkit_auto_scene_handler(self, prompt, only_free=True, free_only=None):
        if free_only is not None:
            only_free = free_only
        """Auto-generate a scene by searching, downloading, and placing multiple BlenderKit assets."""
        try:
            ok, err = self._check_blenderkit_available()
            if not ok:
                return {"success": False, "error": err}

            import blenderkit.search
            import blenderkit.uploader
            import blenderkit.append

            # Parse prompt into asset intents (simple keyword extraction)
            keywords = self._extract_scene_keywords(prompt)
            if not keywords:
                return {"success": False, "error": "Could not parse scene description. Provide more specific keywords."}

            assets_used = []
            objects_created = []
            copyright_table = []
            fallbacks = []
            errors = []

            # Layout positions for placing objects
            angle_step = 2 * 3.14159 / max(len(keywords), 1)

            for i, kw in enumerate(keywords):
                # Search for this asset
                try:
                    results = blenderkit.search.search(
                        search_term=kw,
                        asset_type="model",
                        category="all",
                        only_free=only_free,
                        download=False,
                    )
                except Exception:
                    fallbacks.append(f"Search failed for '{kw}'")
                    continue

                if not results:
                    fallbacks.append(f"No results for '{kw}', falling back to primitive")
                    fallbacks.append(f"  -> Use create_cube/create_sphere as fallback")
                    continue

                # Use first free result
                asset = results[0]
                aid = getattr(asset, 'id', None)
                if not aid:
                    continue

                asset_name = getattr(asset, 'name', kw)
                author = getattr(asset, 'author_name', 'Unknown')

                # Download
                try:
                    downloaded = blenderkit.uploader.download_asset(asset_id=aid, asset_type="model")
                    if not downloaded:
                        errors.append(f"Download failed for '{asset_name}'")
                        continue
                except Exception as dl_err:
                    errors.append(f"Download error for '{asset_name}': {str(dl_err)}")
                    continue

                # Append to scene with positioned placement
                try:
                    import math
                    radius = 3.0
                    x = radius * math.cos(angle_step * i)
                    y = radius * math.sin(angle_step * i)
                    blenderkit.append.append(
                        asset_id=aid,
                        asset_type="model",
                        location=(x, y, 0),
                        rotation=(0, 0, 0),
                        scale=(1, 1, 1),
                    )
                    imported = [obj.name for obj in get_selected_objects()]
                    objects_created.extend(imported)
                    assets_used.append({
                        "id": aid,
                        "name": asset_name,
                        "type": "model",
                        "author": author,
                        "position": [round(x, 2), round(y, 2), 0],
                    })
                    copyright_table.append(
                        f"{asset_name} | {aid} | model | free | Standard License | https://www.blenderkit.com/share/{aid}/"
                    )
                except Exception as append_err:
                    errors.append(f"Append failed for '{asset_name}': {str(append_err)}")

            # Build response
            result = {
                "success": len(objects_created) > 0,
                "prompt": prompt,
                "keywords_parsed": keywords,
                "assets_used": assets_used,
                "objects_created": objects_created,
                "fallbacks_applied": fallbacks,
                "errors": errors,
                "copyright_table": "\n".join(copyright_table) if copyright_table else "No assets used.",
            }
            return result
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": f"Auto scene handler error: {str(e)}"}

    def _extract_scene_keywords(self, prompt):
        """Extract asset keywords from a scene description prompt."""
        # Simple heuristic: split by common delimiters and filter
        import re
        # Remove common non-asset words
        stop_words = {
            "the", "a", "an", "and", "or", "with", "for", "of", "in", "on",
            "at", "to", "by", "has", "have", "had", "is", "are", "was", "were",
            "be", "been", "being", "there", "this", "that", "these", "those",
            "generate", "create", "make", "build", "design", "scene", "room",
            "lab", "laboratory", "office", "room", "environment", "background",
            "setup", "layout", "arrange",
            "布置", "生成", "创建", "一个", "场景", "和", "以及", "的", "有", "包含", "什么",
        }
        # Lowercase and remove non-alpha/numeric
        clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff ]+', ' ', prompt.lower())
        tokens = [t.strip() for t in clean.split() if t.strip() and len(t.strip()) > 1]
        # Filter stop words and keep meaningful tokens (2+ words as phrases)
        meaningful = []
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t not in stop_words:
                meaningful.append(t)
            i += 1
        return meaningful if meaningful else [prompt.strip()]

    def blenderkit_login_handler(self):
        """Trigger BlenderKit login via operator."""
        try:
            import bpy
            try:
                bpy.ops.blenderkit.login()
                return {"success": True, "message": "Login dialog opened. Please authenticate in Blender."}
            except Exception as e:
                return {"success": False, "error": f"Login operator failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Login handler error: {str(e)}"}

    # Camera Alignment Handlers
    # ==================================================================

    def camera_align_to_selected(self, camera_name=None):
        """Align the active (or specified) camera to the center of selected objects."""
        try:
            scene = get_current_scene()
            selected_objects = get_selected_objects()
            selected = [obj for obj in selected_objects if obj.type == 'MESH']
            if not selected:
                return {"success": False, "error": "No mesh objects selected"}

            # Compute bounding box center of selected objects
            center = mathutils.Vector((0, 0, 0))
            for obj in selected:
                center += obj.location
            center /= len(selected)

            # Find camera
            if camera_name:
                camera = bpy.data.objects.get(camera_name)
                if not camera:
                    return {"success": False, "error": f"Camera '{camera_name}' not found"}
                if camera.type != 'CAMERA':
                    return {"success": False, "error": f"'{camera_name}' is not a camera"}
            else:
                camera = scene.camera
                if not camera:
                    camera = bpy.data.objects.get("Camera")
                if not camera or camera.type != 'CAMERA':
                    return {"success": False, "error": "No active camera found"}

            # Compute direction and set camera rotation directly
            direction = center - camera.location
            rot_euler = direction.to_track_quat('Z', 'Y').to_euler()
            camera.rotation_euler = rot_euler

            return {
                "success": True,
                "camera": camera.name,
                "target_center": [round(c, 3) for c in center],
                "camera_location": [round(c, 3) for c in camera.location],
                "selected_count": len(selected),
            }
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def camera_align_to_object(self, target_object_name, camera_name=None):
        """Align the active (or specified) camera to a specific object."""
        try:
            scene = get_current_scene()
            target = bpy.data.objects.get(target_object_name)
            if not target:
                return {"success": False, "error": f"Object '{target_object_name}' not found"}

            # Find camera
            if camera_name:
                camera = bpy.data.objects.get(camera_name)
                if not camera:
                    return {"success": False, "error": f"Camera '{camera_name}' not found"}
                if camera.type != 'CAMERA':
                    return {"success": False, "error": f"'{camera_name}' is not a camera"}
            else:
                camera = scene.camera
                if not camera:
                    camera = bpy.data.objects.get("Camera")
                if not camera or camera.type != 'CAMERA':
                    return {"success": False, "error": "No active camera found"}

            # Compute direction and set camera rotation directly
            direction = target.location - camera.location
            rot_euler = direction.to_track_quat('Z', 'Y').to_euler()
            camera.rotation_euler = rot_euler

            return {
                "success": True,
                "camera": camera.name,
                "target_object": target_object_name,
                "target_location": [round(c, 3) for c in target.location],
                "camera_location": [round(c, 3) for c in camera.location],
            }
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    #endregion
class BLENDERMCP_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    telemetry_consent: BoolProperty(
        name="Allow Telemetry",
        description="Allow collection of prompts, code snippets, and screenshots to help improve Blender MCP",
        default=True
    )

    def draw(self, context):
        layout = self.layout

        # Telemetry section
        layout.label(text="Telemetry & Privacy:", icon='PREFERENCES')

        box = layout.box()
        row = box.row()
        row.prop(self, "telemetry_consent", text="Allow Telemetry")

        # Info text
        box.separator()
        if self.telemetry_consent:
            box.label(text="With consent: We collect anonymized prompts, code, and screenshots.", icon='INFO')
        else:
            box.label(text="Without consent: We only collect minimal anonymous usage data", icon='INFO')
            box.label(text="(tool names, success/failure, duration - no prompts or code).", icon='BLANK1')
        box.separator()
        box.label(text="All data is fully anonymized. You can change this anytime.", icon='CHECKMARK')

        # Terms and Conditions link
        box.separator()
        row = box.row()
        row.operator("blendermcp.open_terms", text="View Terms and Conditions", icon='TEXT')

# Blender UI Panel
class BLENDERMCP_PT_Panel(bpy.types.Panel):
    bl_label = "Blender MCP"
    bl_idname = "BLENDERMCP_PT_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BlenderMCP'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "blendermcp_port")
        layout.prop(scene, "blendermcp_use_polyhaven", text="Use assets from Poly Haven")

        layout.prop(scene, "blendermcp_use_hyper3d", text="Use Hyper3D Rodin 3D model generation")
        if scene.blendermcp_use_hyper3d:
            layout.prop(scene, "blendermcp_hyper3d_mode", text="Rodin Mode")
            layout.prop(scene, "blendermcp_hyper3d_api_key", text="API Key")
            layout.operator("blendermcp.set_hyper3d_free_trial_api_key", text="Set Free Trial API Key")

        layout.prop(scene, "blendermcp_use_sketchfab", text="Use assets from Sketchfab")
        if scene.blendermcp_use_sketchfab:
            layout.prop(scene, "blendermcp_sketchfab_api_key", text="API Key")

        layout.prop(scene, "blendermcp_use_hunyuan3d", text="Use Tencent Hunyuan 3D model generation")
        if scene.blendermcp_use_hunyuan3d:
            layout.prop(scene, "blendermcp_hunyuan3d_mode", text="Hunyuan3D Mode")
            if scene.blendermcp_hunyuan3d_mode == 'OFFICIAL_API':
                layout.prop(scene, "blendermcp_hunyuan3d_secret_id", text="SecretId")
                layout.prop(scene, "blendermcp_hunyuan3d_secret_key", text="SecretKey")
            if scene.blendermcp_hunyuan3d_mode == 'LOCAL_API':
                layout.prop(scene, "blendermcp_hunyuan3d_api_url", text="API URL")
                layout.prop(scene, "blendermcp_hunyuan3d_octree_resolution", text="Octree Resolution")
                layout.prop(scene, "blendermcp_hunyuan3d_num_inference_steps", text="Number of Inference Steps")
                layout.prop(scene, "blendermcp_hunyuan3d_guidance_scale", text="Guidance Scale")
                layout.prop(scene, "blendermcp_hunyuan3d_texture", text="Generate Texture")

        layout.prop(scene, "blendermcp_use_blenderkit", text="Use assets from BlenderKit")
        if scene.blendermcp_use_blenderkit:
            layout.operator("blendermcp.blenderkit_login", text="BlenderKit Login")
            layout.label(text="BlenderKit status checked via MCP tools")

        if not scene.blendermcp_server_running:
            layout.operator("blendermcp.start_server", text="Connect to MCP server")
        else:
            layout.operator("blendermcp.stop_server", text="Disconnect from MCP server")
            layout.label(text=f"Running on port {scene.blendermcp_port}")

# Operator to set Hyper3D API Key
class BLENDERMCP_OT_SetFreeTrialHyper3DAPIKey(bpy.types.Operator):
    bl_idname = "blendermcp.set_hyper3d_free_trial_api_key"
    bl_label = "Set Free Trial API Key"

    def execute(self, context):
        if not RODIN_FREE_TRIAL_KEY:
            self.report({'WARNING'}, "Set BLENDER_MCP_HYPER3D_FREE_TRIAL_KEY before using the trial key shortcut.")
            return {'CANCELLED'}
        context.scene.blendermcp_hyper3d_api_key = RODIN_FREE_TRIAL_KEY
        context.scene.blendermcp_hyper3d_mode = 'MAIN_SITE'
        self.report({'INFO'}, "API Key set successfully!")
        return {'FINISHED'}

# Operator to start the server
class BLENDERMCP_OT_StartServer(bpy.types.Operator):
    bl_idname = "blendermcp.start_server"
    bl_label = "Connect to Claude"
    bl_description = "Start the BlenderMCP server to connect with Claude"

    def execute(self, context):
        scene = context.scene

        # Create a new server instance
        if not hasattr(bpy.types, "blendermcp_server") or not bpy.types.blendermcp_server:
            bpy.types.blendermcp_server = BlenderMCPServer(port=scene.blendermcp_port)

        # Start the server
        bpy.types.blendermcp_server.start()
        scene.blendermcp_server_running = True

        return {'FINISHED'}

# Operator to stop the server
class BLENDERMCP_OT_StopServer(bpy.types.Operator):
    bl_idname = "blendermcp.stop_server"
    bl_label = "Stop the connection to Claude"
    bl_description = "Stop the connection to Claude"

    def execute(self, context):
        scene = context.scene

        # Stop the server if it exists
        if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
            bpy.types.blendermcp_server.stop()
            del bpy.types.blendermcp_server

        scene.blendermcp_server_running = False

        return {'FINISHED'}

# Operator to open Terms and Conditions
class BLENDERMCP_OT_OpenTerms(bpy.types.Operator):
    bl_idname = "blendermcp.open_terms"
    bl_label = "View Terms and Conditions"
    bl_description = "Open the Terms and Conditions document"

    def execute(self, context):
        # Open the Terms and Conditions on GitHub
        terms_url = "https://github.com/ahujasid/blender-mcp/blob/main/TERMS_AND_CONDITIONS.md"
        try:
            import webbrowser
            webbrowser.open(terms_url)
            self.report({'INFO'}, "Terms and Conditions opened in browser")
        except Exception as e:
            self.report({'ERROR'}, f"Could not open Terms and Conditions: {str(e)}")

        return {'FINISHED'}

# Operator to trigger BlenderKit login
class BLENDERMCP_OT_BlenderKitLogin(bpy.types.Operator):
    bl_idname = "blendermcp.blenderkit_login"
    bl_label = "BlenderKit Login"
    bl_description = "Open BlenderKit login dialog in Blender"

    def execute(self, context):
        try:
            import bpy
            bpy.ops.blenderkit.login()
            self.report({'INFO'}, "BlenderKit login dialog opened.")
        except Exception as e:
            self.report({'ERROR'}, f"BlenderKit login failed: {str(e)}")
        return {'FINISHED'}

# Registration functions
def register():
    bpy.types.Scene.blendermcp_port = IntProperty(
        name="Port",
        description="Port for the BlenderMCP server",
        default=9876,
        min=1024,
        max=65535
    )

    bpy.types.Scene.blendermcp_server_running = bpy.props.BoolProperty(
        name="Server Running",
        default=False
    )

    bpy.types.Scene.blendermcp_use_polyhaven = bpy.props.BoolProperty(
        name="Use Poly Haven",
        description="Enable Poly Haven asset integration",
        default=False
    )

    bpy.types.Scene.blendermcp_use_hyper3d = bpy.props.BoolProperty(
        name="Use Hyper3D Rodin",
        description="Enable Hyper3D Rodin generatino integration",
        default=False
    )

    bpy.types.Scene.blendermcp_hyper3d_mode = bpy.props.EnumProperty(
        name="Rodin Mode",
        description="Choose the platform used to call Rodin APIs",
        items=[
            ("MAIN_SITE", "hyper3d.ai", "hyper3d.ai"),
            ("FAL_AI", "fal.ai", "fal.ai"),
        ],
        default="MAIN_SITE"
    )

    bpy.types.Scene.blendermcp_hyper3d_api_key = bpy.props.StringProperty(
        name="Hyper3D API Key",
        subtype="PASSWORD",
        description="API Key provided by Hyper3D",
        default=""
    )

    bpy.types.Scene.blendermcp_use_hunyuan3d = bpy.props.BoolProperty(
        name="Use Hunyuan 3D",
        description="Enable Hunyuan asset integration",
        default=False
    )

    bpy.types.Scene.blendermcp_hunyuan3d_mode = bpy.props.EnumProperty(
        name="Hunyuan3D Mode",
        description="Choose a local or official APIs",
        items=[
            ("LOCAL_API", "local api", "local api"),
            ("OFFICIAL_API", "official api", "official api"),
        ],
        default="LOCAL_API"
    )

    bpy.types.Scene.blendermcp_hunyuan3d_secret_id = bpy.props.StringProperty(
        name="Hunyuan 3D SecretId",
        description="SecretId provided by Hunyuan 3D",
        default=""
    )

    bpy.types.Scene.blendermcp_hunyuan3d_secret_key = bpy.props.StringProperty(
        name="Hunyuan 3D SecretKey",
        subtype="PASSWORD",
        description="SecretKey provided by Hunyuan 3D",
        default=""
    )

    bpy.types.Scene.blendermcp_hunyuan3d_api_url = bpy.props.StringProperty(
        name="API URL",
        description="URL of the Hunyuan 3D API service",
        default="http://localhost:8081"
    )

    bpy.types.Scene.blendermcp_hunyuan3d_octree_resolution = bpy.props.IntProperty(
        name="Octree Resolution",
        description="Octree resolution for the 3D generation",
        default=256,
        min=128,
        max=512,
    )

    bpy.types.Scene.blendermcp_hunyuan3d_num_inference_steps = bpy.props.IntProperty(
        name="Number of Inference Steps",
        description="Number of inference steps for the 3D generation",
        default=20,
        min=20,
        max=50,
    )

    bpy.types.Scene.blendermcp_hunyuan3d_guidance_scale = bpy.props.FloatProperty(
        name="Guidance Scale",
        description="Guidance scale for the 3D generation",
        default=5.5,
        min=1.0,
        max=10.0,
    )

    bpy.types.Scene.blendermcp_hunyuan3d_texture = bpy.props.BoolProperty(
        name="Generate Texture",
        description="Whether to generate texture for the 3D model",
        default=False,
    )

    bpy.types.Scene.blendermcp_use_sketchfab = bpy.props.BoolProperty(
        name="Use Sketchfab",
        description="Enable Sketchfab asset integration",
        default=False
    )

    bpy.types.Scene.blendermcp_sketchfab_api_key = bpy.props.StringProperty(
        name="Sketchfab API Key",
        subtype="PASSWORD",
        description="API Key provided by Sketchfab",
        default=""
    )

    bpy.types.Scene.blendermcp_use_blenderkit = bpy.props.BoolProperty(
        name="Use BlenderKit",
        description="Enable BlenderKit asset integration",
        default=False
    )

    # Register preferences class
    bpy.utils.register_class(BLENDERMCP_AddonPreferences)

    bpy.utils.register_class(BLENDERMCP_PT_Panel)
    bpy.utils.register_class(BLENDERMCP_OT_SetFreeTrialHyper3DAPIKey)
    bpy.utils.register_class(BLENDERMCP_OT_StartServer)
    bpy.utils.register_class(BLENDERMCP_OT_StopServer)
    bpy.utils.register_class(BLENDERMCP_OT_OpenTerms)
    bpy.utils.register_class(BLENDERMCP_OT_BlenderKitLogin)

    print("BlenderMCP addon registered")

    # 鈹€鈹€鈹€ NO server auto-start in register() 鈹€鈹€鈹€
    # In both UI and background modes, bpy.context may be _RestrictContext
    # during addon registration, making bpy.context.scene / bpy.context.collection
    # etc. crash with AttributeError.  The server must only start after the user
    # clicks "Connect" (BLENDERMCP_OT_StartServer.execute), at which point the
    # full Blender context is available.
    #
    # Background-mode users should use boot_server.py (which waits for Blender
    # to fully initialise before loading this addon).

def unregister():
    if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
        bpy.types.blendermcp_server.stop()
        del bpy.types.blendermcp_server

    bpy.utils.unregister_class(BLENDERMCP_PT_Panel)
    bpy.utils.unregister_class(BLENDERMCP_OT_SetFreeTrialHyper3DAPIKey)
    bpy.utils.unregister_class(BLENDERMCP_OT_StartServer)
    bpy.utils.unregister_class(BLENDERMCP_OT_StopServer)
    bpy.utils.unregister_class(BLENDERMCP_OT_OpenTerms)
    bpy.utils.unregister_class(BLENDERMCP_AddonPreferences)

    for prop in [
        "blendermcp_port", "blendermcp_server_running",
        "blendermcp_use_polyhaven", "blendermcp_use_blenderkit", "blendermcp_use_hyper3d",
        "blendermcp_hyper3d_mode", "blendermcp_hyper3d_api_key",
        "blendermcp_use_sketchfab", "blendermcp_sketchfab_api_key",
        "blendermcp_use_hunyuan3d", "blendermcp_hunyuan3d_mode",
        "blendermcp_hunyuan3d_secret_id", "blendermcp_hunyuan3d_secret_key",
        "blendermcp_hunyuan3d_api_url", "blendermcp_hunyuan3d_octree_resolution",
        "blendermcp_hunyuan3d_num_inference_steps", "blendermcp_hunyuan3d_guidance_scale",
        "blendermcp_texture",
    ]:
        try:
            delattr(bpy.types.Scene, prop)
        except AttributeError:
            pass
