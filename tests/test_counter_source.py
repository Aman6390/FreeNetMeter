"""Unit tests for CounterSource and FakeCounterSource."""

from __future__ import annotations

import pytest

from core.counter_source import (
    FakeCounterSource,
    InterfaceCounters,
    InterfaceStatus,
    NetworkSnapshot,
)


def test_interface_counters_dataclass() -> None:
    """Verify InterfaceCounters properties and immutability."""
    counters = InterfaceCounters(
        bytes_sent=1000,
        bytes_recv=2000,
        packets_sent=10,
        packets_recv=20,
    )
    assert counters.bytes_sent == 1000
    assert counters.bytes_recv == 2000
    assert counters.packets_sent == 10
    assert counters.packets_recv == 20

    # Frozen dataclass should reject mutations
    with pytest.raises(Exception):
        counters.bytes_sent = 3000  # type: ignore[misc]


def test_fake_counter_source_snapshot_and_time() -> None:
    """Verify FakeCounterSource produces accurate snapshots with controlled timestamps."""
    source = FakeCounterSource()
    source.set_time(500.0)
    source.set_interface("Ethernet", bytes_sent=1024, bytes_recv=2048, is_up=True, speed_mbps=1000)

    snap = source.read_counters()
    assert isinstance(snap, NetworkSnapshot)
    assert snap.timestamp == 500.0
    assert "Ethernet" in snap.counters
    assert snap.counters["Ethernet"].bytes_sent == 1024
    assert snap.counters["Ethernet"].bytes_recv == 2048

    # Check status inquiry
    statuses = source.read_interface_statuses()
    assert "Ethernet" in statuses
    assert isinstance(statuses["Ethernet"], InterfaceStatus)
    assert statuses["Ethernet"].is_up is True
    assert statuses["Ethernet"].speed_mbps == 1000

    # Advance time and update counters
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=2048, bytes_recv=4096)
    snap2 = source.read_counters()
    assert snap2.timestamp == 501.0
    assert snap2.counters["Ethernet"].bytes_sent == 2048
    assert snap2.counters["Ethernet"].bytes_recv == 4096


def test_fake_counter_source_remove_interface() -> None:
    """Verify interface removal simulates unplugging."""
    source = FakeCounterSource()
    source.set_interface("Wi-Fi", bytes_sent=100, bytes_recv=200)
    assert "Wi-Fi" in source.read_counters().counters

    source.remove_interface("Wi-Fi")
    assert "Wi-Fi" not in source.read_counters().counters
    assert "Wi-Fi" not in source.read_interface_statuses()


def test_psutil_counter_source_live() -> None:
    """Verify PsutilCounterSource reads live system counters and statuses."""
    from core.counter_source import PsutilCounterSource

    source = PsutilCounterSource()
    snapshot = source.read_counters()
    assert isinstance(snapshot, NetworkSnapshot)
    assert snapshot.timestamp > 0
    assert isinstance(snapshot.counters, dict)

    statuses = source.read_interface_statuses()
    assert isinstance(statuses, dict)
