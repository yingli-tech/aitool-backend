from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlsplit, urlunsplit, urlunparse

import requests
import yaml
from requests import HTTPError, RequestException

try:
    from .schemas import (
        CandidateToolRecord,
        SeedSource,
        SourceDiscoveryConfig,
        UrlResolutionSummary,
        dump_candidate_records,
    )
except ImportError:  # Support direct execution: python source_discovery.py
    from schemas import (
        CandidateToolRecord,
        SeedSource,
        SourceDiscoveryConfig,
        UrlResolutionSummary,
        dump_candidate_records,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "etl_config.yaml"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "candidate_tool_records.json"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "source_discovery_summary.json"
LOG_PATH = PROJECT_ROOT / "outputs" / "source_discovery_log.txt"
REQUEST_TIMEOUT_SECONDS = 10


logger = logging.getLogger("source_discovery")


def load_config(config_path: Path = CONFIG_PATH) -> SourceDiscoveryConfig:
    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}
    return SourceDiscoveryConfig.model_validate(raw_config["source_discovery"])


def configure_logging(log_path: Path = LOG_PATH) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False


def log_progress(message: str) -> None:
    logger.info(message)


def build_default_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        )
    }


def fetch_json(url: str, *, params: dict[str, str] | None = None) -> dict:
    log_progress(f"Requesting JSON data: {url}")
    response = requests.get(
        url,
        params=params,
        headers=build_default_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def resolve_final_url(url: str) -> tuple[str | None, str]:
    if not url:
        log_progress("Third-party redirect URL is empty; skipping official URL resolution")
        return None, "other_failure"
    try:
        log_progress(f"Following redirect to resolve official URL: {url}")
        response = requests.get(
            url,
            headers=build_default_headers(),
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        error_body = ""
        if error.response is not None:
            error_body = normalize_text(error.response.text)[:500]
        if status_code == 403:
            log_progress(
                f"Redirect resolution returned 403: {url}; "
                f"status_code={status_code}; error={error}; response_body={error_body}"
            )
            return None, "403"
        log_progress(
            f"Redirect resolution failed with HTTP error: {url}; "
            f"status_code={status_code}; error={error}; response_body={error_body}"
        )
        return None, "other_failure"
    except RequestException as error:
        status_code = None
        response = getattr(error, "response", None)
        error_body = ""
        if response is not None:
            status_code = response.status_code
            error_body = normalize_text(response.text)[:500]
        log_progress(
            f"Redirect resolution failed due to network or SSL error: {url}; "
            f"status_code={status_code}; error={error}; response_body={error_body}"
        )
        return None, "other_failure"
    log_progress(f"Resolved official URL successfully: {response.url}")
    return response.url, "success"


def get_listing_page_urls(seed_source: SeedSource) -> list[str]:
    return [str(seed_source.listing_pages[0])]


def extract_tool_names(listing_response: dict) -> list[str | None]:
    filters_values = listing_response.get("table", {}).get("filtersValues", [])
    if not filters_values:
        return []

    values = filters_values[0].get("values", [])
    names: list[str | None] = []
    for item in values:
        raw_name = item.get("name")
        if raw_name is None:
            names.append(None)
            continue
        name = normalize_text(str(raw_name))
        names.append(name or None)
    return names


def build_detail_request(listing_url: str, name: str) -> tuple[str, dict[str, str]]:
    parsed = urlparse(listing_url)
    sheet_path = parsed.path.split("/filters/")[0]
    detail_base_url = urlunparse((parsed.scheme, parsed.netloc, sheet_path, "", "", ""))
    listing_query = parse_qs(parsed.query)
    options = listing_query.get("options", [""])[0]

    slug = build_tool_slug(name)
    query_payload = {"getRowBy": {"slug": slug}}
    query = base64.b64encode(
        json.dumps(query_payload, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8")

    return detail_base_url, {"query": query, "options": options}


def extract_official_url(detail_response: dict) -> tuple[str | None, str]:
    rows = detail_response.get("table", {}).get("rows", [])
    if not rows:
        return None, "other_failure"

    redirect_url = rows[0].get("cells", {}).get("URL-", {}).get("value")
    if not redirect_url:
        return None, "other_failure"
    final_url, resolution_status = resolve_final_url(str(redirect_url))
    if final_url is None:
        return None, resolution_status
    return normalize_official_url(final_url), resolution_status


def extract_source_description(detail_response: dict) -> str | None:
    rows = detail_response.get("table", {}).get("rows", [])
    if not rows:
        return None

    description = rows[0].get("cells", {}).get("Longdescription-", {}).get("value")
    if description is None:
        return None
    normalized = normalize_multiline_text(str(description))
    return normalized or None


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


def discover_from_source(seed_source: SeedSource) -> list[CandidateToolRecord]:
    candidates: list[CandidateToolRecord] = []
    resolution_summary = UrlResolutionSummary(
        total_tools=0,
        redirect_success=0,
        redirect_403=0,
        redirect_other_failure=0,
    )

    for listing_url in get_listing_page_urls(seed_source):
        log_progress(f"Starting source discovery for: {seed_source.source}")
        log_progress("Fetching tool list")
        listing_response = fetch_json(listing_url)
        tool_names = extract_tool_names(listing_response)
        resolution_summary.total_tools += len(tool_names)
        log_progress(
            f"Tool list fetched successfully. Discovered {len(tool_names)} tools."
        )

        for index, name in enumerate(tool_names, start=1):
            if name is None:
                log_progress(
                    f"Tool #{index} has an empty name; skipping official URL and description retrieval"
                )
                resolution_summary.redirect_other_failure += 1
                candidates.append(
                    build_candidate_record(
                        name=None,
                        official_url=None,
                        source=seed_source.source,
                        source_url=str(seed_source.source_url),
                        source_description=None,
                    )
                )
                continue

            log_progress(f"Fetching tool #{index}: {name}")
            detail_url, detail_params = build_detail_request(listing_url, name)
            detail_response = fetch_json(detail_url, params=detail_params)
            official_url, resolution_status = extract_official_url(detail_response)
            source_description = extract_source_description(detail_response)
            if official_url:
                log_progress(f"Retrieved official URL for {name}: {official_url}")
            else:
                log_progress(f"Failed to retrieve official URL for {name}. Status: {resolution_status}")
            if source_description:
                log_progress(f"Retrieved description for {name}")
            else:
                log_progress(f"Failed to retrieve description for {name}")
            if resolution_status == "success":
                resolution_summary.redirect_success += 1
            elif resolution_status == "403":
                resolution_summary.redirect_403 += 1
            else:
                resolution_summary.redirect_other_failure += 1

            candidates.append(
                build_candidate_record(
                    name=name,
                    official_url=official_url,
                    source=seed_source.source,
                    source_url=str(seed_source.source_url),
                    source_description=source_description,
                )
            )

    log_progress(
        "Redirect resolution summary: "
        f"success={resolution_summary.redirect_success}, "
        f"403={resolution_summary.redirect_403}, "
        f"other_failure={resolution_summary.redirect_other_failure}"
    )
    persist_summary(resolution_summary, SUMMARY_PATH)
    return deduplicate_records(candidates)


def discover_sources(
    seed_sources: list[SeedSource],
    output_path: Path = OUTPUT_PATH,
) -> list[CandidateToolRecord]:

    records: list[CandidateToolRecord] = []

    for seed_source in seed_sources:
        if not seed_source.active:
            continue
        
        records.extend(discover_from_source(seed_source))

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


def build_tool_slug(name: str) -> str:
    return normalize_text(name).lower().replace(" ", "-")


def normalize_official_url(url: str) -> str:
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, "", ""))


def normalize_name_for_dedup(name: str | None) -> str:
    if name is None:
        return ""
    return normalize_text(name)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_multiline_text(value: str) -> str:
    lines = [normalize_text(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def persist_results(records: list[CandidateToolRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(dump_candidate_records(records), handle, indent=2, ensure_ascii=False)


def persist_summary(summary: UrlResolutionSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary.model_dump(mode="json"), handle, indent=2, ensure_ascii=False)


def main() -> None:
    configure_logging()
    log_progress("Source Discovery started")
    config = load_config()
    discover_sources(config.seed_sources, OUTPUT_PATH)
    log_progress(f"Source Discovery finished. Log written to: {LOG_PATH}")


if __name__ == "__main__":
    main()
