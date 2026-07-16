from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from inspire_visualizer_api.device.mapping import HandSide


class SetArmedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["set_armed"]
    side: HandSide
    armed: bool


class ExecutePoseMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["execute_pose"]
    side: HandSide
    command_id: str = Field(min_length=1, max_length=100)
    angles: list[int] = Field(min_length=6, max_length=6)
    speeds: list[int] = Field(min_length=6, max_length=6)
    forces: list[int] = Field(min_length=6, max_length=6)

    @field_validator("angles")
    @classmethod
    def validate_angles(cls, values: list[int]) -> list[int]:
        if any(value < 0 or value > 1000 for value in values):
            raise ValueError("angles must be in the range 0..1000")
        return values

    @field_validator("speeds")
    @classmethod
    def validate_speeds(cls, values: list[int]) -> list[int]:
        if any(value < 0 or value > 1000 for value in values):
            raise ValueError("speeds must be in the range 0..1000")
        return values

    @field_validator("forces")
    @classmethod
    def validate_forces(cls, values: list[int]) -> list[int]:
        if any(value < 0 or value > 3000 for value in values):
            raise ValueError("forces must be in the range 0..3000")
        return values


ClientMessage = Annotated[SetArmedMessage | ExecutePoseMessage, Field(discriminator="type")]
client_message_adapter = TypeAdapter(ClientMessage)
