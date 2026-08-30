from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SeedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    source_url: HttpUrl
    active: bool = True
    listing_pages: list[HttpUrl] = Field(min_length=1)


class SourceDiscoveryRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    base_url: HttpUrl
    listing_container_selector: str
    tool_name_selector: str
    tool_link_selector: str
    detail_try_it_selector: str
    detail_description_container_selector: str
    detail_description_include_tags: list[str] = Field(min_length=1)
    detail_description_terminal_headings: list[str] = Field(default_factory=list)


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
    source_specific_discovery_rules: list[SourceDiscoveryRule] = Field(min_length=1)


def dump_candidate_records(records: list[CandidateToolRecord]) -> list[dict[str, Any]]:
    return [record.model_dump(mode="json") for record in records]
