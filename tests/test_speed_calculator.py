"""Unit tests for SpeedCalculator.

Verifies:
- Normal speed calculation with exact monotonic timing.
- Zero traffic behavior.
- Counter resets and 64-bit wrap-arounds.
- Sleep/resume gaps (> 5 seconds).
- Tiny intervals (< 0.2 seconds).
- Interfaces added or removed at runtime.
- Deduplication and prevention of double-counting.
- Rolling average smoothing.
"""

from __future__ import annotations

from core.counter_source import FakeCounterSource
from core.speed_calculator import SpeedCalculator


def test_normal_speed_calculation() -> None:
    """Verify normal traffic produces accurate download and upload speeds."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=10_000, bytes_recv=20_000)

    calc = SpeedCalculator(rolling_window_size=1)

    # Initial baseline
    sample1 = calc.process_snapshot(source.read_counters())
    assert sample1.total_download_speed == 0.0
    assert sample1.total_upload_speed == 0.0

    # Advance 1.5 seconds and transfer 15,000 bytes down, 30,000 bytes up
    source.advance_time(1.5)
    source.set_interface("Ethernet", bytes_sent=40_000, bytes_recv=35_000)
    sample2 = calc.process_snapshot(source.read_counters())

    # delta_recv = 15,000, elapsed = 1.5s -> 10,000 B/s
    # delta_sent = 30,000, elapsed = 1.5s -> 20,000 B/s
    assert sample2.elapsed_seconds == 1.5
    assert sample2.total_download_speed == 10_000.0
    assert sample2.total_upload_speed == 20_000.0
    assert sample2.total_delta_recv == 15_000
    assert sample2.total_delta_sent == 30_000


def test_zero_traffic() -> None:
    """Verify zero traffic produces exactly zero speed and zero delta."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=5000, bytes_recv=5000)

    calc = SpeedCalculator()
    calc.process_snapshot(source.read_counters())

    # Advance 1 second with no counter changes
    source.advance_time(1.0)
    sample = calc.process_snapshot(source.read_counters())

    assert sample.total_download_speed == 0.0
    assert sample.total_upload_speed == 0.0
    assert sample.total_delta_recv == 0
    assert sample.total_delta_sent == 0


def test_counter_reset() -> None:
    """Verify adapter reset (counter lower than previous) yields 0 speed and re-baselines."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=50_000, bytes_recv=50_000)

    calc = SpeedCalculator()
    calc.process_snapshot(source.read_counters())

    # Counter suddenly drops (adapter reboot/reconnect)
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=500, bytes_recv=600)
    sample = calc.process_snapshot(source.read_counters())

    # Must discard sample, produce 0, and not produce negative numbers
    assert sample.total_download_speed == 0.0
    assert sample.total_upload_speed == 0.0
    assert sample.total_delta_recv == 0
    assert sample.total_delta_sent == 0

    # Next normal tick from the new baseline works correctly
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=1500, bytes_recv=1600)
    sample2 = calc.process_snapshot(source.read_counters())

    assert sample2.total_download_speed == 1000.0
    assert sample2.total_upload_speed == 1000.0
    assert sample2.total_delta_recv == 1000
    assert sample2.total_delta_sent == 1000


def test_counter_wraparound() -> None:
    """Verify wrap-around behaves safely as a reset and never yields negative values."""
    source = FakeCounterSource()
    source.set_time(100.0)
    # Simulate high 64-bit counter value
    source.set_interface("Ethernet", bytes_sent=(1 << 64) - 1000, bytes_recv=(1 << 64) - 1000)

    calc = SpeedCalculator()
    calc.process_snapshot(source.read_counters())

    # Value wrapped to 500
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=500, bytes_recv=500)
    sample = calc.process_snapshot(source.read_counters())

    assert sample.total_download_speed == 0.0
    assert sample.total_upload_speed == 0.0
    assert sample.total_delta_recv == 0
    assert sample.total_delta_sent == 0


def test_sleep_and_resume_gap() -> None:
    """Verify large interval (> 5s) flags is_gap and re-baselines without traffic spike."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=1000, bytes_recv=1000)

    calc = SpeedCalculator(max_gap=5.0)
    calc.process_snapshot(source.read_counters())

    # System sleeps for 60 seconds
    source.advance_time(60.0)
    source.set_interface("Ethernet", bytes_sent=500_000, bytes_recv=500_000)
    sample = calc.process_snapshot(source.read_counters())

    assert sample.is_gap is True
    assert sample.total_download_speed == 0.0
    assert sample.total_upload_speed == 0.0
    assert sample.total_delta_recv == 0
    assert sample.total_delta_sent == 0


def test_tiny_interval_skipped() -> None:
    """Verify samples with elapsed time < 0.2s are safely ignored."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=1000, bytes_recv=1000)

    calc = SpeedCalculator(min_interval=0.2)
    calc.process_snapshot(source.read_counters())

    # Advance only 0.05 seconds
    source.advance_time(0.05)
    source.set_interface("Ethernet", bytes_sent=1500, bytes_recv=1500)
    sample = calc.process_snapshot(source.read_counters())

    assert sample.total_download_speed == 0.0
    assert sample.total_delta_recv == 0


def test_interface_added_and_removed() -> None:
    """Verify dynamic addition and removal of adapters at runtime."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=1000, bytes_recv=1000)

    calc = SpeedCalculator(rolling_window_size=1)
    calc.process_snapshot(source.read_counters())

    # Plug in USB Wi-Fi adapter
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=2000, bytes_recv=2000)
    source.set_interface("Wi-Fi", bytes_sent=5000, bytes_recv=5000)
    sample1 = calc.process_snapshot(source.read_counters())

    # Ethernet has 1000 B/s; new Wi-Fi starts baseline at 0
    assert sample1.per_interface["Ethernet"].download_speed == 1000.0
    assert sample1.per_interface["Wi-Fi"].download_speed == 0.0

    # Next tick: both active
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=3000, bytes_recv=3000)
    source.set_interface("Wi-Fi", bytes_sent=7000, bytes_recv=7000)
    sample2 = calc.process_snapshot(source.read_counters())

    assert sample2.per_interface["Ethernet"].download_speed == 1000.0
    assert sample2.per_interface["Wi-Fi"].download_speed == 2000.0
    assert sample2.total_download_speed == 3000.0

    # Unplug Ethernet
    source.advance_time(1.0)
    source.remove_interface("Ethernet")
    source.set_interface("Wi-Fi", bytes_sent=9000, bytes_recv=9000)
    sample3 = calc.process_snapshot(source.read_counters())

    assert "Ethernet" not in sample3.per_interface
    assert sample3.per_interface["Wi-Fi"].download_speed == 2000.0
    assert sample3.total_download_speed == 2000.0


def test_double_counting_prevention() -> None:
    """Verify duplicate interface entries in selection never double-count."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=1000, bytes_recv=1000)

    calc = SpeedCalculator(rolling_window_size=1)
    calc.process_snapshot(source.read_counters())

    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=2000, bytes_recv=2000)

    # Pass Ethernet multiple times in selection
    sample = calc.process_snapshot(
        source.read_counters(),
        selected_interfaces=["Ethernet", "Ethernet", "Ethernet"],
    )

    # Should count Ethernet exactly once
    assert sample.total_download_speed == 1000.0
    assert sample.total_upload_speed == 1000.0
    assert sample.total_delta_recv == 1000
    assert sample.total_delta_sent == 1000
    assert sample.selected_interfaces == ("Ethernet",)


def test_rolling_average_smoothing() -> None:
    """Verify rolling average smooths speeds across configured window."""
    source = FakeCounterSource()
    source.set_time(100.0)
    source.set_interface("Ethernet", bytes_sent=0, bytes_recv=0)

    calc = SpeedCalculator(rolling_window_size=3)
    calc.process_snapshot(source.read_counters())

    # Sample 1: 3000 B/s (raw 3000, window [3000], avg = 3000)
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=0, bytes_recv=3000)
    s1 = calc.process_snapshot(source.read_counters())
    assert s1.total_download_speed == 3000.0
    assert s1.total_raw_download_speed == 3000.0

    # Sample 2: 0 B/s (raw 0, window [3000, 0], avg = 1500)
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=0, bytes_recv=3000)
    s2 = calc.process_snapshot(source.read_counters())
    assert s2.total_download_speed == 1500.0
    assert s2.total_raw_download_speed == 0.0

    # Sample 3: 0 B/s (raw 0, window [3000, 0, 0], avg = 1000)
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=0, bytes_recv=3000)
    s3 = calc.process_snapshot(source.read_counters())
    assert s3.total_download_speed == 1000.0
    assert s3.total_raw_download_speed == 0.0

    # Sample 4: 0 B/s (raw 0, window [0, 0, 0], avg = 0)
    source.advance_time(1.0)
    source.set_interface("Ethernet", bytes_sent=0, bytes_recv=3000)
    s4 = calc.process_snapshot(source.read_counters())
    assert s4.total_download_speed == 0.0
    assert s4.total_raw_download_speed == 0.0
