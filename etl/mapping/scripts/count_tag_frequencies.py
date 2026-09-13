from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def calculate_count_frequency(records: list[dict]) -> list[dict]:
    """
    Count how many tags have each count value.

    Example:
    count=31 appears in 2 tag records
    -> {"count": 31, "frequency": 2}
    """

    frequencies = Counter(
        record["count"]
        for record in records
        if isinstance(record.get("count"), int)
    )

    return [
        {
            "count": count,
            "frequency": frequency,
        }
        for count, frequency in sorted(
            frequencies.items(),
            reverse=True,
        )
    ]


def save_json(data: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def print_result(title: str, result: list[dict]) -> None:
    print("=" * 50)
    print(title)
    print("=" * 50)

    for item in result:
        print(
            f"Count {item['count']}: "
            f"{item['frequency']} tags"
        )

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate tag-count frequency distributions."
    )
    parser.add_argument(
        "--input",
        required=True,
        nargs=2,
        type=Path,
        metavar=("FUNCTIONS_JSON", "USE_CASES_JSON"),
        help="Unique functions JSON followed by unique use-cases JSON.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for frequency JSON outputs.",
    )
    args = parser.parse_args()

    function_output_path = args.output_dir / "function_count_frequency.json"
    use_case_output_path = args.output_dir / "use_case_count_frequency.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    function_records = load_json(
        args.input[0]
    )

    use_case_records = load_json(
        args.input[1]
    )

    function_result = calculate_count_frequency(
        function_records
    )

    use_case_result = calculate_count_frequency(
        use_case_records
    )

    save_json(
        function_result,
        function_output_path,
    )

    save_json(
        use_case_result,
        use_case_output_path,
    )

    print_result(
        "Function Count Frequency",
        function_result,
    )

    print_result(
        "Use Case Count Frequency",
        use_case_result,
    )

    print(f"Function output: {function_output_path}")
    print(f"Use case output: {use_case_output_path}")


if __name__ == "__main__":
    main()
