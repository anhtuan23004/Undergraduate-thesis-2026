"""Streamlit UI for reviewing and labeling thesis evaluation data.

Run:
    streamlit run eval/labeling_app.py
"""

# ruff: noqa: E402,I001

from __future__ import annotations

import base64
import copy
import json
import shutil
import subprocess  # nosec B404 - pdftoppm is invoked with a fixed executable path and no shell.
import sys
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.labeling import (  # noqa: E402
    COMMON_EXCLUSIONS,
    COMMON_MISSING_DOCS,
    COMMON_QUALITY_ISSUES,
    COMPLEXITY_OPTIONS,
    DECISION_OPTIONS,
    LABEL_STATUS_OPTIONS,
    ROUTING_NODE_OPTIONS,
    claim_label_fields,
    filter_claims,
    get_claims,
    label_progress,
    label_draft_for_claim,
    load_agent_suggestions,
    load_dataset,
    load_reviewed_labels,
    list_to_lines,
    parse_lines,
    parse_tools_json,
    save_reviewed_label,
    suggestion_to_label_updates,
    validate_claim_label,
)
from eval.paths import AGENT_SUGGESTIONS, GROUND_TRUTH, REVIEWED_LABELS  # noqa: E402
from eval.schemas import DEFAULT_EXPECTED_TOOLS  # noqa: E402

DEFAULT_DATASET_PATH = GROUND_TRUTH
DEFAULT_SUGGESTIONS_PATH = AGENT_SUGGESTIONS
DEFAULT_REVIEWED_LABELS_PATH = REVIEWED_LABELS


def main() -> None:
    st.set_page_config(page_title="Claims Labeling", layout="wide")
    st.title("Claims Ground Truth Labeling")

    dataset_path = Path(st.sidebar.text_input("Ground truth JSON", value=str(DEFAULT_DATASET_PATH)))
    suggestions_path = Path(
        st.sidebar.text_input("Agent suggestions JSON", value=str(DEFAULT_SUGGESTIONS_PATH))
    )
    reviewed_labels_path = Path(
        st.sidebar.text_input("Reviewed labels JSON", value=str(DEFAULT_REVIEWED_LABELS_PATH))
    )
    if "dataset_path" not in st.session_state or st.session_state.dataset_path != str(dataset_path):
        st.session_state.dataset_path = str(dataset_path)
        st.session_state.dataset = load_dataset(dataset_path)
    if "suggestions_path" not in st.session_state or st.session_state.suggestions_path != str(
        suggestions_path
    ):
        st.session_state.suggestions_path = str(suggestions_path)
        st.session_state.suggestions = load_agent_suggestions(suggestions_path)
    if (
        "reviewed_labels_path" not in st.session_state
        or st.session_state.reviewed_labels_path != str(reviewed_labels_path)
    ):
        st.session_state.reviewed_labels_path = str(reviewed_labels_path)
        st.session_state.reviewed_labels = load_reviewed_labels(reviewed_labels_path)

    if st.sidebar.button("Reload from disk"):
        st.session_state.dataset = load_dataset(dataset_path)
        st.session_state.suggestions = load_agent_suggestions(suggestions_path)
        st.session_state.reviewed_labels = load_reviewed_labels(reviewed_labels_path)
        st.rerun()

    dataset = st.session_state.dataset
    suggestions = st.session_state.suggestions
    reviewed_labels = st.session_state.reviewed_labels
    claims = get_claims(dataset)
    review_claims = [
        {
            **claim,
            "label_status": reviewed_labels.get(claim.get("claim_id"), {}).get(
                "label_status", "unlabeled"
            ),
        }
        for claim in claims
    ]
    progress = label_progress(review_claims)
    final_count = progress["final"]
    total_count = progress["total"]

    st.sidebar.metric("Final labels", f"{final_count}/{total_count}")
    st.sidebar.progress(final_count / total_count if total_count else 0.0)

    categories = sorted(
        {claim.get("category_code", "") for claim in claims if claim.get("category_code")}
    )
    status_filter = st.sidebar.selectbox("Status", ["all", *LABEL_STATUS_OPTIONS])
    category_filter = st.sidebar.selectbox("Category", ["all", *categories])
    query = st.sidebar.text_input("Search claim")

    visible_claims = filter_claims(review_claims, status_filter, category_filter, query)
    if not visible_claims:
        st.warning("No claims match the current filters.")
        return

    selected_claim_id = st.sidebar.selectbox(
        "Claim",
        [claim["claim_id"] for claim in visible_claims],
        format_func=lambda claim_id: _claim_label(visible_claims, claim_id),
    )
    claim = next(claim for claim in visible_claims if claim["claim_id"] == selected_claim_id)
    suggestion = suggestions.get(selected_claim_id)
    reviewed_label = reviewed_labels.get(selected_claim_id)

    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        _render_claim_review(claim, suggestion, reviewed_label)
    with right:
        _render_label_form(reviewed_labels_path, claim, suggestion, reviewed_label)


def _claim_label(claims: list[dict], claim_id: str) -> str:
    claim = next(claim for claim in claims if claim["claim_id"] == claim_id)
    return (
        f"{claim_id} | {claim.get('category_code', '')} | "
        f"{claim.get('label_status', 'unlabeled')} | {claim.get('file_name', '')}"
    )


def _render_claim_review(
    claim: dict,
    suggestion: dict | None,
    reviewed_label: dict | None,
) -> None:
    st.subheader("Review")
    st.write(
        {
            "claim_id": claim.get("claim_id", ""),
            "file_name": claim.get("file_name", ""),
            "patient_name": claim.get("patient_name", ""),
            "category_code": claim.get("category_code", ""),
            "category": claim.get("category", ""),
            "document_date": claim.get("document_date", ""),
        }
    )

    if reviewed_label:
        with st.expander("Reviewed label JSON", expanded=True):
            st.json(claim_label_fields(reviewed_label), expanded=True)

    if suggestion:
        with st.expander("Agent suggestion", expanded=True):
            st.json(_suggestion_summary(suggestion), expanded=True)
    else:
        st.info("No agent suggestion found for this claim.")

    pdf_path = Path(str(claim.get("file_path", "")))
    st.caption(str(pdf_path))
    if pdf_path.exists():
        st.download_button(
            "Download PDF",
            data=pdf_path.read_bytes(),
            file_name=pdf_path.name,
            mime="application/pdf",
        )
        if st.checkbox("Show PDF preview", value=True):
            tab_images, tab_pdf = st.tabs(["Image pages", "Full PDF"])
            with tab_images:
                max_pages = st.slider("Preview pages", min_value=1, max_value=10, value=5)
                _render_pdf_pages(pdf_path, max_pages=max_pages)
            with tab_pdf:
                _embed_pdf(pdf_path)
    else:
        st.error("PDF file not found on disk.")


def _render_label_form(
    reviewed_labels_path: Path,
    claim: dict,
    suggestion: dict | None,
    reviewed_label: dict | None,
) -> None:
    st.subheader("Review result")
    current = label_draft_for_claim(claim, suggestion, reviewed_label)
    if suggestion and st.button("Use agent suggestion", type="secondary"):
        current.update(suggestion_to_label_updates(suggestion))
        current["label_status"] = "reviewed"
        current["expert_notes"] = _suggestion_note(suggestion)

    with st.form(f"label-form-{claim['claim_id']}"):
        decision = st.selectbox(
            "expected_decision",
            DECISION_OPTIONS,
            index=_index_or_zero(DECISION_OPTIONS, current["expected_decision"]),
        )

        missing_docs = _multiselect_with_custom(
            "expected_missing_docs",
            COMMON_MISSING_DOCS,
            current["expected_missing_docs"],
        )
        icd_codes = parse_lines(
            st.text_area(
                "expected_icd_codes",
                value=list_to_lines(current["expected_icd_codes"]),
                help="One ICD code per line, e.g. J06.9",
            )
        )
        exclusions = _multiselect_with_custom(
            "expected_exclusions",
            COMMON_EXCLUSIONS,
            current["expected_exclusions"],
        )
        quality_issues = _multiselect_with_custom(
            "expected_quality_issues",
            COMMON_QUALITY_ISSUES,
            current["expected_quality_issues"],
        )

        st.caption(f"Suggested routing nodes: {', '.join(ROUTING_NODE_OPTIONS)}")
        routing_path = parse_lines(
            st.text_area(
                "expected_routing_path",
                value=list_to_lines(current["expected_routing_path"]),
                help="One workflow node per line, in execution order.",
            )
        )

        tools_json = st.text_area(
            "expected_tools_by_agent",
            value=json.dumps(
                current.get("expected_tools_by_agent") or DEFAULT_EXPECTED_TOOLS,
                ensure_ascii=False,
                indent=2,
            ),
            height=190,
        )

        complexity = st.selectbox(
            "complexity",
            COMPLEXITY_OPTIONS,
            index=_index_or_zero(COMPLEXITY_OPTIONS, current["complexity"]),
        )
        label_status = st.selectbox(
            "label_status",
            LABEL_STATUS_OPTIONS,
            index=_index_or_zero(LABEL_STATUS_OPTIONS, current["label_status"]),
        )
        expert_notes = st.text_area("expert_notes", value=current["expert_notes"], height=120)

        save = st.form_submit_button("Save reviewed label")

    try:
        expected_tools = parse_tools_json(tools_json)
        tool_error = ""
    except ValueError as exc:
        expected_tools = current.get("expected_tools_by_agent") or DEFAULT_EXPECTED_TOOLS
        tool_error = str(exc)

    updates = {
        "expected_decision": decision,
        "expected_missing_docs": missing_docs,
        "expected_icd_codes": icd_codes,
        "expected_exclusions": exclusions,
        "expected_quality_issues": quality_issues,
        "expected_routing_path": routing_path,
        "expected_tools_by_agent": expected_tools,
        "complexity": complexity,
        "label_status": label_status,
        "expert_notes": expert_notes,
    }
    preview_claim = copy.deepcopy(claim)
    preview_claim.update(updates)
    validation_errors = validate_claim_label(preview_claim)
    if tool_error:
        validation_errors.insert(0, tool_error)

    with st.expander("Preview label before save", expanded=True):
        if validation_errors:
            st.warning("\n".join(f"- {error}" for error in validation_errors))
        else:
            st.success("Label passes validation.")
        st.json(claim_label_fields(preview_claim), expanded=True)

    if save:
        if validation_errors:
            st.error("Fix validation errors before saving.")
            return
        save_reviewed_label(reviewed_labels_path, claim, updates)
        st.session_state.reviewed_labels = load_reviewed_labels(reviewed_labels_path)
        st.success(f"Saved reviewed label for {claim['claim_id']}")
        st.rerun()


def _multiselect_with_custom(label: str, options: list[str], current: list[str]) -> list[str]:
    current = [str(item) for item in current]
    selected_defaults = [item for item in current if item in options]
    custom_defaults = [item for item in current if item not in options]
    selected = st.multiselect(label, options, default=selected_defaults)
    custom = parse_lines(
        st.text_area(
            f"{label}_custom",
            value=list_to_lines(custom_defaults),
            help="Optional. One custom value per line.",
        )
    )
    return [*selected, *custom]


def _suggestion_summary(suggestion: dict) -> dict:
    return {
        "source_mode": suggestion.get("source_mode", ""),
        "final_decision": suggestion.get("final_decision", ""),
        "missing_docs": suggestion.get("missing_docs", []),
        "icd_codes": suggestion.get("icd_codes", []),
        "exclusions": suggestion.get("exclusions", []),
        "quality_issues": suggestion.get("quality_issues", []),
        "routing_path": suggestion.get("routing_path", []),
        "called_tools_by_agent": suggestion.get("called_tools_by_agent", {}),
        "langfuse_trace_id": suggestion.get("langfuse_trace_id", ""),
        "errors": suggestion.get("errors", []),
    }


def _suggestion_note(suggestion: dict) -> str:
    return (
        "Agent-assisted draft. Reviewer must verify against the source PDF before "
        f"setting label_status=final. Source mode: {suggestion.get('source_mode', '')}."
    )


def _embed_pdf(path: Path) -> None:
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    components.html(
        f"""
        <iframe
            src="data:application/pdf;base64,{encoded}"
            width="100%"
            height="760"
            style="border: 1px solid #ddd;"
        ></iframe>
        """,
        height=780,
    )


def _render_pdf_pages(path: Path, max_pages: int) -> None:
    """Render the first pages as PNG images for reliable Streamlit preview."""
    pdftoppm_path = shutil.which("pdftoppm")
    if not pdftoppm_path:
        st.error("pdftoppm is not installed. Use Download PDF or Browser PDF preview.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        prefix = Path(temp_dir) / "page"
        try:
            subprocess.run(  # nosec B603 - fixed command, no shell, controlled args.
                [
                    pdftoppm_path,
                    "-png",
                    "-r",
                    "130",
                    "-f",
                    "1",
                    "-l",
                    str(max_pages),
                    str(path),
                    str(prefix),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            st.error(f"Could not render PDF preview: {exc.stderr or exc.stdout}")
            return

        page_images = sorted(Path(temp_dir).glob("page-*.png"))
        if not page_images:
            st.warning("No preview pages were generated.")
            return

        for index, image_path in enumerate(page_images, start=1):
            st.caption(f"Page {index}")
            st.image(str(image_path), use_container_width=True)


def _index_or_zero(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


if __name__ == "__main__":
    main()
