import argparse
import json
import os
from pathlib import Path

from openai import OpenAI



MODEL = "gpt-5.6"


FUNCTION_SYSTEM_PROMPT = """
You are performing semantic consolidation of AI tool function tags.

The input is one semantic pocket produced by K-Means clustering.
Each pocket contains function tags that are semantically related, but they
do not necessarily represent exactly the same capability.

Your task is to consolidate the tags into a minimal set of clear,
reusable secondary function tags.

Definition:
A capability represents a distinct function that an AI tool can perform.

Rules:
1. Tags that express the same core capability using different wording
   should be consolidated into one secondary tag.

2. Being in the same domain does not mean that tags represent the same
   capability.

3. Do not merge tags that represent meaningfully different functions.

4. A K-Means pocket may contain one or multiple capabilities.
   Do NOT assume that one pocket must produce exactly one secondary tag.

5. Generate the minimum number of secondary tags necessary to preserve
   meaningful capability distinctions.

6. Prefer concise, general, reusable capability names rather than
   overly specific wording copied from an individual input tag.

7. Every input tag must be assigned to exactly one secondary tag.

Return valid JSON only.
"""

USE_CASE_SYSTEM_PROMPT = """
You are performing semantic consolidation of AI tool use-case tags.

The input is one semantic pocket produced by K-Means clustering.
Each pocket contains use-case tags that are semantically related, but they
do not necessarily represent exactly the same user goal or workflow.

Your task is to consolidate the tags into a minimal set of clear,
reusable secondary use-case tags.

Definition:
A use case represents a distinct goal, task, workflow, or usage scenario.

Rules:
1. Tags that express the same core use case using different wording
   should be consolidated into one secondary tag.

2. Being in the same domain does not mean that tags represent the same
   use case.

3. Do not merge tags that represent meaningfully different user goals.

4. A K-Means pocket may contain one or multiple use cases.
   Do NOT assume that one pocket must produce exactly one secondary tag.

5. Generate the minimum number of secondary tags necessary to preserve
   meaningful use-case distinctions.

6. Prefer concise, general, reusable use-case names rather than
   overly specific wording copied from an individual input tag.

7. Every input tag must be assigned to exactly one secondary tag.

Return valid JSON only.
"""


def get_system_prompt(tag_type: str) -> str:
    if tag_type == "functions":
        return FUNCTION_SYSTEM_PROMPT
    return USE_CASE_SYSTEM_PROMPT


def build_user_prompt(pocket_id, tags, tag_type):
    tags_text = "\n".join(f"- {tag}" for tag in tags)
    tag_label = "function" if tag_type == "functions" else "use-case"

    return f"""
Consolidate the following {tag_label}-tag pocket.

Pocket ID: {pocket_id}

Function tags:
{tags_text}

Return the result using exactly this JSON structure:

{{
    "pocket_id": {pocket_id},
    "secondary_tags": [
        {{
            "secondary_tag": "Example Capability",
            "source_tags": [
                "original tag 1",
                "original tag 2"
            ]
        }}
    ]
}}
"""


def consolidate_pocket(client, pocket_id, tags, tag_type):
    response = client.responses.create(
        model=MODEL,
        instructions=get_system_prompt(tag_type),
        input=build_user_prompt(pocket_id, tags, tag_type),
    )

    result_text = response.output_text.strip()

    return json.loads(result_text)


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate clustered function tags into secondary tags."
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
        help="Directory for the consolidated JSON output.",
    )

    parser.add_argument(
        "--tag-type",
        required=True,
        choices=("functions", "use_cases"),
        help="Taxonomy represented by the clustered tags.",
    )

    args = parser.parse_args()

    input_path = args.input

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    if args.tag_type == "functions":
        output_filename = "consolidated_functions_secondary_tags.json"
    else:
        output_filename = "consolidated_use_cases_secondary_tags.json"

    output_path = args.output_dir / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading clusters from: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        clusters = json.load(f)

    print(f"Processing all {len(clusters)} pockets.")

    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY")
    )

    results = []

    for index, (_, pocket_data) in enumerate(
        clusters.items(),
        start=1
    ):
        pocket_id = pocket_data["pocket_id"]

        tags = [
            item["tag"]
            for item in pocket_data["items"]
        ]

        print(
            f"Processing pocket {pocket_id} "
            f"({index}/{len(clusters)}, {len(tags)} tags)..."
        )

        try:
            result = consolidate_pocket(
                client,
                pocket_id,
                tags,
                args.tag_type,
            )

            results.append(result)

        except Exception as e:
            print(
                f"Failed to process pocket {pocket_id}: {e}"
            )

            results.append({
                "pocket_id": pocket_id,
                "secondary_tags": [],
                "error": str(e)
            })

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=4
        )

    print("Consolidation completed.")
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()
