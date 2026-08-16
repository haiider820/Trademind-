from typing import Literal

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    token: str = Field(min_length=20)
    platform: Literal["android", "ios", "web"]
