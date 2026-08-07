"""Repo-wide pytest fixtures."""

from __future__ import annotations

import socket
from typing import Any

import pytest


def _blocked_connect(self: socket.socket, address: Any) -> None:
    raise RuntimeError(f"Network access is blocked in tests (AD-11): blocked connect to {address!r}")


def _blocked_connect_ex(self: socket.socket, address: Any) -> int:
    raise RuntimeError(f"Network access is blocked in tests (AD-11): blocked connect_ex to {address!r}")


@pytest.fixture(autouse=True)
def _block_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block every socket connection for the duration of a test.

    AD-11: tests never touch the network. Any test that tries fails loudly
    with a RuntimeError instead of hitting a real host or hanging.
    """
    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_connect_ex)
