"""Synchronous TrueNAS JSON-RPC WebSocket client wrapper for truenas_ng."""

from __future__ import annotations

import contextlib
import threading
from datetime import datetime, timezone
from typing import Any

import websocket
from truenas_api_client import Client, ClientException


class TrueNASError(Exception):
    """Base error for the TrueNAS client wrapper."""


class TrueNASAuthError(TrueNASError):
    """Bad/expired API key or server-side auth rejection (-> ConfigEntryAuthFailed)."""


class TrueNASConnectionError(TrueNASError):
    """Connection / transport / timeout failure (-> UpdateFailed / ConfigEntryNotReady)."""


def to_int(value: Any) -> int | None:
    """Coerce a value to int, returning None when it cannot be parsed."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def epoch_ms_to_datetime(value: Any) -> datetime | None:
    """Convert a TrueNAS {"$date": ms} node or raw epoch-ms number to aware UTC datetime."""
    if isinstance(value, dict):
        value = value.get("$date")
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def parsed(node: Any) -> Any:
    """Return node["parsed"] for TrueNAS {parsed, value} composites, else the node itself."""
    if isinstance(node, dict) and "parsed" in node:
        return node["parsed"]
    return node


class TrueNASClient:
    """Lock-guarded, reconnecting wrapper around the synchronous truenas_api_client.Client."""

    def __init__(
        self, host: str, port: int, username: str, api_key: str, verify_ssl: bool
    ) -> None:
        """Store connection parameters; the underlying client is created lazily by connect()."""
        self._host = host
        self._port = port
        self._username = username
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._client: Client | None = None
        self._lock = threading.Lock()

    @property
    def uri(self) -> str:
        """Return the JSON-RPC WebSocket endpoint URI."""
        return f"wss://{self._host}:{self._port}/api/current"

    @contextlib.contextmanager
    def _map_errors(self):
        """Translate underlying client/transport exceptions into wrapper exceptions."""
        try:
            yield
        except ClientException as err:
            if getattr(err, "errno", None) == ClientException.ENOTAUTHENTICATED:
                raise TrueNASAuthError(str(err) or "Not authenticated") from err
            raise TrueNASConnectionError(str(err) or "TrueNAS client error") from err
        except websocket.WebSocketException as err:
            raise TrueNASConnectionError(str(err) or "WebSocket error") from err
        except OSError as err:
            raise TrueNASConnectionError(str(err) or "Connection error") from err

    def connect(self) -> None:
        """Construct the underlying client and authenticate with the API key."""
        with self._map_errors():
            client = Client(self.uri, verify_ssl=self._verify_ssl)
        try:
            with self._map_errors():
                try:
                    client.login_with_api_key(self._username, self._api_key)
                except ValueError as err:
                    raise TrueNASAuthError(
                        str(err) or "Authentication failed"
                    ) from err
        except TrueNASError:
            with contextlib.suppress(Exception):
                client.close()
            raise
        self._client = client

    def close(self) -> None:
        """Close and drop the underlying client; never raises."""
        client = self._client
        self._client = None
        if client is not None:
            with contextlib.suppress(Exception):
                client.close()

    def _raw_call(
        self, method: str, *params: Any, job: bool = False, timeout: float | None = None
    ) -> Any:
        """Invoke a single method on the underlying client with exception mapping."""
        with self._map_errors():
            return self._client.call(method, *params, job=job, timeout=timeout)

    def call(
        self, method: str, *params: Any, job: bool = False, timeout: float | None = None
    ) -> Any:
        """Call a JSON-RPC method, lazily connecting and reconnecting once on transport failure."""
        with self._lock:
            if self._client is None:
                self.connect()
            try:
                return self._raw_call(method, *params, job=job, timeout=timeout)
            except TrueNASConnectionError:
                self.close()
                self.connect()
                return self._raw_call(method, *params, job=job, timeout=timeout)

    def ping(self) -> bool:
        """Return True when the underlying client responds to ping with 'pong'."""
        with self._lock:
            if self._client is None:
                self.connect()
            with self._map_errors():
                return self._client.ping() == "pong"
