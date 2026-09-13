from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "outputs" / "extracted_content.json"

OUTPUT_PATH = PROJECT_ROOT / "outputs" / "filtered_extracted_content.json"

CLEAN_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "clean_extracted_content.json"

GARBLED_NAMES_PATH = PROJECT_ROOT / "outputs" / "garbled_tool_names.txt"

def get_content(record: dict) -> str | None:
    """Use raw_text first and fall back to text."""
    raw_text = record.get("raw_text")

    if raw_text and raw_text.strip():
        return raw_text.strip()

    text = record.get("text")

    if text and text.strip():
        return text.strip()

    return None


def normalize_domain(url: str) -> str:
    """Normalize a URL to its domain for comparison."""
    domain = urlparse(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def source_matches_official_url(
    source: str | None,
    official_url: str,
) -> bool | None:
    """
    Compare the Trafilatura source with the original official URL.

    None means Trafilatura did not provide a source.
    """
    if not source:
        return None

    return normalize_domain(source) == normalize_domain(official_url)


def is_garbled(text: str) -> bool:
    """Detect obviously garbled extracted text."""
    if not text or not text.strip():
        return True

    text = text.strip()
    total = len(text)

    # Unicode replacement characters usually indicate decoding problems.
    replacement_ratio = text.count("\ufffd") / total

    # Count unusual control / unassigned characters.
    abnormal_count = sum(
        1
        for char in text
        if unicodedata.category(char) in {"Cc", "Cn"}
        and char not in "\n\r\t"
    )
    abnormal_ratio = abnormal_count / total

    return (
        replacement_ratio > 0.01
        or abnormal_ratio > 0.01
    )



def main() -> None:
    with INPUT_PATH.open("r", encoding="utf-8") as file:
        records = json.load(file)

    filtered_records = []

    source_null_count = 0
    source_non_null_count = 0
    source_match_count = 0

    for record in records:
        content = get_content(record)

        # Exclude records without usable extracted content.
        if content is None:
            continue

        source = record.get("source")
        official_url = record["official_url"]

        matches = source_matches_official_url(
            source,
            official_url,
        )

        if source is None:
            source_null_count += 1
        else:
            source_non_null_count += 1

            if matches:
                source_match_count += 1

        filtered_records.append(
            {
                "name": record["name"],
                "official_url": official_url,
                "source": source,
                "content": content,
                "source_matches_official_url": matches,
            }
        )


    # First output: records with usable content
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            filtered_records,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # Second filtering step: remove garbled content
    clean_records = []
    garbled_names = []

    for record in filtered_records:
        if is_garbled(record["content"]):
            garbled_names.append(record["name"])
        else:
            clean_records.append(record)

    with GARBLED_NAMES_PATH.open("w", encoding="utf-8") as file:
        for name in garbled_names:
            file.write(name + "\n")

    with CLEAN_OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            clean_records,
            file,
            indent=2,
            ensure_ascii=False,
        )




##########################################
    total = len(records)
    filtered = len(filtered_records)

    filtering_rate = (
        filtered / total * 100
        if total
        else 0
    )

    verification_rate = (
        source_match_count / source_non_null_count * 100
        if source_non_null_count
        else 0
    )

    garbled_total = len(garbled_names)
    clean_total = len(clean_records)

    garbled_check_rate = (
        clean_total / filtered * 100
        if filtered
        else 0
    )
    

    print(f"Total extracted records: {total}")
    print(f"Successfully filtered: {filtered}")
    print(f"Excluded: {total - filtered}")
    print(f"Successful filtering rate: {filtering_rate:.2f}%")
    print()
    print(f"Source null: {source_null_count}")
    print(f"Source non-null: {source_non_null_count}")
    print(f"Source matches official URL: {source_match_count}")
    print(
        f"Website verification rate: "
        f"{verification_rate:.2f}%"
    )

    print()
    print("Garbled content check:")
    print(f"Checked: {filtered}")
    print(f"Passed: {clean_total}")
    print(f"Garbled: {garbled_total}")
    print(f"Pass rate: {garbled_check_rate:.2f}%")

    if garbled_names:
        print("Garbled tool names:")
        for name in garbled_names:
            print(f"- {name}")

    print()
    print(f"Filtered output: {OUTPUT_PATH}")
    print(f"Clean output: {CLEAN_OUTPUT_PATH}")
    


if __name__ == "__main__":
    main()
