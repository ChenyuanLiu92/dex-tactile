from ipaddress import IPv4Address
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from inspire_visualizer_api.device.tactile import TactileProfile


class EndpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    host: IPv4Address
    port: int = Field(default=6000, ge=1, le=65535)
    tactile_profile: TactileProfile = "disabled"
    tactile_target_hz: int = Field(default=20, ge=1, le=20)


class HandsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: EndpointConfig
    right: EndpointConfig

    @model_validator(mode="after")
    def endpoints_must_be_distinct(self) -> "HandsConfig":
        left_endpoint = (self.left.host, self.left.port)
        right_endpoint = (self.right.host, self.right.port)
        if self.left.enabled and self.right.enabled and left_endpoint == right_endpoint:
            raise ValueError("enabled left and right hands must use different endpoints")
        return self

    @classmethod
    def defaults(cls) -> "HandsConfig":
        return cls(
            left=EndpointConfig(
                host=IPv4Address("192.0.2.11"),
                port=6000,
                tactile_profile="piezoresistive_v1",
            ),
            right=EndpointConfig(host=IPv4Address("192.0.2.10"), port=6000),
        )


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> HandsConfig:
        if not self.path.exists():
            return HandsConfig.defaults()
        return HandsConfig.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, config: HandsConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        temporary_path.replace(self.path)
