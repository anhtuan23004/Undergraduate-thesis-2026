import fitz

from utils.logging import get_logger

logger = get_logger(__name__)


def slice_pdf_multiple_ranges(file_bytes: bytes, page_ranges: list[tuple[int, int]]) -> bytes:
    """Slice a PDF bytes object for multiple disjoint page ranges and return the sub-PDF bytes as a single file."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        new_doc = fitz.open()

        for start_page, end_page in page_ranges:
            start_idx = max(0, start_page - 1)
            end_idx = min(len(doc) - 1, end_page - 1)

            if start_idx <= end_idx <= len(doc) - 1:
                new_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx)

        if len(new_doc) > 0:
            out_bytes = new_doc.write()
            new_doc.close()
            doc.close()
            return out_bytes

        new_doc.close()
        doc.close()
        return file_bytes
    except Exception as e:
        logger.error(f"Failed to slice PDF with multiple ranges in PyMuPDF: {e}")
        return file_bytes
