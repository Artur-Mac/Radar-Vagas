import multiprocessing
import time
from pathlib import Path

import pytest

from radar_vagas.infrastructure.history import HistoricalStorage, history_lock_path
from radar_vagas.infrastructure.lock import HistoryLock, HistoryLockTimeoutError


def _hold_lock_worker(lock_path: Path, hold_seconds: float, ready) -> None:
    """Worker process that acquires history.lock and holds it."""
    lock = HistoryLock(lock_path, timeout=2.0)
    with lock:
        ready.set()
        time.sleep(hold_seconds)


def test_lock_reentrancy(tmp_path: Path) -> None:
    """Test that same-thread re-entrant lock acquisition succeeds without deadlocking."""
    lock = HistoryLock(tmp_path / "history.lock", timeout=1.0)
    with lock:
        with lock:
            assert lock._get_depth() == 2
        assert lock._get_depth() == 1
    assert lock._get_depth() == 0


def test_interprocess_lock_conflict(tmp_path: Path) -> None:
    """Test that another process holding history.lock raises HistoryLockTimeoutError on timeout."""
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    lock_path = history_lock_path(tmp_path)
    p = context.Process(target=_hold_lock_worker, args=(lock_path, 1.0, ready))
    p.start()
    assert ready.wait(timeout=2.0)

    lock = HistoryLock(lock_path, timeout=0.2)
    with pytest.raises(HistoryLockTimeoutError) as exc_info, lock:
        pass

    assert "Historical storage is locked by another process" in str(exc_info.value)
    p.join()


def test_backup_holds_lock_and_blocks_writer(tmp_path: Path) -> None:
    """Test that backup uses the same lock as a concurrent historical writer."""
    storage_dir = tmp_path / "data"
    storage = HistoricalStorage(storage_dir, lock_timeout=0.2)
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    p = context.Process(
        target=_hold_lock_worker,
        args=(history_lock_path(storage_dir), 1.0, ready),
    )
    p.start()
    assert ready.wait(timeout=2.0)

    with pytest.raises(HistoryLockTimeoutError):
        storage.backup(tmp_path / "blocked-backup")

    p.join()
    storage.close()
