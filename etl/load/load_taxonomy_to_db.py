from __future__ import annotations

import argparse
import configparser
import json
from pathlib import Path

import pymysql


CONFIG_PATH = Path(
    r"D:\Project\aggregationai\codes\backend\aitool\etl\configuration\aitools-config.ini"
)

TABLE_BY_TAG_TYPE = {
    "functions": "functions",
    "use_cases": "use_cases",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load primary-secondary taxonomy pairs into MySQL."
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a deduplicated primary-tags JSON file.",
    )

    parser.add_argument(
        "--tag-type",
        required=True,
        choices=TABLE_BY_TAG_TYPE.keys(),
        help="Choose the target taxonomy table.",
    )

    return parser.parse_args()


def load_database_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Database config file not found: {CONFIG_PATH}"
        )

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")

    if "rds" not in config:
        raise ValueError("Missing [rds] section in config file.")

    rds = config["rds"]

    required_keys = [
        "endpoint",
        "port_number",
        "user_name",
        "user_pwd",
        "db_name",
    ]

    missing_keys = [
        key
        for key in required_keys
        if not rds.get(key)
    ]

    if missing_keys:
        raise ValueError(
            f"Missing database config values: {', '.join(missing_keys)}"
        )

    return {
        "host": rds["endpoint"],
        "port": int(rds["port_number"]),
        "user": rds["user_name"],
        "password": rds["user_pwd"],
        "database": rds["db_name"],
    }


def load_json(input_path: Path) -> list[dict]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list.")

    return data


def build_pairs(records: list[dict]) -> tuple[set[tuple[str, str]], int]:
    pairs: set[tuple[str, str]] = set()
    primary_tag_count = 0

    for index, record in enumerate(records, start=1):
        primary_tag = record.get("primary_tag")
        secondary_tags = record.get("source_secondary_tags")

        if not isinstance(primary_tag, str) or not primary_tag.strip():
            raise ValueError(
                f"Record {index}: primary_tag must be a non-empty string."
            )

        if not isinstance(secondary_tags, list):
            raise ValueError(
                f"Record {index}: source_secondary_tags must be a list."
            )

        primary_tag = primary_tag.strip()

        if len(primary_tag) > 100:
            raise ValueError(
                f"Record {index}: primary_tag exceeds VARCHAR(100): "
                f"{primary_tag}"
            )

        primary_tag_count += 1

        for secondary_tag in secondary_tags:
            if not isinstance(secondary_tag, str) or not secondary_tag.strip():
                raise ValueError(
                    f"Record {index}: every source_secondary_tag must "
                    "be a non-empty string."
                )

            secondary_tag = secondary_tag.strip()

            if len(secondary_tag) > 100:
                raise ValueError(
                    f"Record {index}: source_secondary_tag exceeds "
                    f"VARCHAR(100): {secondary_tag}"
                )

            pairs.add((primary_tag, secondary_tag))

    return pairs, primary_tag_count


def insert_pairs(
    database_config: dict[str, str],
    table_name: str,
    pairs: set[tuple[str, str]],
) -> tuple[int, int]:
    connection = pymysql.connect(
        host=database_config["host"],
        port=database_config["port"],
        user=database_config["user"],
        password=database_config["password"],
        database=database_config["database"],
        charset="utf8mb4",
        autocommit=False,
    )

    sql = f"""
        INSERT IGNORE INTO {table_name} (primary_tag, secondary_tag)
        VALUES (%s, %s)
    """

    inserted_count = 0

    try:
        with connection.cursor() as cursor:
            for primary_tag, secondary_tag in sorted(pairs):
                cursor.execute(sql, (primary_tag, secondary_tag))
                inserted_count += cursor.rowcount

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    skipped_count = len(pairs) - inserted_count

    return inserted_count, skipped_count


def main() -> None:
    args = parse_args()

    records = load_json(args.input)
    pairs, primary_tag_count = build_pairs(records)

    database_config = load_database_config()
    table_name = TABLE_BY_TAG_TYPE[args.tag_type]

    inserted_count, skipped_count = insert_pairs(
        database_config=database_config,
        table_name=table_name,
        pairs=pairs,
    )

    print(f"Target table: {table_name}")
    print(f"Primary-tag records read: {primary_tag_count}")
    print(f"Unique (primary_tag, secondary_tag) pairs prepared: {len(pairs)}")
    print(f"Rows inserted: {inserted_count}")
    print(f"Rows skipped as existing duplicates: {skipped_count}")


if __name__ == "__main__":
    main()
