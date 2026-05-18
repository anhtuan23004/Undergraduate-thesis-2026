"""Tests for OCR v2 page-aware segmentation and extraction."""

from core.engine import v2 as v2_engine
from core.engine.v2 import OCRServiceV2
from schemas import ClassifySegmentDocument


def test_normalize_page_aware_segments_handles_disjoint_order_and_duplicates():
    documents = [
        {
            "document_code": "medical_report",
            "document_name": "Báo cáo y tế",
            "start_page": 8,
            "end_page": 16,
            "page_order": [16, 8, 9, 8],
            "duplicate_pages": [
                {"page": 10, "duplicate_of": 8},
                {"page": 10, "duplicate_of": 8},
                {"page": 11, "duplicate_of": 99},
            ],
        }
    ]

    result = OCRServiceV2._normalize_page_aware_segments(documents)

    assert result == [
        {
            "document_code": "medical_report",
            "document_name": "Báo cáo y tế",
            "start_page": 8,
            "end_page": 16,
            "page_order": [16, 8, 9],
            "page_ranges": [[16, 16], [8, 9]],
            "duplicate_pages": [{"page": 10, "duplicate_of": 8}],
        }
    ]


def test_normalize_page_aware_segments_falls_back_to_start_end():
    documents = [
        {
            "document_code": "medical_report",
            "document_name": "Báo cáo y tế",
            "start_page": 5,
            "end_page": 4,
            "page_order": ["bad"],
            "page_ranges": [["bad", 4]],
            "duplicate_pages": [{"page": "x", "duplicate_of": 4}],
        }
    ]

    result = OCRServiceV2._normalize_page_aware_segments(documents)

    assert result[0]["page_order"] == [5]
    assert result[0]["page_ranges"] == [[5, 5]]
    assert result[0]["duplicate_pages"] == []
    assert result[0]["start_page"] == 5
    assert result[0]["end_page"] == 5


def test_extract_classified_document_slices_pdf_by_page_order(monkeypatch):
    service = object.__new__(OCRServiceV2)
    captured = {}

    def fake_slice_pdf(file_bytes, page_ranges):
        captured["page_ranges"] = page_ranges
        return b"sliced-pdf"

    def fake_extract_segment(file_bytes, *args, **kwargs):
        captured["file_bytes"] = file_bytes
        return {"diagnosis": "Viêm họng"}, {"input_tokens": 1, "output_tokens": 2}

    monkeypatch.setattr(v2_engine, "slice_pdf_multiple_ranges", fake_slice_pdf)
    monkeypatch.setattr(service, "_extract_segment", fake_extract_segment)

    document = ClassifySegmentDocument.model_validate(
        {
            "document_code": "medical_report",
            "document_name": "Báo cáo y tế",
            "start_page": 1,
            "end_page": 3,
            "page_order": [3, 1, 2],
            "page_ranges": [[3, 3], [1, 2]],
            "duplicate_pages": [],
        }
    )

    extracted_doc, usage = service._extract_classified_document(
        document,
        b"%PDF-1.4",
        "claim.pdf",
        "application/pdf",
        schema_map={},
        high_accuracy_codes=set(),
        extract_all_fields=False,
        model_name=None,
        temperature=None,
        top_p=None,
        top_k=None,
        max_output_tokens=None,
        thinking_budget=None,
        thinking_level=None,
    )

    assert captured["page_ranges"] == [(3, 3), (1, 2)]
    assert captured["file_bytes"] == b"sliced-pdf"
    assert extracted_doc["page_order"] == [3, 1, 2]
    assert extracted_doc["extracted_data"] == {"diagnosis": "Viêm họng"}
    assert usage == {"input_tokens": 1, "output_tokens": 2}
