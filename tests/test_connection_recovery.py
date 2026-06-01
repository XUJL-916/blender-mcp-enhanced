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
#      Comprehensive tests for connection recovery, circuit breaker,
#      heartbeat, and auto-reconnect functionality.
#
#  ================================================================
#================================================================

"""Tests for connection recovery, circuit breaker, heartbeat, and auto-reconnect."""

import pytest
import socket
import time
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestCircuitBreaker:
    """Test circuit breaker state machine."""

    def test_initial_state_closed(self):
        from blender_mcp.connection_recovery import CircuitBreaker, CircuitState
        cb = CircuitBreaker()
        assert cb.current_state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_opens_after_threshold(self):
        from blender_mcp.connection_recovery import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.current_state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.current_state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.current_state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.current_state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_can_execute_when_closed(self):
        from blender_mcp.connection_recovery import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.can_execute() == True

    def test_can_execute_when_open_timeout_expired(self):
        from blender_mcp.connection_recovery import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.current_state.value == 'open'
        assert cb.can_execute() == False  # Too soon

        time.sleep(0.15)  # Wait for recovery timeout
        assert cb.can_execute() == True  # Should transition to HALF_OPEN
        assert cb.current_state.value == 'half_open'

    def test_can_execute_fails_when_open_too_early(self):
        from blender_mcp.connection_recovery import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.can_execute() == False

    def test_record_success_resets_circuit(self):
        from blender_mcp.connection_recovery import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.current_state == CircuitState.OPEN

        cb.record_success()
        assert cb.current_state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_success_closes(self):
        from blender_mcp.connection_recovery import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Transition to HALF_OPEN
        assert cb.current_state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.current_state == CircuitState.CLOSED


class TestHealthMetrics:
    """Test health metrics tracking."""

    def test_success_rate_initial(self):
        from blender_mcp.connection_recovery import HealthMetrics
        hm = HealthMetrics()
        assert hm.success_rate == 0.0

    def test_success_rate_after_mix(self):
        from blender_mcp.connection_recovery import HealthMetrics
        hm = HealthMetrics()
        hm.record_success(10.0, 100)
        hm.record_success(15.0, 150)
        hm.record_failure()

        assert hm.success_rate == pytest.approx(0.667, rel=0.01)
        assert hm.total_successes == 2
        assert hm.total_failures == 1
        assert hm.avg_response_time_ms == pytest.approx(12.5, rel=0.01)

    def test_timeout_records_both(self):
        from blender_mcp.connection_recovery import HealthMetrics
        hm = HealthMetrics()
        hm.record_timeout()
        assert hm.total_timeouts == 1
        assert hm.total_failures == 1

    def test_summary_structure(self):
        from blender_mcp.connection_recovery import HealthMetrics
        hm = HealthMetrics()
        hm.record_success(10.0, 100)
        summary = hm.summary()

        assert 'total_connections' in summary
        assert 'total_successes' in summary
        assert 'total_failures' in summary
        assert 'success_rate' in summary
        assert 'avg_response_time_ms' in summary
        assert 'total_bytes_received' in summary


class TestConnectionManagerBasic:
    """Test BlenderConnectionManager basic operations."""

    def test_init_default_values(self):
        from blender_mcp.connection_recovery import BlenderConnectionManager
        cm = BlenderConnectionManager()
        assert cm.host == 'localhost'
        assert cm.port == 9876
        assert cm.is_connected == False

    def test_init_custom_values(self):
        from blender_mcp.connection_recovery import BlenderConnectionManager
        cm = BlenderConnectionManager(host='127.0.0.1', port=1234, timeout=60.0)
        assert cm.host == '127.0.0.1'
        assert cm.port == 1234
        assert cm.timeout == 60.0

    def test_metrics_available(self):
        from blender_mcp.connection_recovery import BlenderConnectionManager
        cm = BlenderConnectionManager()
        metrics = cm.metrics
        assert 'total_connections' in metrics
        assert 'success_rate' in metrics

    def test_circuit_state_accessible(self):
        from blender_mcp.connection_recovery import BlenderConnectionManager
        cm = BlenderConnectionManager()
        assert cm.circuit_state == 'closed'


class TestConnectionManagerMocked:
    """Test connection manager with mocked socket (async tests)."""

    def _get_loop(self):
        """Get event loop compatible with Windows."""
        import asyncio
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def test_connect_success_via_mock(self):
        import asyncio
        from blender_mcp.connection_recovery import BlenderConnectionManager
        from unittest.mock import patch, MagicMock

        def mock_connect(self_sock, addr):
            pass

        def mock_settimeout(self_sock, t):
            pass

        def mock_sendall(self_sock, data):
            pass

        async def run_test():
            cm = BlenderConnectionManager(host='127.0.0.1', port=12345)
            with patch('socket.socket.connect', mock_connect):
                with patch('socket.socket.settimeout', mock_settimeout):
                    with patch('socket.socket.sendall', mock_sendall):
                        result = await cm.connect()
                        assert result == True
                        assert cm.is_connected == True

        asyncio.run(run_test())

    def test_connect_failure_all_retries(self):
        import asyncio
        from blender_mcp.connection_recovery import BlenderConnectionManager
        from unittest.mock import patch

        async def run_test():
            cm = BlenderConnectionManager(
                host='127.0.0.1', port=12345,
                max_retries=2, retry_delay=0.01
            )

            def mock_connect_side_effect(self_sock, addr):
                raise ConnectionRefusedError("Connection refused")

            with patch('socket.socket.connect', mock_connect_side_effect):
                with patch('socket.socket.settimeout'):
                    with patch('socket.socket.sendall'):
                        with pytest.raises(ConnectionError):
                            await cm.connect()
                        assert cm.is_connected == False

        asyncio.run(run_test())

    def test_circuit_breaker_prevents_overload(self):
        import asyncio
        from blender_mcp.connection_recovery import BlenderConnectionManager
        from unittest.mock import patch

        async def run_test():
            cm = BlenderConnectionManager(
                host='127.0.0.1', port=12345,
                max_retries=1,
                circuit_failure_threshold=3,
                circuit_recovery_timeout=60.0
            )

            def mock_connect_side_effect(self_sock, addr):
                raise ConnectionRefusedError("Refused")

            with patch('socket.socket.connect', mock_connect_side_effect):
                with patch('socket.socket.settimeout'):
                    with patch('socket.socket.sendall'):
                        for _ in range(3):
                            try:
                                await cm.connect()
                            except ConnectionError:
                                pass
                        assert cm.circuit_state == 'open'

        asyncio.run(run_test())

    def test_connect_lock_prevents_races(self):
        """Test that is_connected is properly set."""
        from blender_mcp.connection_recovery import BlenderConnectionManager

        cm = BlenderConnectionManager()
        assert cm.is_connected == False
        assert cm._sock is None

    def test_disconnect_cleans_up(self):
        import asyncio
        from blender_mcp.connection_recovery import BlenderConnectionManager
        from unittest.mock import patch, MagicMock

        async def run_test():
            cm = BlenderConnectionManager()
            cm._is_connected = True
            cm._sock = MagicMock()
            await cm.disconnect()
            assert cm.is_connected == False
            assert cm._sock is None

        asyncio.run(run_test())


class TestHeartbeat:
    """Test heartbeat mechanism (non-async tests)."""

    def test_heartbeat_detects_connection(self):
        from blender_mcp.health import HealthChecker
        import socket as real_socket

        def mock_connect_ex(self, addr):
            return 0  # Success

        checker = HealthChecker(host='127.0.0.1', port=12345)

        with patch.object(real_socket.socket, 'connect_ex', mock_connect_ex):
            with patch.object(real_socket.socket, 'close'):
                result = checker.check_blender_connection()
                assert result == True
                assert checker.status.blender_connected == True

    def test_heartbeat_detects_disconnection(self):
        from blender_mcp.health import HealthChecker
        import socket as real_socket

        def mock_connect_ex(self, addr):
            return 111  # Connection refused

        checker = HealthChecker(host='127.0.0.1', port=12345)
        checker.status.blender_connected = True  # Pretend was connected

        with patch.object(real_socket.socket, 'connect_ex', mock_connect_ex):
            with patch.object(real_socket.socket, 'close'):
                result = checker.check_blender_connection()
                assert result == False
                assert checker.status.blender_connected == False

    def test_health_checker_get_full_status_no_blender(self):
        """Test health check returns degraded status when no Blender."""
        from blender_mcp.health import HealthChecker
        import socket as real_socket

        def mock_connect_ex(self, addr):
            return 111

        checker = HealthChecker(host='127.0.0.1', port=12345)

        with patch.object(real_socket.socket, 'connect_ex', mock_connect_ex):
            with patch.object(real_socket.socket, 'close'):
                status = checker.get_full_status()
                assert status['status'] in ['healthy', 'degraded', 'unhealthy']
                assert 'blender' in status
                assert 'mcp' in status
                assert 'timestamp' in status
                assert status['blender']['connected'] == False


class TestErrorScenarios:
    """Test error handling and edge cases."""

    def test_connection_manager_no_blender(self):
        """Connection manager reports no Blender when port 9876 not listening."""
        from blender_mcp.health import HealthChecker
        import socket as real_socket

        def mock_connect_ex(self, addr):
            return 111

        checker = HealthChecker(host='localhost', port=9876)

        with patch.object(real_socket.socket, 'connect_ex', mock_connect_ex):
            with patch.object(real_socket.socket, 'close'):
                result = checker.check_blender_connection()
                assert result == False

    def test_disconnect_cleans_up(self):
        import asyncio
        from blender_mcp.connection_recovery import BlenderConnectionManager
        from unittest.mock import MagicMock

        async def run_test():
            cm = BlenderConnectionManager()
            cm._is_connected = True
            cm._sock = MagicMock()
            await cm.disconnect()
            assert cm.is_connected == False
            assert cm._sock is None

        asyncio.run(run_test())

    def test_health_checker_singleton_behavior(self):
        from blender_mcp.health import get_health_checker
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        assert checker1 is checker2

    def test_health_metrics_empty_summary(self):
        from blender_mcp.connection_recovery import HealthMetrics
        hm = HealthMetrics()
        summary = hm.summary()
        assert summary['total_connections'] == 0
        assert summary['total_successes'] == 0
        assert summary['total_failures'] == 0
        assert summary['success_rate'] == 0.0

    def test_circuit_breaker_timeout_property(self):
        from blender_mcp.connection_recovery import CircuitBreaker
        cb = CircuitBreaker(recovery_timeout=30.0)
        cb.record_failure()
        elapsed = time.time() - cb.last_failure_time
        remaining = cb.recovery_timeout - elapsed
        assert remaining < 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
