from __future__ import annotations

import json
from pathlib import Path


INPUT_PATH = (
    Path(__file__).with_name("outputs")
    / "candidate_tool_records.json"
)

OUTPUT_PATH = (
    Path(__file__).with_name("outputs")
    / "complete_candidate_tool_records.json"
)


REQUIRED_FIELDS = (
    "name",
    "official_url",
    "source",
    "source_url",
    "source_description",
)


def is_complete(record: dict) -> bool:
    """Return True if all required fields contain usable values."""
    return all(
        record.get(field) is not None
        and str(record.get(field)).strip() != ""
        for field in REQUIRED_FIELDS
    )


def filter_complete_records(records: list[dict]) -> list[dict]:
    """Keep only candidate records with all required fields populated."""
    return [record for record in records if is_complete(record)]


def main() -> None:
    with INPUT_PATH.open("r", encoding="utf-8") as file:
        records = json.load(file)

    complete_records = filter_complete_records(records)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            complete_records,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Total candidate records: {len(records)}")
    print(f"Complete records: {len(complete_records)}")
    print(f"Excluded records: {len(records) - len(complete_records)}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()