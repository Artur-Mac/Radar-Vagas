import pytest
from pydantic import ValidationError

from radar_vagas.domain.models import SourceConfig, SourceType


def test_source_config_governance_validation():
    # Valid config
    config = SourceConfig(
        name="valid", source_type=SourceType.aggregator_api, base_url="http://example.com"
    )
    assert config.name == "valid"

    # Missing env var
    with pytest.raises(ValidationError, match="credential_env_var must be set"):
        SourceConfig(
            name="invalid",
            source_type=SourceType.aggregator_api,
            base_url="http://example.com",
            authentication_required=True,
        )

    # Valid authenticated
    authenticated = SourceConfig(
        name="valid_auth",
        source_type=SourceType.aggregator_api,
        base_url="http://example.com",
        authentication_required=True,
        credential_env_var="MY_TOKEN",
    )
    assert authenticated.credential_env_var == "MY_TOKEN"

    # Missing terms_url for paid
    with pytest.raises(ValidationError, match="terms_url must be provided"):
        SourceConfig(
            name="invalid_paid",
            source_type=SourceType.aggregator_api,
            base_url="http://example.com",
            access_type="paid",
        )

    # Valid paid
    paid = SourceConfig(
        name="valid_paid",
        source_type=SourceType.aggregator_api,
        base_url="http://example.com",
        access_type="paid",
        terms_url="http://example.com/terms",
    )
    assert paid.access_type == "paid"
