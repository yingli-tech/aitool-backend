from __future__ import annotations

import json
from pathlib import Path


ENRICH_DIR = Path(__file__).resolve().parent
ETL_DIR = ENRICH_DIR.parent
OUTPUT_DIR = ETL_DIR / "outputs"

INPUT_PATH = OUTPUT_DIR / "enriched_candidate_tool_records.jsonl"
OUTPUT_PATH = OUTPUT_DIR / "enriched_candidate_tool_records.json"


def convert_jsonl_to_json(
    input_path: Path,
    output_path: Path,
) -> None:

    records = []

    with input_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
                records.append(record)

            except json.JSONDecodeError as error:
                print(
                    f"WARNING: Skipping invalid JSONL line "
                    f"{line_number}: {error}"
                )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            records,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Converted records: {len(records)}")
    print(f"Output: {output_path}")


def main() -> None:
    convert_jsonl_to_json(
        INPUT_PATH,
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()