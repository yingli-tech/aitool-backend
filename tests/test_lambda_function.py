import pytest
from unittest.mock import Mock, patch

from lambda_function import (
    lambda_handler, 
    get_http_method, 
    extract_query_from_event,
    validate_request,
)



# OPTIONS 应直接返回 CORS preflight response，不读取环境变量、不连数据库
# OPTIONS should return CORS preflight response directly without loading environment variables and database.
@patch("lambda_function.response.build_options_response")
def test_lambda_handler_returns_options_response_for_preflight(
    mock_build_options_response,
):
    expected_response = {
        "statusCode": 200,
        "body": "",
    }
    mock_build_options_response.return_value = expected_response

    result = lambda_handler(
        event={"httpMethod": "OPTIONS"},
        context=None,
    )

    assert result == expected_response
    mock_build_options_response.assert_called_once()



@patch("lambda_function.response.build_error_response")
def test_lambda_handler_rejects_non_post_method(
    mock_build_error_response,
):
    expected_response = {
        "statusCode": 405,
        "body": "method not allowed",
    }
    mock_build_error_response.return_value = expected_response

    result = lambda_handler(
        event={"httpMethod": "GET"},
        context=None,
    )

    assert result == expected_response

    mock_build_error_response.assert_called_once_with(
        status_code=405,
        message="Method not allowed",
        detail="Unsupported method: GET",
    )



@patch.dict(
    "lambda_function.os.environ",
    {
        "endpoint": "test-endpoint",
        "dbname": "test-db",
        "username": "test-user",
        "pwd": "test-password",
        "portnum": "3306",
        "OPENAI_API_KEY": "test-key",
        "openai_model": "gpt-4.1-mini",
    },
    clear=True,
)
@patch("lambda_function.response.format_response")
@patch("lambda_function.response.log_request")
@patch("lambda_function.retriever.fallback_retrieve")
@patch("lambda_function.retriever.retrieve_candidates")
@patch("lambda_function.parser.normalize_parsed_query")
@patch("lambda_function.parser.validate_llm_output")
@patch("lambda_function.parser.parse_query_with_llm")
@patch("lambda_function.parser.build_parsing_prompt")
@patch("lambda_function.tag_selector.select_candidate_tags")
@patch("lambda_function.db.get_taxonomy_context")
@patch("lambda_function.db.close_db_connection")
@patch("lambda_function.db.get_db_connection")
@patch("lambda_function.OpenAI")
def test_lambda_handler_uses_fallback_when_strict_retrieval_is_empty(
    mock_openai,
    mock_get_db_connection,
    mock_close_db_connection,
    mock_get_taxonomy_context,
    mock_select_candidate_tags,
    mock_build_parsing_prompt,
    mock_parse_query_with_llm,
    mock_validate_llm_output,
    mock_normalize_parsed_query,
    mock_retrieve_candidates,
    mock_fallback_retrieve,
    mock_log_request,
    mock_format_response,
):
    db_conn = Mock()
    client = Mock()

    full_taxonomy_context = {
        "categories": ["ai writing"],
        "price_types": ["free", "paid"],
        "languages": ["english"],
        "use_cases": [
            {
                "primary_tag": "content creation",
                "secondary_tag": "blog creation",
            },
            {
                "primary_tag": "content creation",
                "secondary_tag": "article creation",
            },
        ],
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            },
            {
                "primary_tag": "text generation",
                "secondary_tag": "article writing",
            },
        ],
    }

    top_50_candidate_tags = {
        "use_cases": [
            {
                "primary_tag": "content creation",
                "secondary_tag": "blog creation",
            }
        ],
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }

    llm_output = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [],
        },
        "nice_to_have": {"use_cases": []},
        "functions": [],
    }

    normalized_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [],
        },
        "nice_to_have": {"use_cases": []},
        "functions": [],
    }

    fallback_info = {
        "fallback_used": True,
        "relaxed_fields": ["functions"],
    }
    expected_response = {"statusCode": 200, "body": "{}"}

    mock_openai.return_value = client
    mock_get_db_connection.return_value = db_conn
    mock_get_taxonomy_context.return_value = full_taxonomy_context
    mock_select_candidate_tags.return_value = top_50_candidate_tags
    mock_build_parsing_prompt.return_value = "test prompt"
    mock_parse_query_with_llm.return_value = llm_output
    mock_validate_llm_output.return_value = llm_output
    mock_normalize_parsed_query.return_value = normalized_query
    mock_retrieve_candidates.return_value = []
    mock_fallback_retrieve.return_value = (
        [],
        fallback_info,
        normalized_query,
    )
    mock_format_response.return_value = expected_response

    result = lambda_handler(
        event={
            "httpMethod": "POST",
            "body": '{"query": "write a free blog post"}',
        },
        context=None,
    )

    assert result == expected_response

    # prompt 只使用 Top-50 candidate tags
    # prompt only use Top-50 candidate tags
    prompt_context = mock_build_parsing_prompt.call_args.args[1]
    assert prompt_context["use_cases"] == top_50_candidate_tags["use_cases"]
    assert prompt_context["functions"] == top_50_candidate_tags["functions"]

    # normalize 使用完整 taxonomy
    # normalize uses complete taxonomy
    mock_normalize_parsed_query.assert_called_once_with(
        llm_output,
        full_taxonomy_context,
    )

    mock_fallback_retrieve.assert_called_once_with(
        db_conn,
        normalized_query,
    )
    mock_close_db_connection.assert_called_once_with(db_conn)



# status code = 500
@patch.dict(
    "lambda_function.os.environ",
    {
        "endpoint": "test-endpoint",
        "dbname": "test-db",
        "username": "test-user",
        "pwd": "test-password",
        "portnum": "3306",
        "OPENAI_API_KEY": "test-key",
        "openai_model": "gpt-4.1-mini",
    },
    clear=True,
)
@patch("lambda_function.response.build_error_response")
@patch("lambda_function.response.log_request")
@patch("lambda_function.db.close_db_connection")
@patch("lambda_function.db.get_taxonomy_context")
@patch("lambda_function.db.get_db_connection")
@patch("lambda_function.OpenAI")
def test_lambda_handler_returns_500_and_closes_connection_on_internal_error(
    mock_openai,
    mock_get_db_connection,
    mock_get_taxonomy_context,
    mock_close_db_connection,
    mock_log_request,
    mock_build_error_response,
):
    db_conn = Mock()
    expected_response = {
        "statusCode": 500,
        "body": "internal server error",
    }

    mock_get_db_connection.return_value = db_conn
    mock_get_taxonomy_context.side_effect = RuntimeError("database failed")
    mock_build_error_response.return_value = expected_response

    result = lambda_handler(
        event={
            "httpMethod": "POST",
            "body": '{"query": "write a blog post"}',
        },
        context=None,
    )

    assert result == expected_response

    mock_build_error_response.assert_called_once_with(
        status_code=500,
        message="Internal server error",
        detail="database failed",
    )
    mock_close_db_connection.assert_called_once_with(db_conn)

@patch("lambda_function.response.build_error_response")
@patch("lambda_function.response.log_request")
def test_lambda_handler_returns_400_for_invalid_query(
    mock_log_request,
    mock_build_error_response,
):
    expected_response = {
        "statusCode": 400,
        "body": "invalid request",
    }
    mock_build_error_response.return_value = expected_response

    result = lambda_handler(
        event={
            "httpMethod": "POST",
            "body": '{"query": "   "}',
        },
        context=None,
    )

    assert result == expected_response

    mock_build_error_response.assert_called_once_with(
        status_code=400,
        message="Invalid request",
        detail="query cannot be empty",
    )




@patch.dict(
    "lambda_function.os.environ",
    {
        "endpoint": "test-endpoint",
        "dbname": "test-db",
        "username": "test-user",
        "pwd": "test-password",
        "portnum": "3306",
        "OPENAI_API_KEY": "test-key",
        "openai_model": "gpt-4.1-mini",
    },
    clear=True,
)
@patch("lambda_function.response.format_response")
@patch("lambda_function.response.log_request")
@patch("lambda_function.response.merge_ranked_results_with_details")
@patch("lambda_function.db.fetch_tool_details")
@patch("lambda_function.retriever.limit_top_results")
@patch("lambda_function.retriever.sort_candidates")
@patch("lambda_function.retriever.score_candidates")
@patch("lambda_function.retriever.fallback_retrieve")
@patch("lambda_function.retriever.retrieve_candidates")
@patch("lambda_function.parser.normalize_parsed_query")
@patch("lambda_function.parser.validate_llm_output")
@patch("lambda_function.parser.parse_query_with_llm")
@patch("lambda_function.parser.build_parsing_prompt")
@patch("lambda_function.tag_selector.select_candidate_tags")
@patch("lambda_function.db.get_taxonomy_context")
@patch("lambda_function.db.close_db_connection")
@patch("lambda_function.db.get_db_connection")
@patch("lambda_function.OpenAI")
def test_lambda_handler_skips_fallback_when_strict_retrieval_succeeds(
    mock_openai,
    mock_get_db_connection,
    mock_close_db_connection,
    mock_get_taxonomy_context,
    mock_select_candidate_tags,
    mock_build_parsing_prompt,
    mock_parse_query_with_llm,
    mock_validate_llm_output,
    mock_normalize_parsed_query,
    mock_retrieve_candidates,
    mock_fallback_retrieve,
    mock_score_candidates,
    mock_sort_candidates,
    mock_limit_top_results,
    mock_fetch_tool_details,
    mock_merge_ranked_results_with_details,
    mock_log_request,
    mock_format_response,
):
    db_conn = Mock()

    parsed_query = {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [],
        },
        "nice_to_have": {"use_cases": []},
        "functions": [],
    }

    strict_candidate = {"tool_id": 1, "name": "Blog Tool"}
    ranked_result = {
        "tool_id": 1,
        "name": "Blog Tool",
        "score": 6,
        "rank": 1,
    }
    expected_response = {"statusCode": 200, "body": "{}"}

    mock_get_db_connection.return_value = db_conn
    mock_get_taxonomy_context.return_value = {
        "categories": [],
        "price_types": [],
        "languages": [],
        "use_cases": [],
        "functions": [],
    }
    mock_select_candidate_tags.return_value = {
        "use_cases": [],
        "functions": [],
    }
    mock_build_parsing_prompt.return_value = "test prompt"
    mock_parse_query_with_llm.return_value = parsed_query
    mock_validate_llm_output.return_value = parsed_query
    mock_normalize_parsed_query.return_value = parsed_query
    mock_retrieve_candidates.return_value = [strict_candidate]
    mock_score_candidates.return_value = [ranked_result]
    mock_sort_candidates.return_value = [ranked_result]
    mock_limit_top_results.return_value = [ranked_result]
    mock_fetch_tool_details.return_value = [{"tool_id": 1}]
    mock_merge_ranked_results_with_details.return_value = [
        {"tool_id": 1, "name": "Blog Tool", "rank": 1}
    ]
    mock_format_response.return_value = expected_response

    result = lambda_handler(
        event={
            "httpMethod": "POST",
            "body": '{"query": "write a free blog post"}',
        },
        context=None,
    )

    assert result == expected_response
    mock_fallback_retrieve.assert_not_called()
    mock_score_candidates.assert_called_once_with(
        db_conn,
        [strict_candidate],
        parsed_query,
    )
    mock_close_db_connection.assert_called_once_with(db_conn)




def test_get_http_method_supports_http_api_v2_events():
    event = {
        "requestContext": {
            "http": {
                "method": "post",
            }
        }
    }

    result = get_http_method(event)

    assert result == "POST"



def test_extract_query_from_event_reads_json_string_body():
    event = {
        "body": '{"query": "  write a blog post "}',
    }

    result = extract_query_from_event(event)

    assert result == "  write a blog post "


def test_validate_request_strips_whitespace_from_valid_query():
    result = validate_request("  write a blog post  ")

    assert result == "write a blog post"




def test_validate_request_rejects_query_longer_than_limit():
    query = "a" * 1001

    with pytest.raises(
        ValueError,
        match="query is too long",
    ):
        validate_request(query)

@pytest.mark.parametrize("query", [None, 123])
def test_validate_request_rejects_missing_or_non_string_query(query):
    with pytest.raises(ValueError):
        validate_request(query)

def test_extract_query_from_event_rejects_body_without_query():
    event = {
        "body": '{"category": "ai writing"}',
    }

    with pytest.raises(
        ValueError,
        match="query is missing from request body",
    ):
        extract_query_from_event(event)