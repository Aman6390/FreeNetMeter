"""Entry point for FreeNetMeter.

Coordinates CLI arguments, single-instance lifecycle enforcement, High-DPI
configuration, and Qt application initialization.

Usage:
    python main.py                 # Standard GUI launch (widget + tray)
    python main.py --debug-speeds  # Live console debug stream for Task Manager comparison
    python main.py --version       # Print version information and exit
"""

from __future__ import annotations

import argparse
import sys
import time
from platform.single_instance import SingleInstanceGuard

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.constants import APP_NAME, APP_VERSION
from core.counter_source import PsutilCounterSource
from core.formatter import SpeedFormatter
from core.interface_filter import InterfaceFilter
from core.speed_calculator import SpeedCalculator
from storage.settings_store import SettingsStore
from ui.assets import create_app_icon


def run_debug_speeds() -> None:
    """Run interactive console telemetry stream (Priority 11.B).

    Prints one line per second with the per-interface and total download and
    upload speeds in bytes per second and in formatted display units, plus the
    elapsed time between samples. Runs headlessly without GUI so the user can
    conveniently compare the numbers with Windows Task Manager's Performance tab.
    """
    print(f"=== {APP_NAME} v{APP_VERSION} Live Speed Debug Stream ===")
    print("Sampling live network throughput once per second off psutil.")
    print("Compare these numbers with Windows Task Manager > Performance tab > Network Adapter.")
    print("Press Ctrl+C to stop.\n")

    settings_store = SettingsStore()
    settings = settings_store.load()
    formatter = SpeedFormatter(
        unit_system=settings.unit_system,
        unit_type=settings.unit_type,
        fixed_unit=settings.fixed_unit,
        precision=settings.decimal_precision,
    )

    source = PsutilCounterSource()
    filt = InterfaceFilter(excluded_keywords=settings.excluded_keywords)
    calculator = SpeedCalculator(rolling_window_size=1)  # Raw instant speed for debug

    # Baseline sample
    snap0 = source.read_counters()
    calculator.process_snapshot(snap0)

    try:
        while True:
            time.sleep(1.0)
            snapshot = source.read_counters()
            statuses = source.read_interface_statuses()
            active_ifaces = filt.resolve_active_selection(
                list(snapshot.counters.keys()),
                settings.selected_interfaces,
                statuses,
            )
            sample = calculator.process_snapshot(snapshot, selected_interfaces=active_ifaces)

            fmt_down = formatter.format_speed(sample.total_download_speed)
            fmt_up = formatter.format_speed(sample.total_upload_speed)

            # Per-interface breakdown summary
            iface_parts: list[str] = []
            for iface_name in sample.selected_interfaces:
                iface_res = sample.per_interface.get(iface_name)
                if iface_res:
                    d_str = formatter.format_speed(iface_res.download_speed).full_str
                    u_str = formatter.format_speed(iface_res.upload_speed).full_str
                    iface_parts.append(f"{iface_name}: [Down: {d_str}, Up: {u_str}]")

            iface_summary = " | ".join(iface_parts) if iface_parts else "No active interfaces"

            print(
                f"[{sample.elapsed_seconds:.2f}s] "
                f"TOTAL: Down: {sample.total_download_speed:10.0f} B/s ({fmt_down.full_str:>10}) | "
                f"Up: {sample.total_upload_speed:10.0f} B/s ({fmt_up.full_str:>10}) || "
                f"{iface_summary}"
            )
            sys.stdout.flush()

    except KeyboardInterrupt:
        print(f"\n{APP_NAME} debug speed monitor stopped.")
        sys.exit(0)


def main() -> None:
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME}: Production-quality, open-source network speed meter for Windows."
    )
    parser.add_argument(
        "--debug-speeds",
        action="store_true",
        help="Run headless console stream comparing throughput directly against Task Manager.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )

    args = parser.parse_args()

    # Handle console debug stream mode
    if args.debug_speeds:
        run_debug_speeds()
        return

    # Enable High-DPI PassThrough scaling on Windows displays
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    # Initialize QApplication
    qapp = QApplication(sys.argv)
    qapp.setApplicationName(APP_NAME)
    qapp.setApplicationVersion(APP_VERSION)
    qapp.setOrganizationName(APP_NAME)
    qapp.setWindowIcon(create_app_icon())

    # Prevent application from closing when widget is hidden
    qapp.setQuitOnLastWindowClosed(False)

    # Check Single Instance Guard
    guard = SingleInstanceGuard()
    if not guard.try_acquire():
        # Secondary instance launch: notified running instance and terminating cleanly
        print(f"{APP_NAME} is already running. Brought existing window to front.")
        sys.exit(0)

    # Import and wire main application
    from app import FreeNetMeterApp

    app_instance = FreeNetMeterApp(qapp=qapp, single_instance_guard=guard)
    app_instance.start()

    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
