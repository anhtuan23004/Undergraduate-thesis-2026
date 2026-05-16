import requests

from eval.batch_run import (
    _raise_for_status,
    extract_routing_path,
    extract_token_usage,
    initialize_history,
    save_history,
    save_result,
    update_history,
    workflow_response_to_result,
)
from eval.batch_run import (
    build_parser as build_batch_parser,
)
from eval.cli import build_parser as build_cli_parser
from eval.runner import load_results, write_agent_suggestions


def test_workflow_response_to_result_normalizes_final_decision_and_outputs():
    response = {
        "claim_id": "CLAIM-001",
        "agent_1_result": {"decision": "accept"},
        "agent_2_result": {"decision": "accept"},
        "final_result": {"decision": "approve"},
        "current_step": "completed_decision_agent",
        "pending_human_review": True,
        "paused": True,
        "history": [
            {
                "agent": "CompletenessAgent",
                "step": "completeness_agent",
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "token_usage": 12,
                    "token_usage_source": "provider_metadata",
                },
            },
            {
                "agent": "QualityAgent",
                "step": "quality_agent",
                "token_usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 4,
                    "token_usage": 24,
                    "token_usage_source": "provider_metadata",
                },
            },
            {"agent": "DecisionAgent", "step": "decision_agent"},
        ],
    }

    result = workflow_response_to_result(response, latency_ms=123.4)

    assert result.claim_id == "CLAIM-001"
    assert result.final_decision == "accept"
    assert result.agent_outputs["CompletenessAgent"] == {"decision": "accept"}
    assert result.routing_path == ["completeness_check", "quality_check", "final_decision"]
    assert result.human_reviewed is True
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 6
    assert result.token_usage == 36
    assert result.token_usage_source == "provider_metadata"


def test_workflow_response_marks_missing_final_decision_as_needs_review_when_paused():
    response = {
        "claim_id": "CLAIM-002",
        "current_step": "completed_quality_agent",
        "pending_human_review": True,
        "history": [{"agent": "QualityAgent", "step": "quality_agent"}],
    }

    result = workflow_response_to_result(response, latency_ms=50)

    assert result.final_decision == "needs_review"
    assert result.routing_path == ["quality_check"]


def test_extract_routing_path_adds_pause_node_once():
    path = extract_routing_path(
        history=[
            {"step": "completeness_agent"},
            {"step": "quality_agent"},
        ],
        current_step="completed_quality_agent",
        pause_at="human_review",
    )

    assert path == ["completeness_check", "quality_check", "human_review"]


def test_extract_token_usage_sums_provider_metadata_history_entries():
    usage = extract_token_usage(
        [
            {
                "token_usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 2,
                    "token_usage": 3,
                    "token_usage_source": "provider_metadata",
                }
            },
            {
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 200,
                    "token_usage": 300,
                    "token_usage_source": "char_estimate",
                }
            },
            {
                "token_usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 5,
                    "token_usage": 9,
                    "token_usage_source": "provider_metadata",
                }
            },
        ]
    )

    assert usage == {
        "prompt_tokens": 5,
        "completion_tokens": 7,
        "token_usage": 12,
        "token_usage_source": "provider_metadata",
    }


def test_history_tracks_claim_states(tmp_path):
    history = {"claims": {}}
    claims = [
        {
            "claim_id": "CLAIM-001",
            "file_name": "a.pdf",
            "file_path": "data/a.pdf",
            "category_code": "OP_ILL",
        }
    ]

    initialize_history(history, claims)
    update_history(history, claims[0], "completed", final_decision="accept")
    output = tmp_path / "history.json"
    save_history(output, history)

    assert history["claims"]["CLAIM-001"]["status"] == "completed"
    assert history["claims"]["CLAIM-001"]["final_decision"] == "accept"
    assert history["summary"]["completed"] == 1
    assert output.exists()


def test_completed_history_clears_previous_error():
    claim = {
        "claim_id": "CLAIM-001",
        "file_name": "a.pdf",
        "file_path": "data/a.pdf",
        "category_code": "OP_ILL",
    }
    history = {"claims": {}}

    update_history(history, claim, "failed", error="old error")
    update_history(history, claim, "completed", final_decision="accept")

    assert history["claims"]["CLAIM-001"]["status"] == "completed"
    assert "error" not in history["claims"]["CLAIM-001"]


def test_result_is_saved_per_claim_file(tmp_path):
    result = workflow_response_to_result(
        {
            "claim_id": "CLAIM-001",
            "final_result": {"decision": "approve"},
            "history": [],
        },
        latency_ms=10,
    )

    output = save_result(tmp_path, result)
    loaded = load_results(tmp_path)

    assert output == tmp_path / "CLAIM-001.json"
    assert loaded[0].claim_id == "CLAIM-001"
    assert loaded[0].final_decision == "accept"


def test_suggestions_are_saved_per_claim(tmp_path):
    result = workflow_response_to_result(
        {
            "claim_id": "CLAIM-001",
            "final_result": {"decision": "approve"},
            "history": [],
        },
        latency_ms=10,
    )
    results_dir = tmp_path / "claims"
    suggestions_dir = tmp_path / "suggestions"
    output = tmp_path / "agent_suggestions.json"
    save_result(results_dir, result)

    write_agent_suggestions(
        results_dir,
        output,
        suggestions_dir=suggestions_dir,
    )

    assert output.exists()
    assert (suggestions_dir / "CLAIM-001.json").exists()


def test_no_upload_flag_is_deprecated_noop_for_current_agent_service_contract():
    cli_args = build_cli_parser().parse_args(["run", "--no-upload"])
    batch_args = build_batch_parser().parse_args(["--no-upload"])

    assert cli_args.upload is True
    assert cli_args.deprecated_no_upload is True
    assert batch_args.upload is True
    assert batch_args.deprecated_no_upload is True


def test_clean_ground_truth_cli_defaults_to_dataset_manifest():
    args = build_cli_parser().parse_args(["clean-ground-truth"])

    assert args.command == "clean-ground-truth"
    assert str(args.ground_truth).endswith("eval/dataset/ground_truth.json")
    assert args.output is None


def test_run_baseline_cli_defaults_to_single_agent_results():
    args = build_cli_parser().parse_args(["run-baseline", "--dry-run", "--limit", "2"])

    assert args.command == "run-baseline"
    assert str(args.results_dir).endswith("eval/results/single_agent_claims")
    assert args.dry_run is True
    assert args.limit == 2


def test_label_reference_cli_uses_gemini_31_pro_preview_by_default():
    args = build_cli_parser().parse_args(["label-reference", "--dry-run", "--limit", "1"])

    assert args.command == "label-reference"
    assert args.model == "gemini-3.1-pro-preview"
    assert str(args.output).endswith("eval/results/reviewed_labels.json")


def test_http_error_includes_agent_service_detail():
    response = requests.Response()
    response.status_code = 400
    response.reason = "Bad Request"
    response.url = "http://localhost:8003/api/v1/workflows/run"
    response._content = (
        b'{"detail":{"error":"Failed to prepare OCR data: Input file must be '
        b'inside UPLOADS_DIR","status_code":400,"endpoint":"/workflows/run"}}'
    )
    response.headers["Content-Type"] = "application/json"

    try:
        _raise_for_status(response, "run workflow")
    except requests.HTTPError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected HTTPError")

    assert "Input file must be inside UPLOADS_DIR" in message
    assert "run workflow" in message
