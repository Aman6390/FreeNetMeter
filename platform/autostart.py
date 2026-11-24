"""Windows autostart integration via HKCU Run registry key.

Allows FreeNetMeter to start automatically when the user logs into Windows.
Operates strictly in HKEY_CURRENT_USER (HKCU) so standard user privileges
are sufficient and administrative elevation is never requested.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from core.constants import (
    REGISTRY_AUTOSTART_KEY,
    REGISTRY_AUTOSTART_VALUE_NAME,
)

logger = logging.getLogger("FreeNetMeter.Autostart")


class WindowsAutostartManager:
    """Manages Windows startup registry entry under HKCU."""

    def __init__(
        self,
        value_name: str = REGISTRY_AUTOSTART_VALUE_NAME,
        key_path: str = REGISTRY_AUTOSTART_KEY,
    ) -> None:
        """Initialize autostart manager.

        Args:
            value_name: Registry value name (e.g. 'FreeNetMeter').
            key_path: Relative registry path under HKCU.
        """
        self.value_name = value_name
        self.key_path = key_path

    @staticmethod
    def get_default_command() -> str:
        """Construct the launch command for the current executable or script.

        If running as a frozen PyInstaller binary, returns the quoted exe path.
        If running as a Python script, returns pythonw.exe (or python.exe) with quoted script path.
        """
        if getattr(sys, "frozen", False):
            # Running as compiled PyInstaller executable
            return f'"{sys.executable}"'

        # Running from source: prefer pythonw.exe to suppress console window on startup
        executable = Path(sys.executable)
        pythonw = executable.with_name("pythonw.exe")
        python_bin = pythonw if pythonw.exists() else executable

        # Path to main.py
        main_py = Path(__file__).resolve().parent.parent / "main.py"
        return f'"{python_bin}" "{main_py}"'

    def is_enabled(self) -> bool:
        """Check whether FreeNetMeter is currently registered to start with Windows.

        Returns:
            True if registry value exists in HKCU Run key, False otherwise.
        """
        if sys.platform != "win32":
            return False

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.key_path,
                0,
                winreg.KEY_READ,
            ) as key:
                try:
                    val, _ = winreg.QueryValueEx(key, self.value_name)
                    return bool(val)
                except FileNotFoundError:
                    return False
        except Exception as exc:
            logger.warning("Failed to read autostart registry entry: %s", exc)
            return False

    def set_enabled(self, enabled: bool, command: str | None = None) -> bool:
        """Enable or disable autostart in the Windows registry.

        Args:
            enabled: True to register startup command, False to remove.
            command: Custom command string. If None, uses get_default_command().

        Returns:
            True if registry operation succeeded, False otherwise.
        """
        if sys.platform != "win32":
            logger.info("Autostart is only supported on Windows.")
            return False

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.key_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    cmd_to_set = command or self.get_default_command()
                    winreg.SetValueEx(
                        key,
                        self.value_name,
                        0,
                        winreg.REG_SZ,
                        cmd_to_set,
                    )
                    logger.info("Registered autostart command in HKCU: %s", cmd_to_set)
                else:
                    try:
                        winreg.DeleteValue(key, self.value_name)
                        logger.info("Removed autostart entry from HKCU: %s", self.value_name)
                    except FileNotFoundError:
                        # Value already absent
                        pass
            return True
        except Exception as exc:
            logger.error("Failed to update autostart registry key: %s", exc)
            return False
