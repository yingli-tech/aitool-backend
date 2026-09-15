import pytest
from unittest.mock import Mock, patch

from retriever import (
    retrieve_candidates, 
    score_candidates, 
    fallback_retrieve,
    sort_candidates,
    limit_top_results,
)



# the result must satisfy all strict filters
# category {1,2,3} ∩ use case {1,2} ∩ function {1,3} ∩ price {1,2} ∩ language {1,3} = {1}
@patch("retriever.db.get_tool_ids_by_language")
@patch("retriever.db.get_tool_ids_by_price_types")
@patch("retriever.db.get_tool_ids_by_function_primary_tags")
@patch("retriever.db.get_tool_ids_by_use_case_primary_tags")
@patch("retriever.db.get_tools_by_category")
def test_retrieve_candidates_applies_all_strict_filters(
    mock_get_tools_by_category,
    mock_get_tool_ids_by_use_case_primary_tags,
    mock_get_tool_ids_by_function_primary_tags,
    mock_get_tool_ids_by_price_types,
    mock_get_tool_ids_by_language,
):
    db_conn = Mock()

    mock_get_tools_by_category.return_value = [
        {"tool_id": 1, "name": "Tool One"},
        {"tool_id": 2, "name": "Tool Two"},
        {"tool_id": 3, "name": "Tool Three"},
    ]
    mock_get_tool_ids_by_use_case_primary_tags.return_value = {1, 2}
    mock_get_tool_ids_by_function_primary_tags.return_value = {1, 3}
    mock_get_tool_ids_by_price_types.return_value = {1, 2}
    mock_get_tool_ids_by_language.return_value = {1, 3}

    parsed_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [
                {"primary_tag": "content creation", "secondary_tag": None}
            ],
        },
        "functions": [
            {"primary_tag": "text generation", "secondary_tag": None}
        ],
    }

    result = retrieve_candidates(db_conn, parsed_query)

    assert result == [
        {"tool_id": 1, "name": "Tool One"}
    ]



@patch("retriever.db.get_tool_ids_by_use_case_primary_tags")
@patch("retriever.db.get_tools_by_category")
def test_retrieve_candidates_excludes_tools_without_required_use_case_primary(
    mock_get_tools_by_category,
    mock_get_tool_ids_by_use_case_primary_tags,
):
    db_conn = Mock()

    mock_get_tools_by_category.return_value = [
        {"tool_id": 1, "name": "General Writing Tool"},
        {"tool_id": 2, "name": "Blog Tool"},
    ]
    mock_get_tool_ids_by_use_case_primary_tags.return_value = {2}

    parsed_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": [],
            "language": [],
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "functions": [],
    }

    result = retrieve_candidates(db_conn, parsed_query)

    assert result == [
        {"tool_id": 2, "name": "Blog Tool"}
    ]



# use_case primary-tag match: +2
# use_case secondary-tag match: +4
@patch("retriever.db.get_tool_ids_by_use_case_tag")
@patch("retriever.db.get_tool_ids_by_use_case_primary_tags")
def test_score_candidates_awards_primary_score_without_secondary_match(
    mock_get_tool_ids_by_use_case_primary_tags,
    mock_get_tool_ids_by_use_case_tag,
):
    db_conn = Mock()

    mock_get_tool_ids_by_use_case_primary_tags.return_value = {1}
    mock_get_tool_ids_by_use_case_tag.return_value = set()

    candidates = [
        {"tool_id": 1, "name": "General Content Tool"},
    ]

    parsed_query = {
        "must_have": {
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "nice_to_have": {"use_cases": []},
        "functions": [],
    }

    result = score_candidates(db_conn, candidates, parsed_query)

    assert result[0]["matched_use_case_primary_tag_count"] == 1
    assert result[0]["matched_use_case_secondary_tag_count"] == 0
    assert result[0]["score"] == 2


@patch("retriever.db.get_tool_ids_by_use_case_tag")
@patch("retriever.db.get_tool_ids_by_use_case_primary_tags")
def test_score_candidates_awards_higher_score_for_primary_and_secondary_match(
    mock_get_tool_ids_by_use_case_primary_tags,
    mock_get_tool_ids_by_use_case_tag,
):
    db_conn = Mock()

    mock_get_tool_ids_by_use_case_primary_tags.return_value = {1}
    mock_get_tool_ids_by_use_case_tag.return_value = {1}

    candidates = [
        {"tool_id": 1, "name": "Blog Tool"},
    ]

    parsed_query = {
        "must_have": {
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "nice_to_have": {"use_cases": []},
        "functions": [],
    }

    result = score_candidates(db_conn, candidates, parsed_query)

    assert result[0]["matched_use_case_primary_tag_count"] == 1
    assert result[0]["matched_use_case_secondary_tag_count"] == 1
    assert result[0]["score"] == 6



# function：Primary matches、Secondary mismatches → 2 points
# function：Primary + Secondary both match → 6 points
# nice-to-have use case：Primary + Secondary both match → 3 points

@patch("retriever.db.get_tool_ids_by_function_tag")
@patch("retriever.db.get_tool_ids_by_function_primary_tags")
def test_score_candidates_awards_function_primary_score_without_secondary_match(
    mock_get_tool_ids_by_function_primary_tags,
    mock_get_tool_ids_by_function_tag,
):
    db_conn = Mock()

    mock_get_tool_ids_by_function_primary_tags.return_value = {1}
    mock_get_tool_ids_by_function_tag.return_value = set()

    candidates = [
        {"tool_id": 1, "name": "General Writing Tool"},
    ]

    parsed_query = {
        "must_have": {"use_cases": []},
        "nice_to_have": {"use_cases": []},
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }

    result = score_candidates(db_conn, candidates, parsed_query)

    assert result[0]["matched_function_primary_tag_count"] == 1
    assert result[0]["matched_function_secondary_tag_count"] == 0
    assert result[0]["score"] == 2



@patch("retriever.db.get_tool_ids_by_function_tag")
@patch("retriever.db.get_tool_ids_by_function_primary_tags")
def test_score_candidates_awards_higher_score_for_function_primary_and_secondary_match(
    mock_get_tool_ids_by_function_primary_tags,
    mock_get_tool_ids_by_function_tag,
):
    db_conn = Mock()

    mock_get_tool_ids_by_function_primary_tags.return_value = {1}
    mock_get_tool_ids_by_function_tag.return_value = {1}

    candidates = [
        {"tool_id": 1, "name": "Blog Writing Tool"},
    ]

    parsed_query = {
        "must_have": {"use_cases": []},
        "nice_to_have": {"use_cases": []},
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }

    result = score_candidates(db_conn, candidates, parsed_query)

    assert result[0]["matched_function_primary_tag_count"] == 1
    assert result[0]["matched_function_secondary_tag_count"] == 1
    assert result[0]["score"] == 6


@patch("retriever.db.get_tool_ids_by_use_case_tag")
@patch("retriever.db.get_tool_ids_by_use_case_primary_tags")
def test_score_candidates_awards_nice_to_have_primary_and_secondary_scores(
    mock_get_tool_ids_by_use_case_primary_tags,
    mock_get_tool_ids_by_use_case_tag,
):
    db_conn = Mock()

    mock_get_tool_ids_by_use_case_primary_tags.return_value = {1}
    mock_get_tool_ids_by_use_case_tag.return_value = {1}

    candidates = [
        {"tool_id": 1, "name": "Blog Tool"},
    ]

    parsed_query = {
        "must_have": {"use_cases": []},
        "nice_to_have": {
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "functions": [],
    }

    result = score_candidates(db_conn, candidates, parsed_query)

    assert result[0]["matched_nice_to_have_primary_tag_count"] == 1
    assert result[0]["matched_nice_to_have_secondary_tag_count"] == 1
    assert result[0]["score"] == 3


# relax one constraint at a time
# the relax order:functions → price_type → language 
@patch("retriever.retrieve_candidates")
def test_fallback_retrieve_relaxes_constraints_in_required_order(
    mock_retrieve_candidates,
):
    db_conn = Mock()

    mock_retrieve_candidates.side_effect = [
        [],
        [],
        [{"tool_id": 1, "name": "Blog Tool"}],
    ]

    parsed_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }

    candidates, fallback_info, active_query = fallback_retrieve(
        db_conn,
        parsed_query,
    )

    first_retry_query = mock_retrieve_candidates.call_args_list[0].args[1]
    second_retry_query = mock_retrieve_candidates.call_args_list[1].args[1]
    third_retry_query = mock_retrieve_candidates.call_args_list[2].args[1]

    assert first_retry_query["functions"] == []
    assert first_retry_query["must_have"]["price_type"] == ["free"]
    assert first_retry_query["must_have"]["language"] == ["english"]

    assert second_retry_query["functions"] == []
    assert second_retry_query["must_have"]["price_type"] == []
    assert second_retry_query["must_have"]["language"] == ["english"]

    assert third_retry_query["functions"] == []
    assert third_retry_query["must_have"]["price_type"] == []
    assert third_retry_query["must_have"]["language"] == []

    assert candidates == [{"tool_id": 1, "name": "Blog Tool"}]
    assert fallback_info["relaxed_fields"] == [
        "functions",
        "price_type",
        "language",
    ]
    assert fallback_info["retry_count"] == 3
    assert active_query == third_retry_query



# 放宽 functions 后立即找到：必须停止，不能继续放宽 price/language
# relax the functions constrain and then find the tool, so stop relaxing
@patch("retriever.retrieve_candidates")
def test_fallback_retrieve_stops_after_function_relaxation_finds_results(
    mock_retrieve_candidates,
):
    db_conn = Mock()
    mock_retrieve_candidates.return_value = [
        {"tool_id": 1, "name": "Blog Tool"}
    ]

    parsed_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }

    candidates, fallback_info, active_query = fallback_retrieve(
        db_conn,
        parsed_query,
    )

    assert mock_retrieve_candidates.call_count == 1
    assert candidates == [{"tool_id": 1, "name": "Blog Tool"}]
    assert fallback_info["relaxed_fields"] == ["functions"]
    assert active_query["functions"] == []
    assert active_query["must_have"]["price_type"] == ["free"]
    assert active_query["must_have"]["language"] == ["english"]



# 放宽 price_type 后找到：必须停止，不能继续放宽 language；
# relax price_type and then find the tool, so stop relaxing
@patch("retriever.retrieve_candidates")
def test_fallback_retrieve_stops_after_price_relaxation_finds_results(
    mock_retrieve_candidates,
):
    db_conn = Mock()

    mock_retrieve_candidates.side_effect = [
        [],
        [{"tool_id": 1, "name": "Blog Tool"}],
    ]

    parsed_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }

    candidates, fallback_info, active_query = fallback_retrieve(
        db_conn,
        parsed_query,
    )

    assert mock_retrieve_candidates.call_count == 2
    assert candidates == [{"tool_id": 1, "name": "Blog Tool"}]
    assert fallback_info["relaxed_fields"] == [
        "functions",
        "price_type",
    ]
    assert active_query["functions"] == []
    assert active_query["must_have"]["price_type"] == []
    assert active_query["must_have"]["language"] == ["english"]



# 三步都放宽后仍无结果：返回空列表和完整 retry history
# after relaxing three times and get no tools, return empty list and retry history
@patch("retriever.retrieve_candidates")
def test_fallback_retrieve_returns_empty_after_all_relaxations_fail(
    mock_retrieve_candidates,
):
    db_conn = Mock()
    mock_retrieve_candidates.return_value = []

    parsed_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }

    candidates, fallback_info, active_query = fallback_retrieve(
        db_conn,
        parsed_query,
    )

    assert mock_retrieve_candidates.call_count == 3
    assert candidates == []
    assert fallback_info["fallback_used"] is True
    assert fallback_info["relaxed_fields"] == [
        "functions",
        "price_type",
        "language",
    ]
    assert fallback_info["retry_count"] == 3
    assert fallback_info["retry_history"][-1]["result_count"] == 0

    assert active_query["functions"] == []
    assert active_query["must_have"]["price_type"] == []
    assert active_query["must_have"]["language"] == []

    # use case 始终保留为 hard constraint
    assert active_query["must_have"]["use_cases"] == [
        {
            "primary_tag": "content creation",
            "secondary_tag": "blog creation",
        }
    ]


# tie break: matched_use_case_secondary_tag_count
def test_sort_candidates_uses_secondary_match_as_tie_breaker():
    scored_candidates = [
        {
            "tool_id": 1,
            "name": "Alpha Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 1,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
        {
            "tool_id": 2,
            "name": "Beta Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 1,
            "matched_function_secondary_tag_count": 1,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
    ]

    result = sort_candidates(scored_candidates)

    assert [candidate["tool_id"] for candidate in result] == [2, 1]
    assert [candidate["rank"] for candidate in result] == [1, 2]



# tie break: matched_function_secondary_tag_count

def test_sort_candidates_uses_function_secondary_match_as_tie_breaker():
    scored_candidates = [
        {
            "tool_id": 1,
            "name": "Alpha Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
        {
            "tool_id": 2,
            "name": "Beta Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 1,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
    ]

    result = sort_candidates(scored_candidates)

    assert [candidate["tool_id"] for candidate in result] == [2, 1]
    assert [candidate["rank"] for candidate in result] == [1, 2]



# tie break: matched_use_case_primary_tag_count
def test_sort_candidates_uses_use_case_primary_match_as_tie_breaker():
    scored_candidates = [
        {
            "tool_id": 1,
            "name": "Alpha Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 0,
            "matched_function_primary_tag_count": 1,
        },
        {
            "tool_id": 2,
            "name": "Beta Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
    ]

    result = sort_candidates(scored_candidates)

    assert [candidate["tool_id"] for candidate in result] == [2, 1]
    assert [candidate["rank"] for candidate in result] == [1, 2]



# tie break: matched_function_primary_tag_count
def test_sort_candidates_uses_function_primary_match_as_tie_breaker():
    scored_candidates = [
        {
            "tool_id": 1,
            "name": "Alpha Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 0,
        },
        {
            "tool_id": 2,
            "name": "Beta Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
    ]

    result = sort_candidates(scored_candidates)

    assert [candidate["tool_id"] for candidate in result] == [2, 1]
    assert [candidate["rank"] for candidate in result] == [1, 2]


# tie break: tool name / id
def test_sort_candidates_uses_name_as_tie_breaker():
    scored_candidates = [
        {
            "tool_id": 1,
            "name": "Beta Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
        {
            "tool_id": 2,
            "name": "Alpha Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
    ]

    result = sort_candidates(scored_candidates)

    assert [candidate["tool_id"] for candidate in result] == [2, 1]


# tie break: tool id
def test_sort_candidates_uses_tool_id_as_tie_breaker():
    scored_candidates = [
        {
            "tool_id": 2,
            "name": "Same Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
        {
            "tool_id": 1,
            "name": "Same Tool",
            "score": 6,
            "matched_use_case_secondary_tag_count": 0,
            "matched_function_secondary_tag_count": 0,
            "matched_use_case_primary_tag_count": 1,
            "matched_function_primary_tag_count": 1,
        },
    ]

    result = sort_candidates(scored_candidates)

    assert [candidate["tool_id"] for candidate in result] == [1, 2]


# default limit = 3
def test_limit_top_results_returns_requested_number_of_candidates():
    sorted_candidates = [
        {"tool_id": 1, "name": "Tool One", "rank": 1},
        {"tool_id": 2, "name": "Tool Two", "rank": 2},
        {"tool_id": 3, "name": "Tool Three", "rank": 3},
        {"tool_id": 4, "name": "Tool Four", "rank": 4},
    ]

    result = limit_top_results(sorted_candidates, limit=3)

    assert result == sorted_candidates[:3]


# if change parameter "limit" to 0, -1, it should not return result
@pytest.mark.parametrize("limit", [0, -1])
def test_limit_top_results_returns_empty_for_nonpositive_limit(limit):
    sorted_candidates = [
        {"tool_id": 1, "name": "Tool One", "rank": 1},
    ]

    result = limit_top_results(sorted_candidates, limit=limit)

    assert result == []