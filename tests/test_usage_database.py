"""Unit tests for UsageDatabase.

Verifies:
- SQLite initialization and WAL mode.
- Batch UPSERT accumulation of byte totals.
- Summary aggregates (today, week, month, all-time).
- Interface breakdown and date range filtering.
- Data retention cleanup.
- Safe CSV export with UTF-8 BOM and formula injection protection.
"""

from __future__ import annotations

from pathlib import Path

from core.formatter import SpeedFormatter
from core.usage_accumulator import PendingUsageRecord
from storage.usage_database import UsageDatabase


def test_usage_database_initialization(tmp_path: Path) -> None:
    """Verify database file, table, and WAL mode are initialized."""
    db_file = tmp_path / "usage.db"
    db = UsageDatabase(db_path=db_file)
    assert db_file.exists()

    # Query summary on empty DB
    summary = db.get_summary(today_date_str="2026-11-09")
    assert summary.today_total == 0
    assert summary.week_total == 0
    assert summary.month_total == 0
    assert summary.all_time_total == 0


def test_batch_upsert_accumulation(tmp_path: Path) -> None:
    """Verify multiple batches accumulate correctly on conflict."""
    db_file = tmp_path / "usage.db"
    db = UsageDatabase(db_path=db_file)

    batch1 = [
        PendingUsageRecord("2026-11-09", "Ethernet", bytes_sent=1000, bytes_recv=2000),
        PendingUsageRecord("2026-11-09", "Wi-Fi", bytes_sent=500, bytes_recv=1500),
    ]
    db.record_usage_batch(batch1)

    batch2 = [
        # Same date and interface: should add to existing values
        PendingUsageRecord("2026-11-09", "Ethernet", bytes_sent=500, bytes_recv=1000),
    ]
    db.record_usage_batch(batch2)

    history = db.get_history(start_date="2026-11-09", end_date="2026-11-09")
    hist_map = {h.interface_name: (h.bytes_sent, h.bytes_recv) for h in history}

    assert hist_map["Ethernet"] == (1500, 3000)
    assert hist_map["Wi-Fi"] == (500, 1500)


def test_summary_aggregates(tmp_path: Path) -> None:
    """Verify today, weekly (7 days), monthly (30 days), and all-time summaries."""
    db_file = tmp_path / "usage.db"
    db = UsageDatabase(db_path=db_file)

    records = [
        # Today
        PendingUsageRecord("2026-11-09", "Ethernet", bytes_sent=100, bytes_recv=100),
        # 3 days ago (within week)
        PendingUsageRecord("2026-11-06", "Ethernet", bytes_sent=200, bytes_recv=200),
        # 15 days ago (within month, outside week)
        PendingUsageRecord("2026-10-25", "Ethernet", bytes_sent=400, bytes_recv=400),
        # 40 days ago (outside month)
        PendingUsageRecord("2026-09-30", "Ethernet", bytes_sent=800, bytes_recv=800),
    ]
    db.record_usage_batch(records)

    summary = db.get_summary(today_date_str="2026-11-09")
    assert summary.today_total == 200
    assert summary.week_total == 200 + 400
    assert summary.month_total == 200 + 400 + 800
    assert summary.all_time_total == 200 + 400 + 800 + 1600


def test_interface_breakdown(tmp_path: Path) -> None:
    """Verify per-interface total breakdown."""
    db_file = tmp_path / "usage.db"
    db = UsageDatabase(db_path=db_file)

    db.record_usage_batch(
        [
            PendingUsageRecord("2026-11-09", "Ethernet", bytes_sent=1000, bytes_recv=2000),
            PendingUsageRecord("2026-11-08", "Ethernet", bytes_sent=1000, bytes_recv=2000),
            PendingUsageRecord("2026-11-09", "Wi-Fi", bytes_sent=100, bytes_recv=200),
        ]
    )

    breakdown = db.get_interface_breakdown()
    assert len(breakdown) == 2
    # Ethernet first due to order by total DESC
    assert breakdown[0][0] == "Ethernet"
    assert breakdown[0][3] == 6000  # Total bytes
    assert breakdown[1][0] == "Wi-Fi"
    assert breakdown[1][3] == 300


def test_retention_cleanup(tmp_path: Path) -> None:
    """Verify retention deletes records older than N days."""
    db_file = tmp_path / "usage.db"
    db = UsageDatabase(db_path=db_file)

    db.record_usage_batch(
        [
            PendingUsageRecord("2020-01-01", "Ethernet", bytes_sent=100, bytes_recv=100),
            PendingUsageRecord("2026-11-09", "Ethernet", bytes_sent=100, bytes_recv=100),
        ]
    )

    # 30 day retention should delete 2020 record but keep 2026 record
    deleted = db.cleanup_old_records(retention_days=30)
    assert deleted == 1

    remaining = db.get_history()
    assert len(remaining) == 1
    assert remaining[0].date_str == "2026-11-09"


def test_csv_export_and_formula_injection_defense(tmp_path: Path) -> None:
    """Verify CSV export is UTF-8 BOM encoded and immune to formula injection."""
    db_file = tmp_path / "usage.db"
    csv_file = tmp_path / "export.csv"
    db = UsageDatabase(db_path=db_file)

    # Insert malicious/formula injection values as interface names
    malicious_records = [
        PendingUsageRecord("2026-11-09", "=cmd|' /C calc'!A0", bytes_sent=10, bytes_recv=20),
        PendingUsageRecord("2026-11-08", "+SUM(A1:A10)", bytes_sent=30, bytes_recv=40),
        PendingUsageRecord("2026-11-07", "-1234", bytes_sent=50, bytes_recv=60),
        PendingUsageRecord(
            "2026-11-06", '@HYPERLINK("http://evil.com")', bytes_sent=70, bytes_recv=80
        ),
        PendingUsageRecord("2026-11-05", "\tTabInterface", bytes_sent=90, bytes_recv=100),
        PendingUsageRecord("2026-11-04", "\rReturnInterface", bytes_sent=110, bytes_recv=120),
        PendingUsageRecord("2026-11-03", "Normal-Ethernet", bytes_sent=1000, bytes_recv=2000),
    ]
    db.record_usage_batch(malicious_records)

    count = db.export_csv(csv_file, formatter=SpeedFormatter())
    assert count == len(malicious_records)
    assert csv_file.exists()

    # Verify UTF-8 BOM
    raw_bytes = csv_file.read_bytes()
    assert raw_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM

    # Verify content lines (newline="" to prevent universal newline translation of \r)
    with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()

    # Formula injection characters must have a leading single quote "'"
    assert "'=cmd|' /C calc'!A0" in text
    assert "'+SUM(A1:A10)" in text
    assert "'-1234" in text
    assert "'@HYPERLINK" in text
    assert "'\tTabInterface" in text
    assert "'\rReturnInterface" in text

    # Normal interface should not have single quote prepended
    assert "Normal-Ethernet" in text
    assert "'Normal-Ethernet" not in text
