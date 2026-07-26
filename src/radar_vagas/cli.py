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
    subparsers.add_parser("doctor", help="Run local diagnostic check (Ollama, models, database)")
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
