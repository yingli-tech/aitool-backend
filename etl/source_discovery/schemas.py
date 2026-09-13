from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SeedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    source_url: HttpUrl
    active: bool = True
    listing_pages: list[HttpUrl] = Field(min_length=1)



class CandidateToolRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None
    official_url: str | None
    source: str
    source_url: str
    source_description: str | None


class SourceDiscoveryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_sources: list[SeedSource] = Field(min_length=1)
    


class UrlResolutionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_tools: int
    redirect_success: int
    redirect_403: int
    redirect_other_failure: int


def dump_candidate_records(records: list[CandidateToolRecord]) -> list[dict[str, Any]]:
    return [record.model_dump(mode="json") for record in records]
