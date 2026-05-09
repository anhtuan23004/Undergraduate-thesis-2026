"""
Dataset builder for thesis evaluation.

Processes PDF documents from data/dataset/documents/ into a structured
ground truth dataset for evaluating the agentic claims processing system.

Usage:
    python -m eval.dataset.build
"""

import json
import re
from pathlib import Path
from typing import Any

CATEGORY_MAP = {
    "Ngoại trú do ốm bệnh": {
        "en": "outpatient_illness",
        "code": "OP_ILL",
        "inpatient": False,
        "accident": False,
        "maternity": False,
    },
    "Nội trú do ỐM BỆNH": {
        "en": "inpatient_illness",
        "code": "IP_ILL",
        "inpatient": True,
        "accident": False,
        "maternity": False,
    },
    "Ngoại trú do tai nạn": {
        "en": "outpatient_accident",
        "code": "OP_ACC",
        "inpatient": False,
        "accident": True,
        "maternity": False,
    },
    "Nội trú do TAI NẠN": {
        "en": "inpatient_accident",
        "code": "IP_ACC",
        "inpatient": True,
        "accident": True,
        "maternity": False,
    },
    "Ngoại trú THAI SẢN": {
        "en": "outpatient_maternity",
        "code": "OP_MAT",
        "inpatient": False,
        "accident": False,
        "maternity": True,
    },
    "Nội trú THAI SẢN": {
        "en": "inpatient_maternity",
        "code": "IP_MAT",
        "inpatient": True,
        "accident": False,
        "maternity": True,
    },
}

COMPLEXITY_DISTRIBUTION = {
    "simple": 0.6,
    "ambiguous": 0.3,
    "complex": 0.1,
}


def extract_patient_name(filename: str) -> str:
    """Extract patient name from filename."""
    name = Path(filename).stem
    name = re.sub(r"[._-]+", " ", name)
    name = re.sub(r"\s*\d+\.\d+\.\d+.*$", "", name)
    name = re.sub(r"\s*p\d+.*$", "", name)
    name = name.strip()
    return name if name else "UNKNOWN"


def extract_date(filename: str) -> str | None:
    """Extract date from filename if present."""
    patterns = [
        r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
        r"(\d{4}[./]\d{1,2}[./]\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    return None


def build_claim_entry(
    category_dir: str,
    filename: str,
    file_path: str,
    category_info: dict[str, Any],
) -> dict[str, Any]:
    """Build a single claim entry with metadata."""
    patient_name = extract_patient_name(filename)
    date = extract_date(filename)

    entry = {
        "claim_id": f"CLM-{category_info['code']}-{len([]):04d}",
        "policy_number": "",  # To be extracted from PDF
        "patient_name": patient_name,
        "category": category_info["en"],
        "category_code": category_info["code"],
        "is_inpatient": category_info["inpatient"],
        "is_accident": category_info["accident"],
        "is_maternity": category_info["maternity"],
        "file_path": file_path,
        "file_name": filename,
        "document_date": date,
        "expected_decision": "",  # Requires expert labeling
        "expected_missing_docs": [],  # Requires expert labeling
        "expected_icd_codes": [],  # Requires expert labeling
        "expected_exclusions": [],  # Requires expert labeling
        "expected_quality_issues": [],  # Requires expert labeling
        "expected_routing_path": [],  # Requires expert labeling
        "expected_tools_by_agent": {
            "CompletenessAgent": [
                "classify-benefit",
                "check-required-docs",
                "validate-consistency",
            ],
            "QualityAgent": [
                "check-icd",
                "check-exclusion",
                "validate-medication",
                "search-medicine",
                "web-search",
            ],
            "DecisionAgent": ["aggregate-issues"],
        },
        "complexity": "",  # Requires expert labeling
        "label_status": "unlabeled",
        "expert_notes": "",  # Requires expert labeling
        "ocr_available": True,
        "langfuse_trace_id": "",  # To be filled after running through system
        "agent_1_result": {},  # To be filled after running through system
        "agent_2_result": {},  # To be filled after running through system
        "final_result": {},  # To be filled after running through system
        "routing_path": [],  # To be filled after running through system
        "human_override": False,  # To be filled after running through system
        "processing_time_ms": 0,  # To be filled after running through system
        "token_count": 0,  # To be filled after running through system
    }
    return entry


def build_dataset(base_path: str, output_path: str) -> dict[str, Any]:
    """Build complete ground truth dataset from PDF directory structure."""
    base = Path(base_path)
    all_claims = []
    claim_id_counters = {info["code"]: 0 for info in CATEGORY_MAP.values()}

    for category_dir_name, category_info in CATEGORY_MAP.items():
        category_path = base / category_dir_name
        if not category_path.exists():
            continue

        code = category_info["code"]
        for pdf_file in sorted(category_path.glob("*.pdf")):
            claim_id_counters[code] += 1
            entry = build_claim_entry(
                category_dir_name,
                pdf_file.name,
                str(pdf_file),
                category_info,
            )
            entry["claim_id"] = f"CLM-{code}-{claim_id_counters[code]:04d}"
            all_claims.append(entry)

    dataset = {
        "metadata": {
            "total_claims": len(all_claims),
            "generated_at": "",
            "source": "data/dataset/documents",
            "categories": {
                info["code"]: sum(1 for c in all_claims if c["category_code"] == info["code"])
                for info in CATEGORY_MAP.values()
            },
            "complexity_distribution": COMPLEXITY_DISTRIBUTION,
        },
        "claims": all_claims,
    }
    return dataset


def assign_complexity(claims: list[dict]) -> list[dict]:
    """Assign complexity levels based on distribution strategy.

    For thesis, complexity should be assigned by expert review.
    This is a placeholder that assigns based on category heuristics.
    """
    for claim in claims:
        if claim["is_accident"]:
            claim["complexity"] = "ambiguous"
        elif claim["category_code"] == "OP_DEN":
            claim["complexity"] = "simple"
        else:
            claim["complexity"] = "simple"
    return claims


def save_dataset(dataset: dict[str, Any], output_path: str) -> None:
    """Save dataset to JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)


def load_dataset(input_path: str) -> dict[str, Any]:
    """Load dataset from JSON file."""
    with open(input_path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from datetime import datetime

    base_path = Path(__file__).parent.parent.parent / "data" / "dataset" / "documents"
    output_path = Path(__file__).parent / "ground_truth.json"

    dataset = build_dataset(str(base_path), str(output_path))
    dataset["metadata"]["generated_at"] = datetime.now().isoformat()
    dataset["claims"] = assign_complexity(dataset["claims"])
    dataset["metadata"]["complexity_distribution"] = {
        "simple": sum(1 for c in dataset["claims"] if c["complexity"] == "simple"),
        "ambiguous": sum(1 for c in dataset["claims"] if c["complexity"] == "ambiguous"),
        "complex": sum(1 for c in dataset["claims"] if c["complexity"] == "complex"),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_dataset(dataset, str(output_path))

    print(f"Dataset built: {dataset['metadata']['total_claims']} claims")
    print(f"Output: {output_path}")
    for code, count in dataset["metadata"]["categories"].items():
        print(f"  {code}: {count}")
