import json
from pathlib import Path

import numpy as np

from ai_retry import run_ai_operation


EMBEDDING_MODEL = "text-embedding-3-small"
# Per-request network timeout in seconds; retries use the shared operation budget.
EMBEDDING_REQUEST_TIMEOUT_SECONDS = 15.0
EXPECTED_DIMENSIONS = 1536
DEFAULT_TOP_K = 50
EMBEDDING_DIR = Path(__file__).resolve().parent / "embedding"

_TAG_VECTOR_CACHE = None


###############################################################
# select_candidate_tags
#
# Embeds a query once, then selects the closest canonical tag
# pairs from the precomputed use case and function vector files.
#
def select_candidate_tags(query, client, top_k=DEFAULT_TOP_K):
  try:
    if not isinstance(query, str) or not query.strip():
      raise ValueError("Query is required for tag selection")

    if client is None:
      raise ValueError("OpenAI client is required for tag selection")

    query_vector = _get_query_embedding(query, client)
    resources = _load_tag_vectors()

    return {
      "use_cases": _select_top_tags(
        query_vector,
        resources["use_case_tags"],
        resources["use_case_vectors"],
        top_k
      ),
      "functions": _select_top_tags(
        query_vector,
        resources["function_tags"],
        resources["function_vectors"],
        top_k
      )
    }

  except Exception as err:
    print("tag_selector.select_candidate_tags() failed:")
    print(str(err))
    raise


###############################################################
# _get_query_embedding
#
def _get_query_embedding(query, client):
  response = run_ai_operation("embedding", lambda: client.embeddings.create(
    model=EMBEDDING_MODEL,
    input=query,
    timeout=EMBEDDING_REQUEST_TIMEOUT_SECONDS
  ))

  if not response.data:
    raise ValueError("Embedding API returned no query vector")

  query_vector = np.asarray(response.data[0].embedding, dtype=np.float32)

  if query_vector.shape != (EXPECTED_DIMENSIONS,):
    raise ValueError(
      "Query embedding dimension does not match precomputed tag vectors"
    )

  if not np.isfinite(query_vector).all():
    raise ValueError("Query embedding contains invalid values")

  norm = np.linalg.norm(query_vector)
  if norm == 0:
    raise ValueError("Query embedding has zero magnitude")

  return query_vector / norm


###############################################################
# _load_tag_vectors
#
# Cache immutable deployment assets across warm Lambda invocations.
#
def _load_tag_vectors():
  global _TAG_VECTOR_CACHE

  if _TAG_VECTOR_CACHE is not None:
    return _TAG_VECTOR_CACHE

  use_case_tags = _load_tags(EMBEDDING_DIR / "use_case_tags.json")
  function_tags = _load_tags(EMBEDDING_DIR / "function_tags.json")
  use_case_vectors = np.load(EMBEDDING_DIR / "use_case_embeddings.npy")
  function_vectors = np.load(EMBEDDING_DIR / "function_embeddings.npy")

  _validate_tag_vectors(use_case_tags, use_case_vectors, "use case")
  _validate_tag_vectors(function_tags, function_vectors, "function")

  _TAG_VECTOR_CACHE = {
    "use_case_tags": use_case_tags,
    "use_case_vectors": use_case_vectors.astype(np.float32, copy=False),
    "function_tags": function_tags,
    "function_vectors": function_vectors.astype(np.float32, copy=False)
  }

  return _TAG_VECTOR_CACHE


def _load_tags(path):
  with path.open("r", encoding="utf-8") as file:
    tags = json.load(file)

  if not isinstance(tags, list):
    raise ValueError(f"Tag metadata must be a list: {path.name}")

  return tags


def _validate_tag_vectors(tags, vectors, tag_type):
  if vectors.ndim != 2:
    raise ValueError(f"{tag_type} embeddings must be a two-dimensional matrix")

  if vectors.shape[0] != len(tags):
    raise ValueError(f"{tag_type} tag metadata and embedding counts do not match")

  if vectors.shape[1] != EXPECTED_DIMENSIONS:
    raise ValueError(f"{tag_type} embeddings have an unexpected dimension")


###############################################################
# _select_top_tags
#
# The offline vectors are not assumed to be normalized, so both
# sides are normalized during the cosine similarity calculation.
#
def _select_top_tags(query_vector, tags, vectors, top_k):
  vector_norms = np.linalg.norm(vectors, axis=1)
  valid_rows = np.isfinite(vectors).all(axis=1) & (vector_norms > 0)

  valid_indexes = np.flatnonzero(valid_rows)
  if len(valid_indexes) == 0:
    raise ValueError("No valid tag embeddings are available")

  valid_vectors = vectors[valid_rows]
  similarities = (valid_vectors @ query_vector) / vector_norms[valid_rows]
  result_count = min(max(int(top_k), 0), len(valid_indexes))

  if result_count == 0:
    return []

  top_positions = np.argsort(-similarities)[:result_count]
  selected_tags = []
  seen = set()

  for position in top_positions:
    metadata = tags[valid_indexes[position]]
    primary_tag = metadata.get("primary_tag")
    secondary_tag = metadata.get("secondary_tag")

    if not isinstance(primary_tag, str) or not primary_tag.strip():
      continue

    primary_tag = primary_tag.strip()
    secondary_tag = (
      secondary_tag.strip()
      if isinstance(secondary_tag, str) and secondary_tag.strip()
      else None
    )
    tag_key = (
      primary_tag.lower(),
      secondary_tag.lower() if secondary_tag else None
    )

    if tag_key not in seen:
      seen.add(tag_key)
      selected_tags.append({
        "primary_tag": primary_tag,
        "secondary_tag": secondary_tag
      })

  return selected_tags
