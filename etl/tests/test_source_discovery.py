from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from schemas import CandidateToolRecord
from source_discovery import (
    build_candidate_record,
    deduplicate_records,
    discover_sources,
    extract_official_url,
    extract_source_description,
    extract_tool_links,
    load_config,
    normalize_official_url,
)


class SourceDiscoveryTests(unittest.TestCase):
    def test_load_config_uses_yaml_contract(self) -> None:
        config = load_config()
        self.assertEqual(config.seed_sources[0].source, "aitoolsdirectory")
        self.assertEqual(config.source_specific_discovery_rules[0].source, "aitoolsdirectory")

    def test_extract_tool_links_prefers_href(self) -> None:
        listing_page = """
        <article class="sv-tile">
          <a href="/tool/getsolved">
            <h3 class="sv-tile__title"> Getsolved </h3>
          </a>
        </article>
        """
        rule = load_config().source_specific_discovery_rules[0]
        entries = extract_tool_links(listing_page, "https://aitoolsdirectory.com/", rule)
        self.assertEqual(entries, [("Getsolved", "https://aitoolsdirectory.com/tool/getsolved")])

    def test_extract_official_url_removes_query_string(self) -> None:
        detail_page = '<a class="sv-button" href="https://getsolved.ai/?utm_source=aitoolsdirectory">Try it</a>'
        rule = load_config().source_specific_discovery_rules[0]
        self.assertEqual(extract_official_url(detail_page, rule), "https://getsolved.ai/")
        self.assertEqual(normalize_official_url("https://x.ai/path?a=1&b=2"), "https://x.ai/path")

    def test_extract_source_description_preserves_order_and_stops_after_terminal_list(self) -> None:
        detail_page = """
        <div class="sv-product-page__string sv-product-string sv-text-reset">
          <p>First paragraph.</p>
          <h2>Overview</h2>
          <p>Second paragraph.</p>
          <h3>Bullet Point Features</h3>
          <ul>
            <li>Feature one</li>
            <li>Feature two</li>
          </ul>
          <h2>Alternatives</h2>
          <p>Should not be included.</p>
        </div>
        """
        rule = load_config().source_specific_discovery_rules[0]
        description = extract_source_description(detail_page, rule)
        self.assertEqual(
            description,
            "First paragraph.\nOverview\nSecond paragraph.\nBullet Point Features\nFeature one\nFeature two",
        )

    def test_deduplicate_records_uses_normalized_name(self) -> None:
        records = [
            build_candidate_record(
                name="  Tool   One ",
                official_url="https://one.ai/",
                source="aitoolsdirectory",
                source_url="https://aitoolsdirectory.com/",
                source_description=None,
            ),
            build_candidate_record(
                name="Tool One",
                official_url="https://duplicate.ai/",
                source="aitoolsdirectory",
                source_url="https://aitoolsdirectory.com/",
                source_description=None,
            ),
            build_candidate_record(
                name=None,
                official_url=None,
                source="aitoolsdirectory",
                source_url="https://aitoolsdirectory.com/",
                source_description=None,
            ),
        ]
        deduped = deduplicate_records(records)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0].official_url, "https://one.ai/")

    def test_discover_sources_persists_json_output(self) -> None:
        config = load_config()
        listing_url = str(config.seed_sources[0].listing_pages[0])
        detail_url = "https://aitoolsdirectory.com/tool/getsolved"

        pages = {
            listing_url: """
            <article class="sv-tile">
              <a href="/tool/getsolved">
                <h3 class="sv-tile__title">Getsolved</h3>
              </a>
            </article>
            """,
            detail_url: """
            <a class="sv-button" href="https://getsolved.ai/?utm_source=aitoolsdirectory">Try it</a>
            <div class="sv-product-page__string sv-product-string sv-text-reset">
              <p>Gets things solved.</p>
              <h3>Bullet Point Features</h3>
              <ul><li>Fast</li></ul>
            </div>
            """,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "candidate_tool_records.json"
            with patch("source_discovery.fetch_page", side_effect=lambda url: pages[url]):
                records = discover_sources(
                    config.seed_sources,
                    config.source_specific_discovery_rules,
                    output_path,
                )

            self.assertEqual(
                records,
                [
                    CandidateToolRecord(
                        name="Getsolved",
                        official_url="https://getsolved.ai/",
                        source="aitoolsdirectory",
                        source_url="https://aitoolsdirectory.com/",
                        source_description="Gets things solved.\nBullet Point Features\nFast",
                    )
                ],
            )

            persisted = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted[0]["name"], "Getsolved")
            self.assertEqual(persisted[0]["official_url"], "https://getsolved.ai/")


if __name__ == "__main__":
    unittest.main()
