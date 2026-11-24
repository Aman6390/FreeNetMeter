"""Unit tests for SpeedFormatter.

Verifies:
- Decimal SI boundaries (999 B/s, 1000 B/s, 999.9 KB/s, 1 MB/s).
- Binary IEC boundaries (1023 B/s, 1024 B/s, 1 MiB/s).
- Bits vs bytes conversion.
- Fixed unit formatting.
- Decimal precision (0, 1, 2).
- Clamping of negative values, NaN, and infinity.
- Arrow styles.
- Data usage byte total formatting.
"""

from __future__ import annotations

from core.formatter import SpeedFormatter


def test_decimal_si_boundaries() -> None:
    """Verify exact scaling at decimal SI unit boundaries (base 1000)."""
    fmt = SpeedFormatter(unit_system="decimal", unit_type="bytes", precision=1)

    # 999 B/s stays in B/s
    res999 = fmt.format_speed(999.0)
    assert res999.value_str == "999.0"
    assert res999.unit_str == "B/s"
    assert res999.full_str == "999.0 B/s"

    # 1000 B/s transitions to 1.0 KB/s
    res1000 = fmt.format_speed(1000.0)
    assert res1000.value_str == "1.0"
    assert res1000.unit_str == "KB/s"
    assert res1000.full_str == "1.0 KB/s"

    # 999,900 B/s is 999.9 KB/s
    res999k = fmt.format_speed(999_900.0)
    assert res999k.value_str == "999.9"
    assert res999k.unit_str == "KB/s"

    # 1,000,000 B/s transitions to 1.0 MB/s
    res1m = fmt.format_speed(1_000_000.0)
    assert res1m.value_str == "1.0"
    assert res1m.unit_str == "MB/s"

    # 1,500,000,000 B/s is 1.5 GB/s
    res1g = fmt.format_speed(1_500_000_000.0)
    assert res1g.value_str == "1.5"
    assert res1g.unit_str == "GB/s"


def test_binary_iec_boundaries() -> None:
    """Verify exact scaling at binary IEC unit boundaries (base 1024)."""
    fmt = SpeedFormatter(unit_system="binary", unit_type="bytes", precision=1)

    # 1023 B/s stays in B/s
    res1023 = fmt.format_speed(1023.0)
    assert res1023.value_str == "1023.0"
    assert res1023.unit_str == "B/s"

    # 1024 B/s transitions to 1.0 KiB/s
    res1024 = fmt.format_speed(1024.0)
    assert res1024.value_str == "1.0"
    assert res1024.unit_str == "KiB/s"

    # 1,048,576 B/s is 1.0 MiB/s
    res1mib = fmt.format_speed(1024.0 * 1024.0)
    assert res1mib.value_str == "1.0"
    assert res1mib.unit_str == "MiB/s"


def test_bits_versus_bytes() -> None:
    """Verify bits conversion multiplies bytes by 8 and applies bit labels."""
    # 125,000 bytes/s * 8 = 1,000,000 bits/s = 1.0 Mbps (decimal)
    fmt_bits = SpeedFormatter(unit_system="decimal", unit_type="bits", precision=1)
    res_bits = fmt_bits.format_speed(125_000.0)
    assert res_bits.value_str == "1.0"
    assert res_bits.unit_str == "Mbps"

    # Compare to bytes: 125,000 bytes/s is 125.0 KB/s
    fmt_bytes = SpeedFormatter(unit_system="decimal", unit_type="bytes", precision=1)
    res_bytes = fmt_bytes.format_speed(125_000.0)
    assert res_bytes.value_str == "125.0"
    assert res_bytes.unit_str == "KB/s"


def test_fixed_unit_override() -> None:
    """Verify fixed unit overrides automatic scaling."""
    fmt = SpeedFormatter(
        unit_system="decimal",
        unit_type="bytes",
        fixed_unit="KB/s",
        precision=1,
    )

    # 5,000,000 B/s forced into KB/s -> 5000.0 KB/s
    res = fmt.format_speed(5_000_000.0)
    assert res.value_str == "5000.0"
    assert res.unit_str == "KB/s"


def test_decimal_precision() -> None:
    """Verify precision settings 0, 1, and 2."""
    val = 1234.56  # 1.23456 KB/s

    fmt0 = SpeedFormatter(precision=0)
    assert fmt0.format_speed(val).value_str == "1"

    fmt1 = SpeedFormatter(precision=1)
    assert fmt1.format_speed(val).value_str == "1.2"

    fmt2 = SpeedFormatter(precision=2)
    assert fmt2.format_speed(val).value_str == "1.23"


def test_safe_against_nan_inf_negative() -> None:
    """Verify negative values, NaN, and infinity are clamped to 0."""
    fmt = SpeedFormatter()

    res_neg = fmt.format_speed(-1000.0)
    assert res_neg.value_str == "0.0"
    assert res_neg.unit_str == "B/s"

    res_nan = fmt.format_speed(float("nan"))
    assert res_nan.value_str == "0.0"
    assert res_nan.unit_str == "B/s"

    res_inf = fmt.format_speed(float("inf"))
    assert res_inf.value_str == "0.0"
    assert res_inf.unit_str == "B/s"


def test_arrow_styles() -> None:
    """Verify arrow glyphs for all styles."""
    styles = {
        "triangle": ("▼", "▲"),
        "arrow": ("↓", "↑"),
        "letters": ("D:", "U:"),
        "none": ("", ""),
    }
    for style, (down, up) in styles.items():
        fmt = SpeedFormatter(arrow_style=style)
        glyphs = fmt.get_arrow_glyphs()
        assert glyphs.download == down
        assert glyphs.upload == up


def test_format_bytes_total() -> None:
    """Verify total byte count formatting."""
    fmt_dec = SpeedFormatter(unit_system="decimal", precision=1)
    assert fmt_dec.format_bytes_total(500) == "500 B"
    assert fmt_dec.format_bytes_total(1_500_000) == "1.5 MB"
    assert fmt_dec.format_bytes_total(2_500_000_000) == "2.5 GB"

    fmt_bin = SpeedFormatter(unit_system="binary", precision=1)
    assert fmt_bin.format_bytes_total(1024 * 1024) == "1.0 MiB"
