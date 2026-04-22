from __future__ import annotations

from pydantic import BaseModel, Field


class GenreNode(BaseModel):
    id: int
    slug: str
    name: str
    color_hex: str
    parent_id: int | None
    station_count: int
    children: list[GenreNode] = Field(default_factory=list)


GenreNode.model_rebuild()
