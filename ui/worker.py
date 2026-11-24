"""Background sampling and persistence worker thread.

Runs all network counter sampling, speed calculations, and SQLite writes
off the Qt GUI thread. Results are communicated to the UI exclusively via
thread-safe Qt signals.
"""

from __future__ import annotations

import logging
import time
from typing import Sequence

from PyQt6.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from core.constants import (
    SAMPLE_INTERVAL_SECONDS,
    USAGE_FLUSH_INTERVAL_SECONDS,
)
from core.counter_source import CounterSource
from core.interface_filter import InterfaceFilter
from core.speed_calculator import SpeedCalculator, SpeedSample
from core.usage_accumulator import UsageAccumulator
from storage.usage_database import UsageDatabase

logger = logging.getLogger("FreeNetMeter.Worker")


class SamplingWorker(QThread):
    """QThread performing periodic counter reads and usage flushes off the UI thread."""

    # Thread-safe signal delivering calculated speed metrics to UI
    speed_updated = pyqtSignal(SpeedSample)

    # Signal notifying UI when a database flush occurs
    database_flushed = pyqtSignal(int)

    def __init__(
        self,
        counter_source: CounterSource,
        speed_calculator: SpeedCalculator,
        usage_accumulator: UsageAccumulator,
        usage_database: UsageDatabase,
        interface_filter: InterfaceFilter,
        sample_interval: float = SAMPLE_INTERVAL_SECONDS,
        flush_interval: float = USAGE_FLUSH_INTERVAL_SECONDS,
        parent: QThread | None = None,
    ) -> None:
        """Initialize sampling worker.

        Args:
            counter_source: Source providing network byte counters.
            speed_calculator: Pure logic speed calculation engine.
            usage_accumulator: In-memory delta accumulator for daily usage.
            usage_database: SQLite usage storage instance.
            interface_filter: Filter managing adapter exclusion/selection.
            sample_interval: Seconds between counter samples (default 1.0s).
            flush_interval: Seconds between database commits (default 30.0s).
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._source = counter_source
        self._calculator = speed_calculator
        self._accumulator = usage_accumulator
        self._database = usage_database
        self._filter = interface_filter

        self._sample_interval = max(0.05, sample_interval)
        self._flush_interval = max(0.1, flush_interval)

        # Mutex protecting dynamically updated settings
        self._mutex = QMutex()
        self._selected_interfaces: list[str] | None = None
        self._last_flush_time: float = 0.0
        self._is_paused: bool = False
        self._needs_rebaseline: bool = False
        self._auto_select_nic: bool = True

    def set_paused(self, paused: bool) -> None:
        """Pause or resume sampling thread without losing historical counters."""
        with QMutexLocker(self._mutex):
            self._is_paused = paused
            if not paused:
                self._needs_rebaseline = True

    def refresh_connection(self) -> None:
        """Trigger an immediate re-scan and counter re-baselining."""
        with QMutexLocker(self._mutex):
            self._needs_rebaseline = True

    def set_auto_select_nic(self, auto: bool) -> None:
        """Set whether to automatically select active physical interfaces."""
        with QMutexLocker(self._mutex):
            self._auto_select_nic = auto

    def update_selected_interfaces(self, interfaces: Sequence[str] | None) -> None:
        """Thread-safely update user's selected network interfaces."""
        with QMutexLocker(self._mutex):
            self._selected_interfaces = list(interfaces) if interfaces is not None else None

    def update_rolling_window(self, window_size: int) -> None:
        """Thread-safely update speed calculator rolling window size."""
        with QMutexLocker(self._mutex):
            self._calculator.set_rolling_window_size(window_size)

    def update_sample_interval(self, interval: float) -> None:
        """Thread-safely update counter sampling interval in seconds."""
        with QMutexLocker(self._mutex):
            self._sample_interval = max(0.05, min(10.0, interval))

    def trigger_immediate_flush(self) -> None:
        """Request an immediate database flush off the UI thread."""
        self._flush_database()

    def _flush_database(self) -> None:
        """Extract uncommitted byte deltas and persist to SQLite."""
        with QMutexLocker(self._mutex):
            records = self._accumulator.flush_pending()

        if records:
            try:
                self._database.record_usage_batch(records)
                self.database_flushed.emit(len(records))
            except Exception as exc:
                logger.error("Failed to flush usage to database: %s", exc)

        self._last_flush_time = time.monotonic()

    def run(self) -> None:
        """Worker thread main execution loop.

        Runs once per sample_interval. Checks for interruption requests
        every 100ms to guarantee responsive application termination.
        """
        logger.info("Sampling worker thread started.")
        self._last_flush_time = time.monotonic()

        # Step 1: Initial baseline sample
        try:
            initial_snapshot = self._source.read_counters()
            with QMutexLocker(self._mutex):
                self._calculator.process_snapshot(initial_snapshot)
        except Exception as exc:
            logger.error("Initial counter sampling failed: %s", exc)

        # Step 2: Main monitoring loop
        while not self.isInterruptionRequested():
            with QMutexLocker(self._mutex):
                current_interval = self._sample_interval
                is_paused = self._is_paused
                needs_rebaseline = self._needs_rebaseline
                if needs_rebaseline:
                    self._needs_rebaseline = False

            if is_paused:
                self.msleep(200)
                continue

            # Wait for next sample interval in 100ms slices for fast cancellation
            sleep_slices = max(1, int(current_interval * 10))
            for _ in range(sleep_slices):
                if self.isInterruptionRequested():
                    break
                self.msleep(100)

            if self.isInterruptionRequested():
                break

            try:
                # Sample counters and link statuses off the UI thread
                snapshot = self._source.read_counters()
                statuses = self._source.read_interface_statuses()

                if needs_rebaseline:
                    with QMutexLocker(self._mutex):
                        self._calculator.process_snapshot(snapshot)
                    continue

                # Determine active interfaces to include
                with QMutexLocker(self._mutex):
                    user_pref = None if self._auto_select_nic else self._selected_interfaces
                    active_selection = self._filter.resolve_active_selection(
                        list(snapshot.counters.keys()),
                        user_pref,
                        statuses,
                    )
                    sample = self._calculator.process_snapshot(
                        snapshot,
                        selected_interfaces=active_selection,
                    )

                    # Accumulate deltas into memory
                    self._accumulator.record_sample(sample.per_interface)

                # Emit calculated sample to UI thread
                self.speed_updated.emit(sample)

                # Check if periodic SQLite flush is due
                now = time.monotonic()
                if now - self._last_flush_time >= self._flush_interval:
                    self._flush_database()

            except Exception as exc:
                logger.error("Unexpected error in sampling loop: %s", exc, exc_info=True)

        # Step 3: Final shutdown flush
        logger.info("Sampling worker stopping. Performing final database flush...")
        self._flush_database()
        logger.info("Sampling worker thread terminated gracefully.")
