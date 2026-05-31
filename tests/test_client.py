"""Tests for the truenas_ng synchronous client wrapper and coercion helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from custom_components.truenas_ng.client import (
    ClientException,
    TrueNASAuthError,
    TrueNASClient,
    TrueNASConnectionError,
    epoch_ms_to_datetime,
    parsed,
    to_int,
)


def _make_client_exception(errno: int) -> ClientException:
    """Build a ClientException with the given errno (an int attribute on the class)."""
    exc = ClientException("boom")
    exc.errno = errno
    return exc


def _new_client() -> TrueNASClient:
    """Construct a TrueNASClient with representative connection parameters."""
    return TrueNASClient("truenas.local", 9443, "homeassistant", "1-test", True)


@patch("custom_components.truenas_ng.client.Client")
def test_connect_and_call_returns_value(mock_client_cls):
    """connect() builds the client at the right URI and call() returns the underlying result."""
    instance = mock_client_cls.return_value
    instance.call.return_value = {"version": "26.0.0-BETA.1"}

    client = _new_client()
    client.connect()

    mock_client_cls.assert_called_once_with(
        "wss://truenas.local:9443/api/current", verify_ssl=True
    )
    instance.login_with_api_key.assert_called_once_with("homeassistant", "1-test")

    assert client.call("system.info") == {"version": "26.0.0-BETA.1"}
    instance.call.assert_called_once_with("system.info", job=False, timeout=None)


@patch("custom_components.truenas_ng.client.Client")
def test_login_value_error_maps_to_auth_error(mock_client_cls):
    """A ValueError from login_with_api_key is surfaced as TrueNASAuthError."""
    instance = mock_client_cls.return_value
    instance.login_with_api_key.side_effect = ValueError("invalid api key")

    client = _new_client()
    with pytest.raises(TrueNASAuthError):
        client.connect()


@pytest.mark.parametrize(
    ("errno", "expected"),
    [
        (ClientException.ENOTAUTHENTICATED, TrueNASAuthError),
        (0, TrueNASConnectionError),
    ],
)
@patch("custom_components.truenas_ng.client.Client")
def test_client_exception_errno_mapping(mock_client_cls, errno, expected):
    """ENOTAUTHENTICATED maps to auth error; any other ClientException maps to connection error."""
    instance = mock_client_cls.return_value
    instance.login_with_api_key.side_effect = _make_client_exception(errno)

    client = _new_client()
    with pytest.raises(expected):
        client.connect()


def test_coercion_helpers():
    """to_int, epoch_ms_to_datetime and parsed coerce contract-specified inputs correctly."""
    assert to_int("23") == 23
    assert to_int(None) is None

    result = epoch_ms_to_datetime({"$date": 1777880507000})
    assert result == datetime.fromtimestamp(1777880507, tz=timezone.utc)
    assert result.tzinfo is timezone.utc

    # The real truenas_api_client EJSON decoder returns $date fields as datetime objects,
    # not {"$date": ms} dicts — pass an aware datetime through, and make a naive one aware.
    aware = datetime(2026, 5, 4, 7, 41, 47, tzinfo=timezone.utc)
    assert epoch_ms_to_datetime(aware) is aware
    assert epoch_ms_to_datetime(datetime(2026, 5, 4, 7, 41, 47)) == aware
    assert epoch_ms_to_datetime(None) is None

    assert parsed({"parsed": 5}) == 5
    assert parsed(7) == 7
