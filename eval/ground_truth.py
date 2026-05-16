"""Ground-truth manifest cleanup utilities."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

FAKE_METADATA_KEYS = {
    "labeling_mode",
    "fake_label_source",
    "fake_label_count",
    "fake_label_warning",
}

REFERENCE_LABEL_FIELDS = {
    "expected_decision": "",
    "expected_missing_docs": [],
    "expected_icd_codes": [],
    "expected_exclusions": [],
    "expected_quality_issues": [],
    "expected_routing_path": [],
    "label_status": "unlabeled",
}


def clean_ground_truth_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """Remove fake metric smoke-test labels from a dataset manifest."""
    cleaned = dict(payload)
    metadata = dict(cleaned.get("metadata", {}))
    was_fake_seeded = _has_fake_seed_metadata(metadata)
    removed_metadata_count = 0
    for key in list(metadata):
        if key in FAKE_METADATA_KEYS or key.startswith("fake_"):
            metadata.pop(key, None)
            removed_metadata_count += 1
    cleaned["metadata"] = metadata

    reset_label_count = 0
    claims = []
    for claim in cleaned.get("claims", []):
        row = dict(claim)
        if was_fake_seeded and row.get("label_status") in {"reviewed", "final"}:
            for field, value in REFERENCE_LABEL_FIELDS.items():
                row[field] = list(value) if isinstance(value, list) else value
            if _looks_generated_note(row.get("expert_notes", "")):
                row["expert_notes"] = ""
            reset_label_count += 1
        claims.append(row)
    cleaned["claims"] = claims

    return cleaned, {
        "removed_metadata_count": removed_metadata_count,
        "reset_label_count": reset_label_count,
        "claim_count": len(claims),
    }


def clean_ground_truth_file(path: Path, output_path: Path | None = None) -> dict[str, int]:
    """Clean a ground-truth manifest file and write the result atomically."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    cleaned, stats = clean_ground_truth_payload(payload)
    target = output_path or path
    _write_json_atomic(target, cleaned)
    return stats


def _has_fake_seed_metadata(metadata: dict[str, Any]) -> bool:
    mode = str(metadata.get("labeling_mode", ""))
    warning = str(metadata.get("fake_label_warning", ""))
    return bool(metadata.get("fake_label_count")) or "fake" in mode or "Temporary labels" in warning


def _looks_generated_note(value: Any) -> bool:
    note = str(value or "").lower()
    return "agent" in note or "fake" in note or "temporary" in note


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        tmp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    tmp_path.replace(path)
