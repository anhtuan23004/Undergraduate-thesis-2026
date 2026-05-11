"""Compatibility facade for OCR pipeline helpers."""

from mongodb_client import get_collection as _get_collection

from services import ocr_pipeline as _ocr_pipeline


def _pipeline() -> _ocr_pipeline.OcrPipeline:
    return _ocr_pipeline.OcrPipeline(
        adapter=_ocr_pipeline.OcrServiceAdapter(),
        collection_provider=_get_collection,
        audit_writer=_ocr_pipeline.save_ocr_result,
    )


def run_ocr_document(file_path: str) -> dict:
    """Run OCR service document extraction for a file path."""
    return _ocr_pipeline.OcrServiceAdapter().run_document(file_path)


def run_ocr_v1_document(file_path: str) -> dict:
    """Run OCR service v1 document extraction for a file path."""
    return _ocr_pipeline.OcrServiceAdapter().run_v1_document(file_path)


def run_ocr_v2_document(file_path: str) -> dict:
    """Run OCR service v2 phase 1 classification for a file path."""
    return _ocr_pipeline.OcrServiceAdapter().run_v2_document(file_path)


def run_ocr_v2_classify_segment(file_path: str) -> dict:
    """Run OCR service v2 phase 1 classification and segmentation."""
    return _ocr_pipeline.OcrServiceAdapter().run_v2_classify_segment(file_path)


def run_ocr_v2_extract(file_path: str, phase1_documents: list[dict]) -> dict:
    """Run OCR service v2 phase 2 extraction for classified documents."""
    return _ocr_pipeline.OcrServiceAdapter().run_phase2_extract(file_path, phase1_documents)


async def prepare_ocr_result(
    run_id: str,
    claim_id: str,
    policy_number: str,
    input_file: str,
    file_hash: str | None = None,
) -> dict:
    """Load cached OCR by hash or call OCR service, then audit the result."""
    return await _pipeline().prepare_initial_ocr(
        run_id,
        claim_id,
        policy_number,
        input_file,
        file_hash,
    )


async def prepare_ocr_phase2_result(
    run_id: str,
    claim_id: str,
    policy_number: str,
    input_file: str,
    phase1_documents: list[dict],
    file_hash: str | None = None,
) -> dict:
    """Load cached OCR v2 phase 2 result or extract classified documents."""
    return await _pipeline().prepare_phase2_ocr(
        run_id,
        claim_id,
        policy_number,
        input_file,
        phase1_documents,
        file_hash,
    )
