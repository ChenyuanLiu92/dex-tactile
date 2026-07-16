from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Side = Literal["left", "right"]


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class CalibrationSample(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=_to_camel, populate_by_name=True)

    point: str
    target_uv: tuple[float, float]
    observed_row: float
    observed_column: float
    peak: float = Field(ge=0)
    active: int = Field(ge=0)
    stable_ms: float = Field(ge=0)
    captured_at: float


class RegionCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=_to_camel, populate_by_name=True)

    region_id: str
    status: Literal["incomplete", "good", "review", "poor"]
    samples: list[CalibrationSample] = Field(default_factory=list)
    transform: dict[str, list[float]] | None = None
    residual: float | None = Field(default=None, ge=0)
    applied: bool = False
    sensor_rows: int | None = Field(default=None, ge=1)
    sensor_columns: int | None = Field(default=None, ge=1)


class TactileCalibrationDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    model: Literal["RH56DFTP"] = "RH56DFTP"
    side: Side
    host: str
    port: int = Field(ge=1, le=65535)
    profile: Literal["piezoresistive_v1"] = "piezoresistive_v1"
    regions: dict[str, RegionCalibration] = Field(default_factory=dict)
    drafts: dict[str, RegionCalibration] = Field(default_factory=dict)
    updated_at: str


class TactileCalibrationStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def key(side: Side, host: str, port: int, profile: str) -> str:
        return f"{side}|{host}|{port}|{profile}"

    def _load_records(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        import json

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload.get("records", {})

    def load(self, side: Side, host: str, port: int, profile: str) -> TactileCalibrationDocument | None:
        raw = self._load_records().get(self.key(side, host, port, profile))
        return TactileCalibrationDocument.model_validate(raw) if raw else None

    def save(self, document: TactileCalibrationDocument) -> None:
        records = self._load_records()
        records[self.key(document.side, document.host, document.port, document.profile)] = document.model_dump(mode="json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(__import__("json").dumps({"version": 1, "records": records}, indent=2), encoding="utf-8")
        temporary.replace(self.path)
