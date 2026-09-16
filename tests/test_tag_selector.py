import numpy as np
import pytest

from unittest.mock import Mock, patch

from tag_selector import _select_top_tags
from tag_selector import _get_query_embedding
from tag_selector import _validate_tag_vectors
from tag_selector import select_candidate_tags


###################################################
# top K 
###################################################


# test whether returns the top K tags based on cosine similarity
def test_select_top_tags_returns_descending_cosine_similarity():
    query_vector = np.array([1.0, 0.0], dtype=np.float32)

    tags = [
        {
            "primary_tag": "Text Generation",
            "secondary_tag": "Blog Writing",
        },
        {
            "primary_tag": "Image Generation",
            "secondary_tag": "Image Creation",
        },
        {
            "primary_tag": "Code Generation",
            "secondary_tag": "Code Completion",
        },
    ]

    vectors = np.array(
        [
            [1.0, 0.0],   # cosine = 1.0
            [0.0, 1.0],   # cosine = 0.0
            [0.8, 0.6],   # cosine = 0.8
        ],
        dtype=np.float32,
    )

    result = _select_top_tags(
        query_vector=query_vector,
        tags=tags,
        vectors=vectors,
        top_k=2,
    )

    assert result == [
        {
            "primary_tag": "Text Generation",
            "secondary_tag": "Blog Writing",
        },
        {
            "primary_tag": "Code Generation",
            "secondary_tag": "Code Completion",
        },
    ]


# test whether returns all tags when top_k exceeds the number of candidates
def test_select_top_tags_returns_all_when_top_k_exceeds_candidates():
    query_vector = np.array([1.0, 0.0], dtype=np.float32)

    tags = [
        {
            "primary_tag": "Text Generation",
            "secondary_tag": "Blog Writing",
        },
        {
            "primary_tag": "Image Generation",
            "secondary_tag": "Image Creation",
        },
    ]

    vectors = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )

    result = _select_top_tags(
        query_vector=query_vector,
        tags=tags,
        vectors=vectors,
        top_k=50,
    )

    assert len(result) == 2
    assert result[0]["primary_tag"] == "Text Generation"
    assert result[1]["primary_tag"] == "Image Generation"


# test whether candidate tags with NaN or zero vector will be filtered
def test_select_top_tags_skips_invalid_candidate_vectors():
    query_vector = np.array([1.0, 0.0], dtype=np.float32)

    tags = [
        {
            "primary_tag": "Invalid NaN Tag",
            "secondary_tag": "Bad Vector",
        },
        {
            "primary_tag": "Invalid Zero Tag",
            "secondary_tag": "Bad Vector",
        },
        {
            "primary_tag": "Valid Tag",
            "secondary_tag": "Good Vector",
        },
    ]

    vectors = np.array(
        [
            [np.nan, 0.0],
            [0.0, 0.0],
            [1.0, 0.0],
        ],
        dtype=np.float32,
    )

    result = _select_top_tags(
        query_vector=query_vector,
        tags=tags,
        vectors=vectors,
        top_k=3,
    )

    assert result == [
        {
            "primary_tag": "Valid Tag",
            "secondary_tag": "Good Vector",
        }
    ]

# test whether the error will be raised when no valid vectors exist.
def test_select_top_tags_raises_when_no_valid_vectors_exist():
    query_vector = np.array([1.0, 0.0], dtype=np.float32)

    tags = [
        {
            "primary_tag": "Invalid Tag",
            "secondary_tag": "Bad Vector",
        },
        {
            "primary_tag": "Another Invalid Tag",
            "secondary_tag": "Bad Vector",
        },
    ]

    vectors = np.array(
        [
            [np.nan, 0.0],
            [0.0, 0.0],
        ],
        dtype=np.float32,
    )

    with pytest.raises(
        ValueError,
        match="No valid tag embeddings are available",
    ):
        _select_top_tags(
            query_vector=query_vector,
            tags=tags,
            vectors=vectors,
            top_k=2,
        )



def test_select_top_tags_normalizes_and_deduplicates_metadata():
    query_vector = np.array([1.0, 0.0], dtype=np.float32)

    tags = [
        {
            "primary_tag": " Text Generation ",
            "secondary_tag": " Blog Writing ",
        },
        {
            "primary_tag": "text generation",
            "secondary_tag": "blog writing",
        },
        {
            "primary_tag": "Image Generation",
            "secondary_tag": "   ",
        },
    ]

    vectors = np.array(
        [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.8, 0.2],
        ],
        dtype=np.float32,
    )

    result = _select_top_tags(
        query_vector=query_vector,
        tags=tags,
        vectors=vectors,
        top_k=3,
    )

    assert result == [
        {
            "primary_tag": "Text Generation",
            "secondary_tag": "Blog Writing",
        },
        {
            "primary_tag": "Image Generation",
            "secondary_tag": None,
        },
    ]


# test if function calls a correct model and normalizes the vector when dimensions match
def test_get_query_embedding_calls_openai_and_normalizes_vector():
    client = Mock()

    raw_vector = np.zeros(1536, dtype=np.float32)
    raw_vector[0] = 3.0
    raw_vector[1] = 4.0

    client.embeddings.create.return_value.data = [
        Mock(embedding=raw_vector.tolist())
    ]

    result = _get_query_embedding(
        query="write a blog post",
        client=client,
    )

    client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input="write a blog post",
        timeout=15.0,
    )

    np.testing.assert_allclose(
        result[:2],
        np.array([0.6, 0.8], dtype=np.float32),
    )
    assert np.isclose(np.linalg.norm(result), 1.0)

# refused the value when the dimension of returning vector is not 1536
def test_get_query_embedding_raises_for_unexpected_dimension():
    client = Mock()
    client.embeddings.create.return_value.data = [
        Mock(embedding=[0.0] * 1535)
    ]

    with pytest.raises(
        ValueError,
        match="Query embedding dimension does not match precomputed tag vectors",
    ):
        _get_query_embedding(
            query="write a blog post",
            client=client,
        )


# test whether raises an error when query vector contains NaN
def test_get_query_embedding_raises_for_invalid_values():
    client = Mock()

    vector = np.zeros(1536, dtype=np.float32)
    vector[0] = np.nan

    client.embeddings.create.return_value.data = [
        Mock(embedding=vector.tolist())
    ]

    with pytest.raises(
        ValueError,
        match="Query embedding contains invalid values",
    ):
        _get_query_embedding(
            query="write a blog post",
            client=client,
        )


# test whether raises an error when query vector is zero vector
def test_get_query_embedding_raises_for_zero_vector():
    client = Mock()
    client.embeddings.create.return_value.data = [
        Mock(embedding=[0.0] * 1536)
    ]

    with pytest.raises(
        ValueError,
        match="Query embedding has zero magnitude",
    ):
        _get_query_embedding(
            query="write a blog post",
            client=client,
        )


# two metadata with one vector raises an error
def test_validate_tag_vectors_raises_when_metadata_count_differs_from_vectors():
    tags = [
        {
            "primary_tag": "Text Generation",
            "secondary_tag": "Blog Writing",
        },
        {
            "primary_tag": "Image Generation",
            "secondary_tag": "Image Creation",
        },
    ]

    vectors = np.zeros((1, 1536), dtype=np.float32)

    with pytest.raises(
        ValueError,
        match="use case tag metadata and embedding counts do not match",
    ):
        _validate_tag_vectors(
            tags=tags,
            vectors=vectors,
            tag_type="use case",
        )


# the dimension of one of vectors is not 1536
def test_validate_tag_vectors_raises_for_unexpected_dimension():
    tags = [
        {
            "primary_tag": "Text Generation",
            "secondary_tag": "Blog Writing",
        }
    ]

    vectors = np.zeros((1, 1535), dtype=np.float32)

    with pytest.raises(
        ValueError,
        match="function embeddings have an unexpected dimension",
    ):
        _validate_tag_vectors(
            tags=tags,
            vectors=vectors,
            tag_type="function",
        )


# not two-dimensional matrix raises an error
def test_validate_tag_vectors_raises_for_non_matrix_vectors():
    tags = [
        {
            "primary_tag": "Text Generation",
            "secondary_tag": "Blog Writing",
        }
    ]

    vectors = np.zeros(1536, dtype=np.float32)

    with pytest.raises(
        ValueError,
        match="use case embeddings must be a two-dimensional matrix",
    ):
        _validate_tag_vectors(
            tags=tags,
            vectors=vectors,
            tag_type="use case",
        )


###################################################
# select_candidate_tags()
###################################################


# test whether the main function sends the same query vector
# to both the use‑case candidate set and the function candidate set.
@patch("tag_selector._select_top_tags")
@patch("tag_selector._load_tag_vectors")
@patch("tag_selector._get_query_embedding")
def test_select_candidate_tags_selects_use_cases_and_functions(
    mock_get_query_embedding,
    mock_load_tag_vectors,
    mock_select_top_tags,
):
    client = Mock()
    query_vector = np.ones(1536, dtype=np.float32)

    mock_get_query_embedding.return_value = query_vector
    mock_load_tag_vectors.return_value = {
        "use_case_tags": ["use-case metadata"],
        "use_case_vectors": np.ones((1, 1536), dtype=np.float32),
        "function_tags": ["function metadata"],
        "function_vectors": np.ones((1, 1536), dtype=np.float32),
    }

    mock_select_top_tags.side_effect = [
        [{"primary_tag": "Content Creation", "secondary_tag": "Blog Creation"}],
        [{"primary_tag": "Text Generation", "secondary_tag": "Blog Writing"}],
    ]

    result = select_candidate_tags(
        query="write a blog post",
        client=client,
        top_k=50,
    )

    assert result == {
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

    assert mock_select_top_tags.call_count == 2
    assert mock_select_top_tags.call_args_list[0].args[3] == 50
    assert mock_select_top_tags.call_args_list[1].args[3] == 50



# empty query or only containing blank space or non-string query will be rejected before calling LLM
@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        None,
        int(1011),
        1105,
    ],
)
def test_select_candidate_tags_rejects_invalid_query(query):
    with pytest.raises(
        ValueError,
        match="Query is required for tag selection",
    ):
        select_candidate_tags(
            query=query,
            client=Mock(),
        ) 

# test whether an empty client triggers an error;
# the error occurs before _get_query_embedding() and before loading any files
# so it won’t accidentally call the API or read embedding files.
def test_select_candidate_tags_rejects_missing_client():
    with pytest.raises(
        ValueError,
        match="OpenAI client is required for tag selection",
    ):
        select_candidate_tags(
            query="write a blog post",
            client=None,
        )


def test_get_query_embedding_raises_when_api_returns_no_data():
    client = Mock()
    client.embeddings.create.return_value.data = []

    with pytest.raises(
        ValueError,
        match="Embedding API returned no query vector",
    ):
        _get_query_embedding(
            query="write a blog post",
            client=client,
        )
