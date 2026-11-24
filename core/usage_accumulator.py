"""Data usage accumulator for local calendar day tracking.

Aggregates per-interface raw byte deltas into per-calendar-day totals.
Handles midnight rollovers and daylight saving time (DST) transitions cleanly
by assigning each delta to the local calendar day (YYYY-MM-DD) active at the
moment the sample is processed.

Pending accumulated deltas are buffered in memory and flushed periodically
(and at application shutdown) to SQLite.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Mapping

from core.speed_calculator import InterfaceSpeedResult


@dataclass(frozen=True)
class PendingUsageRecord:
    """A batch of accumulated bytes for a specific calendar date and interface.

    Attributes:
        date_str: Local calendar date in ISO format 'YYYY-MM-DD'.
        interface_name: Name of the network interface.
        bytes_sent: Cumulative bytes sent since last flush.
        bytes_recv: Cumulative bytes received since last flush.
    """

    date_str: str
    interface_name: str
    bytes_sent: int
    bytes_recv: int


class UsageAccumulator:
    """Accumulates raw byte deltas per interface per local calendar day."""

    def __init__(
        self,
        date_provider: Callable[[], str] | None = None,
    ) -> None:
        """Initialize usage accumulator.

        Args:
            date_provider: Optional callable returning 'YYYY-MM-DD' in local time.
                           If None, defaults to datetime.now().strftime("%Y-%m-%d").
        """
        self._date_provider = date_provider or self._default_local_date

        # Buffer of pending deltas: (date_str, interface_name) -> [bytes_sent, bytes_recv]
        self._pending: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])

    @staticmethod
    def _default_local_date() -> str:
        """Get current local calendar date string 'YYYY-MM-DD'."""
        # Using datetime.now().astimezone() respects Windows local timezone and DST shifts
        return datetime.datetime.now().astimezone().strftime("%Y-%m-%d")

    def record_sample(
        self,
        per_interface_results: Mapping[str, InterfaceSpeedResult],
        override_date: str | None = None,
    ) -> None:
        """Record raw byte deltas from a SpeedSample.

        Correctness Rule 8:
        Each delta is stamped with the current local calendar date. When a sample
        arrives after midnight, deltas automatically map to the new date.

        Args:
            per_interface_results: Mapping from interface name to InterfaceSpeedResult.
            override_date: Optional manual date string for testing midnight rollover.
        """
        current_date = override_date or self._date_provider()

        for iface_name, result in per_interface_results.items():
            delta_sent = result.delta_bytes_sent
            delta_recv = result.delta_bytes_recv

            # Discard any negative or zero deltas
            if delta_sent <= 0 and delta_recv <= 0:
                continue

            # Add deltas to the date/interface buffer
            key = (current_date, iface_name)
            self._pending[key][0] += max(0, delta_sent)
            self._pending[key][1] += max(0, delta_recv)

    def has_pending(self) -> bool:
        """Return True if there are uncommitted byte deltas in memory."""
        return any(sent > 0 or recv > 0 for sent, recv in self._pending.values())

    def flush_pending(self) -> list[PendingUsageRecord]:
        """Extract all pending usage records and reset the in-memory buffer.

        Returns:
            List of PendingUsageRecord ready for transactional SQLite insertion.
        """
        if not self._pending:
            return []

        records: list[PendingUsageRecord] = []
        for (date_str, iface_name), (sent, recv) in self._pending.items():
            if sent > 0 or recv > 0:
                records.append(
                    PendingUsageRecord(
                        date_str=date_str,
                        interface_name=iface_name,
                        bytes_sent=sent,
                        bytes_recv=recv,
                    )
                )

        self._pending.clear()
        return records
