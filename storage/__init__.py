"""Storage layer for FreeNetMeter.

Provides atomic JSON settings persistence with schema migration, and ACID-compliant
SQLite data usage storage with WAL mode, parameterized queries, and safe CSV export.
"""
