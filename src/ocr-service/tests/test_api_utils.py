"""Tests for shared OCR API input helpers."""

import pytest
from api.utils import get_file_content, parse_json_list, parse_model_list
from fastapi import HTTPException, UploadFile
from pydantic import BaseModel


class _TinyModel(BaseModel):
    value: str


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


def test_parse_json_list_requires_json_array():
    with pytest.raises(HTTPException) as exc_info:
        parse_json_list('{"value": 1}', "items")

    assert exc_info.value.status_code == 400


def test_parse_model_list_validates_items():
    models = parse_model_list('[{"value": "ok"}]', "items", _TinyModel.model_validate)

    assert models[0].value == "ok"
