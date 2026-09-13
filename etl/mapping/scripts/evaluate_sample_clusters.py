import argparse
import csv
import json
from pathlib import Path

from openai import OpenAI


MODEL = "gpt-5.6"


def evaluate_cluster(client: OpenAI, sample_tags: str) -> dict:
    """
    Evaluate whether tags in one cluster represent the same AI-tool capability.

    Returns:
        {
            "rating": "Good" | "Mixed" | "Bad",
            "failure_reason": ""
        }
    """

    prompt = f"""
You are evaluating the semantic coherence of a cluster of AI-tool function tags.

Each tag describes a FUNCTION or CAPABILITY of an AI tool.

Evaluation standard:

- Good: >= 80% of the tags belong to the same capability.
- Mixed: 50%-79% of the tags belong to the same capability.
- Bad: < 50% of the tags can be grouped into one capability.

Important evaluation rules:

1. Judge by FUNCTION/CAPABILITY, not merely by shared words, objects, or domains.
2. Determine the largest defensible single capability represented in the cluster.
3. Count how many tags genuinely belong to that capability.
4. Do not define the capability too broadly just to make the cluster coherent.
5. Different inputs, outputs, or subtypes may still belong to the same capability
   if the underlying operation is the same.
6. If the rating is Good, failure_reason must be an empty string.
7. If the rating is Mixed or Bad, failure_reason must contain exactly one concise
   English sentence explaining why the cluster is not functionally coherent enough.

Calibration Rubric:

1. Same domain does not necessarily mean the same capability.

2. Identical action verbs (e.g., generation, tracking, research, customization)
   do not constitute the same capability when they operate on substantially
   different objects or serve different functional scenarios.

3. Determine the largest defensible single core capability in the cluster,
   then calculate the proportion of tasks that genuinely belong to it.
   Do not broaden the capability definition solely to increase cluster coherence.

4. Audio and sound processing operations may be treated as one broad core
   capability when they involve manipulation, enhancement, separation,
   transformation, or cleanup of audio content.

5. Authentication-related operations may be treated as one core capability
   when they primarily serve user or system authentication.

6. Image and visual content generation or processing operations may be treated
   as one broad core capability.

7. Data extraction, parsing, cleaning, enrichment, and closely related data
   processing operations may be treated as one broad core capability.

8. Logo generation, design, editing, and related logo-processing operations
   may be treated as one core capability.

9. Database creation, setup, connection, querying, lookup, generation, and
   management operations may be treated as one broad core capability.
   
Examples:
Example 1:
Tags: [Internal Linking | Backlink Analysis | External Linking | File Linking | Internal Link Automation | Internal Link Building | Internal Link Generation | Internal Link Optimization | Internal Linking Optimization | URL Slug Standardization | Website Linking]
Rating: Good
Reason: Over 80% of the tags belong to one capability: SEO Link Structure.

Example 2:
Tags: [Authentication Setup | Password Protection | Authentication | Authentication Management | Cookie Preference Management | Credential Management | End-to-End Encryption | Identity Preservation | Secure Data Handling | User Authentication | VPN User Identification]
Rating: Good
Reason: Over 80% of them are related to authentication.

Example 3:
Tags: [Voice Cloning | Accent Conversion | Audio Format Conversion | Brand Voice Capture | Real-Time Voice Streaming | Share of Voice Measurement | Share Of Voice Tracking | Vocal Extraction | Voice Clone Detection | Voice Conversion | Voice Dubbing | Voice-to-Voice Conversion]
Rating: Good
Reason: Over 80% of them are related to audio or sound processing.


Example 4:
Tags: [Image Generation | AI Image Generation | Text-to-Image Generation | Image-to-Image Generation | Thumbnail Generation | Visual Generation | Mind Map Generation | AI Photo Generation | Bulk Image Generation | Figure Generation | Graphic Generation | Multimodal Content Generation | Multimodal Creation | Multimodal Generation | MultiShot Scene Generation | Photorealistic Image Generation | Pose-to-Image Generation | Product Image Generation | Reference-Based Image Generation | Sketch-to-Image Generation | Text-Based Image Creation | Texture Generation | Thumbnail Creation | Thumbnail Variation Generation | Visual Effects Generation]
Rating: Good
Reason: Over 80% of them are related to images.

Cluster:

{sample_tags}

Return ONLY valid JSON in exactly this structure:

{{
  "rating": "Good",
  "failure_reason": ""
}}
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    result = response.output_text.strip()

    # Remove accidental markdown fences if present.
    if result.startswith("```"):
        result = result.replace("```json", "").replace("```", "").strip()

    parsed = json.loads(result)

    rating = parsed["rating"].strip()
    failure_reason = parsed.get("failure_reason", "").strip()

    if rating not in {"Good", "Mixed", "Bad"}:
        raise ValueError(f"Invalid rating returned: {rating}")

    if rating == "Good":
        failure_reason = ""

    return {
        "rating": rating,
        "failure_reason": failure_reason
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate sampled tag clusters with an LLM."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Evaluation CSV containing sampled clusters.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for the evaluated CSV.",
    )
    args = parser.parse_args()

    output_path = args.output_dir / args.input.name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    # Read everything first because input and output may be the same file.
    with args.input.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if fieldnames is None:
        raise ValueError("CSV has no header.")

    required_columns = {
        "cluster_id",
        "sample_tags",
        "rating",
        "failure_reason"
    }

    missing = required_columns - set(fieldnames)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    total = len(rows)

    for i, row in enumerate(rows, start=1):
        cluster_id = row["cluster_id"]
        sample_tags = row["sample_tags"].strip()
        existing_rating = row["rating"].strip()

        if existing_rating in {"Good", "Mixed", "Bad"}:
            print(
                f"[{i}/{total}] Cluster {cluster_id}: "
                f"skipped (already {existing_rating})"
            )
            continue

        if not sample_tags:
            print(f"[{i}/{total}] Cluster {cluster_id}: skipped (no tags)")
            continue

        print(f"[{i}/{total}] Evaluating cluster {cluster_id}...")

        try:
            result = evaluate_cluster(client, sample_tags)

            row["rating"] = result["rating"]
            row["failure_reason"] = result["failure_reason"]

            print(
                f"    -> {result['rating']}"
                + (
                    f" | {result['failure_reason']}"
                    if result["failure_reason"]
                    else ""
                )
            )

        except Exception as e:
            print(f"    ERROR: {e}")

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Results saved to: {output_path}")

    # Statistics
    rating_counts = {
        "Good": 0,
        "Mixed": 0,
        "Bad": 0
    }

    for row in rows:
        rating = row["rating"].strip()
        if rating in rating_counts:
            rating_counts[rating] += 1

    evaluated_count = sum(rating_counts.values())

    print("\nEvaluation Summary")
    print("------------------")

    for rating in ["Good", "Mixed", "Bad"]:
        count = rating_counts[rating]
        percentage = (
            count / evaluated_count * 100
            if evaluated_count > 0
            else 0
        )

        print(f"{rating}: {count} ({percentage:.2f}%)")

    print(f"Total evaluated: {evaluated_count}")

if __name__ == "__main__":
    main()
