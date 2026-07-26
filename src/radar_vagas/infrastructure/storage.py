"""Local file-based storage for ingestion runs."""

import os
from pathlib import Path

from radar_vagas.domain.models import RunManifest


class LocalStorage:
    """Manages local persistence for ingestion runs, ensuring atomic writes."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def get_run_dir(self, run_id: str) -> Path:
        """Get the base directory for a specific run."""
        return self.base_dir / "runs" / run_id

    def ensure_run_dirs(self, run_id: str) -> None:
        """Create necessary directory structure for a run."""
        run_dir = self.get_run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "raw").mkdir(exist_ok=True)
        (run_dir / "quarantine").mkdir(exist_ok=True)

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write content to a file atomically using a temporary file and rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(content, encoding="utf-8")
            os.replace(tmp_path, path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def save_raw_record(
        self, run_id: str, source_name: str, source_job_id: str, payload: str
    ) -> None:
        """Save a raw job payload."""
        run_dir = self.get_run_dir(run_id)
        safe_name = f"{source_name}-{source_job_id}".replace("/", "_").replace("\\", "_")
        path = run_dir / "raw" / f"{safe_name}.json"
        self._atomic_write(path, payload)

    def save_quarantined_record(
        self, run_id: str, source_name: str, source_job_id: str | None, payload: str | None
    ) -> None:
        """Save a quarantined job payload."""
        run_dir = self.get_run_dir(run_id)
        safe_id = source_job_id if source_job_id else "unknown_id"
        safe_name = f"{source_name}-{safe_id}".replace("/", "_").replace("\\", "_")
        path = run_dir / "quarantine" / f"{safe_name}.json"
        if payload is None:
            payload = "{}"
        self._atomic_write(path, payload)

    def save_manifest(self, run_id: str, manifest: RunManifest) -> None:
        """Save the run manifest and summary."""
        run_dir = self.get_run_dir(run_id)

        manifest_path = run_dir / "manifest.json"
        self._atomic_write(manifest_path, manifest.model_dump_json(indent=2))

        summary_path = run_dir / "summary.json"
        self._atomic_write(summary_path, manifest.summary.model_dump_json(indent=2))
