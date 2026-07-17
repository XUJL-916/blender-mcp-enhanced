import json
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from blender_mcp.server import (
    BlenderCommandError,
    BlenderConnection,
    BlenderProtocolError,
    _redact_sensitive,
)


def test_sensitive_values_are_recursively_redacted():
    params = {
        "api_key": "secret-a",
        "nested": {"SecretId": "secret-b", "ordinary": "visible"},
        "items": [{"authorization": "Bearer hidden"}],
    }
    redacted = _redact_sensitive(params)
    assert redacted["api_key"] == "<redacted>"
    assert redacted["nested"]["SecretId"] == "<redacted>"
    assert redacted["nested"]["ordinary"] == "visible"
    assert redacted["items"][0]["authorization"] == "<redacted>"


def test_request_size_limit_fails_before_socket_write():
    connection = BlenderConnection("localhost", 9876, max_request_bytes=32)
    connection.sock = MagicMock()
    with pytest.raises(BlenderProtocolError, match="request bytes"):
        connection.send_command("execute_code", {"code": "x" * 100})
    connection.sock.sendall.assert_not_called()


def test_response_size_limit_stops_chunk_accumulation():
    connection = BlenderConnection("localhost", 9876, max_response_bytes=4)
    sock = MagicMock()
    sock.recv.return_value = b"12345"
    with pytest.raises(BlenderProtocolError, match="response exceeded"):
        connection.receive_full_response(sock)


def test_structured_addon_error_becomes_typed_exception():
    connection = BlenderConnection("localhost", 9876)
    connection.sock = MagicMock()
    response = {
        "status": "error", "ok": False, "command": "mesh_edit", "result": None,
        "error": {"code": "INVALID_INDEX", "type": "IndexError",
                  "message": "Face index 99 is invalid", "retriable": False},
        "meta": {"duration_ms": 1.25},
    }
    with patch.object(connection, "receive_full_response", return_value=json.dumps(response).encode()):
        with pytest.raises(BlenderCommandError) as raised:
            connection.send_command("mesh_edit", {"indices": [99]})
    error = raised.value
    assert error.code == "INVALID_INDEX"
    assert error.error_type == "IndexError"
    assert error.command == "mesh_edit"
    assert error.meta["duration_ms"] == 1.25
    assert error.to_dict()["message"] == "Face index 99 is invalid"


def test_return_envelope_preserves_structured_error():
    connection = BlenderConnection("localhost", 9876)
    connection.sock = MagicMock()
    response = {"status": "error", "ok": False, "error": {"message": "failed"}}
    with patch.object(connection, "receive_full_response", return_value=json.dumps(response).encode()):
        assert connection.send_command("test", return_envelope=True) == response


def test_max_retries_means_retries_after_initial_attempt(monkeypatch):
    connection = BlenderConnection("localhost", 9876)
    attempts = []

    class TimeoutSocket:
        def sendall(self, data):
            attempts.append(data)
            raise socket.timeout("slow")

        def settimeout(self, value):
            pass

        def close(self):
            pass

    def connect():
        connection.sock = TimeoutSocket()
        return True

    monkeypatch.setattr(connection, "connect", connect)
    monkeypatch.setattr("time.sleep", lambda _: None)
    with pytest.raises(ConnectionError, match="All 3 attempts failed"):
        connection.send_command("health_check", max_retries=2)
    assert len(attempts) == 3


def test_addon_enforces_request_response_and_queue_limits():
    source = (Path(__file__).parents[1] / "addon.py").read_text(encoding="utf-8")
    for marker in (
        "MAX_ADDON_REQUEST_BYTES", "MAX_ADDON_RESPONSE_BYTES", "MAX_COMMAND_QUEUE_SIZE",
        '"REQUEST_TOO_LARGE"', '"RESPONSE_TOO_LARGE"', '"COMMAND_QUEUE_FULL"',
    ):
        assert marker in source
    assert 'print(f"JSON parsed: {command}"' not in source
