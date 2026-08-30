from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import urlopen

import yaml
from bs4 import BeautifulSoup
from bs4.element import Tag

from schemas import (
    CandidateToolRecord,
    SeedSource,
    SourceDiscoveryConfig,
    SourceDiscoveryRule,
    dump_candidate_records,
)


CONFIG_PATH = Path(__file__).with_name("source_discovery.yaml")
OUTPUT_PATH = Path(__file__).with_name("outputs") / "candidate_tool_records.json"


def load_config(config_path: Path = CONFIG_PATH) -> SourceDiscoveryConfig:
    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)
    return SourceDiscoveryConfig.model_validate(raw_config)


def fetch_page(url: str) -> str:
    with urlopen(url) as response:  # nosec B310
        return response.read().decode("utf-8", errors="replace")


def get_listing_page_urls(seed_source: SeedSource) -> list[str]:
    return [str(seed_source.listing_pages[0])]


def extract_tool_links(listing_page: str, base_url: str, rule: SourceDiscoveryRule) -> list[tuple[str | None, str | None]]:
    soup = BeautifulSoup(listing_page, "html.parser")
    entries: list[tuple[str | None, str | None]] = []
    for container in soup.select(rule.listing_container_selector):
        name_element = container.select_one(rule.tool_name_selector)
        link_element = container.select_one(rule.tool_link_selector)
        name = normalize_text(name_element.get_text(" ", strip=True)) if name_element else None
        detail_url = None
        if link_element and link_element.get("href"):
            detail_url = urljoin(base_url, str(link_element["href"]))
        entries.append((name or None, detail_url))
    return entries


def extract_official_url(detail_page: str, rule: SourceDiscoveryRule) -> str | None:
    soup = BeautifulSoup(detail_page, "html.parser")
    for link in soup.select(rule.detail_try_it_selector):
        href = link.get("href")
        if not href:
            continue
        return normalize_official_url(str(href))
    return None


def extract_source_description(detail_page: str, rule: SourceDiscoveryRule) -> str | None:
    soup = BeautifulSoup(detail_page, "html.parser")
    container = soup.select_one(rule.detail_description_container_selector)
    if container is None:
        return None

    allowed_tags = set(rule.detail_description_include_tags)
    terminal_headings = set(rule.detail_description_terminal_headings)
    collected: list[str] = []
    collect_terminal_list = False
    terminal_section_completed = False

    for element in container.children:
        if not isinstance(element, Tag):
            continue
        if element.name not in allowed_tags and element.name != "ul":
            continue
        if terminal_section_completed:
            break

        text = normalize_text(element.get_text(" ", strip=True))
        if not text:
            continue

        if element.name in {"h2", "h3", "h4", "h5", "h6"} and text in terminal_headings:
            collected.append(text)
            collect_terminal_list = True
            continue

        if element.name == "ul" and collect_terminal_list:
            for item in element.find_all("li", recursive=False):
                item_text = normalize_text(item.get_text(" ", strip=True))
                if item_text:
                    collected.append(item_text)
            terminal_section_completed = True
            continue

        if collect_terminal_list:
            terminal_section_completed = True
            break

        if element.name in allowed_tags:
            collected.append(text)

    if not collected:
        return None
    return "\n".join(collected)


def build_candidate_record(
    *,
    name: str | None,
    official_url: str | None,
    source: str,
    source_url: str,
    source_description: str | None,
) -> CandidateToolRecord:
    return CandidateToolRecord(
        name=name,
        official_url=official_url,
        source=source,
        source_url=source_url,
        source_description=source_description,
    )


def discover_from_source(seed_source: SeedSource, rule: SourceDiscoveryRule) -> list[CandidateToolRecord]:
    candidates: list[CandidateToolRecord] = []
    for listing_url in get_listing_page_urls(seed_source):
        print("listing_url:\n", listing_url)
        listing_page = fetch_page(listing_url)
        print("listing page length:", len(listing_page))
        print("\n")
        print(listing_page[:500])
        print("\n")
        print(listing_page)
        print("\n")
        tool_entries = extract_tool_links(listing_page, str(rule.base_url), rule)
        print("tool entries count:", len(tool_entries))
        print("\n")
        print("first few:", tool_entries[:3])
        for name, detail_url in tool_entries:
            detail_page = fetch_page(detail_url) if detail_url else ""
            official_url = extract_official_url(detail_page, rule) if detail_page else None
            source_description = extract_source_description(detail_page, rule) if detail_page else None
            candidates.append(
                build_candidate_record(
                    name=name,
                    official_url=official_url,
                    source=seed_source.source,
                    source_url=str(seed_source.source_url),
                    source_description=source_description,
                )
            )
    return deduplicate_records(candidates)


def discover_sources(
    seed_sources: list[SeedSource],
    source_specific_discovery_rules: list[SourceDiscoveryRule],
    output_path: Path = OUTPUT_PATH,
) -> list[CandidateToolRecord]:
    rules_by_source = {rule.source: rule for rule in source_specific_discovery_rules}
    records: list[CandidateToolRecord] = []
    for seed_source in seed_sources:
        if not seed_source.active:
            continue
        rule = rules_by_source.get(seed_source.source)
        if rule is None:
            continue
        records.extend(discover_from_source(seed_source, rule))
    deduped_records = deduplicate_records(records)
    persist_results(deduped_records, output_path)
    return deduped_records


def deduplicate_records(records: list[CandidateToolRecord]) -> list[CandidateToolRecord]:
    seen_names: set[str] = set()
    deduped: list[CandidateToolRecord] = []
    for record in records:
        normalized_name = normalize_name_for_dedup(record.name)
        if normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)
        deduped.append(record)
    return deduped


def normalize_official_url(url: str) -> str:
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, "", ""))


def normalize_name_for_dedup(name: str | None) -> str:
    if name is None:
        return ""
    return normalize_text(name)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def persist_results(records: list[CandidateToolRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(dump_candidate_records(records), handle, indent=2, ensure_ascii=False)


def main() -> None:
    config = load_config()
    print(config)
    discover_sources(config.seed_sources, config.source_specific_discovery_rules, OUTPUT_PATH)


if __name__ == "__main__":
    main()
