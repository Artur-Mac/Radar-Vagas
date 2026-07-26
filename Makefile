.PHONY: help setup format lint test doctor sources run-poc

help:
	@echo "Radar-Vagas Development Commands:"
	@echo "  make setup     - Create virtualenv and install all dependencies (including dev)"
	@echo "  make format    - Auto-format code using ruff"
	@echo "  make lint      - Check code linting and style using ruff"
	@echo "  make test      - Run automated test suite with pytest"
	@echo "  make doctor    - Run local environment & Ollama LLM diagnostic check"
	@echo "  make sources   - List all registered job data sources from the catalog"
	@echo "  make run-poc   - Execute experimental PoC pipeline script"

setup:
	uv sync --extra dev --frozen

format:
	uv run ruff format .

lint:
	uv run ruff check .

test:
	uv run pytest

doctor:
	uv run radar-vagas doctor

sources:
	uv run radar-vagas sources

run-poc:
	uv run python poc/run_poc.py
