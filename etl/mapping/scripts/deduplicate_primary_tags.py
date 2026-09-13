import argparse
import json
from pathlib import Path


def normalize_tag(tag: str) -> str:
    """
    Normalize a tag for duplicate comparison.

    The original spelling of the first occurrence is retained
    in the output.
    """
    return " ".join(tag.split()).casefold()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Deduplicate primary tags generated independently "
            "across K-Means pockets."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Consolidated primary-tag JSON file.",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for deduplicated primary tags.",
    )

    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    with input_path.open("r", encoding="utf-8") as file:
        pockets = json.load(file)

    deduplicated = {}

    total_primary_tag_occurrences = 0
    duplicate_primary_tag_occurrences = 0

    for pocket in pockets:
        pocket_id = pocket["pocket_id"]

        for primary_item in pocket.get("primary_tags", []):
            primary_tag = primary_item["primary_tag"].strip()

            source_secondary_tags = primary_item.get(
                "source_secondary_tags",
                [],
            )

            normalized_primary_tag = normalize_tag(primary_tag)

            total_primary_tag_occurrences += 1

            if normalized_primary_tag not in deduplicated:
                deduplicated[normalized_primary_tag] = {
                    "primary_tag": primary_tag,
                    "source_secondary_tags": [],
                    "source_pocket_ids": [],
                }
            else:
                duplicate_primary_tag_occurrences += 1

            output_item = deduplicated[
                normalized_primary_tag
            ]

            if pocket_id not in output_item["source_pocket_ids"]:
                output_item["source_pocket_ids"].append(
                    pocket_id
                )

            existing_source_tags = {
                normalize_tag(tag)
                for tag
                in output_item["source_secondary_tags"]
            }

            for secondary_tag in source_secondary_tags:
                cleaned_secondary_tag = secondary_tag.strip()
                normalized_secondary_tag = normalize_tag(
                    cleaned_secondary_tag
                )

                if (
                    normalized_secondary_tag
                    not in existing_source_tags
                ):
                    output_item[
                        "source_secondary_tags"
                    ].append(cleaned_secondary_tag)

                    existing_source_tags.add(
                        normalized_secondary_tag
                    )

    results = list(deduplicated.values())

    results.sort(
        key=lambda item: normalize_tag(
            item["primary_tag"]
        )
    )

    for item in results:
        item["source_pocket_ids"].sort()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=4,
        )

    print("Primary-tag deduplication completed.")
    print(
        "Original primary-tag occurrences: "
        f"{total_primary_tag_occurrences}"
    )
    print(
        "Duplicate primary-tag occurrences merged: "
        f"{duplicate_primary_tag_occurrences}"
    )
    print(
        "Unique primary tags: "
        f"{len(results)}"
    )
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()