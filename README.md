# Data Career Radar (Radar-Vagas)

**Data Career Radar** is a local-first job market intelligence platform focused on Data Engineering, Data Science, Machine Learning, Analytics Engineering, MLOps, and AI Engineering roles.

---

## 1. Project Goal & Current Status (Época 2 - Source Catalog & Connector Framework)

Época 1 established a clean, reproducible, and well-tested technical foundation. Época 2 adds a catalogue-driven, contract-based connector framework for job data sources.

**Completed:**
- Core package structure under `src/radar_vagas/` with typed configuration, CLI, consistent formatted logging, and Ollama diagnostics.
- Source Catalog: TOML-driven configuration for all job data sources (`catalogs/`).
- Connector Framework: Protocol-based connector interface with 4 production-grade implementations (Remotive, Arbeitnow, Greenhouse, Lever).
- HTTP Policy Layer: Centralised timeouts, retries with exponential backoff, rate limiting, and user-agent management.
- Connector Registry: Factory-pattern mapping `SourceType → Connector` for extensibility.

> [!NOTE]
> **PoC Technical Review Note**: The initial PoC proved end-to-end data flow (ingestion, raw storage, canonical schema mapping, DuckDB analytics). However, per [TECHNICAL_REVIEW.md](poc/TECHNICAL_REVIEW.md), the PoC report does **NOT** constitute proof of local LLM quality (H4), LLM latency/throughput (H5), fuzzy deduplication (H6), or recommendation utility (H7) until a manually labeled evaluation dataset is executed.

---

## 2. Requirements

- **Linux OS**
- **Python**: $\ge 3.12.3$
- **uv**: Python package and environment manager
- **Ollama** (Optional): Local LLM inference server. (Note: Installed model on local host: `gemma4:26b`)

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

   Key configuration variables in `.env`:
   - `ENVIRONMENT`: `development` | `testing` | `production`
   - `LOG_LEVEL`: `INFO` | `DEBUG`
   - `DB_PATH`: `data/radar_vagas.db`
   - `OLLAMA_BASE_URL`: `http://localhost:11434`
   - `OLLAMA_MODEL`: `gemma4:26b` (or `llama3.2`)

---

## 4. Execution & Diagnostics

### Application CLI Commands
You can run the application using the `radar-vagas` command or `uv run radar-vagas`:

- **Display Application Configuration**:
  ```bash
  uv run radar-vagas info
  ```

- **Run Environment & Ollama Diagnostic Check**:
  ```bash
  uv run radar-vagas doctor
  ```
  *(Or `uv run radar-vagas check-llm`)*

- **List Registered Data Sources**:
  ```bash
  uv run radar-vagas sources
  uv run radar-vagas sources --active-only
  ```

The `doctor` command inspects whether the Ollama HTTP daemon is reachable and whether the configured model is installed locally. If Ollama is offline, it outputs a clear explanatory status message without crashing.

---

## 5. Source Catalog & Adding New Sources

Job data sources are configured as TOML files in the `catalogs/` directory. Each file defines one or more sources using the `[[sources]]` array-of-tables syntax.

### Example: Adding a new Greenhouse board

Create or edit `catalogs/greenhouse.toml`:

```toml
[[sources]]
name = "greenhouse_mycompany"
source_type = "ats_greenhouse"
base_url = "https://boards-api.greenhouse.io/v1/boards"
board_identifier = "mycompany"
active = true
request_timeout = 15.0
rate_limit_delay = 1.0
description = "My Company Greenhouse board"
```

### Supported Source Types

| Source Type       | Connector          | Required Field        |
|-------------------|--------------------|-----------------------|
| `aggregator_api`  | Remotive/Arbeitnow | —                     |
| `ats_greenhouse`  | Greenhouse         | `board_identifier`    |
| `ats_lever`       | Lever              | `company_identifier`  |

After adding a source, verify it appears in the catalog:
```bash
uv run radar-vagas sources
```

---

## 6. Developer Quality Tools (Test, Lint, Format)

All development commands are accessible via `make` shortcuts:

- **Run Automated Tests**:
  ```bash
  make test
  # or: uv run pytest
  ```
  *(Note: Unit tests run 100% offline and do not require network or an active Ollama daemon)*

- **Run Linter (Ruff)**:
  ```bash
  make lint
  # or: uv run ruff check .
  ```

- **Run Code Formatter**:
  ```bash
  make format
  # or: uv run ruff format .
  ```

---

## 7. Experimental PoC Execution (Optional)

The experimental PoC code remains preserved inside `poc/` for sandbox testing and reference:

```bash
make run-poc
# or: uv run python poc/run_poc.py
```

---

## 8. Directory Structure

```text
Radar-Vagas/
├── pyproject.toml              # Dependencies, build configs, CLI script entrypoint
├── Makefile                    # Developer shortcut commands
├── README.md                   # System documentation and setup guide
├── .env.example                # Environment configuration template
├── catalogs/                   # TOML source catalog files
│   ├── aggregators.toml        # Remotive, Arbeitnow
│   ├── greenhouse.toml         # Greenhouse ATS boards
│   └── lever.toml              # Lever ATS companies
├── docs/                       # Project specifications & architecture
│   ├── AGENTS.md
│   ├── Epochs.md
│   ├── POC.md
│   └── ARCHITECTURE.md
├── src/
│   └── radar_vagas/
│       ├── __init__.py         # Package version
│       ├── cli.py              # Application CLI Entrypoint
│       ├── core/               # Configuration & Logging
│       ├── domain/             # Domain Models, Schemas & Connector Protocol
│       │   ├── models.py       # CanonicalJob, SourceConfig, ConnectorResult, etc.
│       │   └── connector.py    # JobConnector Protocol (structural interface)
│       ├── connectors/         # Production connector implementations
│       │   ├── remotive.py     # Remotive aggregator API
│       │   ├── arbeitnow.py    # Arbeitnow aggregator API
│       │   ├── greenhouse.py   # Greenhouse ATS Board API
│       │   └── lever.py        # Lever ATS Postings API
│       ├── sources/            # Source catalog & connector registry
│       │   ├── catalog.py      # TOML catalog loader
│       │   └── registry.py     # SourceType → Connector factory registry
│       └── infrastructure/     # External Services & HTTP Policies
│           ├── http.py         # HttpPolicy, polite_get, retry/backoff
│           └── llm/
│               └── ollama_client.py
├── poc/                        # Experimental PoC scripts (sandbox)
│   ├── TECHNICAL_REVIEW.md
│   ├── connectors/
│   ├── data/
│   └── run_poc.py
└── tests/                      # Unit test suite (50 tests)
```

---

## 9. Current Limitations & Heuristic vs. LLM Distinction

- **Heuristic Engine vs. LLM**: The PoC uses deterministic rules for some extraction and classification tasks. These rules do not generate new prose, but can still produce false positives and false negatives and require evaluation against labeled data.
- **LLM Inference**: LLM enrichment via Ollama is optional and deferred. LLM quality, latency percentiles, and structured extraction precision will be formally evaluated in future epics using labeled ground-truth fixtures per [TECHNICAL_REVIEW.md](poc/TECHNICAL_REVIEW.md).
- **Connector Framework Ready, Ingestion Deferred**: The connector framework (Época 2) defines contracts, policies, and catalog management. Actual pipeline execution (fetch → store raw → normalize → deduplicate) will be implemented in Época 3.
