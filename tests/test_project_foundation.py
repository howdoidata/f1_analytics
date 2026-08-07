"""Smoke tests for the project foundation: package layout and the network guard."""

from __future__ import annotations

import socket

import pytest

import f1_analytics
import f1_analytics.analysis
import f1_analytics.data_sources
import f1_analytics.database
import f1_analytics.validation


def test_package_and_subpackages_importable():
    for module in (
        f1_analytics,
        f1_analytics.analysis,
        f1_analytics.data_sources,
        f1_analytics.database,
        f1_analytics.validation,
    ):
        assert module.__file__


def test_network_access_is_blocked():
    # A literal IP avoids a DNS lookup ahead of the patched connect() call —
    # a hostname would let getaddrinfo raise socket.gaierror instead in a
    # genuinely offline environment, bypassing the guard this test checks.
    with pytest.raises(RuntimeError):
        socket.create_connection(("203.0.113.1", 80), timeout=2)
