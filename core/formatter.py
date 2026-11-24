"""Speed and data usage text formatting and unit conversion.

Handles decimal SI (1000) and binary IEC (1024) unit scaling, bits vs bytes,
fixed or automatic units, decimal precision, arrow glyphs, and safety clamps
(preventing NaN, infinity, and negative values).

Canonical internal representations are strictly floats in bytes per second
(or total raw integer bytes for usage). Conversions to display strings occur
exclusively in this module.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class FormattedSpeed(NamedTuple):
    """Formatted speed representation with separate numeric and unit strings.

    Attributes:
        value_str: The formatted numeric string (e.g. '12.5', '950').
        unit_str: The unit suffix string (e.g. 'MB/s', 'Kbps').
        full_str: Combined value and unit (e.g. '12.5 MB/s').
    """

    value_str: str
    unit_str: str
    full_str: str


class ArrowGlyphs(NamedTuple):
    """Pair of glyphs representing download and upload direction."""

    download: str
    upload: str


# Pre-defined arrow sets
ARROW_STYLES: dict[str, ArrowGlyphs] = {
    "triangle": ArrowGlyphs(download="▼", upload="▲"),
    "arrow": ArrowGlyphs(download="↓", upload="↑"),
    "letters": ArrowGlyphs(download="D:", upload="U:"),
    "none": ArrowGlyphs(download="", upload=""),
}


class SpeedFormatter:
    """Formats raw speeds and byte counts according to user preferences."""

    def __init__(
        self,
        unit_system: str = "decimal",  # 'decimal' (1000) or 'binary' (1024)
        unit_type: str = "bytes",  # 'bytes' or 'bits'
        fixed_unit: str = "auto",  # 'auto' or specific unit e.g. 'MB/s'
        precision: int = 1,  # 0, 1, or 2 decimal places
        arrow_style: str = "triangle",  # 'triangle', 'arrow', 'letters', 'none'
    ) -> None:
        """Initialize formatter with display settings."""
        self.unit_system = unit_system
        self.unit_type = unit_type
        self.fixed_unit = fixed_unit.strip().lower()
        self.precision = max(0, min(2, precision))
        self.arrow_style = arrow_style

    def get_arrow_glyphs(self) -> ArrowGlyphs:
        """Get the configured arrow glyphs for download and upload."""
        return ARROW_STYLES.get(self.arrow_style, ARROW_STYLES["triangle"])

    def format_speed(self, bytes_per_sec: float) -> FormattedSpeed:
        """Format a single speed value (in bytes per second) into display text.

        Correctness Rule 9 & 10:
        Clamps any negative, NaN, or infinite value to zero.
        Converts bytes to bits if unit_type == 'bits'.
        Always includes the unit label.

        Args:
            bytes_per_sec: Instantaneous speed in bytes per second.

        Returns:
            FormattedSpeed with value_str, unit_str, and full_str.
        """
        # Clamp invalid or negative values safely to 0.0
        if math.isnan(bytes_per_sec) or math.isinf(bytes_per_sec) or bytes_per_sec < 0.0:
            val = 0.0
        else:
            val = float(bytes_per_sec)

        # Convert to bits if selected (1 byte = 8 bits)
        is_bits = self.unit_type.lower() == "bits"
        if is_bits:
            val *= 8.0

        is_binary = self.unit_system.lower() == "binary"
        base = 1024.0 if is_binary else 1000.0

        # Define unit tables for bytes and bits
        if is_bits:
            if is_binary:
                units = ["bps", "Kibps", "Mibps", "Gibps", "Tibps"]
            else:
                units = ["bps", "Kbps", "Mbps", "Gbps", "Tbps"]
        else:
            if is_binary:
                units = ["B/s", "KiB/s", "MiB/s", "GiB/s", "TiB/s"]
            else:
                units = ["B/s", "KB/s", "MB/s", "GB/s", "TB/s"]

        # Check for fixed unit override
        if self.fixed_unit != "auto":
            # Map canonical lowercase unit to target scale index
            fixed_lower = self.fixed_unit.lower()
            target_idx = None
            for idx, u in enumerate(units):
                if u.lower() == fixed_lower:
                    target_idx = idx
                    break

            if target_idx is not None:
                scaled_val = val / (base**target_idx)
                val_text = self._format_number(scaled_val, self.precision)
                unit_label = units[target_idx]
                return FormattedSpeed(
                    value_str=val_text,
                    unit_str=unit_label,
                    full_str=f"{val_text} {unit_label}",
                )

        # Automatic scaling
        idx = 0
        while val >= base and idx < len(units) - 1:
            val /= base
            idx += 1

        val_text = self._format_number(val, self.precision)
        unit_label = units[idx]

        return FormattedSpeed(
            value_str=val_text,
            unit_str=unit_label,
            full_str=f"{val_text} {unit_label}",
        )

    def format_bytes_total(self, total_bytes: int) -> str:
        """Format accumulated byte counts for usage reporting.

        Uses either decimal SI (KB, MB, GB, TB) or binary IEC (KiB, MiB, GiB, TiB).

        Args:
            total_bytes: Cumulative bytes.

        Returns:
            Human-readable string e.g. '1.45 GB'.
        """
        if total_bytes < 0:
            total_bytes = 0

        is_binary = self.unit_system.lower() == "binary"
        base = 1024.0 if is_binary else 1000.0

        if is_binary:
            units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
        else:
            units = ["B", "KB", "MB", "GB", "TB", "PB"]

        val = float(total_bytes)
        idx = 0
        while val >= base and idx < len(units) - 1:
            val /= base
            idx += 1

        # Use 2 decimal places for data usage totals unless it's pure bytes
        prec = 0 if idx == 0 else max(1, self.precision)
        formatted_num = self._format_number(val, prec)
        return f"{formatted_num} {units[idx]}"

    @staticmethod
    def _format_number(val: float, precision: int) -> str:
        """Format a floating point number with specified decimal precision.

        Avoids scientific notation and formats 0.0 accurately.
        """
        if precision <= 0:
            return f"{round(val):d}"
        if precision == 1:
            return f"{val:.1f}"
        return f"{val:.2f}"
