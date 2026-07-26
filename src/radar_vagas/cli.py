"""CLI entrypoint for Radar-Vagas application."""

import argparse
import sys
from pathlib import Path

from radar_vagas import __version__
from radar_vagas.core.config import get_settings
from radar_vagas.core.logging import setup_logging
from radar_vagas.infrastructure.llm.ollama_client import OllamaClient
from radar_vagas.sources.catalog import get_active_sources, load_catalog


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
    collect_parser.add_argument("--source", action="append", help="Specific source to run (repeatable)")
    collect_parser.add_argument("--source-type", type=str, help="Specific source type to run")
    collect_parser.add_argument("--limit", type=int, help="Global limit of records to fetch")
    collect_parser.add_argument("--per-source-limit", type=int, help="Limit of records per source")
    collect_parser.add_argument("--catalog-dir", type=str, default="catalogs", help="Path to catalog directory")
    collect_parser.add_argument("--output-dir", type=str, default="data", help="Output directory for runs")
    collect_parser.add_argument("--dry-run", action="store_true", help="Do not persist records to disk")
    collect_parser.add_argument("--fail-fast", action="store_true", help="Fail fast on configuration errors")

    # Command: runs
    runs_parser = subparsers.add_parser("runs", help="Manage ingestion runs")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command")
    
    runs_show = runs_subparsers.add_parser("show", help="Show details of a specific run")
    runs_show.add_argument("run_id", type=str, help="The ID of the run to show")
    runs_show.add_argument("--output-dir", type=str, default="data", help="Base directory for runs")

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

        sources = load_catalog(catalog_dir)
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

        sources = load_catalog(catalog_dir)
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
        client = create_http_client(HttpPolicy())

        if parsed_args.dry_run:
            print("⚠️ DRY RUN ENABLED - No records will be persisted to disk.")
            import unittest.mock

            storage.save_raw_record = unittest.mock.MagicMock()  # type: ignore
            storage.save_quarantined_record = unittest.mock.MagicMock()  # type: ignore
            storage.save_manifest = unittest.mock.MagicMock()  # type: ignore

        runner = ConnectorRunner(registry=registry, storage=storage, client=client)

        manifest = runner.run(
            configs=sources,
            global_limit=parsed_args.limit,
            per_source_limit=parsed_args.per_source_limit,
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
