import pytest
from etl.load.load_tools_to_db import (
    build_raw_to_secondary_map, 
    build_secondary_to_primary_map,
    )

from unittest.mock import Mock, patch

from etl.load.load_tools_to_db import (
    build_raw_to_secondary_map,
    build_secondary_to_primary_map,
    get_taxonomy_id,
)

# do not insert mapping if the mapping already exists in the database
from etl.load.load_tools_to_db import ensure_mapping

# check the mapping of secondary tags to raw tags
from etl.load.load_tools_to_db import load_tool_relationships

######################################################################
# Taxonomy mapping tests
######################################################################

# raw tags are mapped to secondary tags based on the consolidated records.
def test_build_raw_to_secondary_map_success():
    consolidated_records = [
        {
            "secondary_tags": [
                {
                    "secondary_tag": "Website Creation",
                    "source_tags": [
                        "Website Generation",
                        "AI Website Builder",
                        "Website Editor",
                    ],
                }
            ]
        }
    ]


    result = build_raw_to_secondary_map(
        consolidated_records,
        tag_level="use case",
    )

    assert result == {
        "Website Generation": "Website Creation",
        "AI Website Builder": "Website Creation",
        "Website Editor": "Website Creation",
    }




# one raw tag mapped to two different secondary tags should raise ValueError.
def test_build_raw_to_secondary_map_raises_on_conflict():
    consolidated_records = [
        {
            "secondary_tags": [
                {
                    "secondary_tag": "Website Creation",
                    "source_tags": ["Website Generation"],
                },
                {
                    "secondary_tag": "Code Generation",
                    "source_tags": ["Website Generation"],
                },
            ]
        }
    ]

    with pytest.raises(
        ValueError,
        match="Conflicting use case mapping",
    ):
        build_raw_to_secondary_map(
            consolidated_records,
            tag_level="use case",
        )

# secondary tags are mapped to primary tags based on the consolidated records.
def test_build_secondary_to_primary_map_success():
    primary_records = [
        {
            "primary_tag": "Website Development",
            "source_secondary_tags": [
                "Website Creation",
                "Landing Page Creation",
            ],
        }
    ]

    result = build_secondary_to_primary_map(
        primary_records,
        tag_level="use case",
    )

    assert result == {
        "Website Creation": "Website Development",
        "Landing Page Creation": "Website Development",
    }

# one secondary tag mapped to two different primary tags should raise ValueError.
def test_build_secondary_to_primary_map_raises_on_conflict():
    primary_records = [
        {
            "primary_tag": "Website Development",
            "source_secondary_tags": ["Website Creation"],
        },
        {
            "primary_tag": "Content Creation",
            "source_secondary_tags": ["Website Creation"],
        },
    ]

    with pytest.raises(
        ValueError,
        match="Conflicting use case primary mapping",
    ):
        build_secondary_to_primary_map(
            primary_records,
            tag_level="use case",
        )

# get_taxonomy_id should return the correct taxonomy_id
def test_get_taxonomy_id_success():
    cursor = Mock()
    # determine what the mock value should return when fetchone is called
    cursor.fetchone.return_value = (1105,)

    result = get_taxonomy_id(
        cursor=cursor,
        table_name="use_cases",
        id_column="usecase_id",
        primary_tag="Website Development",
        secondary_tag="Website Creation",
    )

    assert result == 1105

    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (
        "Website Development",
        "Website Creation",
    )
    """ cursor.execute.call_args.args == (
        sql,
        ("Website Development", "Website Creation"),
    )"""

# get_taxonomy_id should raise ValueError when the taxonomy pair is not found
def test_get_taxonomy_id_raises_when_pair_not_found():
    cursor = Mock()
    cursor.fetchone.return_value = None

    with pytest.raises(
        ValueError,
        match="Taxonomy pair not found in use_cases",
    ):
        get_taxonomy_id(
            cursor=cursor,
            table_name="use_cases",
            id_column="usecase_id",
            primary_tag="Website Development",
            secondary_tag="Website Creation",
        )

    cursor.execute.assert_called_once()


# do not insert mapping if the mapping already exists in the database
def test_ensure_mapping_does_not_insert_existing_mapping():
    cursor = Mock()
    cursor.fetchone.return_value = (1,)

    ensure_mapping(
        cursor=cursor,
        table_name="tool_usecase_map",
        left_column="tool_id",
        left_id=10,
        right_column="usecase_id",
        right_id=123,
    )

    # only execute SELECT and not INSERT any records since the mapping already exists
    cursor.execute.assert_called_once()

    assert cursor.execute.call_args.args[1] == (10, 123)


# insert mapping if the mapping does not exist in the database
def test_ensure_mapping_inserts_missing_mapping():
    cursor = Mock()
    cursor.fetchone.return_value = None

    ensure_mapping(
        cursor=cursor,
        table_name="tool_usecase_map",
        left_column="tool_id",
        left_id=1011,
        right_column="usecase_id",
        right_id=1105,
    )

    # fist time is SELECT and then INSERT
    assert cursor.execute.call_count == 2

    select_call = cursor.execute.call_args_list[0]
    insert_call = cursor.execute.call_args_list[1]

    assert select_call.args[1] == (1011, 1105)
    assert insert_call.args[1] == (1011, 1105)

    assert "SELECT 1" in select_call.args[0]
    assert "INSERT INTO tool_usecase_map" in insert_call.args[0]


# function secondary tags not in the mapping should raise ValueError
@patch("etl.load.load_tools_to_db.ensure_mapping")
@patch("etl.load.load_tools_to_db.get_or_create_source")
def test_load_tool_relationships_raises_when_function_has_no_secondary_mapping(
    mock_get_or_create_source,
    mock_ensure_mapping,
):
    mock_get_or_create_source.return_value = 1
    cursor = Mock()

    record = {
        "source": "aitoolsdirectory",
        "source_url": "https://aitoolsdirectory.com/",
        "function": ["Unknown Raw Function"],
        "use_case": [],
    }

    with pytest.raises(
        ValueError,
        match="Function has no secondary mapping: 'Unknown Raw Function'",
    ):
        load_tool_relationships(
            cursor=cursor,
            tool_id=1011,
            record=record,
            function_secondary_map={},
            use_case_secondary_map={},
            function_primary_map={},
            use_case_primary_map={},
        )


# secondary function has no primary mapping should raise ValueError
@patch("etl.load.load_tools_to_db.ensure_mapping")
@patch("etl.load.load_tools_to_db.get_or_create_source")
def test_load_tool_relationships_raises_when_function_secondary_has_no_primary(
    mock_get_or_create_source,
    mock_ensure_mapping,
):
    mock_get_or_create_source.return_value = 1
    cursor = Mock()

    record = {
        "source": "aitoolsdirectory",
        "source_url": "https://aitoolsdirectory.com/",
        "function": ["Website Generation"],
        "use_case": [],
    }

    with pytest.raises(
        ValueError,
        match="Secondary function has no primary mapping: 'Website Creation'",
    ):
        load_tool_relationships(
            cursor=cursor,
            tool_id=1011,
            record=record,
            function_secondary_map={
                "Website Generation": "Website Creation",
            },
            use_case_secondary_map={},
            function_primary_map={},
            use_case_primary_map={},
        )

# use case has no secondary mapping should raise ValueError
@patch("etl.load.load_tools_to_db.ensure_mapping")
@patch("etl.load.load_tools_to_db.get_or_create_source")
def test_load_tool_relationships_raises_when_use_case_has_no_secondary_mapping(
    mock_get_or_create_source,
    mock_ensure_mapping,
):
    mock_get_or_create_source.return_value = 1
    cursor = Mock()

    record = {
        "source": "aitoolsdirectory",
        "source_url": "https://aitoolsdirectory.com/",
        "function": [],
        "use_case": ["Unknown Raw Use Case"],
    }

    with pytest.raises(
        ValueError,
        match="Use case has no secondary mapping: 'Unknown Raw Use Case'",
    ):
        load_tool_relationships(
            cursor=cursor,
            tool_id=10,
            record=record,
            function_secondary_map={},
            use_case_secondary_map={},
            function_primary_map={},
            use_case_primary_map={},
        )

# secondary use case has no primary mapping should raise ValueError
@patch("etl.load.load_tools_to_db.ensure_mapping")
@patch("etl.load.load_tools_to_db.get_or_create_source")
def test_load_tool_relationships_raises_when_use_case_secondary_has_no_primary(
    mock_get_or_create_source,
    mock_ensure_mapping,
):
    mock_get_or_create_source.return_value = 1
    cursor = Mock()

    record = {
        "source": "aitoolsdirectory",
        "source_url": "https://aitoolsdirectory.com/",
        "function": [],
        "use_case": ["Blog Generation"],
    }

    with pytest.raises(
        ValueError,
        match="Secondary use case has no primary mapping: 'Blog Creation'",
    ):
        load_tool_relationships(
            cursor=cursor,
            tool_id=1011,
            record=record,
            function_secondary_map={},
            use_case_secondary_map={
                "Blog Generation": "Blog Creation",
            },
            function_primary_map={},
            use_case_primary_map={},
        )


# test the entire link of source -> function -> use case, with secondary and primary mapping
@patch("etl.load.load_tools_to_db.get_taxonomy_id")
@patch("etl.load.load_tools_to_db.ensure_mapping")
@patch("etl.load.load_tools_to_db.get_or_create_source")
def test_load_tool_relationships_maps_function_and_use_case_successfully(
    mock_get_or_create_source,
    mock_ensure_mapping,
    mock_get_taxonomy_id,
):
    mock_get_or_create_source.return_value = 1
    mock_get_taxonomy_id.side_effect = [20, 30]
    cursor = Mock()

    record = {
        "source": "aitoolsdirectory",
        "source_url": "https://aitoolsdirectory.com/",
        "function": ["Text Writing"],
        "use_case": ["Blog Generation"],
    }

    load_tool_relationships(
        cursor=cursor,
        tool_id=10,
        record=record,
        function_secondary_map={
            "Text Writing": "Text Generation",
        },
        use_case_secondary_map={
            "Blog Generation": "Blog Creation",
        },
        function_primary_map={
            "Text Generation": "Content Generation",
        },
        use_case_primary_map={
            "Blog Creation": "Content Creation",
        },
    )

    assert mock_get_taxonomy_id.call_count == 2

    # mock_get_taxonomy_id.call_args_list is a list of call objects.
    # kwargs is a dictionary of the keyword arguments passed to the function.
    # This list starts from 0.
    function_lookup = mock_get_taxonomy_id.call_args_list[0].kwargs
    assert function_lookup["table_name"] == "functions"
    assert function_lookup["primary_tag"] == "Content Generation"
    assert function_lookup["secondary_tag"] == "Text Generation"

    use_case_lookup = mock_get_taxonomy_id.call_args_list[1].kwargs
    assert use_case_lookup["table_name"] == "use_cases"
    assert use_case_lookup["primary_tag"] == "Content Creation"
    assert use_case_lookup["secondary_tag"] == "Blog Creation"

    # source、function、use case 各写入一次关联
    assert mock_ensure_mapping.call_count == 3


######################################################################
# price_type and language mapping tests
######################################################################

# test that the price_type and language are correctly mapped to their respective IDs and inserted into the database.
@patch("etl.load.load_tools_to_db.ensure_mapping")
@patch("etl.load.load_tools_to_db.get_or_create_language")
@patch("etl.load.load_tools_to_db.get_or_create_price_type")
@patch("etl.load.load_tools_to_db.get_or_create_source")
def test_load_tool_relationships_maps_price_and_language(
    mock_get_or_create_source,
    mock_get_or_create_price_type,
    mock_get_or_create_language,
    mock_ensure_mapping,
):
    mock_get_or_create_source.return_value = 1
    mock_get_or_create_price_type.return_value = 2
    mock_get_or_create_language.return_value = 3
    cursor = Mock()

    record = {
        "source": "aitoolsdirectory",
        "source_url": "https://aitoolsdirectory.com/",
        "price_type": ["free"],
        "language": ["English"],
        "function": [],
        "use_case": [],
    }

    load_tool_relationships(
        cursor=cursor,
        tool_id=1011,
        record=record,
        function_secondary_map={},
        use_case_secondary_map={},
        function_primary_map={},
        use_case_primary_map={},
    )

    assert mock_get_or_create_price_type.call_args.args[1] == "free"
    assert mock_get_or_create_language.call_args.args[1] == "English"

    mapping_tables = [
        call.kwargs["table_name"]
        for call in mock_ensure_mapping.call_args_list
    ]

    assert mapping_tables == [
        "tool_source_map",
        "tool_price_map",
        "tool_language_map",
    ]


# test whether multiple price types and languages are correctly mapped and inserted into the database.
@patch("etl.load.load_tools_to_db.ensure_mapping")
@patch("etl.load.load_tools_to_db.get_or_create_language")
@patch("etl.load.load_tools_to_db.get_or_create_price_type")
@patch("etl.load.load_tools_to_db.get_or_create_source")
def test_load_tool_relationships_maps_multiple_prices_and_languages(
    mock_get_or_create_source,
    mock_get_or_create_price_type,
    mock_get_or_create_language,
    mock_ensure_mapping,
):
    mock_get_or_create_source.return_value = 1
    mock_get_or_create_price_type.side_effect = [2, 3]
    mock_get_or_create_language.side_effect = [4, 5]
    cursor = Mock()

    record = {
        "source": "aitoolsdirectory",
        "source_url": "https://aitoolsdirectory.com/",
        "price_type": ["free", "paid"],
        "language": ["English", "Spanish"],
        "function": [],
        "use_case": [],
    }

    load_tool_relationships(
        cursor=cursor,
        tool_id=10,
        record=record,
        function_secondary_map={},
        use_case_secondary_map={},
        function_primary_map={},
        use_case_primary_map={},
    )

    assert [
        call.args[1]
        for call in mock_get_or_create_price_type.call_args_list
    ] == ["free", "paid"]

    assert [
        call.args[1]
        for call in mock_get_or_create_language.call_args_list
    ] == ["English", "Spanish"]

    assert mock_ensure_mapping.call_count == 5