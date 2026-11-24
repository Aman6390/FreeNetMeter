"""Speed calculation engine.

Transforms discrete counter snapshots into instant and smoothed transfer speeds
and raw byte deltas per interface and across selected interface sets.

Correctness invariants implemented here:
1. Exact timing: speed is always computed as (delta bytes) / (elapsed seconds) from time.monotonic().
2. Counter resets: if current counter < previous counter, treat as adapter reset/reboot.
   Delta is clamped to 0, speed is 0, and the baseline is reset to the current counter.
3. 64-bit counter safety: Windows GetIfEntry2 provides 64-bit unsigned integer counters.
   Any negative delta or wrap-around is safely caught and re-baselined.
4. Sleep and resume: if elapsed time between samples > max_gap_seconds (default 5.0 s),
   the gap is treated as a sleep period. Baseline is updated without computing speed or usage.
5. Tiny intervals: if elapsed time < min_interval_seconds (0.2 s), sample is skipped to avoid division by zero.
6. Dynamic interfaces: interfaces can appear or disappear at any time without crashes or double-counting.
7. Rolling smoothing: rolling average (default 3 samples) for smooth UI display while maintaining
   exact raw deltas for the usage database.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from core.constants import (
    DEFAULT_ROLLING_WINDOW_SIZE,
    MAX_SAMPLE_GAP_SECONDS,
    MIN_SAMPLE_INTERVAL_SECONDS,
)
from core.counter_source import InterfaceCounters, NetworkSnapshot


@dataclass(frozen=True)
class InterfaceSpeedResult:
    """Speed and byte delta metrics for a single network interface.

    Attributes:
        interface_name: Name of the network interface.
        download_speed: Smoothed download speed in bytes per second.
        upload_speed: Smoothed upload speed in bytes per second.
        raw_download_speed: Instantaneous unsmoothed download speed in bytes per second.
        raw_upload_speed: Instantaneous unsmoothed upload speed in bytes per second.
        delta_bytes_recv: Exact raw bytes downloaded since previous sample.
        delta_bytes_sent: Exact raw bytes uploaded since previous sample.
    """

    interface_name: str
    download_speed: float
    upload_speed: float
    raw_download_speed: float
    raw_upload_speed: float
    delta_bytes_recv: int
    delta_bytes_sent: int


@dataclass(frozen=True)
class SpeedSample:
    """Consolidated speed and usage measurement for a single sampling interval.

    Attributes:
        timestamp: Monotonic timestamp of the current sample.
        elapsed_seconds: Elapsed monotonic seconds since the baseline sample.
        total_download_speed: Smoothed download speed across all selected interfaces (B/s).
        total_upload_speed: Smoothed upload speed across all selected interfaces (B/s).
        total_raw_download_speed: Raw download speed across selected interfaces (B/s).
        total_raw_upload_speed: Raw upload speed across selected interfaces (B/s).
        total_delta_recv: Sum of raw bytes received across selected interfaces.
        total_delta_sent: Sum of raw bytes sent across selected interfaces.
        per_interface: Speed and delta results keyed by interface name.
        selected_interfaces: Tuple of interface names included in the total.
        is_gap: True if this sample followed a system sleep/resume or gap.
    """

    timestamp: float
    elapsed_seconds: float
    total_download_speed: float
    total_upload_speed: float
    total_raw_download_speed: float
    total_raw_upload_speed: float
    total_delta_recv: int
    total_delta_sent: int
    per_interface: Mapping[str, InterfaceSpeedResult]
    selected_interfaces: tuple[str, ...]
    is_gap: bool = False


@dataclass
class _InterfaceHistory:
    """Internal tracker for an interface's previous counters and rolling speeds."""

    last_counters: InterfaceCounters
    download_history: deque[float] = field(default_factory=deque)
    upload_history: deque[float] = field(default_factory=deque)


class SpeedCalculator:
    """Calculates network speeds from snapshots with robust error-handling and smoothing."""

    def __init__(
        self,
        min_interval: float = MIN_SAMPLE_INTERVAL_SECONDS,
        max_gap: float = MAX_SAMPLE_GAP_SECONDS,
        rolling_window_size: int = DEFAULT_ROLLING_WINDOW_SIZE,
    ) -> None:
        """Initialize the speed calculator.

        Args:
            min_interval: Minimum elapsed seconds to compute speed (avoids div by zero).
            max_gap: Maximum elapsed seconds before treating interval as sleep/resume.
            rolling_window_size: Number of samples to include in the rolling average.
        """
        self._min_interval: float = min_interval
        self._max_gap: float = max_gap
        self._rolling_window_size: int = max(1, rolling_window_size)

        # Baseline timestamp and state tracker
        self._last_timestamp: float | None = None
        self._history: dict[str, _InterfaceHistory] = {}

    def set_rolling_window_size(self, size: int) -> None:
        """Update rolling average window size dynamically."""
        self._rolling_window_size = max(1, size)
        # Resize existing rolling deques
        for hist in self._history.values():
            hist.download_history = deque(hist.download_history, maxlen=self._rolling_window_size)
            hist.upload_history = deque(hist.upload_history, maxlen=self._rolling_window_size)

    def reset(self) -> None:
        """Clear all historical baselines and history."""
        self._last_timestamp = None
        self._history.clear()

    def process_snapshot(
        self,
        snapshot: NetworkSnapshot,
        selected_interfaces: Sequence[str] | None = None,
    ) -> SpeedSample:
        """Process a new network counter snapshot and return calculated speeds.

        Args:
            snapshot: Current NetworkSnapshot from CounterSource.
            selected_interfaces: List of interface names to include in totals.
                                 If None, all present interfaces are included.

        Returns:
            SpeedSample with per-interface metrics and totals.
        """
        current_time = snapshot.timestamp
        current_counters = snapshot.counters

        # Deduplicate and normalize selected interfaces to prevent double-counting
        if selected_interfaces is not None:
            # Preserve deterministic order while ensuring uniqueness
            seen: set[str] = set()
            normalized_selected: list[str] = []
            for iface in selected_interfaces:
                if iface not in seen:
                    seen.add(iface)
                    normalized_selected.append(iface)
            active_selected = tuple(normalized_selected)
        else:
            active_selected = tuple(sorted(current_counters.keys()))

        # Initial baseline snapshot: no speed can be computed yet
        if self._last_timestamp is None:
            self._last_timestamp = current_time
            for name, counters in current_counters.items():
                self._history[name] = _InterfaceHistory(
                    last_counters=counters,
                    download_history=deque(maxlen=self._rolling_window_size),
                    upload_history=deque(maxlen=self._rolling_window_size),
                )
            return SpeedSample(
                timestamp=current_time,
                elapsed_seconds=0.0,
                total_download_speed=0.0,
                total_upload_speed=0.0,
                total_raw_download_speed=0.0,
                total_raw_upload_speed=0.0,
                total_delta_recv=0,
                total_delta_sent=0,
                per_interface={},
                selected_interfaces=active_selected,
                is_gap=False,
            )

        # Compute elapsed time using high-resolution monotonic clock
        elapsed = current_time - self._last_timestamp

        # Correctness Rule 5: Tiny intervals (e.g. clock jitter, rapid trigger)
        # If elapsed time is below threshold, return 0 delta and keep previous baseline
        if elapsed < self._min_interval:
            return SpeedSample(
                timestamp=current_time,
                elapsed_seconds=elapsed,
                total_download_speed=0.0,
                total_upload_speed=0.0,
                total_raw_download_speed=0.0,
                total_raw_upload_speed=0.0,
                total_delta_recv=0,
                total_delta_sent=0,
                per_interface={},
                selected_interfaces=active_selected,
                is_gap=False,
            )

        # Correctness Rule 4: Sleep and resume detection
        # If gap exceeds threshold (e.g. machine went to sleep), re-baseline without computing speed
        if elapsed > self._max_gap:
            self._last_timestamp = current_time
            # Update baseline counters to current values, reset history, produce no speed or usage
            for name, counters in current_counters.items():
                if name in self._history:
                    self._history[name].last_counters = counters
                    self._history[name].download_history.clear()
                    self._history[name].upload_history.clear()
                else:
                    self._history[name] = _InterfaceHistory(
                        last_counters=counters,
                        download_history=deque(maxlen=self._rolling_window_size),
                        upload_history=deque(maxlen=self._rolling_window_size),
                    )
            return SpeedSample(
                timestamp=current_time,
                elapsed_seconds=elapsed,
                total_download_speed=0.0,
                total_upload_speed=0.0,
                total_raw_download_speed=0.0,
                total_raw_upload_speed=0.0,
                total_delta_recv=0,
                total_delta_sent=0,
                per_interface={},
                selected_interfaces=active_selected,
                is_gap=True,
            )

        # Clean up interfaces that disappeared (unplugged or disconnected)
        current_names = set(current_counters.keys())
        disappeared = set(self._history.keys()) - current_names
        for name in disappeared:
            del self._history[name]

        per_interface_results: dict[str, InterfaceSpeedResult] = {}
        total_raw_down = 0.0
        total_raw_up = 0.0
        total_delta_recv = 0
        total_delta_sent = 0
        total_smoothed_down = 0.0
        total_smoothed_up = 0.0

        # Calculate per-interface speeds
        for name, counters in current_counters.items():
            hist = self._history.get(name)

            # Correctness Rule 6: New interface appeared
            if hist is None:
                # Initialize new baseline, speed and delta start at 0
                self._history[name] = _InterfaceHistory(
                    last_counters=counters,
                    download_history=deque([0.0], maxlen=self._rolling_window_size),
                    upload_history=deque([0.0], maxlen=self._rolling_window_size),
                )
                per_interface_results[name] = InterfaceSpeedResult(
                    interface_name=name,
                    download_speed=0.0,
                    upload_speed=0.0,
                    raw_download_speed=0.0,
                    raw_upload_speed=0.0,
                    delta_bytes_recv=0,
                    delta_bytes_sent=0,
                )
                continue

            # Calculate raw byte deltas
            prev = hist.last_counters
            delta_recv = counters.bytes_recv - prev.bytes_recv
            delta_sent = counters.bytes_sent - prev.bytes_sent

            # Correctness Rule 2 & 3: Counter resets or 64-bit counter wraps
            # If counter value decreased, adapter reset occurred. Re-baseline and drop delta.
            if delta_recv < 0 or delta_sent < 0:
                hist.last_counters = counters
                hist.download_history.clear()
                hist.upload_history.clear()
                per_interface_results[name] = InterfaceSpeedResult(
                    interface_name=name,
                    download_speed=0.0,
                    upload_speed=0.0,
                    raw_download_speed=0.0,
                    raw_upload_speed=0.0,
                    delta_bytes_recv=0,
                    delta_bytes_sent=0,
                )
                continue

            # Valid normal delta: update baseline
            hist.last_counters = counters

            # Instantaneous raw speed in bytes per second
            raw_down_speed = delta_recv / elapsed
            raw_up_speed = delta_sent / elapsed

            # Update rolling history for smoothing
            hist.download_history.append(raw_down_speed)
            hist.upload_history.append(raw_up_speed)

            # Calculate smoothed rolling average
            smoothed_down = sum(hist.download_history) / len(hist.download_history)
            smoothed_up = sum(hist.upload_history) / len(hist.upload_history)

            result = InterfaceSpeedResult(
                interface_name=name,
                download_speed=smoothed_down,
                upload_speed=smoothed_up,
                raw_download_speed=raw_down_speed,
                raw_upload_speed=raw_up_speed,
                delta_bytes_recv=delta_recv,
                delta_bytes_sent=delta_sent,
            )
            per_interface_results[name] = result

            # Accumulate totals only for selected interfaces
            if name in active_selected:
                total_raw_down += raw_down_speed
                total_raw_up += raw_up_speed
                total_delta_recv += delta_recv
                total_delta_sent += delta_sent
                total_smoothed_down += smoothed_down
                total_smoothed_up += smoothed_up

        # Advance baseline timestamp for next sample
        self._last_timestamp = current_time

        return SpeedSample(
            timestamp=current_time,
            elapsed_seconds=elapsed,
            total_download_speed=total_smoothed_down,
            total_upload_speed=total_smoothed_up,
            total_raw_download_speed=total_raw_down,
            total_raw_upload_speed=total_raw_up,
            total_delta_recv=total_delta_recv,
            total_delta_sent=total_delta_sent,
            per_interface=per_interface_results,
            selected_interfaces=active_selected,
            is_gap=False,
        )
