from __future__ import annotations

import json
from pathlib import Path


ENRICH_DIR = Path(__file__).resolve().parent
ETL_DIR = ENRICH_DIR.parent
OUTPUT_DIR = ETL_DIR / "outputs"

INPUT_PATH = OUTPUT_DIR / "enriched_candidate_tool_records.json"
OUTPUT_PATH = OUTPUT_DIR / "unique_languages.json"


def load_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_unique_languages(records: list[dict]) -> list[str]:
    languages = set()

    for record in records:
        for language in record.get("language", []):
            if isinstance(language, str):
                language = language.strip()

                if language:
                    languages.add(language)

    return sorted(languages, key=str.lower)


def main() -> None:
    records = load_records(INPUT_PATH)

    unique_languages = extract_unique_languages(records)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            unique_languages,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Total tools: {len(records)}")
    print(f"Unique language values: {len(unique_languages)}")
    print(f"Output: {OUTPUT_PATH}")

    print("\nLanguages:")

    for language in unique_languages:
        print(f"- {language}")


if __name__ == "__main__":
    main()