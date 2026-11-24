"""Windows System Network Shortcuts and Diagnostic Quick Links.

Provides safe, sandboxed shortcuts to native Windows diagnostic utilities:
- Network Connections (ncpa.cpl)
- Network & Internet Settings (ms-settings:network)
- Windows Resource Monitor (resmon.exe /net)
- Task Manager (taskmgr.exe)
- Device Manager (devmgmt.msc)
- Windows Defender Firewall (firewall.cpl)
- External Speed Test (launches browser to Cloudflare Speed Test)

Security: Never invokes shell=True; uses explicit subprocess argument lists
or os.startfile for Windows shell protocols.
"""

from __future__ import annotations

import logging
import os
import subprocess
import webbrowser
from typing import Sequence

logger = logging.getLogger("FreeNetMeter.QuickLinks")


def _safe_launch_command(cmd: Sequence[str]) -> bool:
    """Launch a local Windows process safely using explicit arguments.

    Args:
        cmd: List of executable and arguments.

    Returns:
        True if process launched successfully, False otherwise.
    """
    try:
        subprocess.Popen(
            list(cmd),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (FileNotFoundError, OSError, PermissionError) as exc:
        logger.error("Failed to launch command %s: %s", cmd, exc)
        return False


def _safe_start_file(target: str) -> bool:
    """Launch a Windows shell target or protocol URL via os.startfile.

    Args:
        target: File path, control panel applet, or URI protocol.

    Returns:
        True if launched successfully, False otherwise.
    """
    try:
        os.startfile(target)
        return True
    except (FileNotFoundError, OSError, PermissionError) as exc:
        logger.error("Failed to open target '%s': %s", target, exc)
        return False


def open_network_connections() -> bool:
    """Open Windows Classic Network Connections (ncpa.cpl)."""
    return _safe_start_file("ncpa.cpl") or _safe_launch_command(["control.exe", "netconnections"])


def open_network_settings() -> bool:
    """Open Modern Windows Network & Internet Settings (ms-settings:network)."""
    return _safe_start_file("ms-settings:network")


def open_resource_monitor() -> bool:
    """Open Windows Resource Monitor focused on the Network tab."""
    # resmon.exe is standard on all 64-bit Windows installations in System32
    return _safe_launch_command(["resmon.exe", "/net"]) or _safe_launch_command(["resmon.exe"])


def open_task_manager() -> bool:
    """Open Windows Task Manager."""
    return _safe_launch_command(["taskmgr.exe"])


def open_device_manager() -> bool:
    """Open Windows Device Manager (devmgmt.msc)."""
    return _safe_start_file("devmgmt.msc") or _safe_launch_command(["mmc.exe", "devmgmt.msc"])


def open_firewall() -> bool:
    """Open Windows Defender Firewall (firewall.cpl)."""
    return _safe_start_file("firewall.cpl") or _safe_launch_command(["control.exe", "firewall.cpl"])


def open_speed_test(url: str = "https://speed.cloudflare.com/") -> bool:
    """Open trusted speed test website in the user's default browser."""
    try:
        webbrowser.open(url)
        return True
    except Exception as exc:
        logger.error("Failed to open browser speed test: %s", exc)
        return False
