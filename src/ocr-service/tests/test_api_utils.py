"""Tests for shared OCR API input helpers."""

import pytest
from api.utils import get_file_content
from fastapi import HTTPException, UploadFile


@pytest.mark.asyncio
async def test_get_file_content_rejects_multiple_sources():
    with pytest.raises(HTTPException) as exc_info:
        await get_file_content(file_url="https://example.com/a.pdf", file_data="abc")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_file_content_rejects_unsupported_upload_type():
    upload = UploadFile(filename="claim.txt", file=None, headers={"content-type": "text/plain"})

    with pytest.raises(HTTPException) as exc_info:
        await get_file_content(file=upload)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_file_content_accepts_base64_pdf_data_uri():
    file_bytes, file_name, mime_type = await get_file_content(
        file_data="data:application/pdf;base64,JVBERi0xLjQ="
    )

    assert file_bytes == b"%PDF-1.4"
    assert file_name == "base64_upload"
    assert mime_type == "application/pdf"
