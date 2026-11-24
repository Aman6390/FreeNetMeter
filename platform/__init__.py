"""Platform-specific integrations for FreeNetMeter.

Contains Windows autostart registry management, single-instance local IPC,
and Windows light/dark theme detection.
"""

from __future__ import annotations

import importlib.util
import os
import sys

# Re-export our platform integration classes
from platform.autostart import WindowsAutostartManager
from platform.single_instance import SingleInstanceGuard
from platform.theme_listener import WindowsThemeDetector

__all__ = [
    "WindowsAutostartManager",
    "SingleInstanceGuard",
    "WindowsThemeDetector",
]

# Compatibility bridge: If third-party dependencies or test plugins (such as pytest,
# anyio, or urllib) execute `import platform`, they expect the Python standard library
# `platform` module. Since this local directory is named `platform/` as required by the
# architecture spec, we proxy all attributes of the standard library module to prevent
# shadowing and maintain 100% compatibility with all standard library and external callers.
try:
    _stdlib_candidates = [
        p
        for p in sys.path
        if p and p != sys.path[0] and os.path.exists(os.path.join(p, "platform.py"))
    ]
    if _stdlib_candidates:
        _spec = importlib.util.spec_from_file_location(
            "_stdlib_platform_internal", os.path.join(_stdlib_candidates[0], "platform.py")
        )
        if _spec and _spec.loader:
            _stdlib_mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_stdlib_mod)
            for _attr_name in dir(_stdlib_mod):
                if not _attr_name.startswith("__") and _attr_name not in globals():
                    globals()[_attr_name] = getattr(_stdlib_mod, _attr_name)
except Exception:
    pass
