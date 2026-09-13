from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


# --------------------------------------------------
# Load data
# --------------------------------------------------

def load_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# Extract and count tags
# --------------------------------------------------

def extract_tag_counts(
    records: list[dict],
    field_name: str,
) -> list[dict]:

    counter = Counter()

    for record in records:

        values = record.get(field_name, [])

        if not isinstance(values, list):
            continue

        for value in values:

            if not isinstance(value, str):
                continue

            value = value.strip()

            if value:
                counter[value] += 1

    # Sort primarily by frequency descending,
    # then alphabetically for equal counts.
    sorted_tags = sorted(
        counter.items(),
        key=lambda item: (-item[1], item[0].lower()),
    )

    return [
        {
            "tag": tag,
            "count": count,
        }
        for tag, count in sorted_tags
    ]


# --------------------------------------------------
# Save JSON
# --------------------------------------------------

def save_json(
    data: list[dict],
    path: Path,
) -> None:

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract unique function and use-case tags from enriched records."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Enriched candidate-tool records JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for unique function and use-case tag JSON files.",
    )
    args = parser.parse_args()

    function_output_path = args.output_dir / "unique_functions.json"
    use_case_output_path = args.output_dir / "unique_use_cases.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(args.input)

    function_tags = extract_tag_counts(
        records,
        "function",
    )

    use_case_tags = extract_tag_counts(
        records,
        "use_case",
    )

    save_json(
        function_tags,
        function_output_path,
    )

    save_json(
        use_case_tags,
        use_case_output_path,
    )

    print("=" * 50)
    print("Tag Extraction")
    print("=" * 50)

    print(f"Total tools: {len(records)}")

    print()
    print(
        f"Unique function tags: "
        f"{len(function_tags)}"
    )

    print(
        f"Function output: "
        f"{function_output_path}"
    )

    print()
    print(
        f"Unique use case tags: "
        f"{len(use_case_tags)}"
    )

    print(
        f"Use case output: "
        f"{use_case_output_path}"
    )


if __name__ == "__main__":
    main()
