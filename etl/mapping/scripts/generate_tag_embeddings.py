from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import os
from openai import OpenAI


MODEL_NAME = "text-embedding-3-small"
# embeding vector dimension for text-embedding-3-small is 1536
EXPECTED_DIM = 1536
# Batch size for embedding generation.
BATCH_SIZE = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate embeddings for primary-secondary tag pairs."
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the input JSON file.",
    )

    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for output metadata JSON and embeddings NPY.",
    )

    parser.add_argument(
        "--model",
        default=MODEL_NAME,
        help=f"SentenceTransformer model. Default: {MODEL_NAME}",
    )

    return parser.parse_args()


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_tag_pairs(records: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Convert:

    {
        "primary_tag": "3D Animation Production",
        "source_secondary_tags": [
            "Automatic Rigging",
            "Character Rigging"
        ]
    }

    into individual primary-secondary pairs.
    """

    metadata = []
    texts = []

    for record in records:
        primary_tag = record.get("primary_tag")
        secondary_tags = record.get("source_secondary_tags", [])

        if not isinstance(primary_tag, str) or not primary_tag.strip():
            continue

        if not isinstance(secondary_tags, list):
            continue

        primary_tag = primary_tag.strip()

        for secondary_tag in secondary_tags:
            if not isinstance(secondary_tag, str) or not secondary_tag.strip():
                continue

            secondary_tag = secondary_tag.strip()

            metadata.append(
                {
                    "primary_tag": primary_tag,
                    "secondary_tag": secondary_tag,
                }
            )

            texts.append(
                f"{primary_tag}; {secondary_tag}"
            )

    return metadata, texts




def generate_embeddings(
    texts: list[str],
    model_name: str,
) -> tuple[np.ndarray, list[dict]]:

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    all_embeddings = []
    errors = []

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]

        try:
            response = client.embeddings.create(
                model=model_name,
                input=batch,
            )

        except Exception as error:
            errors.append({
                "batch_start": start,
                "error_type": "api_error",
                "message": str(error),
            })

            # Keep indexes aligned
            for _ in batch:
                all_embeddings.append(
                    np.full(EXPECTED_DIM, np.nan, dtype=np.float32)
                )

            continue

        # Validate number of returned embeddings
        if len(response.data) != len(batch):
            errors.append({
                "batch_start": start,
                "error_type": "count_mismatch",
                "expected": len(batch),
                "actual": len(response.data),
            })

        # Map API results by index
        returned = {
            item.index: item.embedding
            for item in response.data
        }

        for local_index in range(len(batch)):

            embedding = returned.get(local_index)

            # Missing embedding
            if embedding is None:
                errors.append({
                    "global_index": start + local_index,
                    "error_type": "missing_embedding",
                })

                all_embeddings.append(
                    np.full(EXPECTED_DIM, np.nan, dtype=np.float32)
                )

                continue

            # Wrong dimension
            if len(embedding) != EXPECTED_DIM:
                errors.append({
                    "global_index": start + local_index,
                    "error_type": "dimension_mismatch",
                    "expected": EXPECTED_DIM,
                    "actual": len(embedding),
                })

                all_embeddings.append(
                    np.full(EXPECTED_DIM, np.nan, dtype=np.float32)
                )

                continue

            # Valid
            all_embeddings.append(
                np.asarray(embedding, dtype=np.float32)
            )

        print(
            f"Processed {min(start + BATCH_SIZE, len(texts))}"
            f"/{len(texts)}"
        )

    embeddings = np.stack(all_embeddings)

    return embeddings, errors


def save_outputs(
    metadata: list[dict],
    embeddings: np.ndarray,
    input_path: Path,
    output_dir: Path,
) -> None:

    output_dir.mkdir(parents=True, exist_ok=True)

    # Example:
    # deduplicated_functions_primary_tags.json
    # ->
    # functions_tags.json
    # functions_embeddings.npy

    input_name = input_path.stem.lower()

    if "functions" in input_name:
        prefix = "function"
    elif "use_cases" in input_name:
        prefix = "use_case"
    else:
        raise ValueError(
        "Cannot determine tag type from input filename. "
        "Expected 'functions' or 'use_cases' in the filename."
        )

    metadata_path = output_dir / f"{prefix}_tags.json"
    embeddings_path = output_dir / f"{prefix}_embeddings.npy"

    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
        )

    np.save(embeddings_path, embeddings)

    print("\nEmbedding generation completed.")
    print(f"Tag pairs: {len(metadata)}")
    print(f"Embedding shape: {embeddings.shape}")
    print(f"Metadata: {metadata_path}")
    print(f"Embeddings: {embeddings_path}")


def main() -> None:
    args = parse_args()

    records = load_json(args.input)

    metadata, texts = build_tag_pairs(records)

    if not metadata:
        raise ValueError(
            "No valid primary-secondary tag pairs were found."
        )

    print(f"Input: {args.input}")
    print(f"Model: {args.model}")
    print(f"Tag pairs: {len(metadata)}")

    embeddings, errors = generate_embeddings(
        texts=texts,
        model_name=args.model,
    )

    save_outputs(
        metadata=metadata,
        embeddings=embeddings,
        input_path=args.input,
        output_dir=args.output_dir,
    )

    if errors:
        error_path = args.output_dir / "embedding_errors.json"

        with error_path.open("w", encoding="utf-8") as file:
            json.dump(errors, file, ensure_ascii=False, indent=2)

        print(f"Embedding errors: {len(errors)}")
        print(f"Error log: {error_path}")

if __name__ == "__main__":
    main()