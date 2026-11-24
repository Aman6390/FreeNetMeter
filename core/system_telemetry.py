"""System telemetry extractor for hardware and operating system badges.

Extracts:
- Hostname
- CPU model name (from Windows registry with platform fallback)
- Installed RAM and current memory utilization
- Windows OS edition and build
- System uptime since boot
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("FreeNetMeter.Telemetry")


@dataclass(frozen=True)
class SystemBadgeInfo:
    """Snapshot of host system telemetry badges."""

    hostname: str
    cpu_name: str
    ram_display: str
    ram_total_gb: float
    ram_used_percent: float
    os_display: str
    uptime_display: str


def get_cpu_model_name() -> str:
    """Retrieve clean CPU model name on Windows."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        )
        val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        winreg.CloseKey(key)
        name = str(val).strip()
        if name:
            return name
    except Exception as exc:
        logger.debug("Could not read CPU name from registry: %s", exc)

    fallback = os.environ.get("PROCESSOR_IDENTIFIER", "Intel / AMD Processor")
    return fallback.strip()


def get_os_display_name() -> str:
    """Retrieve user-friendly Windows version name."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        try:
            prod_name, _ = winreg.QueryValueEx(key, "ProductName")
            winreg.CloseKey(key)
            if prod_name:
                return str(prod_name).strip()
        except Exception:
            winreg.CloseKey(key)
    except Exception:
        pass

    ver = sys.getwindowsversion() if hasattr(sys, "getwindowsversion") else None
    if ver is not None:
        return f"Windows {ver.major}"
    return "Windows 10 / 11"


def format_uptime(boot_time_seconds: float) -> str:
    """Format elapsed seconds since boot into 'Up Xd Yh' or 'Up Xh Ym'."""
    now = time.time()
    uptime_s = max(0.0, now - boot_time_seconds)
    days = int(uptime_s // 86400)
    hours = int((uptime_s % 86400) // 3600)
    mins = int((uptime_s % 3600) // 60)

    if days > 0:
        return f"Up {days}d {hours}h"
    elif hours > 0:
        return f"Up {hours}h {mins}m"
    else:
        return f"Up {mins}m"


class SystemTelemetryProvider:
    """Queries and caches system hardware telemetry."""

    def __init__(self) -> None:
        self._cached_cpu: Optional[str] = None
        self._cached_os: Optional[str] = None

    def get_snapshot(self) -> SystemBadgeInfo:
        """Query fresh system metrics."""
        import psutil

        hostname = socket.gethostname() or "Localhost"

        if self._cached_cpu is None:
            self._cached_cpu = get_cpu_model_name()
        if self._cached_os is None:
            self._cached_os = get_os_display_name()

        # RAM telemetry
        try:
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            ram_display = f"{total_gb:.1f} GB RAM"
            used_pct = mem.percent
        except Exception:
            total_gb = 0.0
            ram_display = "RAM Info N/A"
            used_pct = 0.0

        # Uptime
        try:
            b_time = psutil.boot_time()
            uptime_str = format_uptime(b_time)
        except Exception:
            uptime_str = "Up --"

        return SystemBadgeInfo(
            hostname=hostname,
            cpu_name=self._cached_cpu,
            ram_display=ram_display,
            ram_total_gb=total_gb,
            ram_used_percent=used_pct,
            os_display=self._cached_os,
            uptime_display=uptime_str,
        )
