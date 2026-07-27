import json
from pathlib import Path

from radar_vagas.core.normalization.adapters.registry import NormalizationAdapterRegistry

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_dataset.json"


def test_golden_dataset_regression_eval():
    assert FIXTURE_PATH.is_file(), f"Golden dataset fixture not found at {FIXTURE_PATH}"
    records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(records) >= 8, "Golden dataset must contain at least 8 manually verified records"

    registry = NormalizationAdapterRegistry()

    for item in records:
        source_name = item["source_name"]
        payload = item["payload"]
        expected = item["expected"]
        record_id = item["id"]

        adapter = registry.get_adapter(source_name)
        canonical = adapter.normalize_payload(
            payload=payload,
            observation_id=f"obs_{record_id}",
            raw_content_hash="a" * 64,
            source_name=source_name,
        )

        for key, exp_val in expected.items():
            actual_val = getattr(canonical, key)
            if hasattr(actual_val, "value"):
                actual_val = actual_val.value
            assert actual_val == exp_val, (
                f"Golden dataset regression failure [{record_id}] on key '{key}': expected {exp_val}, got {actual_val}"
            )
