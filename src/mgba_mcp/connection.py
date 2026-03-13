"""Async TCP client for communicating with the mGBA Lua server."""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class MGBAConnection:
    """Manages TCP socket connection to the Lua script running in mGBA."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5555):
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self, retries: int = 5, delay: float = 1.0) -> None:
        """Connect to the mGBA Lua TCP server with retry logic."""
        for attempt in range(retries):
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self.host, self.port
                )
                logger.info(f"Connected to mGBA at {self.host}:{self.port}")
                return
            except (ConnectionRefusedError, OSError) as e:
                if attempt < retries - 1:
                    logger.warning(
                        f"Connection attempt {attempt + 1}/{retries} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise ConnectionError(
                        f"Could not connect to mGBA at {self.host}:{self.port} "
                        f"after {retries} attempts. Make sure mGBA is running and "
                        f"the mgba_server.lua script is loaded."
                    ) from e

    async def disconnect(self) -> None:
        """Close the connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    async def send_command(
        self, cmd: str, timeout: float = 10.0, **params
    ) -> dict:
        """Send a JSON command and wait for the response.

        Args:
            cmd: The command name (e.g., "screenshot", "press_button")
            timeout: Timeout in seconds for the response
            **params: Additional parameters for the command

        Returns:
            The parsed JSON response dict.
        """
        async with self._lock:
            if not self.is_connected:
                await self.connect()

            self._request_id += 1
            request = {"cmd": cmd, "id": self._request_id, **params}

            try:
                message = json.dumps(request) + "\n"
                self._writer.write(message.encode("utf-8"))
                await self._writer.drain()

                raw = await asyncio.wait_for(
                    self._reader.readline(), timeout=timeout
                )
                if not raw:
                    await self.disconnect()
                    raise ConnectionError("mGBA connection closed unexpectedly.")

                response = json.loads(raw.decode("utf-8"))
                if response.get("error"):
                    raise RuntimeError(
                        f"mGBA error: {response['error']}"
                    )
                return response

            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to command: {cmd}")
                await self.disconnect()
                raise TimeoutError(
                    f"mGBA did not respond to '{cmd}' within {timeout}s. "
                    f"The emulator may be paused or the Lua script crashed."
                )
            except (ConnectionResetError, BrokenPipeError) as e:
                await self.disconnect()
                raise ConnectionError(
                    f"Lost connection to mGBA: {e}"
                ) from e

    async def ensure_connected(self) -> None:
        """Ensure the connection is active, reconnecting if needed."""
        if not self.is_connected:
            await self.connect()


# Global connection instance
_connection: MGBAConnection | None = None


def get_connection() -> MGBAConnection:
    """Get or create the global connection instance."""
    global _connection
    if _connection is None:
        _connection = MGBAConnection()
    return _connection
