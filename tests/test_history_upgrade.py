from pathlib import Path

import duckdb
import pytest

from radar_vagas.infrastructure.history import MIGRATIONS, HistoricalStorage


def test_migration_safety(tmp_path: Path):
    db_path = tmp_path / "db" / "history.duckdb"
    db_path.parent.mkdir(parents=True)

    # Simulate an old DB with only first 3 migrations
    conn = duckdb.connect(str(db_path))
    for i in range(3):
        conn.execute(MIGRATIONS[i])
        if i > 0:
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", [i])
        else:
            conn.execute("INSERT INTO schema_migrations (version) VALUES (0)")
    conn.close()

    # Initialize storage, which should apply remaining migrations
    storage = HistoricalStorage(tmp_path)

    # Check that schema version is now up-to-date
    res = storage.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    assert res == len(MIGRATIONS) - 1

    # Check that new column exists
    storage.conn.execute("SELECT application_version FROM ingestion_runs LIMIT 1")
    missing_checksums = storage.conn.execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE checksum IS NULL"
    ).fetchone()[0]
    assert missing_checksums == 0
    storage.close()


def test_future_database_version(tmp_path: Path):
    db_path = tmp_path / "db" / "history.duckdb"
    db_path.parent.mkdir(parents=True)

    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    # Set to a future version
    conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", [len(MIGRATIONS) + 5])
    conn.close()

    with pytest.raises(RuntimeError, match="newer than supported"):
        HistoricalStorage(tmp_path)


def test_migration_tampering_raises_error(tmp_path: Path):
    from radar_vagas.infrastructure.history import MigrationTamperedError

    storage = HistoricalStorage(tmp_path)
    storage.close()

    # Manually tamper with an applied migration checksum in DB
    conn = duckdb.connect(str(tmp_path / "db" / "history.duckdb"))
    conn.execute("UPDATE schema_migrations SET checksum = 'tampered_checksum' WHERE version = 1")
    conn.close()

    with pytest.raises(MigrationTamperedError, match="has been modified"):
        HistoricalStorage(tmp_path)
