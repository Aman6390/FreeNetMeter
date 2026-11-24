"""Unit tests for constants and path resolutions."""

from __future__ import annotations

import core.constants as const


def test_constants_values() -> None:
    """Verify application identity and core constants."""
    import importlib

    importlib.reload(const)
    assert const.APP_NAME == "FreeNetMeter"
    assert const.APP_VERSION == "1.0.0"
    assert const.SETTINGS_SCHEMA_VERSION == 1
    assert const.SAMPLE_INTERVAL_SECONDS == 1.0
    assert const.MIN_SAMPLE_INTERVAL_SECONDS == 0.2
    assert const.MAX_SAMPLE_GAP_SECONDS == 5.0
    assert const.DEFAULT_ROLLING_WINDOW_SIZE == 3
    assert const.USAGE_FLUSH_INTERVAL_SECONDS == 30.0
    assert const.SQLITE_BUSY_TIMEOUT_MS == 5000
    assert len(const.DEFAULT_EXCLUDED_INTERFACE_KEYWORDS) > 0
    assert const.APP_DATA_DIR.name in ("FreeNetMeter", ".freenetmeter")
