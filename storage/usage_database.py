"""ACID SQLite storage for network data usage tracking.

Implements high-performance, crash-resilient local persistence for cumulative
bytes sent and received per interface and local calendar day.

Correctness & Reliability Guarantees:
1. Write-Ahead Logging (WAL) mode enables concurrent reads without blocking writes.
2. Parameterized SQL queries exclusively to prevent SQL injection vulnerabilities.
3. Explicit transaction management ensures atomic batch flushes.
4. Busy timeout (5000 ms) prevents locking contention errors.
5. Safe CSV export with UTF-8 BOM encoding for Excel compatibility and CSV/formula
   injection escaping.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.constants import SQLITE_BUSY_TIMEOUT_MS, USAGE_DB_PATH
from core.formatter import SpeedFormatter
from core.speed_test_engine import SpeedTestResult
from core.usage_accumulator import PendingUsageRecord

logger = logging.getLogger("FreeNetMeter.Database")


@dataclass(frozen=True)
class DailyUsageEntry:
    """Historical usage record for a specific day and interface."""

    date_str: str
    interface_name: str
    bytes_sent: int
    bytes_recv: int

    @property
    def total_bytes(self) -> int:
        """Sum of sent and received bytes."""
        return self.bytes_sent + self.bytes_recv


@dataclass(frozen=True)
class UsageSummary:
    """Aggregated usage totals across time intervals."""

    today_recv: int
    today_sent: int
    week_recv: int
    week_sent: int
    month_recv: int
    month_sent: int
    all_time_recv: int
    all_time_sent: int

    @property
    def today_total(self) -> int:
        return self.today_recv + self.today_sent

    @property
    def week_total(self) -> int:
        return self.week_recv + self.week_sent

    @property
    def month_total(self) -> int:
        return self.month_recv + self.month_sent

    @property
    def all_time_total(self) -> int:
        return self.all_time_recv + self.all_time_sent


class UsageDatabase:
    """Manages SQLite database operations for network data usage."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize database connection manager.

        Args:
            db_path: Path to the SQLite database file. Defaults to %APPDATA%/FreeNetMeter/usage.db.
        """
        self.db_path = db_path or USAGE_DB_PATH
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure an SQLite database connection.

        Enables Write-Ahead Logging (WAL), sets busy timeout, and disables autocommit
        so transactions can be explicitly controlled.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0,
            isolation_level=None,  # Manual transaction management
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
        return conn

    def _init_database(self) -> None:
        """Create tables and indexes if they do not exist."""
        conn = self._get_connection()
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_usage (
                    date TEXT NOT NULL,
                    interface TEXT NOT NULL,
                    bytes_sent INTEGER NOT NULL,
                    bytes_recv INTEGER NOT NULL,
                    PRIMARY KEY (date, interface)
                );
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_usage_date
                ON daily_usage(date);
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS speed_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    download_mbps REAL NOT NULL,
                    upload_mbps REAL NOT NULL,
                    idle_ping_ms REAL NOT NULL,
                    jitter_ms REAL NOT NULL,
                    loaded_down_ping_ms REAL NOT NULL,
                    loaded_up_ping_ms REAL NOT NULL,
                    packet_loss_pct REAL NOT NULL,
                    bufferbloat_grade TEXT NOT NULL,
                    streaming_rating TEXT NOT NULL,
                    gaming_rating TEXT NOT NULL,
                    video_calls_rating TEXT NOT NULL
                );
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_speed_tests_timestamp
                ON speed_tests(timestamp);
                """)
            conn.execute("COMMIT;")
        except Exception as exc:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            logger.error("Failed to initialize usage database: %s", exc)
            raise
        finally:
            conn.close()

    def record_usage_batch(self, records: Sequence[PendingUsageRecord]) -> None:
        """Flush a batch of pending usage records into the database atomically.

        Uses UPSERT syntax: if (date, interface) exists, adds to existing byte totals;
        otherwise inserts a new row.

        Args:
            records: Sequence of PendingUsageRecord to commit.
        """
        if not records:
            return

        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            query = """
                INSERT INTO daily_usage (date, interface, bytes_sent, bytes_recv)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, interface) DO UPDATE SET
                    bytes_sent = bytes_sent + excluded.bytes_sent,
                    bytes_recv = bytes_recv + excluded.bytes_recv;
            """
            params = [(r.date_str, r.interface_name, r.bytes_sent, r.bytes_recv) for r in records]
            conn.executemany(query, params)
            conn.execute("COMMIT;")
            logger.debug("Successfully committed %d usage records to database", len(records))
        except Exception as exc:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            logger.error("Failed to commit usage records batch: %s", exc)
            raise
        finally:
            conn.close()

    def get_summary(self, today_date_str: str) -> UsageSummary:
        """Calculate aggregate usage metrics for today, last 7 days, last 30 days, and all time.

        Args:
            today_date_str: Current local date string 'YYYY-MM-DD'.

        Returns:
            UsageSummary with byte totals.
        """
        conn = self._get_connection()
        try:
            # Today's total
            cur = conn.execute(
                """
                SELECT COALESCE(SUM(bytes_recv), 0) AS recv, COALESCE(SUM(bytes_sent), 0) AS sent
                FROM daily_usage
                WHERE date = ?;
                """,
                (today_date_str,),
            )
            row_today = cur.fetchone()
            today_recv, today_sent = row_today["recv"], row_today["sent"]

            # Last 7 days (weekly)
            cur = conn.execute(
                """
                SELECT COALESCE(SUM(bytes_recv), 0) AS recv, COALESCE(SUM(bytes_sent), 0) AS sent
                FROM daily_usage
                WHERE date >= date(?, '-6 days') AND date <= ?;
                """,
                (today_date_str, today_date_str),
            )
            row_week = cur.fetchone()
            week_recv, week_sent = row_week["recv"], row_week["sent"]

            # Last 30 days (monthly)
            cur = conn.execute(
                """
                SELECT COALESCE(SUM(bytes_recv), 0) AS recv, COALESCE(SUM(bytes_sent), 0) AS sent
                FROM daily_usage
                WHERE date >= date(?, '-29 days') AND date <= ?;
                """,
                (today_date_str, today_date_str),
            )
            row_month = cur.fetchone()
            month_recv, month_sent = row_month["recv"], row_month["sent"]

            # All time
            cur = conn.execute("""
                SELECT COALESCE(SUM(bytes_recv), 0) AS recv, COALESCE(SUM(bytes_sent), 0) AS sent
                FROM daily_usage;
                """)
            row_all = cur.fetchone()
            all_recv, all_sent = row_all["recv"], row_all["sent"]

            return UsageSummary(
                today_recv=today_recv,
                today_sent=today_sent,
                week_recv=week_recv,
                week_sent=week_sent,
                month_recv=month_recv,
                month_sent=month_sent,
                all_time_recv=all_recv,
                all_time_sent=all_sent,
            )
        finally:
            conn.close()

    def get_interface_breakdown(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[tuple[str, int, int, int]]:
        """Compute usage breakdown per network adapter across an optional date range.

        Returns:
            List of tuples: (interface_name, total_recv, total_sent, total_bytes)
            sorted by total_bytes descending.
        """
        conn = self._get_connection()
        try:
            where_clauses: list[str] = []
            params: list[str] = []

            if start_date:
                where_clauses.append("date >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("date <= ?")
                params.append(end_date)

            where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            query = f"""
                SELECT interface,
                       COALESCE(SUM(bytes_recv), 0) AS recv,
                       COALESCE(SUM(bytes_sent), 0) AS sent,
                       COALESCE(SUM(bytes_recv + bytes_sent), 0) AS total
                FROM daily_usage
                {where_str}
                GROUP BY interface
                ORDER BY total DESC;
            """
            cur = conn.execute(query, params)
            return [(row["interface"], row["recv"], row["sent"], row["total"]) for row in cur]
        finally:
            conn.close()

    def get_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        interface_name: str | None = None,
    ) -> list[DailyUsageEntry]:
        """Query individual daily records filtered by date range and interface.

        Returns:
            List of DailyUsageEntry objects ordered by date DESC, interface ASC.
        """
        conn = self._get_connection()
        try:
            where_clauses: list[str] = []
            params: list[str] = []

            if start_date:
                where_clauses.append("date >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("date <= ?")
                params.append(end_date)
            if interface_name and interface_name.lower() != "all":
                where_clauses.append("interface = ?")
                params.append(interface_name)

            where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            query = f"""
                SELECT date, interface, bytes_sent, bytes_recv
                FROM daily_usage
                {where_str}
                ORDER BY date DESC, interface ASC;
            """
            cur = conn.execute(query, params)
            return [
                DailyUsageEntry(
                    date_str=row["date"],
                    interface_name=row["interface"],
                    bytes_sent=row["bytes_sent"],
                    bytes_recv=row["bytes_recv"],
                )
                for row in cur
            ]
        finally:
            conn.close()

    def cleanup_old_records(self, retention_days: int) -> int:
        """Delete historical records older than specified retention days.

        Args:
            retention_days: Number of days to retain. If 0, retention is disabled.

        Returns:
            Number of deleted rows.
        """
        if retention_days <= 0:
            return 0

        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                """
                DELETE FROM daily_usage
                WHERE date < date('now', 'localtime', '-' || ? || ' days');
                """,
                (retention_days,),
            )
            deleted_count = cur.rowcount
            conn.execute("COMMIT;")
            logger.info(
                "Cleaned up %d usage records older than %d days", deleted_count, retention_days
            )
            return deleted_count
        except Exception as exc:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            logger.error("Failed to cleanup old usage records: %s", exc)
            return 0
        finally:
            conn.close()

    def export_csv(
        self,
        output_path: Path,
        formatter: SpeedFormatter | None = None,
    ) -> int:
        """Export all usage history to a CSV file.

        Requirement 12:
        - Output uses UTF-8 encoding with BOM ('utf-8-sig') so Microsoft Excel opens it correctly.
        - Escaped against CSV/formula injection: cells starting with '=', '+', '-', '@', '\\t', or '\\r'
          are prefixed with a single quote "'" to prevent formula execution.

        Args:
            output_path: Target CSV destination path.
            formatter: Formatter instance to generate human-readable byte counts.

        Returns:
            Number of data rows exported.
        """
        fmt = formatter or SpeedFormatter()
        entries = self.get_history()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            # Header
            writer.writerow(
                [
                    "Date",
                    "Interface",
                    "Bytes Downloaded",
                    "Downloaded",
                    "Bytes Uploaded",
                    "Uploaded",
                    "Total Bytes",
                    "Total",
                ]
            )

            for entry in entries:
                safe_date = self._sanitize_for_csv(entry.date_str)
                safe_iface = self._sanitize_for_csv(entry.interface_name)
                total_b = entry.total_bytes

                writer.writerow(
                    [
                        safe_date,
                        safe_iface,
                        entry.bytes_recv,
                        fmt.format_bytes_total(entry.bytes_recv),
                        entry.bytes_sent,
                        fmt.format_bytes_total(entry.bytes_sent),
                        total_b,
                        fmt.format_bytes_total(total_b),
                    ]
                )
                row_count += 1

        return row_count

    @staticmethod
    def _sanitize_for_csv(value: str) -> str:
        """Sanitize text against spreadsheet formula injection.

        If a string begins with any of '= + - @ \\t \\r', prepend a single quote
        so Excel treats it strictly as literal text.
        """
        if not value:
            return ""
        first_char = value[0]
        if first_char in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{value}"
        return value

    def record_speed_test(self, result: SpeedTestResult) -> int:
        """Persist a completed speed test outcome into the database."""
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                """
                INSERT INTO speed_tests (
                    timestamp, download_mbps, upload_mbps, idle_ping_ms,
                    jitter_ms, loaded_down_ping_ms, loaded_up_ping_ms,
                    packet_loss_pct, bufferbloat_grade, streaming_rating,
                    gaming_rating, video_calls_rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    result.timestamp_iso,
                    result.download_mbps,
                    result.upload_mbps,
                    result.idle_ping_ms,
                    result.jitter_ms,
                    result.loaded_down_ping_ms,
                    result.loaded_up_ping_ms,
                    result.packet_loss_pct,
                    result.bufferbloat_grade,
                    result.streaming_rating,
                    result.gaming_rating,
                    result.video_calls_rating,
                ),
            )
            inserted_id = cur.lastrowid or 0
            conn.execute("COMMIT;")
            logger.info(
                "Recorded speed test ID %d: Down=%.1f Mbps, Up=%.1f Mbps",
                inserted_id,
                result.download_mbps,
                result.upload_mbps,
            )
            return inserted_id
        except Exception as exc:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            logger.error("Failed to record speed test: %s", exc)
            raise
        finally:
            conn.close()

    def get_speed_test_history(self, limit: int = 50) -> list[SpeedTestResult]:
        """Query past speed test records in reverse chronological order."""
        conn = self._get_connection()
        try:
            cur = conn.execute(
                """
                SELECT timestamp, download_mbps, upload_mbps, idle_ping_ms,
                       jitter_ms, loaded_down_ping_ms, loaded_up_ping_ms,
                       packet_loss_pct, bufferbloat_grade, streaming_rating,
                       gaming_rating, video_calls_rating
                FROM speed_tests
                ORDER BY id DESC
                LIMIT ?;
                """,
                (limit,),
            )
            results: list[SpeedTestResult] = []
            for row in cur:
                results.append(
                    SpeedTestResult(
                        timestamp_iso=row["timestamp"],
                        download_mbps=float(row["download_mbps"]),
                        upload_mbps=float(row["upload_mbps"]),
                        idle_ping_ms=float(row["idle_ping_ms"]),
                        jitter_ms=float(row["jitter_ms"]),
                        loaded_down_ping_ms=float(row["loaded_down_ping_ms"]),
                        loaded_up_ping_ms=float(row["loaded_up_ping_ms"]),
                        packet_loss_pct=float(row["packet_loss_pct"]),
                        bufferbloat_grade=str(row["bufferbloat_grade"]),
                        streaming_rating=str(row["streaming_rating"]),
                        gaming_rating=str(row["gaming_rating"]),
                        video_calls_rating=str(row["video_calls_rating"]),
                    )
                )
            return results
        finally:
            conn.close()

    def clear_speed_test_history(self) -> int:
        """Clear all historical speed test runs."""
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute("DELETE FROM speed_tests;")
            deleted = cur.rowcount
            conn.execute("COMMIT;")
            return deleted
        except Exception as exc:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            logger.error("Failed to clear speed tests: %s", exc)
            return 0
        finally:
            conn.close()
