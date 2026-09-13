from __future__ import annotations

import json
from pathlib import Path

import trafilatura


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "outputs" / "complete_candidate_tool_records.json"

OUTPUT_PATH = PROJECT_ROOT / "outputs" / "extracted_content.json"

LOG_PATH = PROJECT_ROOT / "outputs" / "website_content_extraction_log.txt"

def load_tools(input_path: Path = INPUT_PATH) -> list[dict]:
    """Load tool name and official URLs from complete candidate records."""
    with input_path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    return [
        {
            "name": record["name"],
            "official_url": record["official_url"]
        }
        for record in records
        if record.get("name") and record.get("official_url")
    ]


def extract_content(url: str) -> dict | None:
    """Download and extract website content with metadata."""
    downloaded = trafilatura.fetch_url(url)

    if not downloaded:
        return None

    result = trafilatura.extract(
        downloaded,
        with_metadata=True,
        output_format="json",
    )

    if not result:
        return None

    return json.loads(result)


def log(message: str, log_file) -> None:
    """Print a message and write it to the log file."""
    print(message)
    log_file.write(message + "\n")
    log_file.flush()


def main() -> None:
    tools = load_tools()
    extracted_records = []

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with LOG_PATH.open("w", encoding="utf-8") as log_file:

        for index, tool in enumerate(tools, start=1):
            name = tool["name"]
            official_url = tool["official_url"]

            log(
                f"[{index}/{len(tools)}] Extracting: {name} | {official_url}",
                log_file,
            )

            try:
                result = extract_content(official_url)

                if result is not None:
                    # Preserve identity from Source Discovery.
                    result["name"] = name
                    result["official_url"] = official_url

                    extracted_records.append(result)
                    
                    log(f"SUCCESS: {name} | {official_url}", log_file)
                else:
                    log(f"FAILED: {name} | {official_url}", log_file)

            except Exception as error:
                log(
                    f"ERROR: {name} | {official_url} | {error}",
                    log_file,
                )

        with OUTPUT_PATH.open("w", encoding="utf-8") as file:
            json.dump(
                extracted_records,
                file,
                indent=2,
                ensure_ascii=False,
            )

        log("", log_file)
        log(f"Total Tools: {len(tools)}", log_file)
        log(
            f"Successfully extracted: {len(extracted_records)}",
            log_file,
        )
        log(
            f"Failed: {len(tools) - len(extracted_records)}",
            log_file,
        )
        log(f"Output: {OUTPUT_PATH}", log_file)




if __name__ == "__main__":
    main()
