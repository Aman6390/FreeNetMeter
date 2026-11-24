"""Unit tests for UsageAccumulator.

Verifies:
- Normal byte delta accumulation per interface.
- Midnight rollover: correct date attribution across day boundaries.
- Daylight saving time (DST) transition handling.
- Flush and pending buffer reset.
- Negative or zero delta rejection.
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from core.speed_calculator import InterfaceSpeedResult
from core.usage_accumulator import UsageAccumulator


def _make_result(
    iface: str,
    delta_recv: int,
    delta_sent: int,
) -> InterfaceSpeedResult:
    """Helper to construct InterfaceSpeedResult for tests."""
    return InterfaceSpeedResult(
        interface_name=iface,
        download_speed=float(delta_recv),
        upload_speed=float(delta_sent),
        raw_download_speed=float(delta_recv),
        raw_upload_speed=float(delta_sent),
        delta_bytes_recv=delta_recv,
        delta_bytes_sent=delta_sent,
    )


def test_normal_accumulation() -> None:
    """Verify bytes sent and received accumulate properly for multiple adapters."""
    acc = UsageAccumulator(date_provider=lambda: "2026-11-09")

    # Record first tick
    results1 = {
        "Ethernet": _make_result("Ethernet", delta_recv=1000, delta_sent=500),
        "Wi-Fi": _make_result("Wi-Fi", delta_recv=2000, delta_sent=800),
    }
    acc.record_sample(results1)

    # Record second tick
    results2 = {
        "Ethernet": _make_result("Ethernet", delta_recv=500, delta_sent=200),
    }
    acc.record_sample(results2)

    assert acc.has_pending() is True
    records = acc.flush_pending()

    # Buffer should now be cleared
    assert acc.has_pending() is False
    assert len(acc.flush_pending()) == 0

    record_map = {(r.date_str, r.interface_name): (r.bytes_sent, r.bytes_recv) for r in records}
    assert record_map[("2026-11-09", "Ethernet")] == (700, 1500)
    assert record_map[("2026-11-09", "Wi-Fi")] == (800, 2000)


def test_midnight_rollover() -> None:
    """Verify samples crossing midnight attribute usage to the respective dates."""
    date_val = "2026-11-09"
    acc = UsageAccumulator(date_provider=lambda: date_val)

    # Sample before midnight
    acc.record_sample({"Ethernet": _make_result("Ethernet", delta_recv=10_000, delta_sent=5_000)})

    # Midnight strikes! Date changes to 2026-11-10
    date_val = "2026-11-10"
    acc.record_sample({"Ethernet": _make_result("Ethernet", delta_recv=20_000, delta_sent=8_000)})

    records = acc.flush_pending()
    record_map = {(r.date_str, r.interface_name): (r.bytes_sent, r.bytes_recv) for r in records}

    assert record_map[("2026-11-09", "Ethernet")] == (5_000, 10_000)
    assert record_map[("2026-11-10", "Ethernet")] == (8_000, 20_000)


def test_dst_transition_boundary() -> None:
    """Verify attribution works across DST transitions (e.g. clock jumps)."""
    # Simulate a timezone with DST, e.g. US Eastern
    tz = ZoneInfo("America/New_York")

    # Time just before spring-forward: 2026-03-08 01:59:59 EST
    t1 = datetime.datetime(2026, 3, 8, 1, 59, 59, tzinfo=tz)
    # Time after spring-forward: 2026-03-08 03:00:01 EDT
    t2 = datetime.datetime(2026, 3, 8, 3, 0, 1, tzinfo=tz)

    current_dt = t1
    acc = UsageAccumulator(date_provider=lambda: current_dt.strftime("%Y-%m-%d"))

    acc.record_sample({"Ethernet": _make_result("Ethernet", delta_recv=1000, delta_sent=200)})

    current_dt = t2
    acc.record_sample({"Ethernet": _make_result("Ethernet", delta_recv=2000, delta_sent=400)})

    records = acc.flush_pending()
    assert len(records) == 1
    # Both belong to the same local calendar date 2026-03-08
    assert records[0].date_str == "2026-03-08"
    assert records[0].bytes_recv == 3000
    assert records[0].bytes_sent == 600


def test_zero_and_negative_deltas_discarded() -> None:
    """Verify zero or negative deltas are never accumulated."""
    acc = UsageAccumulator(date_provider=lambda: "2026-11-09")
    acc.record_sample({"Ethernet": _make_result("Ethernet", delta_recv=0, delta_sent=0)})
    acc.record_sample({"Ethernet": _make_result("Ethernet", delta_recv=-100, delta_sent=-50)})

    assert acc.has_pending() is False
    assert len(acc.flush_pending()) == 0
