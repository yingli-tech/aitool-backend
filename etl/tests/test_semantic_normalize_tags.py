from __future__ import annotations

import unittest

from mapping.semantic_normalize_tags import (
    TagMapping,
    TagMappingResult,
    split_into_batches,
    validate_llm_result,
)


class SemanticNormalizeTagsTests(unittest.TestCase):
    def test_split_into_batches_preserves_global_ids(self) -> None:
        records = [
            {"id": index, "tag": f"Tag {index}", "count": 1}
            for index in range(1, 602)
        ]

        batches = split_into_batches(records, batch_size=300)

        self.assertEqual([len(batch) for batch in batches], [300, 300, 1])
        self.assertEqual(batches[0][0]["id"], 1)
        self.assertEqual(batches[1][0]["id"], 301)
        self.assertEqual(batches[2][0]["id"], 601)

    def test_validate_llm_result_rejects_incomplete_batch(self) -> None:
        records = [
            {"id": 301, "tag": "Video Creation", "count": 4},
            {"id": 302, "tag": "Video Generation", "count": 8},
        ]
        result = TagMappingResult(
            mappings=[TagMapping(id=301, secondary_tag="Video Generation")]
        )

        with self.assertRaisesRegex(
            ValueError,
            r"Batch 2/3 failed validation\. Expected 2 mappings, received 1\. "
            r"missing IDs: \[302\]",
        ):
            validate_llm_result(result, records, "Batch 2/3")

    def test_validate_llm_result_rejects_duplicate_and_unexpected_ids(self) -> None:
        records = [
            {"id": 1, "tag": "Image Creation", "count": 1},
            {"id": 2, "tag": "Image Editing", "count": 1},
        ]
        result = TagMappingResult(
            mappings=[
                TagMapping(id=1, secondary_tag="Image Generation"),
                TagMapping(id=1, secondary_tag="Image Generation"),
                TagMapping(id=3, secondary_tag="Image Editing"),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            r"missing IDs: \[2\].*unexpected IDs: \[3\].*duplicate IDs: \[1\]",
        ):
            validate_llm_result(result, records, "Complete dataset")


if __name__ == "__main__":
    unittest.main()
