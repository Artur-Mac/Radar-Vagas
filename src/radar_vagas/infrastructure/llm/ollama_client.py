"""Ollama local LLM service diagnostic client."""

import httpx

from radar_vagas.core.config import Settings
from radar_vagas.domain.models import ServiceDiagnostic


class OllamaClient:
    """Client for local Ollama service inspection and diagnostic checks."""

    def __init__(
        self,
        settings: Settings | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        client: httpx.Client | None = None,
    ):
        if settings:
            self.base_url = str(settings.ollama_base_url).rstrip("/")
            self.model_name = settings.ollama_model
        else:
            self.base_url = (base_url or "http://localhost:11434").rstrip("/")
            self.model_name = model_name or "gemma4:26b"

        self._client = client

    def _get_http_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=3.0)

    def _fetch_models(self) -> tuple[bool, list[str]]:
        """Fetch server availability and installed models with one request."""
        client = self._get_http_client()
        should_close = self._client is None
        try:
            res = client.get(f"{self.base_url}/api/tags")
            if res.status_code != 200:
                return False, []
            models_raw = res.json().get("models", [])
            names = {
                str(model["name"])
                for model in models_raw
                if isinstance(model, dict) and model.get("name")
            }
            names.update(name.split(":", maxsplit=1)[0] for name in tuple(names) if ":" in name)
            return True, sorted(names)
        except (httpx.HTTPError, TypeError, ValueError):
            return False, []
        finally:
            if should_close:
                client.close()

    def is_server_available(self) -> bool:
        """Check if Ollama HTTP daemon is reachable."""
        available, _ = self._fetch_models()
        return available

    def list_models(self) -> list[str]:
        """Fetch list of models currently installed in local Ollama instance."""
        _, models = self._fetch_models()
        return models

    def get_diagnostic(self) -> ServiceDiagnostic:
        """Run complete diagnostic check and return structured status report."""
        server_ok, installed_models = self._fetch_models()

        if not server_ok:
            return ServiceDiagnostic(
                server_available=False,
                server_url=self.base_url,
                configured_model=self.model_name,
                model_installed=False,
                available_models=[],
                message=(
                    f"🟡 Ollama server is NOT reachable at '{self.base_url}'. "
                    "Make sure the Ollama daemon is running ('ollama serve'). "
                    "The application will operate using deterministic heuristic mode."
                ),
            )

        model_ok = self.model_name in installed_models

        if model_ok:
            msg = (
                f"🟢 Ollama server is ONLINE at '{self.base_url}' "
                f"and configured model '{self.model_name}' is INSTALLED."
            )
        else:
            msg = (
                f"🟠 Ollama server is ONLINE at '{self.base_url}', but configured "
                f"model '{self.model_name}' was NOT found in installed models ({installed_models}). "
                f"Run 'ollama pull {self.model_name}' to download it."
            )

        return ServiceDiagnostic(
            server_available=True,
            server_url=self.base_url,
            configured_model=self.model_name,
            model_installed=model_ok,
            available_models=installed_models,
            message=msg,
        )
