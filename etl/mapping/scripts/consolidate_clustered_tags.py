import argparse
import json
import os
from pathlib import Path

from openai import OpenAI



MODEL = "gpt-5.6"


FUNCTION_SECONDARY_SYSTEM_PROMPT = """
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

USE_CASE_SECONDARY_SYSTEM_PROMPT = """
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

FUNCTION_PRIMARY_SYSTEM_PROMPT = """
You are organizing secondary AI tool function tags into a higher-level
primary function taxonomy.

The input is one semantic pocket produced by K-Means clustering.
Each pocket contains secondary function tags that are semantically related,
but they may belong to one or multiple broader capability families.

Your task is to consolidate the secondary tags into a minimal set of clear,
reusable primary function tags.

Definition:
A primary function tag represents a broad family of related AI tool
capabilities and must be more general than a secondary function tag.

Rules:
1. Group secondary tags that belong to the same broad capability family
   under one primary tag.

2. Primary tags must be broader than the input secondary tags.

3. Do not create one primary tag for every secondary tag unless they
   represent genuinely different broad capability families.

4. Being in the same domain does not necessarily mean that tags belong
   to the same primary capability.

5. A K-Means pocket may produce one or multiple primary tags.

6. Generate the minimum number of primary tags necessary to preserve
   meaningful high-level distinctions.

7. Prefer concise, stable, reusable taxonomy names.

8. Every input secondary tag must be assigned to exactly one primary tag.

Return valid JSON only.
"""


USE_CASE_PRIMARY_SYSTEM_PROMPT = """
You are organizing secondary AI tool use-case tags into a higher-level
primary use-case taxonomy.

The input is one semantic pocket produced by K-Means clustering.
Each pocket contains secondary use-case tags that are semantically related,
but they may belong to one or multiple broader goal or workflow families.

Your task is to consolidate the secondary tags into a minimal set of clear,
reusable primary use-case tags.

Definition:
A primary use-case tag represents a broad family of related user goals,
tasks, workflows, or usage scenarios and must be more general than a
secondary use-case tag.

Rules:
1. Group secondary tags that belong to the same broad goal or workflow
   family under one primary tag.

2. Primary tags must be broader than the input secondary tags.

3. Do not create one primary tag for every secondary tag unless they
   represent genuinely different broad goal or workflow families.

4. Being in the same domain does not necessarily mean that tags belong
   to the same primary use case.

5. A K-Means pocket may produce one or multiple primary tags.

6. Generate the minimum number of primary tags necessary to preserve
   meaningful high-level distinctions.

7. Prefer concise, stable, reusable taxonomy names.

8. Every input secondary tag must be assigned to exactly one primary tag.

Return valid JSON only.
"""

SYSTEM_PROMPTS = {
    ("functions", "secondary"): FUNCTION_SECONDARY_SYSTEM_PROMPT,
    ("use_cases", "secondary"): USE_CASE_SECONDARY_SYSTEM_PROMPT,
    ("functions", "primary"): FUNCTION_PRIMARY_SYSTEM_PROMPT,
    ("use_cases", "primary"): USE_CASE_PRIMARY_SYSTEM_PROMPT,
}


def get_system_prompt(tag_type: str, target_level: str) -> str:
    key = (tag_type, target_level)

    if key not in SYSTEM_PROMPTS:
        raise ValueError(
            f"Unsupported tag configuration: "
            f"tag_type={tag_type}, target_level={target_level}"
        )

    return SYSTEM_PROMPTS[key]

def get_output_filename(tag_type: str, target_level: str) -> str:
    return (
        f"consolidated_{tag_type}_"
        f"{target_level}_tags.json"
    )

def build_user_prompt(pocket_id: int, tags: list[str], tag_type: str, target_level: str)-> str:

    tags_text = "\n".join(
        f"- {tag}"
        for tag in tags
    )

    tag_label = (
        "function"
        if tag_type == "functions"
        else "use-case"
    )

    if target_level == "secondary":
        return f"""
Consolidate the following {tag_label} tags into secondary tags.

Pocket ID: {pocket_id}

Input {tag_label} tags:
{tags_text}

Return the result using exactly this JSON structure:

{{
    "pocket_id": {pocket_id},
    "secondary_tags": [
        {{
            "secondary_tag": "Example Secondary Tag",
            "source_tags": [
                "original tag 1",
                "original tag 2"
            ]
        }}
    ]
}}
"""

    return f"""
Consolidate the following secondary {tag_label} tags into primary tags.

Pocket ID: {pocket_id}

Input secondary {tag_label} tags:
{tags_text}

Return the result using exactly this JSON structure:

{{
    "pocket_id": {pocket_id},
    "primary_tags": [
        {{
            "primary_tag": "Example Primary Tag",
            "source_secondary_tags": [
                "secondary tag 1",
                "secondary tag 2"
            ]
        }}
    ]
}}
"""


def consolidate_pocket(
    client: OpenAI,
    pocket_id: int,
    tags: list[str],
    tag_type: str,
    target_level: str,
) -> dict:
    response = client.responses.create(
        model=MODEL,
        instructions=get_system_prompt(
            tag_type,
            target_level,
        ),
        input=build_user_prompt(
            pocket_id,
            tags,
            tag_type,
            target_level,
        ),
    )

    result_text = response.output_text.strip()

    return json.loads(result_text)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Consolidate clustered tags into secondary "
            "or primary taxonomy tags."
        )
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

    parser.add_argument(
    "--target-level",
    required=True,
    choices=("secondary", "primary"),
    help="Taxonomy level generated by this consolidation run.",
    )

    args = parser.parse_args()

    input_path = args.input

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    output_filename = get_output_filename(
        args.tag_type,
        args.target_level,
    )

    output_path = args.output_dir / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading clusters from: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        clusters = json.load(f)

    print(f"Processing all {len(clusters)} pockets.")

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set."
        )
    
    client = OpenAI(api_key=api_key)

    results = []
    result_key = f"{args.target_level}_tags"

    for index, (_, pocket_data) in enumerate(
        clusters.items(),
        start=1,
    ):
        pocket_id = pocket_data["pocket_id"]

        tags = [
            item["tag"]
            for item in pocket_data["items"]
        ]

        print(
            f"Processing pocket {pocket_id} "
            f"({index}/{len(clusters)}, "
            f"{len(tags)} tags)..."
        )

        try:
            result = consolidate_pocket(
                client=client,
                pocket_id=pocket_id,
                tags=tags,
                tag_type=args.tag_type,
                target_level=args.target_level,
            )

            results.append(result)

        except Exception as e:
            print(
                f"Failed to process pocket "
                f"{pocket_id}: {e}"
            )

            results.append({
                "pocket_id": pocket_id,
                result_key: [],
                "error": str(e),
            })

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=4,
        )

    print("Consolidation completed.")
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()
