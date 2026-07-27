from radar_vagas.core.normalization.adapters.arbeitnow import ArbeitnowNormalizer
from radar_vagas.core.normalization.adapters.base import BaseNormalizationAdapter
from radar_vagas.core.normalization.adapters.greenhouse import GreenhouseNormalizer
from radar_vagas.core.normalization.adapters.lever import LeverNormalizer
from radar_vagas.core.normalization.adapters.remotive import RemotiveNormalizer
from radar_vagas.core.normalization.taxonomy import TaxonomyManager


class NormalizationAdapterRegistry:
    """Registry mapping source_name or source_type to specific NormalizationAdapter classes."""

    def __init__(self, taxonomy_manager: TaxonomyManager | None = None) -> None:
        self.taxonomy = taxonomy_manager or TaxonomyManager()
        self._registry: dict[str, type[BaseNormalizationAdapter]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("greenhouse", GreenhouseNormalizer)
        self.register("ats_greenhouse", GreenhouseNormalizer)
        self.register("lever", LeverNormalizer)
        self.register("ats_lever", LeverNormalizer)
        self.register("remotive", RemotiveNormalizer)
        self.register("arbeitnow", ArbeitnowNormalizer)

    def register(self, key: str, adapter_cls: type[BaseNormalizationAdapter]) -> None:
        self._registry[key.lower()] = adapter_cls

    def get_adapter(
        self, source_identifier: str, rule_version: str = "1.0.0"
    ) -> BaseNormalizationAdapter:
        key = source_identifier.strip().lower()
        if not key:
            raise ValueError("A non-empty source identifier is required for normalization")

        adapter_cls = self._registry.get(key)
        if adapter_cls is not None:
            return adapter_cls(taxonomy_manager=self.taxonomy, rule_version=rule_version)

        # Catalog names qualify the provider (for example,
        # ``greenhouse_gitlab``). Delimited matching avoids accidentally
        # treating an unrelated name such as ``cleverjobs`` as Lever.
        for reg_key, adapter_cls in sorted(
            self._registry.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if key.startswith(f"{reg_key}_") or key.endswith(f"_{reg_key}"):
                return adapter_cls(taxonomy_manager=self.taxonomy, rule_version=rule_version)

        raise ValueError(f"No normalization adapter registered for source: {source_identifier}")
