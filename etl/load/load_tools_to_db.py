from __future__ import annotations

import argparse
import configparser
import json
from pathlib import Path

import pymysql


CONFIG_PATH = Path(
    r"D:\Project\aggregationai\codes\backend\aitool\etl\configuration\aitools-config.ini"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load enriched AI tool records into MySQL."
    )

    parser.add_argument(
        "--tools-input",
        required=True,
        type=Path,
        help="Path to enriched_candidate_tool_records_cleaned.json.",
    )

    parser.add_argument(
        "--functions-secondary-input",
        required=True,
        type=Path,
        help="Path to consolidated_functions_secondary_tags.json.",
    )

    parser.add_argument(
        "--use-cases-secondary-input",
        required=True,
        type=Path,
        help="Path to consolidated_use_cases_secondary_tags.json.",
    )

    parser.add_argument(
        "--functions-primary-input",
        required=True,
        type=Path,
        help="Path to deduplicated_functions_primary_tags.json.",
    )

    parser.add_argument(
        "--use-cases-primary-input",
        required=True,
        type=Path,
        help="Path to deduplicated_use_cases_primary_tags.json.",
    )

    return parser.parse_args()


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list: {path}")

    return data


def load_database_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Database config file not found: {CONFIG_PATH}"
        )

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")

    rds = config["rds"]

    return {
        "host": rds["endpoint"],
        "port": int(rds["port_number"]),
        "user": rds["user_name"],
        "password": rds["user_pwd"],
        "database": rds["db_name"],
        "charset": "utf8mb4",
        "autocommit": False,
    }


def build_raw_to_secondary_map(
    consolidated_records: list[dict],
    tag_level: str,
) -> dict[str, str]:
    """
    Build:
    raw source tag -> secondary tag

    Example:
    "Website Generation" -> "Website Creation"
    """
    mapping: dict[str, str] = {}

    for pocket in consolidated_records:
        for secondary_group in pocket.get("secondary_tags", []):
            secondary_tag = secondary_group["secondary_tag"]

            for source_tag in secondary_group.get("source_tags", []):
                existing_secondary = mapping.get(source_tag)

                if (
                    existing_secondary is not None
                    and existing_secondary != secondary_tag
                ):
                    raise ValueError(
                        f"Conflicting {tag_level} mapping for "
                        f"'{source_tag}': '{existing_secondary}' vs "
                        f"'{secondary_tag}'"
                    )

                mapping[source_tag] = secondary_tag

    return mapping

def build_secondary_to_primary_map(
    primary_records: list[dict],
    tag_level: str,
) -> dict[str, str]:
    mapping: dict[str, str] = {}

    for record in primary_records:
        primary_tag = record["primary_tag"]

        for secondary_tag in record.get(
            "source_secondary_tags",
            [],
        ):
            existing_primary = mapping.get(secondary_tag)

            if (
                existing_primary is not None
                and existing_primary != primary_tag
            ):
                raise ValueError(
                    f"Conflicting {tag_level} primary mapping for "
                    f"'{secondary_tag}': '{existing_primary}' vs "
                    f"'{primary_tag}'"
                )

            mapping[secondary_tag] = primary_tag

    return mapping


def get_or_create_tool(
    cursor,
    record: dict,
) -> int:
    name = record["name"]
    url = record["official_url"]
    description = record.get("one_line_desc")
    category = record["category"]

    cursor.execute(
        """
        SELECT tool_id
        FROM tools
        WHERE url = %s
        ORDER BY tool_id
        LIMIT 1
        """,
        (url,),
    )

    existing_tool = cursor.fetchone()

    if existing_tool:
        tool_id = existing_tool[0]

        cursor.execute(
            """
            UPDATE tools
            SET name = %s,
                description = %s,
                category = %s
            WHERE tool_id = %s
            """,
            (name, description, category, tool_id),
        )

        return tool_id

    cursor.execute(
        """
        INSERT INTO tools (name, url, description, category)
        VALUES (%s, %s, %s, %s)
        """,
        (name, url, description, category),
    )

    return cursor.lastrowid


def get_or_create_source(
    cursor,
    source_name: str,
    source_url: str,
) -> int:
    cursor.execute(
        """
        SELECT source_id
        FROM sources
        WHERE name = %s AND source_url = %s
        LIMIT 1
        """,
        (source_name, source_url),
    )

    existing_source = cursor.fetchone()

    if existing_source:
        return existing_source[0]

    cursor.execute(
        """
        INSERT INTO sources (name, source_url)
        VALUES (%s, %s)
        """,
        (source_name, source_url),
    )

    return cursor.lastrowid


def get_or_create_price_type(
    cursor,
    price_type: str,
) -> int:
    cursor.execute(
        """
        SELECT price_type_id
        FROM price_types
        WHERE price_type = %s
        LIMIT 1
        """,
        (price_type,),
    )

    existing_price_type = cursor.fetchone()

    if existing_price_type:
        return existing_price_type[0]

    cursor.execute(
        """
        INSERT INTO price_types (price_type)
        VALUES (%s)
        """,
        (price_type,),
    )

    return cursor.lastrowid


def get_or_create_language(
    cursor,
    language_name: str,
) -> int:
    cursor.execute(
        """
        SELECT language_id
        FROM languages
        WHERE language = %s
        LIMIT 1
        """,
        (language_name,),
    )

    existing_language = cursor.fetchone()

    if existing_language:
        return existing_language[0]

    cursor.execute(
        """
        INSERT INTO languages (language)
        VALUES (%s)
        """,
        (language_name,),
    )

    return cursor.lastrowid


def get_taxonomy_id(
    cursor,
    table_name: str,
    id_column: str,
    primary_tag: str,
    secondary_tag: str,
) -> int:
    cursor.execute(
        f"""
        SELECT {id_column}
        FROM {table_name}
        WHERE primary_tag = %s
          AND secondary_tag = %s
        LIMIT 1
        """,
        (primary_tag, secondary_tag),
    )

    row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Taxonomy pair not found in {table_name}: "
            f"({primary_tag}, {secondary_tag})"
        )

    return row[0]


def ensure_mapping(
    cursor,
    table_name: str,
    left_column: str,
    left_id: int,
    right_column: str,
    right_id: int,
) -> None:
    cursor.execute(
        f"""
        SELECT 1
        FROM {table_name}
        WHERE {left_column} = %s
          AND {right_column} = %s
        LIMIT 1
        """,
        (left_id, right_id),
    )

    if cursor.fetchone():
        return

    cursor.execute(
        f"""
        INSERT INTO {table_name} ({left_column}, {right_column})
        VALUES (%s, %s)
        """,
        (left_id, right_id),
    )


def load_tool_relationships(
    cursor,
    tool_id: int,
    record: dict,
    function_secondary_map: dict[str, str],
    use_case_secondary_map: dict[str, str],
    function_primary_map: dict[str, str],
    use_case_primary_map: dict[str, str],
) -> None:
    # source -> sources -> tool_source_map
    source_id = get_or_create_source(
        cursor,
        record["source"],
        record["source_url"],
    )

    ensure_mapping(
        cursor,
        table_name="tool_source_map",
        left_column="tool_id",
        left_id=tool_id,
        right_column="source_id",
        right_id=source_id,
    )

    # price_type -> price_types -> tool_price_map
    for price_type in record.get("price_type", []):
        price_type_id = get_or_create_price_type(cursor, price_type)

        ensure_mapping(
            cursor,
            table_name="tool_price_map",
            left_column="tool_id",
            left_id=tool_id,
            right_column="price_type_id",
            right_id=price_type_id,
        )

    # language -> language -> tool_language_map
    for language_name in record.get("language", []):
        language_id = get_or_create_language(cursor, language_name)

        ensure_mapping(
            cursor,
            table_name="tool_language_map",
            left_column="tool_id",
            left_id=tool_id,
            right_column="language_id",
            right_id=language_id,
        )

    # raw function -> secondary function -> functions -> tool_function_map
    for raw_function in record.get("function", []):
        secondary_function = function_secondary_map.get(raw_function)

        if secondary_function is None:
            raise ValueError(
                f"Function has no secondary mapping: '{raw_function}'"
            )

        primary_function = function_primary_map.get(
            secondary_function
        )

        if primary_function is None:
            raise ValueError(
                f"Secondary function has no primary mapping: "
                f"'{secondary_function}'"
            )

        function_id = get_taxonomy_id(
            cursor=cursor,
            table_name="functions",
            id_column="function_id",
            primary_tag=primary_function,
            secondary_tag=secondary_function,
        )

        ensure_mapping(
            cursor,
            table_name="tool_function_map",
            left_column="tool_id",
            left_id=tool_id,
            right_column="function_id",
            right_id=function_id,
        )

    # raw use case -> secondary use case -> use_cases -> tool_usecase_map
    for raw_use_case in record.get("use_case", []):
        secondary_use_case = use_case_secondary_map.get(
            raw_use_case
        )

        if secondary_use_case is None:
            raise ValueError(
                f"Use case has no secondary mapping: '{raw_use_case}'"
            )

        primary_use_case = use_case_primary_map.get(
            secondary_use_case
        )

        if primary_use_case is None:
            raise ValueError(
                f"Secondary use case has no primary mapping: "
                f"'{secondary_use_case}'"
            )

        usecase_id = get_taxonomy_id(
            cursor=cursor,
            table_name="use_cases",
            id_column="usecase_id",
            primary_tag=primary_use_case,
            secondary_tag=secondary_use_case,
        )

        ensure_mapping(
            cursor,
            table_name="tool_usecase_map",
            left_column="tool_id",
            left_id=tool_id,
            right_column="usecase_id",
            right_id=usecase_id,
        )

def main() -> None:
    args = parse_args()

    tool_records = load_json(args.tools_input)

    consolidated_functions = load_json(
        args.functions_secondary_input
    )

    consolidated_use_cases = load_json(
        args.use_cases_secondary_input
    )

    function_secondary_map = build_raw_to_secondary_map(
        consolidated_functions,
        tag_level="function",
    )

    use_case_secondary_map = build_raw_to_secondary_map(
        consolidated_use_cases,
        tag_level="use case",
    )

    deduplicated_functions_primary = load_json(
        args.functions_primary_input
    )

    deduplicated_use_cases_primary = load_json(
        args.use_cases_primary_input
    )

    function_primary_map = build_secondary_to_primary_map(
        deduplicated_functions_primary,
        tag_level="function",
    )

    use_case_primary_map = build_secondary_to_primary_map(
        deduplicated_use_cases_primary,
        tag_level="use case",
    )

    database_config = load_database_config()
    connection = pymysql.connect(**database_config)

    try:
        with connection.cursor() as cursor:
            for index, record in enumerate(tool_records, start=1):
                required_fields = [
                    "name",
                    "official_url",
                    "source",
                    "source_url",
                    "category",
                ]

                missing_fields = [
                    field
                    for field in required_fields
                    if not record.get(field)
                ]

                if missing_fields:
                    raise ValueError(
                        f"Tool record {index} is missing required fields: "
                        f"{', '.join(missing_fields)}"
                    )

                tool_id = get_or_create_tool(cursor, record)

                load_tool_relationships(
                    cursor=cursor,
                    tool_id=tool_id,
                    record=record,
                    function_secondary_map=function_secondary_map,
                    use_case_secondary_map=use_case_secondary_map,
                    function_primary_map=function_primary_map,
                    use_case_primary_map=use_case_primary_map,
                )

                print(
                    f"Processed {index}/{len(tool_records)}: "
                    f"{record['name']} (tool_id={tool_id})"
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print("\nImport completed successfully.")
    print(f"Tools processed: {len(tool_records)}")


if __name__ == "__main__":
    main()
