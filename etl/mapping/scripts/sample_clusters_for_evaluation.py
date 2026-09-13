import argparse
import csv
import json
import random
from pathlib import Path

RANDOM_SEED = 42
SAMPLE_SIZE = 70


def main():
    parser = argparse.ArgumentParser(
        description="Sample clustered tags for manual evaluation."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Cluster JSON file without vectors.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for the evaluation CSV.",
    )
    parser.add_argument(
        "--tag-type",
        required=True,
        choices=("functions", "use_cases"),
        help="Taxonomy represented by the clustered tags.",
    )
    args = parser.parse_args()

    output_filename = f"{args.tag_type}_cluster_evaluation.csv"
    output_path = args.output_dir / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load clusters
    with args.input.open("r", encoding="utf-8") as f:
        data = json.load(f)

    clusters = list(data.values())

    # Randomly sample 50 clusters with a fixed seed
    random.seed(RANDOM_SEED)
    sampled_clusters = random.sample(clusters, SAMPLE_SIZE)

    # Sort by pocket_id for easier manual review
    sampled_clusters.sort(key=lambda x: x["pocket_id"])

    # Write evaluation CSV
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "cluster_id",
            "sample_tags",
            "rating",
            "failure_reason",
        ])

        for cluster in sampled_clusters:
            tags = [
                item["tag"]
                for item in cluster["items"]
            ]

            writer.writerow([
                cluster["pocket_id"],
                " | ".join(tags),
                "",
                "",
            ])

    print(f"Sampled {SAMPLE_SIZE} clusters.")
    print(f"Evaluation file saved to: {output_path}")


if __name__ == "__main__":
    main()
