from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AlliumBase(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
