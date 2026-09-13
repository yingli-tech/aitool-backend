from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import yaml
from openai import OpenAI
from pydantic import BaseModel, Field

import time

# --------------------------------------------------
# Paths
# --------------------------------------------------

ENRICH_DIR = Path(__file__).resolve().parent
ETL_DIR = ENRICH_DIR.parent
OUTPUT_DIR = ETL_DIR / "outputs"

FILTERED_CONTENT_PATH = OUTPUT_DIR / "filtered_extracted_content.json"
GARBLED_NAMES_PATH = OUTPUT_DIR / "garbled_tool_names.txt"
CANDIDATE_RECORDS_PATH = OUTPUT_DIR / "complete_candidate_tool_records.json"
CONFIG_PATH = ETL_DIR / "etl_config.yaml"

#ENRICH_OUTPUT_PATH = OUTPUT_DIR / "enriched_candidate_tool_records.json"

ENRICH_OUTPUT_PATH = OUTPUT_DIR / "enriched_candidate_tool_records.jsonl"
ERROR_OUTPUT_PATH = OUTPUT_DIR / "enrichment_errors.jsonl"



# --------------------------------------------------
# LLM output schema
# --------------------------------------------------

class EnrichedFields(BaseModel):
    category: Literal[
        "AI Video",
        "AI Image",
        "AI Writing",
        "AI Coding",
        "AI Chat",
        "AI Audio",
    ]

    language: list[str] = Field(min_length=1)

    use_case: list[str] = Field(min_length=1)

    function: list[str] = Field(min_length=1)

    price_type: list[
        Literal[
            "free",
            "free trial",
            "paid",
        ]
    ] = Field(min_length=1)

    one_line_desc: str


# --------------------------------------------------
# Load data
# --------------------------------------------------

def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_garbled_names(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def load_source_config(path: Path) -> tuple[str, str]:
    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    seed_source = config["source_discovery"]["seed_sources"][0]

    return (
        seed_source["source"],
        seed_source["source_url"],
    )


def build_candidate_lookup(records: list[dict]) -> dict[str, dict]:
    return {
        record["name"]: record
        for record in records
    }


# --------------------------------------------------
# Resume
# --------------------------------------------------

def load_completed_names(path: Path) -> set[str]:
    """
    Load names already successfully persisted to the JSONL output.

    This allows the enrichment process to resume without calling
    the LLM again for tools that have already completed.
    """
    if not path.exists():
        return set()

    completed_names = set()

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)

                name = record.get("name")

                if name:
                    completed_names.add(name)

            except json.JSONDecodeError:
                print(
                    f"WARNING: Invalid JSONL line "
                    f"{line_number} in {path}"
                )

    return completed_names


# --------------------------------------------------
# Content selection
# --------------------------------------------------

def get_enrichment_content(
    record: dict,
    garbled_names: set[str],
    candidate_lookup: dict[str, dict],
) -> tuple[str, str]:
    """
    Return:
        content used for enrichment
        content source: 'website_content' or 'source_description'
    """

    name = record["name"]

    if name in garbled_names:
        candidate = candidate_lookup.get(name)

        if candidate is None:
            raise ValueError(
                f"Cannot find candidate record for garbled tool: {name}"
            )

        source_description = candidate.get("source_description")

        if not source_description:
            raise ValueError(
                f"No source_description available for garbled tool: {name}"
            )

        return source_description, "source_description"

    return record["content"], "website_content"


# --------------------------------------------------
# LLM enrichment
# --------------------------------------------------

SYSTEM_PROMPT = """
You extract structured information about AI tools.

You must use ONLY the supplied tool content.

Rules:

1. category
Choose exactly one:
- AI Video
- AI Image
- AI Writing
- AI Coding
- AI Chat
- AI Audio

Choose the category that best represents the tool's primary purpose.

2. language
Return all languages explicitly supported or mentioned in the content.
Always include "English" in the language list. Extract and include any additional languages mentioned in the source text. 
If no other language information is provided, return ["English"].
Do not infer additional languages.

language refers only to human natural languages. 
Do not include programming languages, markup languages, or other computer languages such as Python, JavaScript, TypeScript, PHP, HTML, or SQL.

No duplicates are allowed

3. use_case
Return one or more concise, tag-like noun phrases representing the tool's use cases.

Rules:
- Each tag must represent one clear concept.
- Keep tags short and concept-focused, preferably 2-4 words when possible.
- Do not return full sentences or action-style descriptions.
- Avoid verb-ing phrases such as:
  - "creating business and project websites"
  - "building websites and online stores"
- Prefer standardized tag-style phrases such as:
  - "Website Generation"
  - "E-commerce Website Creation"
- Multiple use_case tags may be returned when supported by the content.
- Every tag must be grounded in the supplied content.
- Do not invent unsupported use cases.
- No duplicates are allowed

4. function
Return one or more concise, tag-like noun phrases representing the tool's core functions.

Rules:
- Each tag must represent one clear function.
- Keep tags short and concept-focused, preferably 2-4 words when possible.
- Do not return full sentences or action-style descriptions.
- Avoid verb-ing phrases such as:
  - "generating business names"
  - "customizing websites through AI copilot"
- Prefer standardized tag-style phrases such as:
  - "Business Name Generation"
  - "Website Customization"
- Multiple function tags may be returned when supported by the content.
- Every tag must be grounded in the supplied content.
- Do not invent unsupported functions.
- No duplicates are allowed

5. price_type
Return one or more applicable values from:
- free
- free trial
- paid

Multiple values are allowed when the tool offers multiple pricing options.
For example, if a tool has both a free plan and paid subscriptions, return ["free", "paid"].

If no pricing information is provided in the content, return ["free"].

Include Free Trial only when the source text explicitly states that the tool offers a free trial, trial period, or limited trial access. 
Do not infer Free Trial from the existence of paid plans, free credits, demos, or general free access.
If Free Trial is included, Paid must also be included. Never return Free Trial as the only price type.

Do not return any values outside this list.
No duplicates are allowed

6. one_line_desc
Write one concise sentence describing the tool's primary purpose.
It must be supported by the supplied content.

All generated information must be grounded in the supplied text,
except for these explicit default rules:
- language = ["English"] when no language information is provided.
- price_type = ["free"] when no pricing information is provided.

For both use_case and function:
- Output tags, not explanatory sentences.
- Prefer canonical noun-phrase labels that can be used directly as taxonomy tags.
- Split distinct concepts into separate tags rather than combining multiple concepts into one long phrase.
- These fields will be normalized and mapped into a two-level taxonomy in a later ETL stage.

Generate all distinct function/use_case tags that are clearly supported by the source text. 
Do not add redundant, overlapping, or artificially fragmented tags solely to increase tag coverage.
"""



def enrich_content(
    client: OpenAI,
    name: str,
    content: str,
) -> EnrichedFields:

    response = client.responses.parse(
        model="gpt-5.6-luna",
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Tool name: {name}\n\n"
                    f"Tool content:\n{content}"
                ),
            },
        ],
        text_format=EnrichedFields,
    )

    return response.output_parsed


# --------------------------------------------------
# Build output
# --------------------------------------------------

def build_output_record(
    name: str,
    official_url: str,
    candidate: dict,
    enriched: EnrichedFields,
    source: str,
    source_url: str,
) -> dict:

    return {
        "name": name,
        "official_url": official_url,
        "source": source,
        "source_url": source_url,
        "source_description": candidate.get("source_description"),
        "category": enriched.category,
        "language": enriched.language,
        "use_case": enriched.use_case,
        "function": enriched.function,
        "price_type": enriched.price_type,
        "one_line_desc": enriched.one_line_desc,
    }

# --------------------------------------------------
# JSONL persistence
# --------------------------------------------------

def append_jsonl(
    record: dict,
    file,
) -> None:
    """
    Persist one record immediately.

    flush() ensures Python's userspace buffer is written out
    after every successfully enriched tool.
    """
    file.write(
        json.dumps(
            record,
            ensure_ascii=False,
        )
        + "\n"
    )

    file.flush()



# --------------------------------------------------
# Main
# --------------------------------------------------

def main() -> None:

    start_time = time.perf_counter()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )    

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"]
    )

    filtered_records = load_json(
        FILTERED_CONTENT_PATH
    )

    candidate_records = load_json(
        CANDIDATE_RECORDS_PATH
    )

    garbled_names = load_garbled_names(
        GARBLED_NAMES_PATH
    )

    source, source_url = load_source_config(
        CONFIG_PATH
    )

    candidate_lookup = build_candidate_lookup(
        candidate_records
    )


    # --------------------------------------------------
    # Resume state
    # --------------------------------------------------

    completed_names = load_completed_names(
        ENRICH_OUTPUT_PATH
    )

    print(
        f"Previously completed: {len(completed_names)}"
    )

    # Keep test limit for now.
    records_to_process = filtered_records

    success_count = 0
    failed_count = 0
    skipped_count = 0
    failed_tools = []

    print(
        f"Current test batch: "
        f"{len(records_to_process)} tools"
    )
    print()

    # Append mode is essential for resume.
    with (
        ENRICH_OUTPUT_PATH.open(
            "a",
            encoding="utf-8",
        ) as output_file,
        ERROR_OUTPUT_PATH.open(
            "a",
            encoding="utf-8",
        ) as error_file,
    ):

        for index, record in enumerate(
            records_to_process,
            start=1,
        ):
            name = record["name"]
            official_url = record["official_url"]

            print(
                f"[{index}/{len(records_to_process)}] "
                f"{name}"
            )

            # ------------------------------------------
            # Resume: skip completed tools
            # ------------------------------------------

            if name in completed_names:
                skipped_count += 1

                print("  SKIPPED: already completed")
                continue

            # ------------------------------------------
            # Isolate each tool's processing
            # ------------------------------------------

            try:
                content, content_source = (
                    get_enrichment_content(
                        record,
                        garbled_names,
                        candidate_lookup,
                    )
                )

                print(
                    f"  Content source: {content_source}"
                )

                enriched = enrich_content(
                    client,
                    name,
                    content,
                )

                candidate = candidate_lookup[name]

                output_record = build_output_record(
                    name=name,
                    official_url=official_url,
                    candidate=candidate,
                    enriched=enriched,
                    source=source,
                    source_url=source_url,
                )

                # --------------------------------------
                # Incremental persistence
                # --------------------------------------

                append_jsonl(
                    output_record,
                    output_file,
                )

                # Update in-memory resume state too.
                completed_names.add(name)

                success_count += 1

                print("  SUCCESS")

            except Exception as error:

                failed_count += 1

                error_record = {
                    "name": name,
                    "official_url": official_url,
                    "error": str(error),
                }

                # Persist error immediately as well.
                append_jsonl(
                    error_record,
                    error_file,
                )

                failed_tools.append(
                    error_record
                )

                print(
                    f"  ERROR: {error}"
                )

                # No raise here.
                # Continue processing the next tool.

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    elapsed_time = (
        time.perf_counter() - start_time
    )

    print()
    print("=" * 50)
    print("Enrichment summary")
    print("=" * 50)

    print(
        f"Batch size: {len(records_to_process)}"
    )

    print(
        f"Successfully enriched: {success_count}"
    )

    print(
        f"Skipped (already completed): {skipped_count}"
    )

    print(
        f"Failed: {failed_count}"
    )

    if failed_tools:
        print()
        print("Failed tools:")

        for failure in failed_tools:
            print(
                f"- {failure['name']}: "
                f"{failure['error']}"
            )

    print()
    print(
        f"Total runtime: {elapsed_time:.2f} seconds"
    )

    print(
        f"Output: {ENRICH_OUTPUT_PATH}"
    )

    print(
        f"Errors: {ERROR_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()