from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MAPPING_DIR = Path(__file__).resolve().parent

MODEL = "gpt-5.6-luna"
# MODEL = "gpt-4o-mini"
BATCH_SIZE = 300


# --------------------------------------------------
# Pydantic Contract
# --------------------------------------------------

class TagMapping(BaseModel):
    id: int
    secondary_tag: str


class TagMappingResult(BaseModel):
    mappings: list[TagMapping]


# --------------------------------------------------
# System Prompt
# --------------------------------------------------

SYSTEM_PROMPT = """
You are performing semantic normalization for an AI tools taxonomy.

Your task is to normalize raw tags into consistent secondary tags.

Each input item contains:
- id: a temporary numeric identifier
- tag: the original raw tag
- count: the frequency of that raw tag in the dataset

Example input item:
{"id": 1, "tag": "AI Video Generation", "count": 23}

The count is contextual information only.
Do not merge or separate tags based primarily on frequency.
Semantic meaning must be the primary criterion.

Normalization rules:

1. Map raw tags with the same or highly equivalent semantic meaning
   to the same secondary tag.

2. Preserve meaningful semantic distinctions.
   Do not merge tags merely because they belong to the same broad topic.

   For example:
   - "AI Image Generation" and "Generate Images"
     may map to "Image Generation".
   - "Image Generation" and "Background Removal"
     must remain separate.
   - "Code Generation" and "Code Debugging"
     must remain separate.

3. Secondary tags should represent specific, reusable capabilities
   or use cases rather than broad categories.

4. Normalize wording into concise, clear, and consistent noun phrases.

5. Prefer established and commonly understandable terminology.

6. Do not create unnecessary distinctions based only on wording differences.

7. Do not create broader primary categories in this step.
   Only produce secondary tags.

8. Every input id must appear exactly once in the output.

9. Preserve the provided id exactly.

10. Return only the id and secondary_tag for each item.
    Do not repeat the raw tag or count in the output.

Return structured output only.
"""


# --------------------------------------------------
# Detect Tag Type
# --------------------------------------------------

def detect_tag_type(input_path: Path) -> str:
    filename = input_path.stem.lower()

    if "function" in filename:
        return "function"

    if "use_case" in filename or "usecase" in filename:
        return "use_case"

    raise ValueError(
        "Cannot determine tag type from filename. "
        "Filename must contain 'function' or 'use_case'."
    )


def build_tag_type_context(tag_type: str) -> str:
    if tag_type == "function":
        return """
You are currently normalizing FUNCTION tags.

Function tags describe what an AI tool can do:
its capabilities, operations, or functional behaviors.

Normalize tags according to capability-level semantic meaning.
"""

    return """
You are currently normalizing USE CASE tags.

Use case tags describe what a user is trying to accomplish:
their goals, tasks, workflows, or usage scenarios.

Normalize tags according to use-case-level semantic meaning.
"""


# --------------------------------------------------
# Read Input JSON and Assign Temporary IDs
# --------------------------------------------------

def load_input_records(input_path: Path) -> list[dict]:
    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Input JSON must contain a list of tag records.")

    records = []

    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Input item {index} must be a JSON object.")

        tag = item.get("tag")
        count = item.get("count")

        if not isinstance(tag, str) or not tag.strip():
            raise ValueError(f"Input item {index} has an invalid tag.")

        if not isinstance(count, int) or count < 1:
            raise ValueError(f"Input item {index} has an invalid count.")

        records.append(
            {
                "id": index,
                "tag": tag,
                "count": count,
            }
        )

    return records


# --------------------------------------------------
# LLM Semantic Normalization
# --------------------------------------------------

def normalize_tags(
    client: OpenAI,
    input_records: list[dict],
    tag_type: str,
) -> TagMappingResult:

    tag_type_context = build_tag_type_context(tag_type)

    input_text = json.dumps(
        input_records,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    response = client.responses.parse(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT + tag_type_context,
            },
            {
                "role": "user",
                "content": (
                    "Normalize all of the following raw tags. "
                    "Return exactly one mapping for every input id.\n\n"
                    + input_text
                ),
            },
        ],
        text_format=TagMappingResult,
    )

    return response.output_parsed


def split_into_batches(
    input_records: list[dict],
    batch_size: int = BATCH_SIZE,
) -> list[list[dict]]:
    if batch_size < 1:
        raise ValueError("Batch size must be at least 1.")

    return [
        input_records[index : index + batch_size]
        for index in range(0, len(input_records), batch_size)
    ]


# --------------------------------------------------
# Validate LLM Output
# --------------------------------------------------

def validate_llm_result(
    result: TagMappingResult,
    input_records: list[dict],
    validation_scope: str = "LLM mapping output",
) -> None:
    expected_ids = {record["id"] for record in input_records}
    returned_ids = [mapping.id for mapping in result.mappings]
    returned_id_set = set(returned_ids)

    duplicate_ids = sorted(
        mapping_id
        for mapping_id in returned_id_set
        if returned_ids.count(mapping_id) > 1
    )
    missing_ids = sorted(expected_ids - returned_id_set)
    unexpected_ids = sorted(returned_id_set - expected_ids)

    if (
        len(result.mappings) != len(input_records)
        or duplicate_ids
        or missing_ids
        or unexpected_ids
    ):
        details = []

        if missing_ids:
            details.append(f"missing IDs: {missing_ids[:20]}")
        if unexpected_ids:
            details.append(f"unexpected IDs: {unexpected_ids[:20]}")
        if duplicate_ids:
            details.append(f"duplicate IDs: {duplicate_ids[:20]}")

        raise ValueError(
            f"{validation_scope} failed validation. "
            f"Expected {len(input_records)} mappings, "
            f"received {len(result.mappings)}. "
            + "; ".join(details)
        )


# --------------------------------------------------
# Join LLM Output Back to Original Records
# --------------------------------------------------

def rebuild_full_mappings(
    result: TagMappingResult,
    input_records: list[dict],
) -> list[dict]:
    record_by_id = {
        record["id"]: record
        for record in input_records
    }

    mappings = []

    for mapping in result.mappings:
        original = record_by_id[mapping.id]

        mappings.append(
            {
                "raw_tag": original["tag"],
                "raw_count": original["count"],
                "secondary_tag": mapping.secondary_tag.strip(),
            }
        )

    return mappings


# --------------------------------------------------
# Save Raw Reconstructed Result
# --------------------------------------------------

def save_raw_result(
    mappings: list[dict],
    output_path: Path,
) -> None:
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            {"mappings": mappings},
            file,
            ensure_ascii=False,
            indent=2,
        )


# --------------------------------------------------
# Group by Secondary Tag
# --------------------------------------------------

def group_mappings(
    mappings: list[dict],
) -> list[dict]:

    grouped = defaultdict(
        lambda: {
            "total_count": 0,
            "raw_tags": [],
        }
    )

    for mapping in mappings:
        secondary_tag = mapping["secondary_tag"].strip()

        grouped[secondary_tag]["total_count"] += mapping["raw_count"]

        grouped[secondary_tag]["raw_tags"].append(
            {
                "raw_tag": mapping["raw_tag"],
                "raw_count": mapping["raw_count"],
            }
        )

    result = []

    for secondary_tag, data in grouped.items():
        raw_tags = sorted(
            data["raw_tags"],
            key=lambda item: (
                -item["raw_count"],
                item["raw_tag"].lower(),
            ),
        )

        result.append(
            {
                "secondary_tag": secondary_tag,
                "total_count": data["total_count"],
                "raw_tag_count": len(raw_tags),
                "raw_tags": raw_tags,
            }
        )

    result.sort(
        key=lambda item: (
            -item["total_count"],
            item["secondary_tag"].lower(),
        )
    )

    return result


# --------------------------------------------------
# Save Grouped Result
# --------------------------------------------------

def save_grouped_result(
    grouped_result: list[dict],
    output_path: Path,
) -> None:
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            grouped_result,
            file,
            ensure_ascii=False,
            indent=2,
        )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main() -> None:

    if len(sys.argv) != 2:
        print(
            "Usage: python semantic_normalize_tags.py "
            "<unique_functions.json | unique_use_cases.json>"
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.is_absolute():
        input_path = MAPPING_DIR / input_path

    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    try:
        tag_type = detect_tag_type(input_path)
    except ValueError as error:
        print(f"ERROR: {error}")
        sys.exit(1)

    if tag_type == "function":
        raw_output_path = MAPPING_DIR / "normalized_functions_raw.json"
        grouped_output_path = MAPPING_DIR / "normalized_functions_grouped.json"
    else:
        raw_output_path = MAPPING_DIR / "normalized_use_cases_raw.json"
        grouped_output_path = MAPPING_DIR / "normalized_use_cases_grouped.json"

    try:
        input_records = load_input_records(input_path)
    except (json.JSONDecodeError, ValueError) as error:
        print(f"ERROR: Invalid input JSON: {error}")
        sys.exit(1)

    if not input_records:
        print("ERROR: Input file contains no tag records.")
        sys.exit(1)

    print("=" * 60)
    print("Semantic Tag Normalization")
    print("=" * 60)
    print(f"Tag type: {tag_type}")
    print(f"Input: {input_path}")
    print(f"Model: {MODEL}")
    print()

    client = OpenAI()

    batches = split_into_batches(input_records)
    print(f"Total input tags: {len(input_records)}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Total batches: {len(batches)}")

    try:
        all_mappings: list[TagMapping] = []

        for batch_number, batch_records in enumerate(batches, start=1):
            first_id = batch_records[0]["id"]
            last_id = batch_records[-1]["id"]
            print(
                f"Batch {batch_number}/{len(batches)}: sending "
                f"{len(batch_records)} tags (IDs {first_id}-{last_id})..."
            )

            batch_result = normalize_tags(
                client=client,
                input_records=batch_records,
                tag_type=tag_type,
            )
            validate_llm_result(
                result=batch_result,
                input_records=batch_records,
                validation_scope=f"Batch {batch_number}/{len(batches)}",
            )
            all_mappings.extend(batch_result.mappings)
            print(
                f"Batch {batch_number}/{len(batches)}: received "
                f"{len(batch_result.mappings)} mappings."
            )

        result = TagMappingResult(mappings=all_mappings)
        validate_llm_result(
            result=result,
            input_records=input_records,
            validation_scope="Complete dataset",
        )
    except Exception as error:
        print(f"ERROR: LLM normalization failed: {error}")
        sys.exit(1)

    print(f"Total mappings received: {len(result.mappings)}")

    full_mappings = rebuild_full_mappings(
        result=result,
        input_records=input_records,
    )

    save_raw_result(
        mappings=full_mappings,
        output_path=raw_output_path,
    )
    print(f"Raw result: {raw_output_path}")

    grouped_result = group_mappings(full_mappings)

    save_grouped_result(
        grouped_result=grouped_result,
        output_path=grouped_output_path,
    )
    print(f"Grouped result: {grouped_output_path}")

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Raw tags: {len(full_mappings)}")
    print(f"Secondary tags: {len(grouped_result)}")

    if full_mappings:
        reduction_rate = (
            1 - len(grouped_result) / len(full_mappings)
        ) * 100
        print(f"Tag reduction: {reduction_rate:.2f}%")


if __name__ == "__main__":
    main()
