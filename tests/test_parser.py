import pytest
from unittest.mock import Mock

from parser import normalize_parsed_query, validate_llm_output, parse_query_with_llm


# 当前实现会保留 unknown tag，且没有跨域拒绝规则
# remain unknown tags and does not have cross-domain refusal.
# e.g. tags don't exist in primary/secondary tags in the database
# e.g. function tags are put in use case 

# This check verifies that case‑insensitive text, leading/trailing spaces,
# price aliases, duplicates, and valid tags are all normalized into a stable format.
def test_normalize_parsed_query_normalizes_and_deduplicates_known_values():
    parsed = {
        "category": " AI Writing ",
        "must_have": {
            "price_type": ["Free-Trial", "free trial"],
            "language": [" English ", "english"],
            "use_cases": [
                {
                    "primary_tag": "Content Creation",
                    "secondary_tag": "Blog Creation",
                }
            ],
        },
        "nice_to_have": {
            "use_cases": [],
        },
        "functions": [
            {
                "primary_tag": "Text Generation",
                "secondary_tag": "Blog Writing",
            }
        ],
    }

    taxonomy_context = {
        "categories": ["AI Writing"],
        "price_types": ["free", "free trial", "paid"],
        "languages": ["English"],
        "use_cases": [
            {
                "primary_tag": "Content Creation",
                "secondary_tag": "Blog Creation",
            }
        ],
        "functions": [
            {
                "primary_tag": "Text Generation",
                "secondary_tag": "Blog Writing",
            }
        ],
    }

    result = normalize_parsed_query(
        parsed,
        taxonomy_context=taxonomy_context,
    )

    assert result == {
        "category": "ai writing",
        "must_have": {
            "price_type": ["free trial"],
            "language": ["english"],
            "use_cases": [
                {
                    "primary_tag": "content creation",
                    "secondary_tag": "blog creation",
                }
            ],
        },
        "nice_to_have": {
            "use_cases": [],
        },
        "functions": [
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            }
        ],
    }


# test whether the funtions adds the primary tags from unique secondary
def test_normalize_parsed_query_completes_primary_from_unique_secondary():
    parsed = {
        "category": "AI Writing",
        "must_have": {
            "price_type": [],
            "language": [],
            "use_cases": [
                {
                    "primary_tag": "",
                    "secondary_tag": "Blog Creation",
                }
            ],
        },
        "nice_to_have": {
            "use_cases": [],
        },
        "functions": [],
    }

    taxonomy_context = {
        "categories": ["AI Writing"],
        "price_types": [],
        "languages": [],
        "use_cases": [
            {
                "primary_tag": "Content Creation",
                "secondary_tag": "Blog Creation",
            }
        ],
        "functions": [],
    }

    result = normalize_parsed_query(
        parsed,
        taxonomy_context=taxonomy_context,
    )

    assert result["must_have"]["use_cases"] == [
        {
            "primary_tag": "content creation",
            "secondary_tag": "blog creation",
        }
    ]


# test whether lack of required JSON field raises a valueError
def test_validate_llm_output_raises_when_functions_field_is_missing():
    parsed = {
        "category": "AI Writing",
        "must_have": {
            "price_type": ["free"],
            "language": ["english"],
            "use_cases": [],
        },
        "nice_to_have": {
            "use_cases": [],
        },
        # leave "functions" blank intentionally
    }

    with pytest.raises(
        ValueError,
        match="Missing 'functions' in LLM output",
    ):
        validate_llm_output(parsed)



def test_parse_query_with_llm_strips_code_fences_and_returns_json():
    client = Mock()

    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = """
        ```json
        {"category": "AI Writing"}
        """
    client.chat.completions.create.return_value = response

    result = parse_query_with_llm(
    prompt="parse this query",
    client=client,
    model="gpt-4.1-mini",
)

    assert result == {"category": "AI Writing"}

    client.chat.completions.create.assert_called_once_with(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a precise JSON generator.",
            },
            {
                "role": "user",
                "content": "parse this query",
            },
        ],
        temperature=0,
    )



@pytest.mark.parametrize(
    ("client", "model", "expected_message"),
    [
        (None, "gpt-4.1-mini", "LLM client is required"),
        (Mock(), None, "Model name is required"),
    ],
    )
def test_parse_query_with_llm_requires_client_and_model(
    client,
    model,
    expected_message,
    ):
    with pytest.raises(ValueError, match=expected_message):
        parse_query_with_llm(
            prompt="parse this query",
            client=client,
            model=model,
        )


def test_validate_llm_output_raises_when_price_type_is_not_a_list():
    parsed = {
        "category": "AI Writing",
        "must_have": {
        "price_type": "free",
        "language": [],
        "use_cases": [],
        },
        "nice_to_have": {
        "use_cases": [],
        },
        "functions": [],
        }
    with pytest.raises(
        ValueError,
        match="'must_have.price_type' must be a list",
        ):
        validate_llm_output(parsed)



def test_validate_llm_output_raises_when_tag_has_no_primary_tag():
    parsed = {
        "category": "AI Writing",
        "must_have": {
        "price_type": [],
        "language": [],
        "use_cases": [
            {
                "secondary_tag": "Blog Creation",
            }
        ],
        },
        "nice_to_have": {
        "use_cases": [],
        },
        "functions": [],
        }

    with pytest.raises(
        ValueError,
        match="Each item in 'must_have.use_cases' must contain 'primary_tag'",
        ):
        validate_llm_output(parsed)

def test_normalize_parsed_query_deduplicates_use_case_and_function_tags():
    parsed = {
        "category": "AI Writing",
        "must_have": {
        "price_type": [],
        "language": [],
        "use_cases": [
            {
                "primary_tag": "Content Creation",
                "secondary_tag": "Blog Creation",
            },
            {
                "primary_tag": " content creation ",
                "secondary_tag": " blog creation ",
            },
        ],
        },
        "nice_to_have": {
        "use_cases": [],
        },
        "functions": [
            {
                "primary_tag": "Text Generation",
                "secondary_tag": "Blog Writing",
            },
            {
                "primary_tag": "text generation",
                "secondary_tag": "blog writing",
            },
            ],
        }

    taxonomy_context = {
        "categories": ["AI Writing"],
        "price_types": [],
        "languages": [],
        "use_cases": [
            {
                "primary_tag": "Content Creation",
                "secondary_tag": "Blog Creation",
            }
        ],
        "functions": [
            {
                "primary_tag": "Text Generation",
                "secondary_tag": "Blog Writing",
            }
        ],
        }

    result = normalize_parsed_query(parsed, taxonomy_context)

    assert result["must_have"]["use_cases"] == [
        {
            "primary_tag": "content creation",
            "secondary_tag": "blog creation",
        }
    ]

    assert result["functions"] == [
        {
            "primary_tag": "text generation",
            "secondary_tag": "blog writing",
        }
    ]


def test_normalize_parsed_query_resolves_unique_secondary_string_tag():
    parsed = {
        "category": "AI Writing",
        "must_have": {
            "price_type": [],
            "language": [],
            "use_cases": ["Blog Creation"],
            },
        "nice_to_have": {
            "use_cases": [],
            },
        "functions": [],
        }

    taxonomy_context = {
        "categories": ["AI Writing"],
        "price_types": [],
        "languages": [],
        "use_cases": [
            {
                "primary_tag": "Content Creation",
                "secondary_tag": "Blog Creation",
            }
        ],
        "functions": [],
    }

    result = normalize_parsed_query(parsed, taxonomy_context)

    assert result["must_have"]["use_cases"] == [
        {
            "primary_tag": "content creation",
            "secondary_tag": "blog creation",
        }
    ]



