#================================================================
#  ================================================================
#  connection_recovery.py
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
#      Connection recovery — circuit breaker pattern, auto-reconnect and health check mechanism
#
#  This software is released under the MIT License.
#  See LICENSE file in the project root for full terms.
#
#  ================================================================
#================================================================

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("blender-mcp.connection_recovery")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, stop trying
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    current_state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0

    def record_success(self):
        self.failure_count = 0
        self.current_state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.current_state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")

    def can_execute(self) -> bool:
        if self.current_state == CircuitState.CLOSED:
            return True
        if self.current_state == CircuitState.HALF_OPEN:
            return True
        if self.current_state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.current_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker HALF_OPEN, testing connection")
                return True
        return False


@dataclass
class HealthMetrics:
    """Tracks connection health statistics."""
    total_connections: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_timeouts: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    avg_response_time_ms: float = 0.0
    _response_times: list = field(default_factory=list, repr=False)
    _last_health_check: float = 0.0

    def record_success(self, response_time_ms: float, bytes_received: int):
        self.total_successes += 1
        self._response_times.append(response_time_ms)
        if len(self._response_times) > 100:
            self._response_times = self._response_times[-100:]
        self.avg_response_time_ms = sum(self._response_times) / len(self._response_times)
        self.total_bytes_received += bytes_received

    def record_failure(self, reason: str = ""):
        self.total_failures += 1
        logger.debug(f"Health failure recorded: {reason}")

    def record_timeout(self):
        self.total_timeouts += 1
        self.total_failures += 1

    @property
    def success_rate(self) -> float:
        total = self.total_successes + self.total_failures
        return self.total_successes / total if total > 0 else 0.0

    def summary(self) -> dict:
        return {
            "total_connections": self.total_connections,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "success_rate": round(self.success_rate * 100, 1),
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "total_bytes_received": self.total_bytes_received,
        }


class BlenderConnectionManager:
    """
    Enhanced connection manager with auto-reconnect and circuit breaker.

    Replaces manual socket.connect() calls with a robust connection lifecycle.
    Does not modify any existing code — used as a drop-in replacement.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9876,
        timeout: float = 180.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._sock: Optional[socket.socket] = None
        self._circuit = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout,
        )
        self._metrics = HealthMetrics()
        self._is_connected = False
        self._connect_lock: Optional[asyncio.Lock] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._sock is not None

    @property
    def circuit_state(self) -> str:
        return self._circuit.current_state.value

    @property
    def metrics(self) -> dict:
        return self._metrics.summary()

    def _validate_circuit(self) -> bool:
        """Check if the circuit breaker allows execution."""
        if not self._circuit.can_execute():
            raise ConnectionError(
                f"Circuit breaker is OPEN. "
                f"Failures: {self._circuit.failure_count}, "
                f"Recovery in {self._circuit.recovery_timeout - (time.time() - self._circuit.last_failure_time):.1f}s"
            )
        return True

    async def connect(self) -> bool:
        """
        Establish connection to Blender with retry logic.

        Returns True if connected, raises on failure.
        """
        self._validate_circuit()

        # If already connected, verify
        if self.is_connected:
            try:
                self._sock.sendall(b"\x00")  # Send null byte to test
                self._metrics.record_success(0, 0)
                return True
            except Exception:
                self._close_socket()
                self._is_connected = False

        max_attempts = self.max_retries if not self.is_connected else 1
        for attempt in range(1, max_attempts + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                self._sock = sock
                self._is_connected = True
                self._metrics.total_connections += 1
                self._circuit.record_success()
                logger.info(f"Connected to Blender at {self.host}:{self.port} (attempt {attempt})")
                return True
            except (socket.timeout, socket.timeout) as e:
                self._metrics.record_timeout()
                self._circuit.record_failure(reason=f"timeout attempt {attempt}")
                logger.warning(f"Connection timeout (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(self.retry_delay * attempt)  # Exponential backoff
                    self._close_socket()
            except (ConnectionRefusedError, OSError) as e:
                self._metrics.record_failure(str(e))
                self._circuit.record_failure(reason=str(e))
                logger.warning(f"Connection failed (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(self.retry_delay * attempt)
                    self._close_socket()
            except Exception as e:
                self._metrics.record_failure(str(e))
                self._circuit.record_failure(reason=str(e))
                logger.error(f"Unexpected connection error: {e}")
                break

        logger.error("All connection attempts failed")
        raise ConnectionError(f"Could not connect to Blender at {self.host}:{self.port}")

    async def disconnect(self):
        """Close the connection cleanly."""
        self._close_socket()
        self._is_connected = False
        logger.info("Disconnected from Blender")

    async def send_command(self, command_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send a command and receive a response with recovery logic.

        Automatically retries on transient failures.
        """
        if not self.is_connected:
            await self.connect()

        command = {"type": command_type, "params": params or {}}
        max_attempts = 2  # Allow one reconnection attempt
        last_error = None

        for attempt in range(max_attempts):
            try:
                # Send command
                start_time = time.time()
                payload = json.dumps(command).encode("utf-8")
                self._sock.sendall(payload)
                self._metrics.total_bytes_sent += len(payload)

                # Receive response
                self._sock.settimeout(self.timeout)
                response_data = await self._receive_full_response(self._sock)
                response_time_ms = (time.time() - start_time) * 1000
                self._metrics.record_success(response_time_ms, len(response_data))

                response = json.loads(response_data.decode("utf-8"))
                self._circuit.record_success()

                if response.get("status") == "error":
                    error_msg = response.get("message", "Unknown error from Blender")
                    logger.error(f"Blender error: {error_msg}")
                    raise Exception(error_msg)

                return response.get("result", {})

            except socket.timeout:
                self._metrics.record_timeout()
                self._circuit.record_failure(reason="socket timeout")
                last_error = "Socket timeout"
                logger.warning(f"Timeout on attempt {attempt + 1}, reconnecting...")
                self._close_socket()
                self._is_connected = False
                await self.connect()
            except ConnectionError as e:
                self._circuit.record_failure(reason=str(e))
                last_error = str(e)
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                self._is_connected = False
                await self.connect()
            except Exception as e:
                last_error = str(e)
                raise

        raise ConnectionError(f"All attempts failed. Last error: {last_error}")

    async def _receive_full_response(self, sock: socket.socket, buffer_size: int = 8192) -> bytes:
        """Receive complete JSON response from socket."""
        chunks = []
        sock.settimeout(self.timeout)

        try:
            while True:
                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        if not chunks:
                            raise Exception("Connection closed before receiving data")
                        break
                    chunks.append(chunk)
                    try:
                        b''.join(chunks).decode("utf-8")
                        json.loads(b''.join(chunks))
                        logger.info(f"Received complete response ({len(b''.join(chunks))} bytes)")
                        return b''.join(chunks)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                except socket.timeout:
                    logger.warning("Socket timeout during receive")
                    break
        except Exception as e:
            logger.error(f"Error during receive: {e}")
            raise

        if chunks:
            data = b''.join(chunks)
            try:
                json.loads(data.decode("utf-8"))
                return data
            except json.JSONDecodeError:
                raise Exception("Incomplete JSON response received")
        raise Exception("No data received")

    def _close_socket(self):
        """Safely close the socket."""
        if self._sock:
            try:
                self._sock.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")
            finally:
                self._sock = None

    async def health_check(self) -> dict:
        """
        Run a health check against the Blender connection.

        Returns health metrics and connection status.
        """
        status = {
            "connected": self.is_connected,
            "circuit_breaker": self.circuit_state,
            "metrics": self.metrics,
        }

        if self.is_connected:
            try:
                result = await self.send_command("get_polyhaven_status")
                status["blender_reachable"] = True
                status["last_health_check"] = time.time()
            except Exception as e:
                status["blender_reachable"] = False
                status["last_error"] = str(e)
        else:
            status["blender_reachable"] = False

        self._metrics._last_health_check = time.time()
        return status

    def __enter__(self):
        """Support sync context manager for sync code paths."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_socket()
        self._is_connected = False
        return False


class AsyncBlenderConnectionManager:
    """
    Async wrapper around BlenderConnectionManager for asyncio contexts.
    """

    def __init__(self, **kwargs):
        self._manager = BlenderConnectionManager(**kwargs)

    @property
    def is_connected(self) -> bool:
        return self._manager.is_connected

    @property
    def metrics(self) -> dict:
        return self._manager.metrics

    @property
    def circuit_state(self) -> str:
        return self._manager.circuit_state

    async def connect(self) -> bool:
        return await self._manager.connect()

    async def disconnect(self):
        await self._manager.disconnect()

    async def send_command(self, command_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._manager.send_command(command_type, params)

    async def health_check(self) -> dict:
        return await self._manager.health_check()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        return False


# Convenience function matching the existing API style
def create_connection_manager(
    host: str = "localhost",
    port: int = 9876,
    timeout: float = 180.0,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> BlenderConnectionManager:
    """Create a new connection manager instance."""
    return BlenderConnectionManager(
        host=host,
        port=port,
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
