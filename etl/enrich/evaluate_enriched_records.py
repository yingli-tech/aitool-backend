from __future__ import annotations

import json
from pathlib import Path


ENRICH_DIR = Path(__file__).resolve().parent
ETL_DIR = ENRICH_DIR.parent
OUTPUT_DIR = ETL_DIR / "outputs"

INPUT_PATH = OUTPUT_DIR / "enriched_candidate_tool_records.json"
LANGUAGE_REFERENCE_PATH = OUTPUT_DIR / "allowed_human_languages.json"

EVALUATION_OUTPUT_PATH = OUTPUT_DIR / "enrichment_evaluation.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_languages(
    records: list[dict],
    allowed_languages: set[str],
) -> dict:

    failed_tools = []

    for record in records:
        name = record.get("name")
        languages = record.get("language", [])

        invalid_languages = [
            language
            for language in languages
            if language not in allowed_languages
        ]

        # A tool fails if even one language value
        # is outside the approved human-language library.
        if invalid_languages:
            failed_tools.append(
                {
                    "name": name,
                    "languages": languages,
                    "invalid_languages": invalid_languages,
                }
            )

    total = len(records)
    failed = len(failed_tools)
    passed = total - failed

    error_rate = failed / total if total else 0
    pass_rate = passed / total if total else 0

    return {
        "total_tools": total,
        "passed_tools": passed,
        "failed_tools_count": failed,
        "pass_rate": pass_rate,
        "error_rate": error_rate,
        "failed_tools": failed_tools,
    }


def evaluate_price_type(records: list[dict]) -> dict:

    failed_tools = []

    for record in records:
        name = record.get("name")
        price_types = record.get("price_type", [])

        # "free trial" without "paid" is logically inconsistent:
        # a free trial implies a paid offering exists afterward.
        if (
            "free trial" in price_types
            and "paid" not in price_types
        ):
            failed_tools.append(
                {
                    "name": name,
                    "price_type": price_types,
                }
            )

    total = len(records)
    failed = len(failed_tools)
    passed = total - failed

    error_rate = failed / total if total else 0
    pass_rate = passed / total if total else 0

    return {
        "total_tools": total,
        "passed_tools": passed,
        "failed_tools_count": failed,
        "pass_rate": pass_rate,
        "error_rate": error_rate,
        "failed_tools": failed_tools,
    }


def main() -> None:

    records = load_json(INPUT_PATH)

    allowed_languages = set(
        load_json(LANGUAGE_REFERENCE_PATH)
    )

    language_evaluation = evaluate_languages(
        records,
        allowed_languages,
    )

    price_type_evaluation = evaluate_price_type(
        records
    )

    evaluation_result = {
        "language_evaluation": language_evaluation,
        "price_type_evaluation": price_type_evaluation,
    }

    with EVALUATION_OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            evaluation_result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # ------------------------------------------
    # Console summary
    # ------------------------------------------

    print("=" * 50)
    print("Language Evaluation")
    print("=" * 50)

    print(
        f"Total tools: "
        f"{language_evaluation['total_tools']}"
    )

    print(
        f"Passed: "
        f"{language_evaluation['passed_tools']}"
    )

    print(
        f"Failed: "
        f"{language_evaluation['failed_tools_count']}"
    )

    print(
        f"Pass rate: "
        f"{language_evaluation['pass_rate']:.2%}"
    )

    print(
        f"Error rate: "
        f"{language_evaluation['error_rate']:.2%}"
    )

    if language_evaluation["failed_tools"]:
        print("\nLanguage failed tools:")

        for tool in language_evaluation["failed_tools"]:
            print(
                f"- {tool['name']}: "
                f"{tool['invalid_languages']}"
            )

    print()

    print("=" * 50)
    print("Price Type Evaluation")
    print("=" * 50)

    print(
        f"Total tools: "
        f"{price_type_evaluation['total_tools']}"
    )

    print(
        f"Passed: "
        f"{price_type_evaluation['passed_tools']}"
    )

    print(
        f"Failed: "
        f"{price_type_evaluation['failed_tools_count']}"
    )

    print(
        f"Pass rate: "
        f"{price_type_evaluation['pass_rate']:.2%}"
    )

    print(
        f"Error rate: "
        f"{price_type_evaluation['error_rate']:.2%}"
    )

    if price_type_evaluation["failed_tools"]:
        print("\nPrice type failed tools:")

        for tool in price_type_evaluation["failed_tools"]:
            print(
                f"- {tool['name']}: "
                f"{tool['price_type']}"
            )

    print()
    print(
        f"Evaluation output: "
        f"{EVALUATION_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()