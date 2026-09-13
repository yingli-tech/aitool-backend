import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Count secondary and source tags in consolidated pockets."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Consolidated secondary-tag JSON file.",
    )
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as file:
        data = json.load(file)

    total_secondary_tags = 0
    total_source_tags = 0

    print("Tags per pocket:")
    print("-" * 50)

    for pocket in data:
        pocket_id = pocket["pocket_id"]
        secondary_tags = pocket.get("secondary_tags", [])

        secondary_tag_count = len(secondary_tags)
        source_tag_count = sum(
            len(item.get("source_tags", []))
            for item in secondary_tags
        )

        total_secondary_tags += secondary_tag_count
        total_source_tags += source_tag_count

        print(
            f"Pocket {pocket_id}: "
            f"{secondary_tag_count} secondary tags, "
            f"{source_tag_count} source tags"
        )

    print("-" * 50)
    print(f"Total pockets: {len(data)}")
    print(f"Total secondary tags: {total_secondary_tags}")
    print(f"Total source tags: {total_source_tags}")


if __name__ == "__main__":
    main()
