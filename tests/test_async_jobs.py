import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    ("function_name", "kwargs", "command"),
    [
        ("submit_async_job", {
            "kind": "render", "params": {"output_path": "x.png"},
            "priority": 20, "max_retries": 2, "retry_delay": 0.5,
            "depends_on": ["parent-job"], "resource": "gpu",
        }, "async_job_submit"),
        ("get_async_job", {"job_id": "job-1"}, "async_job_status"),
        ("list_async_jobs", {}, "async_job_list"),
        ("cancel_async_job", {"job_id": "job-1"}, "async_job_cancel"),
        ("pause_async_job", {"job_id": "job-1"}, "async_job_pause"),
        ("resume_async_job", {"job_id": "job-1"}, "async_job_resume"),
        ("get_async_job_graph", {}, "async_job_graph"),
        ("subscribe_async_job_events", {"after": 12}, "async_job_events"),
        ("get_async_job_resources", {}, "async_job_resources"),
        ("cleanup_async_jobs", {}, "async_job_cleanup"),
    ],
)
def test_async_mcp_tools_forward_structured_commands(function_name, kwargs, command):
    import blender_mcp.server as server

    connection = MagicMock()
    connection.send_command.return_value = {
        "status": "success", "ok": True, "command": command,
        "result": {"job_id": "job-1", "status": "queued"},
        "warnings": [], "error": None, "meta": {},
    }
    with patch("blender_mcp.server.get_blender_connection", return_value=connection):
        payload = json.loads(getattr(server, function_name)(None, **kwargs))
    assert payload["ok"] is True
    assert payload["command"] == command
    assert connection.send_command.call_args.args[0] == command
    assert connection.send_command.call_args.kwargs["return_envelope"] is True


def test_addon_job_manager_uses_subprocess_for_blender_work():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    assert "class AsyncJobManager:" in source
    assert 'subprocess.Popen([bpy.app.binary_path, "--background", snapshot' in source
    assert 'if job["kind"] == "download": self._download(job)' in source
    assert 'MCP_PROGRESS' in source
    assert "target=self._worker_loop" in source
    assert "threading.Semaphore(MAX_ASYNC_WORKERS)" not in source
    assert "Async job queue reached" in source
    assert source.count("p, m = json.dumps(params), manifest") == 2
    assert 'job.update(status="cancelled", message="Cancelled before start"' in source
    assert "Recovered after Blender restart" in source
    assert "Retrying in {delay:.1f}s" in source
    assert "_persist_locked" in source
    assert "persist=False, progress=" in source
    assert '"status": "blocked" if depends_on else "queued"' in source
    assert 'self.active_resources = {"cpu": 0, "gpu": 0}' in source
    assert 'def pause(self, job_id):' in source
    assert 'def resume(self, job_id):' in source
    assert 'def get_events(self, after=0' in source
    assert '"cursor_expired": after < oldest_cursor - 1' in source


def test_async_limits_are_exposed_in_capabilities():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    assert '"max_async_jobs": MAX_ASYNC_JOBS' in source
    assert '"max_async_workers": MAX_ASYNC_WORKERS' in source
    assert '"max_async_retries": MAX_ASYNC_RETRIES' in source
    assert '"async_job_recovery": True' in source


def test_async_job_commands_are_registered():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    for command in (
        "async_job_submit", "async_job_status", "async_job_list",
        "async_job_cancel", "async_job_pause", "async_job_resume",
        "async_job_graph", "async_job_events", "async_job_resources",
        "async_job_cleanup",
    ):
        assert f'"{command}": self._' in source


def test_async_domain_status_does_not_fail_transport_envelope():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    assert 'if cmd_type.startswith("async_job_"):' in source
    assert "inner_status = None" in source


def test_job_snapshots_are_created_on_blender_main_thread():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    submit = source[source.index("def _async_job_submit("):source.index("def _async_job_status(")]
    assert "bpy.ops.wm.save_as_mainfile" in submit
    assert "copy=True" in submit
