import fcntl
import os
import threading
import time
from pathlib import Path
from types import TracebackType
from typing import Self


class HistoryLockTimeoutError(RuntimeError):
    """Raised when lock acquisition times out because another process holds the lock."""


class HistoryLock:
    """Inter-process file lock protecting DuckDB and CAS historical storage operations.

    Uses `fcntl.flock` on Linux to enforce mutual exclusion across processes.
    Supports same-thread process re-entrancy via recursion tracking.
    """

    def __init__(self, lock_file_path: Path, timeout: float = 10.0) -> None:
        self.lock_file_path = Path(lock_file_path)
        self.timeout = timeout
        self._fd: int | None = None
        self._local_state = threading.local()

    def _get_depth(self) -> int:
        return getattr(self._local_state, "depth", 0)

    def _set_depth(self, depth: int) -> None:
        self._local_state.depth = depth

    def acquire(self) -> None:
        depth = self._get_depth()
        if depth > 0:
            # Re-entrant acquire within the same thread/process
            self._set_depth(depth + 1)
            return

        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_file_path, os.O_RDWR | os.O_CREAT, 0o666)

        start_time = time.monotonic()

        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except InterruptedError:
                continue
            except BlockingIOError:
                if time.monotonic() - start_time >= self.timeout:
                    os.close(fd)
                    raise HistoryLockTimeoutError(
                        f"Historical storage is locked by another process ({self.lock_file_path}). "
                        f"Timeout ({self.timeout:.1f}s) waiting for lock."
                    ) from None
                time.sleep(0.05)
            except OSError:
                os.close(fd)
                raise

        self._fd = fd
        self._set_depth(1)

    def release(self) -> None:
        depth = self._get_depth()
        if depth <= 0:
            return

        if depth > 1:
            self._set_depth(depth - 1)
            return

        # Reached outer-most unlock level
        self._set_depth(0)
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            finally:
                self._fd = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()
