import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Count consolidated taxonomy tags "
            "and their source tags."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Consolidated tag JSON file.",
    )


    parser.add_argument(
        "--target-level",
        required=True,
        choices=("secondary", "primary"),
        help="Taxonomy level contained in the input file.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Input file not found: {args.input}"
        )

    with args.input.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if args.target_level == "secondary":
        tag_list_key = "secondary_tags"
        source_list_key = "source_tags"
        target_label = "secondary tags"
        source_label = "source tags"
    else:
        tag_list_key = "primary_tags"
        source_list_key = "source_secondary_tags"
        target_label = "primary tags"
        source_label = "source secondary tags"

    total_target_tags = 0
    total_source_tags = 0

    print("Tags per pocket:")
    print("-" * 50)

    for pocket in data:
        pocket_id = pocket["pocket_id"]
        target_tags = pocket.get(tag_list_key, [])

        target_tag_count = len(target_tags)

        source_tag_count = sum(
            len(item.get(source_list_key, []))
            for item in target_tags
        )

        total_target_tags += target_tag_count
        total_source_tags += source_tag_count

        print(
            f"Pocket {pocket_id}: "
            f"{target_tag_count} {target_label}, "
            f"{source_tag_count} {source_label}"
        )

    print("-" * 60)
    print(f"Total pockets: {len(data)}")
    print(f"Total {target_label}: {total_target_tags}")
    print(f"Total {source_label}: {total_source_tags}")



if __name__ == "__main__":
    main()
