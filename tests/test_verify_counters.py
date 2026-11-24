"""Unit tests for tools.verify_counters parser and comparison logic.

Uses synthetic test data without executing external PowerShell commands.
"""

from __future__ import annotations

from tools.verify_counters import compare_counter_deltas, parse_powershell_output


def test_parse_powershell_single_adapter() -> None:
    """Verify parsing single adapter JSON output."""
    raw_json = """
    {
        "Name": "Wi-Fi",
        "ReceivedBytes": 12345678,
        "SentBytes": 8765432
    }
    """
    parsed = parse_powershell_output(raw_json)
    assert "Wi-Fi" in parsed
    assert parsed["Wi-Fi"] == (12345678, 8765432)


def test_parse_powershell_multiple_adapters() -> None:
    """Verify parsing JSON array of multiple adapters."""
    raw_json = """
    [
        {"Name": "Ethernet", "ReceivedBytes": 5000000, "SentBytes": 2000000},
        {"Name": "Wi-Fi", "ReceivedBytes": 1000000, "SentBytes": 500000}
    ]
    """
    parsed = parse_powershell_output(raw_json)
    assert len(parsed) == 2
    assert parsed["Ethernet"] == (5000000, 2000000)
    assert parsed["Wi-Fi"] == (1000000, 500000)


def test_parse_powershell_invalid_inputs() -> None:
    """Verify parser handles corrupt or empty input gracefully."""
    assert parse_powershell_output("") == {}
    assert parse_powershell_output("not json") == {}
    assert parse_powershell_output("{}") == {}
    assert parse_powershell_output("[1, 2, 3]") == {}


def test_compare_counters_pass_cases() -> None:
    """Verify identical or near-identical counters pass."""
    # Exact match: 0% diff
    p_deltas = {"Ethernet": (10_000_000, 5_000_000)}
    ps_deltas = {"Ethernet": (10_000_000, 5_000_000)}
    res = compare_counter_deltas(p_deltas, ps_deltas)
    assert len(res) == 1
    assert res[0].passed is True
    assert res[0].recv_diff_pct == 0.0

    # 1.5% diff (within 2% tolerance)
    p_deltas = {"Ethernet": (10_000_000, 5_000_000)}
    ps_deltas = {"Ethernet": (10_150_000, 5_050_000)}
    res2 = compare_counter_deltas(p_deltas, ps_deltas)
    assert res2[0].passed is True

    # Idle connection with 5KB absolute difference (within 50KB tolerance)
    p_idle = {"Wi-Fi": (100, 100)}
    ps_idle = {"Wi-Fi": (5000, 1000)}
    res3 = compare_counter_deltas(p_idle, ps_idle)
    assert res3[0].passed is True


def test_compare_counters_fail_case() -> None:
    """Verify significant mismatch on high volume fails."""
    # 50% mismatch on 10 MB traffic
    p_deltas = {"Ethernet": (10_000_000, 5_000_000)}
    ps_deltas = {"Ethernet": (5_000_000, 2_500_000)}
    res = compare_counter_deltas(p_deltas, ps_deltas)
    assert len(res) == 1
    assert res[0].passed is False
    assert "Difference exceeded" in res[0].reason
