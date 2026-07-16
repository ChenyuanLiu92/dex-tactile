from pathlib import Path

import pytest
from pydantic import ValidationError

from inspire_visualizer_api.config import ConfigStore, EndpointConfig, HandsConfig


def test_project_defaults_use_non_routable_documentation_endpoints() -> None:
    config = HandsConfig.defaults()

    assert str(config.left.host) == "192.0.2.11"
    assert str(config.right.host) == "192.0.2.10"
    assert config.left.tactile_profile == "piezoresistive_v1"
    assert config.left.tactile_target_hz == 20
    assert config.right.tactile_profile == "disabled"


def test_existing_endpoint_config_defaults_tactile_to_disabled() -> None:
    endpoint = EndpointConfig.model_validate(
        {"enabled": True, "host": "192.0.2.10", "port": 6000}
    )

    assert endpoint.tactile_profile == "disabled"
    assert endpoint.tactile_target_hz == 20


def test_enabled_hands_cannot_share_the_same_endpoint() -> None:
    with pytest.raises(ValidationError):
        HandsConfig(
            left=EndpointConfig(host="192.0.2.10", port=6000),
            right=EndpointConfig(host="192.0.2.10", port=6000),
        )


def test_config_store_round_trips_hand_endpoints(tmp_path: Path) -> None:
    path = tmp_path / "hands.json"
    store = ConfigStore(path)
    config = HandsConfig(
        left=EndpointConfig(host="192.0.2.11", port=6000),
        right=EndpointConfig(host="192.0.2.10", port=6001),
    )

    store.save(config)

    assert store.load() == config
