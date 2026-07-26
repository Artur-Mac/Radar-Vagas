"""CLI entrypoint for Radar-Vagas application."""

import argparse
import sys
from pathlib import Path

from radar_vagas import __version__
from radar_vagas.core.config import get_settings
from radar_vagas.core.logging import setup_logging
from radar_vagas.domain.models import RunState
from radar_vagas.infrastructure.llm.ollama_client import OllamaClient
from radar_vagas.sources.catalog import get_active_sources, load_catalog


def positive_int(value: str) -> int:
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer")
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be a positive integer")
    return ivalue


def main(args: list[str] | None = None) -> int:
    """CLI entrypoint function."""
    parser = argparse.ArgumentParser(
        prog="radar-vagas",
        description="Data Career Radar - Local-First Job Intelligence Platform",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: doctor / check-llm
    subparsers.add_parser("doctor", help="Run local Ollama and model diagnostic checks")
    subparsers.add_parser(
        "check-llm", help="Check local Ollama server connectivity and model status"
    )

    # Command: info
    subparsers.add_parser("info", help="Display current environment configuration")

    # Command: sources
    sources_parser = subparsers.add_parser(
        "sources", help="List registered job data sources from the catalog"
    )
    sources_parser.add_argument(
        "--active-only",
        action="store_true",
        default=False,
        help="Show only active sources",
    )
    sources_parser.add_argument(
        "--catalog-dir",
        type=str,
        default=None,
        help="Path to catalog directory (default: catalogs/)",
    )

    # Command: collect
    collect_parser = subparsers.add_parser("collect", help="Execute initial job ingestion pipeline")
    collect_parser.add_argument(
        "--source", action="append", help="Specific source to run (repeatable)"
    )
    collect_parser.add_argument("--source-type", type=str, help="Specific source type to run")
    collect_parser.add_argument(
        "--limit", type=positive_int, help="Global limit of records to fetch"
    )
    collect_parser.add_argument(
        "--per-source-limit", type=positive_int, help="Limit of records per source"
    )
    collect_parser.add_argument(
        "--scheduling-quantum",
        type=positive_int,
        default=25,
        help="Maximum records requested from one source before rotating (default: 25)",
    )
    collect_parser.add_argument(
        "--catalog-dir", type=str, default="catalogs", help="Path to catalog directory"
    )
    collect_parser.add_argument(
        "--output-dir", type=str, default="data", help="Output directory for runs"
    )
    collect_parser.add_argument(
        "--dry-run", action="store_true", help="Do not persist records to disk"
    )
    collect_parser.add_argument(
        "--fail-fast", action="store_true", help="Fail fast on configuration errors"
    )

    # Command: runs
    runs_parser = subparsers.add_parser("runs", help="Manage ingestion runs")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command")

    runs_show = runs_subparsers.add_parser("show", help="Show details of a specific run")
    runs_show.add_argument("run_id", type=str, help="The ID of the run to show")
    runs_show.add_argument("--output-dir", type=str, default="data", help="Base directory for runs")

    # Command: history
    history_parser = subparsers.add_parser("history", help="Manage historical duckdb+cas storage")
    history_subparsers = history_parser.add_subparsers(dest="history_command", required=True)

    history_import = history_subparsers.add_parser(
        "import", help="Import all runs from local storage into historical storage"
    )
    history_import.add_argument(
        "--output-dir", type=str, default="data", help="Base directory for local runs"
    )
    history_import.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_replay = history_subparsers.add_parser(
        "replay", help="Replay records from a specific run"
    )
    history_replay.add_argument("run_id", type=str, help="The ID of the run to replay")
    history_replay.add_argument("--db-path", type=str, help="Path to DuckDB database")
    history_replay.add_argument("--limit", type=positive_int, help="Limit number of output records")
    replay_output = history_replay.add_mutually_exclusive_group()
    replay_output.add_argument("--json", action="store_true", help="Output as JSON array")
    replay_output.add_argument("--jsonl", action="store_true", help="Output as JSON lines")

    history_init = history_subparsers.add_parser(
        "init", help="Initialize historical database schema"
    )
    history_init.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_stats = history_subparsers.add_parser(
        "stats", help="Show statistics of the historical database"
    )
    history_stats.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_verify = history_subparsers.add_parser(
        "verify", help="Verify integrity of historical data and CAS blobs"
    )
    history_verify.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_backup = history_subparsers.add_parser(
        "backup", help="Create an atomic snapshot backup of history DB and blobs"
    )
    history_backup.add_argument(
        "--dest-dir", type=str, required=True, help="Destination directory for backup snapshot"
    )
    history_backup.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_restore = history_subparsers.add_parser(
        "restore", help="Restore history DB and blobs from a backup snapshot"
    )
    history_restore.add_argument(
        "--backup-dir", type=str, required=True, help="Directory containing backup snapshot"
    )
    history_restore.add_argument(
        "--target-dir", type=str, default="data", help="Target data directory (default: data/)"
    )
    history_restore.add_argument(
        "--force", action="store_true", help="Overwrite target directory if non-empty"
    )
    history_restore.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_clean = history_subparsers.add_parser(
        "clean", help="Derive versioned cleaned source text for observations"
    )
    history_clean.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_prune = history_subparsers.add_parser(
        "prune", help="Preview or execute retention pruning"
    )
    history_prune.add_argument("--max-age-days", type=int, help="Maximum age of runs in days")
    history_prune.add_argument(
        "--keep-min-runs", type=int, default=5, help="Minimum number of latest runs to keep"
    )
    history_prune.add_argument(
        "--force", action="store_true", help="Execute deletion (default is preview mode)"
    )
    history_prune.add_argument("--db-path", type=str, help="Path to DuckDB database")

    history_req = history_subparsers.add_parser(
        "reprocess-quarantine",
        help="Attempt to reprocess records from historical quarantine",
    )
    history_req.add_argument("--db-path", type=str, help="Path to DuckDB database")

    parsed_args = parser.parse_args(args)

    settings = get_settings()
    logger = setup_logging(settings)

    if parsed_args.command in ("doctor", "check-llm"):
        logger.info("Executing local environment & LLM diagnostic check...")
        client = OllamaClient(settings=settings)
        diag = client.get_diagnostic()

        print("\n" + "=" * 60)
        print("🔍 RADAR-VAGAS LOCAL DIAGNOSTIC REPORT")
        print("=" * 60)
        print(f"• Environment:        {settings.environment}")
        print(f"• Database Path:      {settings.db_path}")
        print(f"• Ollama Server URL:  {diag.server_url}")
        print(f"• Configured Model:   {diag.configured_model}")
        print(f"• Server Available:   {'YES' if diag.server_available else 'NO'}")
        print(f"• Model Installed:    {'YES' if diag.model_installed else 'NO'}")
        if diag.available_models:
            print(f"• Installed Models:   {', '.join(diag.available_models)}")
        print(f"\nStatus Message:\n  {diag.message}")
        print("=" * 60 + "\n")
        return 0

    if parsed_args.command == "info":
        print("\n" + "=" * 60)
        print("⚙️ RADAR-VAGAS CONFIGURATION")
        print("=" * 60)
        print(f"• Version:           {__version__}")
        print(f"• Environment:       {settings.environment}")
        print(f"• Log Level:         {settings.log_level}")
        print(f"• Database Path:     {settings.db_path}")
        print(f"• Ollama Base URL:   {settings.ollama_base_url}")
        print(f"• Ollama Model:      {settings.ollama_model}")
        print("=" * 60 + "\n")
        return 0

    if parsed_args.command == "sources":
        catalog_dir = Path(parsed_args.catalog_dir or "catalogs")
        if not catalog_dir.is_dir():
            print(f"❌ Catalog directory not found: {catalog_dir}")
            return 1

        try:
            sources = load_catalog(catalog_dir)
        except ValueError as e:
            print(f"❌ Catalog Validation Error:\n{e}")
            return 1
        if parsed_args.active_only:
            sources = get_active_sources(sources)

        print("\n" + "=" * 60)
        print("📋 RADAR-VAGAS SOURCE CATALOG")
        print("=" * 60)
        if not sources:
            print("  No sources found.")
        else:
            for src in sources:
                status = "🟢 active" if src.active else "⚪ inactive"
                print(f"  • {src.name:<30} [{src.source_type.value}] {status}")
                if src.board_identifier:
                    print(f"    board: {src.board_identifier}")
                if src.company_identifier:
                    print(f"    company: {src.company_identifier}")
        print(f"\n  Total: {len(sources)} source(s)")
        print("=" * 60 + "\n")
        return 0

    if parsed_args.command == "collect":
        catalog_dir = Path(parsed_args.catalog_dir)
        output_dir = Path(parsed_args.output_dir)

        if not catalog_dir.is_dir():
            print(f"❌ Catalog directory not found: {catalog_dir}")
            return 1 if parsed_args.fail_fast else 0

        try:
            sources = load_catalog(catalog_dir)
        except ValueError as e:
            print(f"❌ Catalog Validation Error:\n{e}")
            return 1

        sources = get_active_sources(sources)

        if parsed_args.source:
            sources = [s for s in sources if s.name in parsed_args.source]
        if parsed_args.source_type:
            sources = [s for s in sources if s.source_type.value == parsed_args.source_type]

        if not sources:
            print("❌ No active sources match the criteria.")
            return 1

        print(f"🚀 Starting collection across {len(sources)} sources...")

        from radar_vagas.core.ingestion import ConnectorRunner
        from radar_vagas.infrastructure.http import HttpPolicy, create_http_client
        from radar_vagas.infrastructure.storage import LocalStorage
        from radar_vagas.sources.registry import build_default_registry

        registry = build_default_registry()
        storage = LocalStorage(output_dir)
        if parsed_args.dry_run:
            print("⚠️ DRY RUN ENABLED - No files or directories will be persisted.")

        with create_http_client(HttpPolicy()) as client:
            runner = ConnectorRunner(registry=registry, storage=storage, client=client)
            manifest = runner.run(
                configs=sources,
                global_limit=parsed_args.limit,
                per_source_limit=parsed_args.per_source_limit,
                scheduling_quantum=parsed_args.scheduling_quantum,
                fail_fast=parsed_args.fail_fast,
                persist=not parsed_args.dry_run,
            )

        print("\n" + "=" * 60)
        print("📊 INGESTION SUMMARY")
        print("=" * 60)
        print(f"Run ID:      {manifest.summary.run_id}")
        print(f"Duration:    {manifest.summary.duration_seconds:.2f}s")
        print(f"Sources:     {manifest.summary.total_sources_executed} executed")
        print(f"Fetched:     {manifest.summary.total_fetched}")
        print(f"Valid:       {manifest.summary.total_valid}")
        print(f"Relevant:    {manifest.summary.total_relevant}")
        print(f"Rejected:    {manifest.summary.total_rejected}")
        print(f"Quarantined: {manifest.summary.total_quarantined}")
        print(f"Duplicates:  {manifest.summary.total_duplicated}")
        if not parsed_args.dry_run:
            print(f"Manifest:    {storage.get_run_dir(manifest.summary.run_id) / 'manifest.json'}")
        print("=" * 60 + "\n")

        # Exit code evaluation
        if manifest.summary.total_sources_executed == 0:
            return 1

        success_count = sum(
            1
            for s in manifest.summary.sources.values()
            if s.state in (RunState.success, RunState.empty, RunState.skipped_global_limit)
        )

        if success_count == 0:
            return 1  # Total failure
        if success_count < manifest.summary.total_sources_executed:
            return 2  # Partial failure

        return 0

    if parsed_args.command == "runs" and getattr(parsed_args, "runs_command", None) == "show":
        output_dir = Path(parsed_args.output_dir)
        manifest_path = output_dir / "runs" / parsed_args.run_id / "manifest.json"

        if not manifest_path.exists():
            print(f"❌ Run manifest not found: {manifest_path}")
            return 1

        import json

        data = json.loads(manifest_path.read_text())
        summary = data.get("summary", {})

        print("\n" + "=" * 60)
        print(f"📊 RUN MANIFEST: {parsed_args.run_id}")
        print("=" * 60)
        print(f"Started:     {summary.get('started_at')}")
        print(f"Duration:    {summary.get('duration_seconds', 0):.2f}s")
        print(f"Sources:     {summary.get('total_sources_executed', 0)} executed")
        print(f"Fetched:     {summary.get('total_fetched', 0)}")
        print(f"Valid:       {summary.get('total_valid', 0)}")
        print(f"Relevant:    {summary.get('total_relevant', 0)}")
        print("=" * 60 + "\n")

        for name, src in summary.get("sources", {}).items():
            print(f"  • {name:<30} [{src.get('state')}]")
            print(
                f"    fetched: {src.get('records_fetched', 0)}, "
                f"valid: {src.get('records_valid', 0)}, "
                f"relevant: {src.get('records_relevant', 0)}"
            )

        print("=" * 60 + "\n")
        return 0

    if parsed_args.command == "history":
        from radar_vagas.core.history_service import HistoryService
        from radar_vagas.infrastructure.history import HistoricalStorage
        from radar_vagas.infrastructure.storage import LocalStorage

        db_path_str = parsed_args.db_path or settings.db_path
        db_path = Path(db_path_str)
        data_dir = db_path.parent.parent if db_path.parent.name == "db" else db_path.parent

        if parsed_args.history_command == "import":
            output_dir = Path(parsed_args.output_dir)
            storage = LocalStorage(output_dir)
            history = HistoricalStorage(data_dir, db_path=db_path)
            service = HistoryService(storage, history)

            print(f"📦 Importing runs from {storage.runs_dir} into historical storage...")
            report = service.import_all_runs()
            history.close()

            print("\n" + "=" * 60)
            print("📊 IMPORT REPORT")
            print("=" * 60)
            print(f"Discovered Runs:  {report.discovered_runs}")
            print(f"Imported Runs:    {report.imported_runs}")
            print(f"Skipped Runs:     {report.skipped_runs}")
            print(f"Failed Runs:      {report.failed_runs}")
            print(f"Imported Records: {report.imported_records}")
            print(f"Rejected Records: {report.rejected_records}")

            if report.errors:
                print("\nErrors:")
                for err in report.errors:
                    print(f"  - [{err.run_dir}] {err.error_type}: {err.message}")

            print("=" * 60 + "\n")

            if report.discovered_runs == 0:
                return 0
            if report.failed_runs == 0:
                return 0
            if report.imported_runs == 0 and report.failed_runs > 0:
                return 1
            if report.imported_runs > 0 and report.failed_runs > 0:
                return 2

            return 0

        if parsed_args.history_command == "replay":
            history = HistoricalStorage(data_dir, db_path=db_path)
            service = HistoryService(LocalStorage(Path("data")), history)

            run_exists = service.run_exists(parsed_args.run_id)
            records = service.get_run_records(parsed_args.run_id)
            history.close()

            if not run_exists:
                print(f"❌ Run not imported: {parsed_args.run_id}.")
                return 1

            total_records = len(records)
            if parsed_args.limit:
                records = records[: parsed_args.limit]

            if parsed_args.json or parsed_args.jsonl:
                import json

                if parsed_args.json:
                    print(json.dumps([r.model_dump(mode="json") for r in records], indent=2))
                else:
                    for r in records:
                        print(json.dumps(r.model_dump(mode="json")))
                return 0

            print("\n" + "=" * 60)
            print(f"🔄 REPLAY RESULTS: {parsed_args.run_id}")
            print("=" * 60)
            displayed_records = records if parsed_args.limit else records[:20]
            for rec in displayed_records:
                print(f"  • {rec.source_name:<15} | Job ID: {rec.source_job_id}")
            print(f"\n  Total Records: {total_records}")
            if len(displayed_records) < total_records:
                print(f"  Showing:       {len(displayed_records)} (use --limit to change)")
            print("=" * 60 + "\n")
            return 0

        if parsed_args.history_command == "init":
            history = HistoricalStorage(data_dir, db_path=db_path)
            print(f"✅ Historical storage initialized at {history.db_path}")
            history.close()
            return 0

        if parsed_args.history_command == "stats":
            history = HistoricalStorage(data_dir, db_path=db_path)
            runs = history.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
            jobs = history.conn.execute("SELECT COUNT(*) FROM source_jobs").fetchone()[0]
            obs = history.conn.execute("SELECT COUNT(*) FROM source_job_observations").fetchone()[0]
            blobs = history.conn.execute("SELECT COUNT(*) FROM raw_blobs").fetchone()[0]
            history.close()

            print("\n" + "=" * 60)
            print("📈 HISTORICAL STORAGE STATS")
            print("=" * 60)
            print(f"  Runs:           {runs}")
            print(f"  Source Jobs:    {jobs}")
            print(f"  Observations:   {obs}")
            print(f"  CAS Blobs:      {blobs}")
            print("=" * 60 + "\n")
            return 0

        if parsed_args.history_command == "verify":
            history = HistoricalStorage(data_dir, db_path=db_path)
            report = history.verify_integrity()
            history.close()

            print("\n" + "=" * 60)
            print("🔍 HISTORICAL STORAGE VERIFICATION")
            print("=" * 60)
            print(f"  Database Blobs:       {report.total_database_blobs}")
            print(f"  Missing Blobs:        {len(report.missing_files)}")
            print(f"  Corrupt Blobs:        {len(report.corrupt_files)}")
            print(f"  Missing Metadata:     {len(report.missing_metadata)}")
            print(f"  Orphan Blobs (DB):    {len(report.orphan_database_blobs)}")
            print(f"  Orphan Blobs (FS):    {len(report.orphan_files)}")
            print(f"  Invalid Paths:        {len(report.invalid_blob_paths)}")
            status = "🟢 VALID" if report.is_valid else "🔴 INVALID"
            print(f"  Status:               {status}")
            print("=" * 60 + "\n")
            return 0 if report.is_valid else 1

        if parsed_args.history_command == "backup":
            dest_dir = Path(parsed_args.dest_dir)
            with HistoricalStorage(data_dir, db_path=db_path) as history:
                service = HistoryService(LocalStorage(Path("data")), history)
                manifest = service.backup(dest_dir)

            print("\n" + "=" * 60)
            print("💾 BACKUP COMPLETED")
            print("=" * 60)
            print(f"  Backup ID:        {manifest.backup_id}")
            print(f"  Destination:      {dest_dir}")
            print(f"  DB Checksum:      {manifest.db_checksum[:16]}...")
            print(f"  Total Blobs:      {manifest.total_blobs}")
            print(f"  Total Bytes:      {manifest.total_bytes}")
            print("=" * 60 + "\n")
            return 0

        if parsed_args.history_command == "restore":
            backup_dir = Path(parsed_args.backup_dir)
            target_dir = Path(parsed_args.target_dir)

            try:
                storage = HistoryService.restore(
                    backup_dir=backup_dir, target_data_dir=target_dir, force=parsed_args.force
                )
                storage.close()
                print("\n" + "=" * 60)
                print("♻️ RESTORE COMPLETED & VERIFIED")
                print("=" * 60)
                print(f"  Source Backup:    {backup_dir}")
                print(f"  Target Data Dir:  {target_dir}")
                print("=" * 60 + "\n")
                return 0
            except Exception as e:  # noqa: BLE001
                print(f"❌ Restore failed: {e}")
                return 1

        if parsed_args.history_command == "clean":
            with HistoricalStorage(data_dir, db_path=db_path) as history:
                service = HistoryService(LocalStorage(Path("data")), history)
                count = service.clean_all_observations()

            print(f"✨ Cleaned and versioned {count} observation(s).")
            return 0

        if parsed_args.history_command == "prune":
            from radar_vagas.domain.models import RetentionPolicy

            policy = RetentionPolicy(
                active=True,
                max_age_days=parsed_args.max_age_days,
                keep_minimum_runs=parsed_args.keep_min_runs,
            )

            with HistoricalStorage(data_dir, db_path=db_path) as history:
                service = HistoryService(LocalStorage(Path("data")), history)
                report = service.prune_retention(policy, force=parsed_args.force)

            mode_str = "PREVIEW (DRY-RUN)" if report.preview_only else "DESTRUCTIVE EXECUTION"
            print("\n" + "=" * 60)
            print(f"🧹 RETENTION PRUNING [{mode_str}]")
            print("=" * 60)
            print(f"  Pruned Runs:          {report.pruned_runs}")
            print(f"  Pruned Observations:  {report.pruned_observations}")
            print(f"  Pruned Blobs:         {report.pruned_blobs}")
            print(f"  Freed Bytes:          {report.freed_bytes}")
            if report.preview_only:
                print("  Note: No data was modified. Use --force to execute deletion.")
            print("=" * 60 + "\n")
            return 0

        if parsed_args.history_command == "reprocess-quarantine":
            with HistoricalStorage(data_dir, db_path=db_path) as history:
                service = HistoryService(LocalStorage(Path("data")), history)
                count = service.reprocess_quarantine()

            print(f"🔄 Reprocessed {count} quarantined record(s).")
            return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
