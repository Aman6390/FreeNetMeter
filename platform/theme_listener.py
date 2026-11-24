"""Windows dark and light theme detection.

Reads Windows system personalization settings via the registry to match
the user's OS-level light/dark theme preference.
"""

from __future__ import annotations

import logging
import sys

from core.constants import REGISTRY_THEMES_KEY, REGISTRY_THEMES_VALUE_NAME

logger = logging.getLogger("FreeNetMeter.Theme")


class WindowsThemeDetector:
    """Detects system-wide dark/light theme state on Windows."""

    @classmethod
    def is_system_dark_mode(cls) -> bool:
        """Check whether Windows application theme is set to dark mode.

        Reads HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize
        AppsUseLightTheme value:
          0 -> Dark mode enabled
          1 -> Light mode enabled

        Returns:
            True if dark mode is active, False for light mode or if undetectable.
        """
        if sys.platform != "win32":
            return False

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REGISTRY_THEMES_KEY,
                0,
                winreg.KEY_READ,
            ) as key:
                val, _ = winreg.QueryValueEx(key, REGISTRY_THEMES_VALUE_NAME)
                # 0 means dark mode, 1 means light mode
                return int(val) == 0
        except Exception as exc:
            logger.debug("Could not read Windows theme registry key: %s", exc)
            return False

    @classmethod
    def resolve_theme(cls, theme_mode: str) -> str:
        """Resolve effective theme ('dark' or 'light') based on user setting.

        Args:
            theme_mode: 'system', 'dark', or 'light'.

        Returns:
            'dark' or 'light'.
        """
        mode = theme_mode.lower().strip()
        if mode == "dark":
            return "dark"
        if mode == "light":
            return "light"

        # 'system' mode: query OS
        return "dark" if cls.is_system_dark_mode() else "light"
