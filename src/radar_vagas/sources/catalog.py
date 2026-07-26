"""TOML-driven source catalog loader and filter utilities."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from pydantic import ValidationError

from radar_vagas.domain.models import SourceConfig

logger = logging.getLogger("radar_vagas.sources.catalog")


def load_catalog_file(path: Path) -> list[SourceConfig]:
    """Parse a single TOML catalog file into ``SourceConfig`` instances.

    Each file must contain a ``[[sources]]`` array-of-tables.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the TOML structure is invalid or missing ``sources``.
    """
    if not path.exists():
        msg = f"Catalog file not found: {path}"
        raise FileNotFoundError(msg)

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    sources_raw = data.get("sources")
    if sources_raw is None:
        msg = f"Catalog file {path.name} is missing the [[sources]] table"
        raise ValueError(msg)

    if not isinstance(sources_raw, list):
        msg = f"'sources' in {path.name} must be a TOML array-of-tables ([[sources]])"
        raise TypeError(msg)

    configs: list[SourceConfig] = []
    errors: list[str] = []
    for idx, entry in enumerate(sources_raw):
        try:
            configs.append(SourceConfig(**entry))
        except (ValidationError, TypeError) as exc:
            errors.append(f"entry #{idx}: {exc}")
    if errors:
        msg = f"Invalid source entries in {path.name}: " + "; ".join(errors)
        raise ValueError(msg)
    return configs


def load_catalog(catalog_dir: Path) -> list[SourceConfig]:
    """Load all ``.toml`` files in *catalog_dir* and return merged configs.

    Files are processed in sorted order for deterministic results.
    """
    if not catalog_dir.is_dir():
        msg = f"Catalog directory not found: {catalog_dir}"
        raise FileNotFoundError(msg)

    all_configs: list[SourceConfig] = []
    for toml_path in sorted(catalog_dir.glob("*.toml")):
        all_configs.extend(load_catalog_file(toml_path))

    names = [config.name for config in all_configs]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        msg = f"Duplicate source names in catalog: {', '.join(duplicates)}"
        raise ValueError(msg)

    logger.info("Loaded %d source configs from %s", len(all_configs), catalog_dir)
    return all_configs


def get_active_sources(configs: list[SourceConfig]) -> list[SourceConfig]:
    """Return only sources where ``active`` is True."""
    return [c for c in configs if c.active]
