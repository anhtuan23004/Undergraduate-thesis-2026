"""Tests for human review graph node state updates."""

from graphs.human_review import HumanReviewNode


async def test_edit_from_completeness_review_keeps_completeness_active():
    node = HumanReviewNode()

    result = await node.run(
        {
            "review_stage": "completeness",
            "human_review_result": {"decision": "edit", "stage": "completeness"},
        }
    )

    assert result["active_stage"] == "completeness"
    assert result["review_stage"] == "none"


async def test_edit_from_quality_review_keeps_quality_active():
    node = HumanReviewNode()

    result = await node.run(
        {
            "review_stage": "quality",
            "human_review_result": {"decision": "edit", "stage": "quality"},
        }
    )

    assert result["active_stage"] == "quality"


async def test_edit_from_final_review_reopens_quality_stage():
    node = HumanReviewNode()

    result = await node.run(
        {
            "review_stage": "final",
            "human_review_result": {"decision": "edit", "stage": "final"},
        }
    )

    assert result["active_stage"] == "quality"
