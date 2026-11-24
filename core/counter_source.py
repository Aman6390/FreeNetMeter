"""Network interface counter abstraction layer.

This module defines the abstract interface `CounterSource` and provides:
1. `PsutilCounterSource`: production implementation reading 64-bit Windows network counters.
2. `FakeCounterSource`: controllable in-memory source for unit tests.

Under Windows, psutil calls the Win32 IP Helper API function `GetIfTable2` / `GetIfEntry2`.
The resulting `MIB_IF_ROW2` structures provide 64-bit unsigned integer counters
(`InOctets` and `OutOctets`). This ensures counters do not overflow at 4 GB as
legacy 32-bit `MIB_IFROW` counters did. Even on ultra-high-speed 10 Gbps+ links,
a 64-bit unsigned integer takes hundreds of years of continuous saturation to wrap.
"""

from __future__ import annotations

import abc
import logging
import time
from dataclasses import dataclass
from typing import Mapping

logger = logging.getLogger("FreeNetMeter.CounterSource")


@dataclass(frozen=True)
class InterfaceCounters:
    """Snapshot of traffic counters for a single network interface.

    Attributes:
        bytes_sent: Cumulative count of bytes sent (uploaded). 64-bit unsigned int.
        bytes_recv: Cumulative count of bytes received (downloaded). 64-bit unsigned int.
        packets_sent: Cumulative packets transmitted.
        packets_recv: Cumulative packets received.
        errin: Total input errors.
        errout: Total output errors.
        dropin: Incoming packets dropped.
        dropout: Outgoing packets dropped.
    """

    bytes_sent: int
    bytes_recv: int
    packets_sent: int = 0
    packets_recv: int = 0
    errin: int = 0
    errout: int = 0
    dropin: int = 0
    dropout: int = 0


@dataclass(frozen=True)
class NetworkSnapshot:
    """Point-in-time snapshot of all network interface counters.

    Attributes:
        timestamp: Monotonic time in seconds (from time.monotonic()) when sample was taken.
        counters: Mapping from interface name (e.g. 'Ethernet', 'Wi-Fi') to InterfaceCounters.
    """

    timestamp: float
    counters: Mapping[str, InterfaceCounters]


@dataclass(frozen=True)
class InterfaceStatus:
    """Operating status and metadata of an interface.

    Attributes:
        is_up: True if the link is active and operational.
        speed_mbps: Link speed in Megabits per second (0 if unknown).
    """

    is_up: bool
    speed_mbps: int = 0


class CounterSource(abc.ABC):
    """Abstract interface for sampling network counters and adapter states."""

    @abc.abstractmethod
    def read_counters(self) -> NetworkSnapshot:
        """Sample the current byte counters across all interfaces.

        Returns:
            A NetworkSnapshot containing the monotonic timestamp and per-interface counters.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def read_interface_statuses(self) -> Mapping[str, InterfaceStatus]:
        """Query the operational link status for all interfaces.

        Returns:
            A mapping from interface name to its InterfaceStatus.
        """
        raise NotImplementedError


class PsutilCounterSource(CounterSource):
    """Production implementation of CounterSource using psutil.

    Reads 64-bit network I/O counters via psutil.net_io_counters(pernic=True).
    Under Windows, psutil queries GetIfEntry2 (MIB_IF_ROW2) where InOctets and OutOctets
    are ULONG64 (64-bit unsigned integer values).
    """

    def read_counters(self) -> NetworkSnapshot:
        """Read live network counters using psutil and record the monotonic timestamp.

        Returns:
            NetworkSnapshot with current monotonic timestamp and counters per interface.
        """
        # Import psutil here to keep core logic independent when using FakeCounterSource
        import psutil

        # Record monotonic timestamp immediately prior to sampling to ensure accurate elapsed time
        sample_time = time.monotonic()
        try:
            raw_counters = psutil.net_io_counters(pernic=True) or {}
        except Exception as exc:
            # Handle transient driver reset or system sleep/resume
            logger.warning("Transient error reading psutil network counters: %s", exc)
            raw_counters = {}

        parsed_counters: dict[str, InterfaceCounters] = {}
        for name, counters in raw_counters.items():
            if counters is None:
                continue
            parsed_counters[name] = InterfaceCounters(
                bytes_sent=getattr(counters, "bytes_sent", 0),
                bytes_recv=getattr(counters, "bytes_recv", 0),
                packets_sent=getattr(counters, "packets_sent", 0),
                packets_recv=getattr(counters, "packets_recv", 0),
                errin=getattr(counters, "errin", 0),
                errout=getattr(counters, "errout", 0),
                dropin=getattr(counters, "dropin", 0),
                dropout=getattr(counters, "dropout", 0),
            )

        return NetworkSnapshot(timestamp=sample_time, counters=parsed_counters)

    def read_interface_statuses(self) -> Mapping[str, InterfaceStatus]:
        """Query the link state for all detected network interfaces.

        Returns:
            Mapping of adapter name to InterfaceStatus (is_up, speed_mbps).
        """
        import psutil

        try:
            stats = psutil.net_if_stats()
        except Exception:
            # Fallback if net_if_stats fails on a restricted system
            return {}

        statuses: dict[str, InterfaceStatus] = {}
        for name, stat in stats.items():
            statuses[name] = InterfaceStatus(
                is_up=stat.isup,
                speed_mbps=stat.speed,
            )
        return statuses


class FakeCounterSource(CounterSource):
    """Controllable test double for CounterSource.

    Allows tests to inject specific snapshots, advance monotonic time,
    and simulate network events (counter resets, interface plug/unplug).
    """

    def __init__(self) -> None:
        """Initialize an empty fake counter source."""
        self._current_time: float = 1000.0
        self._counters: dict[str, InterfaceCounters] = {}
        self._statuses: dict[str, InterfaceStatus] = {}

    def set_time(self, timestamp: float) -> None:
        """Manually override current monotonic time."""
        self._current_time = timestamp

    def advance_time(self, seconds: float) -> None:
        """Advance fake monotonic clock by a given duration."""
        self._current_time += seconds

    def set_interface(
        self,
        name: str,
        bytes_sent: int,
        bytes_recv: int,
        is_up: bool = True,
        speed_mbps: int = 1000,
    ) -> None:
        """Configure or update counters and status for an interface."""
        self._counters[name] = InterfaceCounters(
            bytes_sent=bytes_sent,
            bytes_recv=bytes_recv,
        )
        self._statuses[name] = InterfaceStatus(
            is_up=is_up,
            speed_mbps=speed_mbps,
        )

    def remove_interface(self, name: str) -> None:
        """Simulate unplugging an adapter."""
        self._counters.pop(name, None)
        self._statuses.pop(name, None)

    def read_counters(self) -> NetworkSnapshot:
        """Return the programmed snapshot at current fake monotonic time."""
        # Return a copy to prevent test mutation
        return NetworkSnapshot(
            timestamp=self._current_time,
            counters=dict(self._counters),
        )

    def read_interface_statuses(self) -> Mapping[str, InterfaceStatus]:
        """Return programmed interface statuses."""
        return dict(self._statuses)
