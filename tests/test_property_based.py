"""Property-based tests for mathematical invariants in speed and usage calculations.

Uses hypothesis to generate arbitrary sequences of counter values, time jumps,
and adapter events, verifying that:
1. Speed outputs are strictly >= 0.0 (never negative, NaN, or infinite).
2. Data usage delta accumulations are strictly >= 0.
3. Formatted outputs never contain negative signs or NaN/inf representations.
"""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from core.counter_source import FakeCounterSource
from core.formatter import SpeedFormatter
from core.speed_calculator import SpeedCalculator
from core.usage_accumulator import UsageAccumulator


@settings(max_examples=100, deadline=None)
@given(
    # Sequence of (delta_time, bytes_sent, bytes_recv)
    st.lists(
        st.tuples(
            st.floats(min_value=-5.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            st.integers(min_value=0, max_value=(1 << 64) - 1),
            st.integers(min_value=0, max_value=(1 << 64) - 1),
        ),
        min_size=2,
        max_size=30,
    )
)
def test_hypothesis_speed_and_usage_never_negative(
    samples: list[tuple[float, int, int]],
) -> None:
    """Prove that for any sequence of counter transitions, speeds and usages are non-negative."""
    source = FakeCounterSource()
    calc = SpeedCalculator()
    acc = UsageAccumulator(date_provider=lambda: "2026-11-09")
    fmt = SpeedFormatter()

    current_time = 1000.0
    source.set_time(current_time)

    for delta_t, b_sent, b_recv in samples:
        # Advance time safely (skip or handle non-positive delta_t)
        if delta_t > 0:
            current_time += delta_t
        source.set_time(current_time)
        source.set_interface("TestAdapter", bytes_sent=b_sent, bytes_recv=b_recv)

        snapshot = source.read_counters()
        speed_sample = calc.process_snapshot(snapshot)

        # Invariant 1: Speed outputs are finite and non-negative
        assert not math.isnan(speed_sample.total_download_speed)
        assert not math.isinf(speed_sample.total_download_speed)
        assert speed_sample.total_download_speed >= 0.0

        assert not math.isnan(speed_sample.total_upload_speed)
        assert not math.isinf(speed_sample.total_upload_speed)
        assert speed_sample.total_upload_speed >= 0.0

        # Invariant 2: Byte deltas are strictly non-negative
        assert speed_sample.total_delta_recv >= 0
        assert speed_sample.total_delta_sent >= 0

        # Feed into accumulator
        acc.record_sample(speed_sample.per_interface)

        # Invariant 3: Formatted strings never have '-' or 'nan'
        fmt_down = fmt.format_speed(speed_sample.total_download_speed)
        fmt_up = fmt.format_speed(speed_sample.total_upload_speed)
        assert "-" not in fmt_down.value_str
        assert "nan" not in fmt_down.value_str.lower()
        assert "inf" not in fmt_down.value_str.lower()
        assert "-" not in fmt_up.value_str
        assert "nan" not in fmt_up.value_str.lower()
        assert "inf" not in fmt_up.value_str.lower()

    # Flush accumulator and verify stored values are non-negative
    pending = acc.flush_pending()
    for record in pending:
        assert record.bytes_sent >= 0
        assert record.bytes_recv >= 0
