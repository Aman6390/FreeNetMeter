"""Independent cross-check tool verifying FreeNetMeter counters against Windows.

Compares byte counters from two independent sources over a 30-second interval:
- Source 1: psutil.net_io_counters(pernic=True) (the same source FreeNetMeter uses)
- Source 2: Windows PowerShell Get-NetAdapterStatistics (Windows kernel network stack)

Requirements:
- Subprocess uses argument list (never shell=True).
- Proper timeout and exception handling if PowerShell fails.
- PASS criterion: difference <= 2.0%, or within absolute byte tolerance (50 KB) when traffic is low.
- Plain-English result line.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ComparisonResult:
    """Outcome of comparing byte counters between psutil and PowerShell.

    Attributes:
        adapter_name: Name of the network interface.
        psutil_recv: Bytes received recorded by psutil.
        powershell_recv: Bytes received recorded by PowerShell.
        recv_diff_pct: Percentage difference in received bytes.
        psutil_sent: Bytes sent recorded by psutil.
        powershell_sent: Bytes sent recorded by PowerShell.
        sent_diff_pct: Percentage difference in sent bytes.
        passed: True if difference is within allowable tolerance.
        reason: Plain-English explanation.
    """

    adapter_name: str
    psutil_recv: int
    powershell_recv: int
    recv_diff_pct: float
    psutil_sent: int
    powershell_sent: int
    sent_diff_pct: float
    passed: bool
    reason: str


def parse_powershell_output(raw_json: str) -> dict[str, tuple[int, int]]:
    """Parse JSON output from PowerShell Get-NetAdapterStatistics.

    Args:
        raw_json: String output from PowerShell ConvertTo-Json.

    Returns:
        Mapping from adapter name to (received_bytes, sent_bytes).
    """
    if not raw_json.strip():
        return {}

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}

    # Convert single-item dict into list for uniform handling
    items = data if isinstance(data, list) else [data]

    results: dict[str, tuple[int, int]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name", "")).strip()
        if not name:
            continue
        try:
            recv = int(item.get("ReceivedBytes", 0))
            sent = int(item.get("SentBytes", 0))
            results[name] = (recv, sent)
        except (ValueError, TypeError):
            continue

    return results


def read_powershell_statistics(timeout_sec: float = 10.0) -> dict[str, tuple[int, int]]:
    """Query Windows network statistics via PowerShell Get-NetAdapterStatistics.

    Uses an explicit argument list with shell=False for security.

    Args:
        timeout_sec: Maximum time to wait for PowerShell process.

    Returns:
        Mapping of adapter name to (received_bytes, sent_bytes).
    """
    cmd = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-NetAdapterStatistics | Select-Object Name, ReceivedBytes, SentBytes | ConvertTo-Json",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        if result.returncode != 0:
            sys.stderr.write(f"PowerShell error ({result.returncode}): {result.stderr}\n")
            return {}
        return parse_powershell_output(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"Failed to query PowerShell statistics: {exc}\n")
        return {}


def read_psutil_statistics() -> dict[str, tuple[int, int]]:
    """Sample network statistics using psutil.

    Returns:
        Mapping of adapter name to (bytes_recv, bytes_sent).
    """
    import psutil

    counters = psutil.net_io_counters(pernic=True)
    return {name: (c.bytes_recv, c.bytes_sent) for name, c in counters.items()}


def compare_counter_deltas(
    psutil_deltas: Mapping[str, tuple[int, int]],
    powershell_deltas: Mapping[str, tuple[int, int]],
    percent_tolerance: float = 2.0,
    abs_tolerance_bytes: int = 50_000,
) -> list[ComparisonResult]:
    """Compare traffic deltas between psutil and PowerShell.

    Tolerance rule:
    Difference is considered PASS if percentage difference <= percent_tolerance (2%),
    OR absolute difference <= abs_tolerance_bytes (50 KB) to prevent false failures
    on idle connections with tiny background broadcast traffic.

    Args:
        psutil_deltas: Adapter -> (recv_delta, sent_delta) from psutil.
        powershell_deltas: Adapter -> (recv_delta, sent_delta) from PowerShell.
        percent_tolerance: Acceptable percentage difference.
        abs_tolerance_bytes: Maximum acceptable byte difference when traffic is low.

    Returns:
        List of ComparisonResult per mutual adapter.
    """
    results: list[ComparisonResult] = []

    # Check mutual adapters
    common_adapters = sorted(set(psutil_deltas.keys()) & set(powershell_deltas.keys()))

    for name in common_adapters:
        p_recv, p_sent = psutil_deltas[name]
        ps_recv, ps_sent = powershell_deltas[name]

        # Calculate received difference
        abs_diff_recv = abs(p_recv - ps_recv)
        max_recv = max(p_recv, ps_recv)
        recv_pct = (abs_diff_recv / max_recv * 100.0) if max_recv > 0 else 0.0

        # Calculate sent difference
        abs_diff_sent = abs(p_sent - ps_sent)
        max_sent = max(p_sent, ps_sent)
        sent_pct = (abs_diff_sent / max_sent * 100.0) if max_sent > 0 else 0.0

        # Evaluate pass criteria
        recv_ok = (recv_pct <= percent_tolerance) or (abs_diff_recv <= abs_tolerance_bytes)
        sent_ok = (sent_pct <= percent_tolerance) or (abs_diff_sent <= abs_tolerance_bytes)

        passed = recv_ok and sent_ok
        reason = (
            "OK"
            if passed
            else (f"Difference exceeded tolerance (Recv: {recv_pct:.1f}%, Sent: {sent_pct:.1f}%)")
        )

        results.append(
            ComparisonResult(
                adapter_name=name,
                psutil_recv=p_recv,
                powershell_recv=ps_recv,
                recv_diff_pct=recv_pct,
                psutil_sent=p_sent,
                powershell_sent=ps_sent,
                sent_diff_pct=sent_pct,
                passed=passed,
                reason=reason,
            )
        )

    return results


def run_verification(duration_seconds: int = 30) -> bool:
    """Run interactive 30-second verification session and print results table.

    Returns:
        True if all verified adapters passed, False otherwise.
    """
    print("=== FreeNetMeter Independent Counter Verification ===")
    print(f"Sampling byte counters for {duration_seconds} seconds across two independent sources:")
    print("  Source 1: psutil.net_io_counters(pernic=True) [used by FreeNetMeter]")
    print("  Source 2: Windows PowerShell Get-NetAdapterStatistics [Windows Kernel]")
    print()

    # Step 1: Initial Snapshot
    print("Taking baseline snapshot (T=0s)...")
    psutil_start = read_psutil_statistics()
    ps_start = read_powershell_statistics()

    if not ps_start:
        print("ERROR: Failed to read initial statistics from PowerShell.")
        print("Please ensure PowerShell is accessible on your system.")
        return False

    # Step 2: Sampling countdown
    print(
        f"Waiting {duration_seconds} seconds. For a stronger test, generate traffic now (e.g. video or download)..."
    )
    for remaining in range(duration_seconds, 0, -5):
        print(f"  {remaining} seconds remaining...")
        time.sleep(min(5, remaining))

    # Step 3: Final Snapshot
    print("Taking final snapshot...")
    psutil_end = read_psutil_statistics()
    ps_end = read_powershell_statistics()

    if not ps_end:
        print("ERROR: Failed to read final statistics from PowerShell.")
        return False

    # Step 4: Compute deltas
    psutil_deltas: dict[str, tuple[int, int]] = {}
    for name, (recv_end, sent_end) in psutil_end.items():
        if name in psutil_start:
            recv_start, sent_start = psutil_start[name]
            psutil_deltas[name] = (max(0, recv_end - recv_start), max(0, sent_end - sent_start))

    ps_deltas: dict[str, tuple[int, int]] = {}
    for name, (recv_end, sent_end) in ps_end.items():
        if name in ps_start:
            recv_start, sent_start = ps_start[name]
            ps_deltas[name] = (max(0, recv_end - recv_start), max(0, sent_end - sent_start))

    # Step 5: Compare results
    comparisons = compare_counter_deltas(psutil_deltas, ps_deltas)

    if not comparisons:
        print("WARNING: No mutual adapters found to compare.")
        return False

    # Step 6: Print Table
    print()
    header = f"{'Adapter Name':<20} | {'Recv (psutil)':<14} | {'Recv (Win)':<14} | {'Diff %':<8} | {'Status':<6}"
    divider = "-" * len(header)
    print(divider)
    print(header)
    print(divider)

    all_passed = True
    for c in comparisons:
        status_str = "PASS" if c.passed else "FAIL"
        if not c.passed:
            all_passed = False
        print(
            f"{c.adapter_name:<20} | {c.psutil_recv:<14,d} | {c.powershell_recv:<14,d} | {c.recv_diff_pct:<7.2f}% | {status_str:<6}"
        )
    print(divider)
    print()

    # Step 7: Print Conclusion and Instructions
    if all_passed:
        print("RESULT: PASS - the app's numbers match Windows")
    else:
        print("RESULT: FAIL - see the rows marked FAIL")

    print()
    print("For a stronger test, start a large download now and run this again.")
    return all_passed


if __name__ == "__main__":
    success = run_verification(duration_seconds=30)
    sys.exit(0 if success else 1)
