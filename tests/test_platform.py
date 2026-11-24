"""Unit tests for platform integration modules."""

from __future__ import annotations

from platform.autostart import WindowsAutostartManager
from platform.theme_listener import WindowsThemeDetector


def test_autostart_default_command() -> None:
    """Verify default command string contains executable."""
    cmd = WindowsAutostartManager.get_default_command()
    assert isinstance(cmd, str)
    assert len(cmd) > 0


def test_theme_detector_resolve_theme() -> None:
    """Verify resolve_theme returns 'dark' or 'light'."""
    assert WindowsThemeDetector.resolve_theme("dark") == "dark"
    assert WindowsThemeDetector.resolve_theme("light") == "light"

    # System resolution
    sys_theme = WindowsThemeDetector.resolve_theme("system")
    assert sys_theme in ("dark", "light")


def test_stdlib_platform_reexport() -> None:
    """Verify stdlib platform attributes are accessible through the bridge."""
    import platform as p

    assert hasattr(p, "system")
    assert callable(p.system)
    assert p.system() in ("Windows", "Linux", "Darwin")
