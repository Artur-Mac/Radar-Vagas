# Data Career Radar (Radar-Vagas)

**Data Career Radar** is a job market and career intelligence platform focused on Data
Engineering, Data Science, Machine Learning, Analytics Engineering, MLOps, and AI Engineering
roles. It currently runs locally and is designed to evolve into an accessible hosted web
product.

---

## 1. Project Goal & Current Status (Época 5 Completed)

Épocas 1–4 established the local connector framework, multi-source ingestion service, local run storage, and hardened historical database layer with CAS blob storage. **Época 5 (Job Normalization)** is now fully implemented and verified, providing a deterministic, versioned normalization engine (`CanonicalJobPost`), TOML taxonomy mapping, field provenance tracking (`FieldProvenance`), inter-process history locking (`HistoryLock`), and golden dataset regression testing.

**Completed Features:**
- **Core Package**: Typed configuration, CLI, formatted logging, and Ollama diagnostics.
- **Source Catalog & Governance**: TOML source catalog entries with governance metadata (`access_type`, `authentication_required`, `terms_url`).
- **Connector Framework**: Production connectors for Remotive, Arbeitnow, Greenhouse, and Lever.
- **HTTP Policy**: Centralized timeouts, retries with exponential backoff, rate limiting, and user-agent management.
- **Historical Storage & CAS**: Idempotent DuckDB metadata storage linked to SHA-256 CAS payload blobs with integrity verification.
- **Inter-Process Locking (Phase 0)**: `HistoryLock` protecting DuckDB & CAS across import, cleaning, backup, restore, pruning, and normalization.
- **Canonical Schema & Provenance (Época 5)**: `CanonicalJobPost` model with strict `None` defaults for missing values and full field provenance.
- **Deterministic Source Adapters**: Source-specific normalizers for Greenhouse, Lever, Remotive, and Arbeitnow powered by TOML taxonomies (`catalogs/taxonomies/`).
- **Idempotency & Versioning**: Multi-version normalization rules preserved per `(observation_id, rule_version)`.
- **Golden Dataset**: Versioned 8+ record golden dataset regression suite (`tests/fixtures/golden_dataset.json`).

> [!NOTE]
> **Next product milestone**: Época 6 introduces evidence-based hybrid enrichment:
> deterministic extraction first, optional replaceable inference providers, shared caching,
> and a fully functional no-LLM mode. See
> [Product Direction](docs/PRODUCT_DIRECTION.md).

---

## 2. Requirements

- **Linux OS**
- **Python**: $\ge 3.12.3$
- **uv**: Python package and environment manager
- **Ollama** (Optional): Used only for bounded local provider evaluation; it is not required
  for collection, normalization, or future website users.

---

## 3. Installation & Environment Setup

1. **Clone & Set Up Environment**:
   ```bash
   uv sync --extra dev --frozen
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

   Relevant configuration includes `ENVIRONMENT`, `LOG_LEVEL`, `DB_PATH`, and optional
   Ollama diagnostic settings.

---

## 4. Execution & Diagnostics

### Application CLI Commands
You can run the application using `radar-vagas` or `uv run radar-vagas`:

- **Display Configuration & Doctor Check**:
  ```bash
  uv run radar-vagas info
  uv run radar-vagas doctor
  ```

- **List Registered Data Sources**:
  ```bash
  uv run radar-vagas sources --active-only
  ```

- **Collect a bounded sample**:
  ```bash
  uv run radar-vagas collect --limit 50 --per-source-limit 25 --scheduling-quantum 10
  ```

- **Inspect a persisted collection run**:
  ```bash
  uv run radar-vagas runs show <run-id>
  ```

- **Manage Historical Storage**:
  ```bash
  uv run radar-vagas history init --db-path data/radar_vagas.db
  uv run radar-vagas history import --output-dir data --db-path data/radar_vagas.db
  uv run radar-vagas history stats --db-path data/radar_vagas.db
  uv run radar-vagas history verify --db-path data/radar_vagas.db
  uv run radar-vagas history replay <run-id> --db-path data/radar_vagas.db --limit 10 --jsonl
  uv run radar-vagas history clean --db-path data/radar_vagas.db
  uv run radar-vagas history backup --dest-dir backups/snapshot_1 --db-path data/radar_vagas.db
  uv run radar-vagas history restore --backup-dir backups/snapshot_1 --target-dir restored_data --force
  # Preview is the default; --force executes deletion.
  uv run radar-vagas history prune --max-age-days 30 --keep-min-runs 5
  uv run radar-vagas history prune --max-age-days 30 --keep-min-runs 5 --force
  uv run radar-vagas history quarantine --db-path data/radar_vagas.db
  ```

- **Normalize Raw Observations into Canonical Job Schema**:
  ```bash
  # Preview normalization in dry-run mode
  uv run radar-vagas normalize --db-path data/radar_vagas.db --dry-run

  # Execute normalization with rule version 1.0.0
  uv run radar-vagas normalize --db-path data/radar_vagas.db --rule-version 1.0.0

  # Re-process with a new rule version without overwriting prior history
  uv run radar-vagas normalize --db-path data/radar_vagas.db --rule-version 1.1.0
  ```

---

## 5. Developer Quality Tools (Test, Lint, Format)

- **Run Automated Test Suite**:
  ```bash
  make test
  # or: uv run pytest
  ```
  *(Note: All unit tests run 100% offline without network or Ollama dependencies)*

- **Run Linter & Formatter**:
  ```bash
  make lint
  make format
  ```

---

## 6. Directory Structure

```text
Radar-Vagas/
├── pyproject.toml              # Dependencies, build configs, CLI script entrypoint
├── Makefile                    # Developer shortcut commands
├── README.md                   # System documentation and setup guide
├── .env.example                # Environment configuration template
├── .github/workflows/ci.yml    # GitHub Actions CI workflow
├── catalogs/                   # TOML source catalog files
│   ├── aggregators.toml        # Remotive, Arbeitnow
│   ├── greenhouse.toml         # Greenhouse ATS boards
│   ├── lever.toml              # Lever ATS companies
│   └── taxonomies/             # Role family, seniority, work arrangement TOML taxonomies
├── docs/                       # Project specifications & reports
│   ├── AGENTS.md
│   ├── Epochs.md
│   ├── ARCHITECTURE.md
│   ├── EPOCH4_REPORT.md
│   ├── EPOCH5_REPORT.md
│   └── PRODUCT_DIRECTION.md
├── src/
│   └── radar_vagas/
│       ├── cli.py              # Application CLI Entrypoint
│       ├── core/
│       │   ├── cleaner.py      # TextCleaner service
│       │   ├── history_service.py # Historical operations & backup/restore
│       │   ├── normalization/  # Normalization service & source adapters
│       │   │   ├── taxonomy.py # TOML taxonomy loader
│       │   │   ├── service.py  # NormalizationService
│       │   │   └── adapters/   # Greenhouse, Lever, Remotive, Arbeitnow adapters
│       │   └── ingestion.py    # ConnectorRunner with scheduling quantum
│       ├── domain/
│       │   ├── canonical.py    # CanonicalJobPost, FieldProvenance, enums
│       │   └── models.py       # RawJobRecord, CleanedSourceText, etc.
│       └── infrastructure/
│           ├── history.py      # DuckDB storage, CAS SHA-256 blobs, migrations
│           └── lock.py         # HistoryLock inter-process lock
└── tests/                      # 100% offline test suite
```
