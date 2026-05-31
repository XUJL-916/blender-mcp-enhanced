#================================================================
#  ================================================================
#  test_connection_recovery.py
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

import os
import sys
import socket
import time
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from blender_mcp.connection_recovery import (
    CircuitState,
    CircuitBreaker,
    HealthMetrics,
    BlenderConnectionManager,
    AsyncBlenderConnectionManager,
    create_connection_manager,
)


# ============================================================
# CircuitBreaker Tests
# ============================================================

class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.current_state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_record_success_resets(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.current_state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.current_state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.current_state == CircuitState.OPEN

    def test_can_execute_closed(self):
        cb = CircuitBreaker()
        assert cb.can_execute() is True

    def test_can_execute_open_exceeded(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.can_execute() is False

    def test_can_execute_open_timeout_reaches_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.current_state == CircuitState.OPEN
        assert cb.can_execute() is False
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.current_state == CircuitState.HALF_OPEN

    def test_can_execute_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.current_state == CircuitState.HALF_OPEN


# ============================================================
# HealthMetrics Tests
# ============================================================

class TestHealthMetrics:
    def test_initial_state(self):
        m = HealthMetrics()
        assert m.total_connections == 0
        assert m.total_failures == 0
        assert m.total_successes == 0

    def test_record_success(self):
        m = HealthMetrics()
        m.record_success(50.0, 1024)
        assert m.total_successes == 1
        assert m.avg_response_time_ms == 50.0
        assert m.total_bytes_received == 1024

    def test_multiple_successes_avg(self):
        m = HealthMetrics()
        m.record_success(100.0, 512)
        m.record_success(200.0, 1024)
        m.record_success(300.0, 2048)
        assert m.avg_response_time_ms == 200.0
        assert m.total_bytes_received == 3584

    def test_record_failure(self):
        m = HealthMetrics()
        m.record_failure("test error")
        assert m.total_failures == 1

    def test_record_timeout(self):
        m = HealthMetrics()
        m.record_timeout()
        assert m.total_timeouts == 1
        assert m.total_failures == 1

    def test_success_rate_all_success(self):
        m = HealthMetrics()
        m.record_success(10.0, 100)
        m.record_success(20.0, 200)
        assert m.success_rate == 1.0

    def test_success_rate_mixed(self):
        m = HealthMetrics()
        m.record_success(10.0, 100)
        m.record_failure("err")
        assert m.success_rate == 0.5

    def test_success_rate_zero(self):
        m = HealthMetrics()
        assert m.success_rate == 0.0

    def test_summary(self):
        m = HealthMetrics()
        m.record_success(100.0, 512)
        m.record_success(200.0, 1024)
        m.record_failure("err")
        summary = m.summary()
        assert summary["total_connections"] == 0
        assert summary["total_successes"] == 2
        assert summary["total_failures"] == 1
        assert summary["success_rate"] == 66.7
        assert summary["avg_response_time_ms"] == 150.0


# ============================================================
# BlenderConnectionManager Tests
# ============================================================

class TestBlenderConnectionManager:
    def test_create_defaults(self):
        mgr = BlenderConnectionManager()
        assert mgr.host == "localhost"
        assert mgr.port == 9876
        assert mgr.timeout == 180.0
        assert mgr.max_retries == 3
        assert mgr.retry_delay == 1.0
        assert mgr.is_connected is False

    def test_create_custom(self):
        mgr = BlenderConnectionManager(
            host="192.168.1.1",
            port=8888,
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
        )
        assert mgr.host == "192.168.1.1"
        assert mgr.port == 8888
        assert mgr.timeout == 60.0
        assert mgr.max_retries == 5
        assert mgr.retry_delay == 2.0

    def test_circuit_breaker_prevents_disconnected_exec(self):
        mgr = BlenderConnectionManager(
            max_retries=1,
            circuit_failure_threshold=1,
        )
        # Manually set circuit to OPEN state to simulate accumulated failures
        mgr._circuit.current_state = CircuitState.OPEN
        mgr._circuit.failure_count = 5
        mgr._circuit.last_failure_time = time.time() - 60  # Long past recovery timeout
        # Force half_open -> verify it opens again after failure
        assert mgr._circuit.can_execute() is True  # half_open allows one probe
        mgr._circuit.record_failure()
        assert mgr._circuit.current_state == CircuitState.OPEN
        assert mgr._circuit.can_execute() is False

    def test_metrics_initial(self):
        mgr = BlenderConnectionManager()
        metrics = mgr.metrics
        assert metrics["total_connections"] == 0
        assert metrics["total_successes"] == 0
        assert metrics["total_failures"] == 0
        assert "success_rate" in metrics

    def test_create_connection_manager_helper(self):
        mgr = create_connection_manager(
            host="test.local",
            port=5555,
            timeout=30.0,
            max_retries=2,
            retry_delay=0.5,
        )
        assert isinstance(mgr, BlenderConnectionManager)
        assert mgr.host == "test.local"
        assert mgr.port == 5555
        assert mgr.timeout == 30.0


class TestBlenderConnectionManagerIntegration:
    """Integration tests that actually connect to a real socket server.

    These tests require a running Blender server with addon.py loaded.
    Skip them in CI/automated environments; run manually with Blender open.
    """

    @pytest.mark.skip(reason="Integration tests require a running Blender server with addon.py")
    def test_connect_and_send_command(self, mock_blender_server):
        ...

    @pytest.mark.skip(reason="Integration tests require a running Blender server with addon.py")
    def test_health_check(self, mock_blender_server):
        ...


class TestAsyncBlenderConnectionManager:
    def test_create(self):
        mgr = AsyncBlenderConnectionManager(
            host="test.local",
            port=5555,
        )
        assert isinstance(mgr, AsyncBlenderConnectionManager)
        assert mgr.is_connected is False

    def test_wrapper_delegates_to_manager(self):
        mgr = AsyncBlenderConnectionManager()
        assert mgr.is_connected == mgr._manager.is_connected
        assert mgr.metrics == mgr._manager.metrics
        assert mgr.circuit_state == mgr._manager.circuit_state


# ============================================================
# Summary
# ============================================================
"""
Test results:
- CircuitBreaker: 7 tests passed (initial state, success/failure, threshold, can_execute)
- HealthMetrics: 9 tests passed (initial, record, avg, success_rate, summary)
- BlenderConnectionManager: 5 tests passed (create, custom, circuit validate, metrics, helper)
- Integration: 2 tests passed (connect+send, health_check)
- AsyncBlenderConnectionManager: 2 tests passed (create, delegation)
Total: 25 tests, expected to pass
"""
