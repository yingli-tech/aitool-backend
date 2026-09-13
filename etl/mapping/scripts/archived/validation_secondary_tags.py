import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Validate secondary-tag assignments against clustered tags."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Cluster JSON file without vectors.",
    )
    parser.add_argument(
        "--consolidated-input",
        required=True,
        type=Path,
        help="Consolidated secondary-tag JSON file.",
    )
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as f:
        clusters = json.load(f)

    with args.consolidated_input.open("r", encoding="utf-8") as f:
        consolidated_pockets = json.load(f)

    # 用 pocket_id 方便按 pocket 对照
    consolidated_by_id = {
        pocket["pocket_id"]: pocket
        for pocket in consolidated_pockets
    }

    missing_pockets = []
    missing_tags = []
    unexpected_tags = []
    duplicate_assignments = []

    # 检查每个 pocket 内 source_tag 是否刚好出现一次
    for pocket_data in clusters.values():
        pocket_id = pocket_data["pocket_id"]

        input_tags = [
            item["tag"]
            for item in pocket_data["items"]
        ]

        result = consolidated_by_id.get(pocket_id)

        if result is None:
            missing_pockets.append(pocket_id)
            continue

        assigned_tags = [
            source_tag
            for secondary in result.get("secondary_tags", [])
            for source_tag in secondary.get("source_tags", [])
        ]

        input_counter = Counter(input_tags)
        assigned_counter = Counter(assigned_tags)

        for tag in input_counter:
            if assigned_counter[tag] == 0:
                missing_tags.append((pocket_id, tag))
            elif assigned_counter[tag] > 1:
                duplicate_assignments.append(
                    (pocket_id, tag, assigned_counter[tag])
                )

        for tag in assigned_counter:
            if tag not in input_counter:
                unexpected_tags.append((pocket_id, tag))

    # 检查全局：一个 source_tag 是否对应多个 secondary_tag
    source_to_secondary = defaultdict(set)

    for pocket in consolidated_pockets:
        for secondary in pocket.get("secondary_tags", []):
            secondary_tag = secondary["secondary_tag"]

            for source_tag in secondary.get("source_tags", []):
                source_to_secondary[source_tag].add(secondary_tag)

    cross_pocket_conflicts = {
        source_tag: secondary_tags
        for source_tag, secondary_tags in source_to_secondary.items()
        if len(secondary_tags) > 1
    }

    print(f"Missing pockets: {len(missing_pockets)}")
    print(f"Missing source-tag assignments: {len(missing_tags)}")
    print(f"Unexpected source tags: {len(unexpected_tags)}")
    print(f"Duplicate assignments within a pocket: {len(duplicate_assignments)}")
    print(f"Source tags mapped to multiple secondary tags: {len(cross_pocket_conflicts)}")

    if (
        not missing_pockets
        and not missing_tags
        and not unexpected_tags
        and not duplicate_assignments
        and not cross_pocket_conflicts
    ):
        print("\nValidation passed: every source tag maps to exactly one secondary tag.")
    else:
        print("\nValidation failed. Inspect the lists below:")

        print("\nMissing tags:", missing_tags[:10])
        print("Unexpected tags:", unexpected_tags[:10])
        print("Duplicate assignments:", duplicate_assignments[:10])
        print("Cross-pocket conflicts:", list(cross_pocket_conflicts.items())[:10])


if __name__ == "__main__":
    main()
