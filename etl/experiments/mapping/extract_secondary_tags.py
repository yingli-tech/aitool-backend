from __future__ import annotations

import json
import sys
from pathlib import Path


MAPPING_DIR = Path(__file__).resolve().parent


def load_mappings(input_path: Path) -> list[dict]:
    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    mappings = data.get("mappings")

    if not isinstance(mappings, list):
        raise ValueError("Input JSON must contain a 'mappings' list.")

    return mappings


def extract_unique_secondary_tags(mappings: list[dict]) -> list[str]:
    tags = {
        item["secondary_tag"].strip()
        for item in mappings
        if isinstance(item.get("secondary_tag"), str)
        and item["secondary_tag"].strip()
    }

    return sorted(tags, key=str.lower)


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python extract_secondary_tags.py "
            "<normalized_functions_raw.json>"
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.is_absolute():
        input_path = MAPPING_DIR / input_path

    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    try:
        mappings = load_mappings(input_path)
        secondary_tags = extract_unique_secondary_tags(mappings)
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)

    output_path = input_path.with_name(
        input_path.stem.replace("_raw", "_secondary_tags") + ".json"
    )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            secondary_tags,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Raw mappings: {len(mappings)}")
    print(f"Unique secondary tags: {len(secondary_tags)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()