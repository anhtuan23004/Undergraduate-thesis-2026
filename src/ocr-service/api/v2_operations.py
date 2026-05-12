"""Application operations for OCR service v2 endpoints."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from core.config import settings
from core.engine.v2 import OCRServiceV2
from fastapi import HTTPException, UploadFile
from schemas import (
    ClassificationSchema,
    ClassifySegmentDocument,
    ClassifySegmentResponse,
    ExtractionSchema,
    ExtractResponse,
    PrefilterResponse,
    SchemaSelectionError,
    resolve_default_extraction_schemas,
    to_classification_schemas,
)

from api.utils import get_file_content, validate_model_response

FileLoader = Callable[..., Awaitable[tuple[bytes, str, str]]]
EngineFactory = Callable[..., Any]


@dataclass(frozen=True)
class V2FileSource:
    """Transport-neutral file source for v2 OCR operations."""

    file: UploadFile | None = None
    file_url: str | None = None
    file_data: str | None = None
    operation: str = "v2_json"


@dataclass(frozen=True)
class V2ModelOptions:
    """Gemini model options shared by v2 operations."""

    model_name: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_output_tokens: int | None = None
    thinking_budget: int | None = None
    thinking_level: str | None = None

    @classmethod
    def from_payload(cls, payload: Any) -> "V2ModelOptions":
        return cls(
            model_name=getattr(payload, "model_name", None),
            temperature=getattr(payload, "temperature", None),
            top_p=getattr(payload, "top_p", None),
            top_k=getattr(payload, "top_k", None),
            max_output_tokens=getattr(payload, "max_output_tokens", None),
            thinking_budget=getattr(payload, "thinking_budget", None),
            thinking_level=getattr(payload, "thinking_level", None),
        )

    def as_kwargs(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_output_tokens": self.max_output_tokens,
            "thinking_budget": self.thinking_budget,
            "thinking_level": self.thinking_level,
        }


@dataclass(frozen=True)
class V2PrefilterCommand:
    source: V2FileSource
    api_key: str | None = None
    model_name: str | None = None
    log_prefix: str = "V2 Prefilter"


@dataclass(frozen=True)
class V2ClassifySegmentCommand:
    source: V2FileSource
    extraction_schemas: list[ClassificationSchema] | None = None
    document_codes: list[str] | None = None
    document_names: list[str] | None = None
    model_options: V2ModelOptions = field(default_factory=V2ModelOptions)
    api_key: str | None = None
    log_prefix: str = "V2"


@dataclass(frozen=True)
class V2ExtractCommand:
    source: V2FileSource
    documents: list[ClassifySegmentDocument]
    extraction_schemas: list[ExtractionSchema] | None = None
    document_codes: list[str] | None = None
    document_names: list[str] | None = None
    extract_all_fields: bool = False
    model_options: V2ModelOptions = field(default_factory=V2ModelOptions)
    api_key: str | None = None
    log_prefix: str = "V2"


@dataclass(frozen=True)
class V2ExtractFullCommand:
    source: V2FileSource
    extraction_schemas: list[ExtractionSchema] | None = None
    document_codes: list[str] | None = None
    document_names: list[str] | None = None
    extract_all_fields: bool = False
    model_options: V2ModelOptions = field(default_factory=V2ModelOptions)
    api_key: str | None = None
    log_prefix: str = "V2 Full"


def v2_json_file_source(payload: Any) -> V2FileSource:
    return V2FileSource(
        file_url=payload.file_url,
        file_data=payload.file_data,
        operation="v2_json",
    )


def v2_form_file_source(
    *,
    file: UploadFile | None = None,
    file_url: str | None = None,
    file_data: str | None = None,
) -> V2FileSource:
    return V2FileSource(
        file=file,
        file_url=file_url,
        file_data=file_data,
        operation="v2_form",
    )


class OCRV2Operations:
    """Coordinates v2 OCR application operations outside the route layer."""

    def __init__(
        self,
        *,
        engine_factory: EngineFactory | None = None,
        file_loader: FileLoader | None = None,
    ) -> None:
        self._engine_factory = engine_factory or OCRServiceV2
        self._file_loader = file_loader or get_file_content

    async def prefilter(self, command: V2PrefilterCommand) -> PrefilterResponse:
        service = self._create_engine(command.api_key)
        file_bytes, file_name, mime_type = await self._load_file(command.source)
        result = service.run_prefilter_only(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            model_name=command.model_name,
        )
        return validate_model_response(
            result=result,
            response_model=PrefilterResponse.model_validate,
            log_prefix=command.log_prefix,
        )

    async def classify_segment(self, command: V2ClassifySegmentCommand) -> ClassifySegmentResponse:
        service = self._create_engine(command.api_key)
        file_bytes, file_name, mime_type = await self._load_file(command.source)
        extraction_schemas = _resolve_classification_schemas(
            extraction_schemas=command.extraction_schemas,
            document_codes=command.document_codes,
            document_names=command.document_names,
        )
        return self._classify_segment_with_engine(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=extraction_schemas,
            model_options=command.model_options,
            log_prefix=command.log_prefix,
        )

    async def extract(self, command: V2ExtractCommand) -> ExtractResponse:
        service = self._create_engine(command.api_key)
        file_bytes, file_name, mime_type = await self._load_file(command.source)
        extraction_schemas = _resolve_extraction_schemas(
            extraction_schemas=command.extraction_schemas,
            document_codes=command.document_codes,
            document_names=command.document_names,
        )
        return self._extract_with_engine(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            documents=command.documents,
            extraction_schemas=extraction_schemas,
            extract_all_fields=command.extract_all_fields,
            model_options=command.model_options,
            log_prefix=command.log_prefix,
        )

    async def extract_full(self, command: V2ExtractFullCommand) -> ExtractResponse:
        service = self._create_engine(command.api_key)
        file_bytes, file_name, mime_type = await self._load_file(command.source)
        extraction_schemas = _resolve_extraction_schemas(
            extraction_schemas=command.extraction_schemas,
            document_codes=command.document_codes,
            document_names=command.document_names,
        )
        classification = self._classify_segment_with_engine(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=to_classification_schemas(extraction_schemas),
            model_options=command.model_options,
            log_prefix=command.log_prefix,
        )
        return self._extract_with_engine(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            documents=classification.documents,
            extraction_schemas=extraction_schemas,
            extract_all_fields=command.extract_all_fields,
            model_options=command.model_options,
            log_prefix=command.log_prefix,
        )

    def _create_engine(self, api_key: str | None) -> Any:
        return self._engine_factory(api_key=api_key)

    async def _load_file(self, source: V2FileSource) -> tuple[bytes, str, str]:
        return await self._file_loader(
            file=source.file,
            file_url=source.file_url,
            file_data=source.file_data,
            operation=source.operation,
        )

    def _classify_segment_with_engine(
        self,
        *,
        service: Any,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        extraction_schemas: list[ClassificationSchema],
        model_options: V2ModelOptions,
        log_prefix: str,
    ) -> ClassifySegmentResponse:
        result = service.run_classify_and_segment(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=extraction_schemas,
            extract_all_documents=settings.OCR_EXTRACT_ALL_DOCUMENTS,
            **model_options.as_kwargs(),
        )
        return validate_model_response(
            result=result,
            response_model=ClassifySegmentResponse.model_validate,
            log_prefix=log_prefix,
        )

    def _extract_with_engine(
        self,
        *,
        service: Any,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        documents: list[ClassifySegmentDocument],
        extraction_schemas: list[ExtractionSchema],
        extract_all_fields: bool,
        model_options: V2ModelOptions,
        log_prefix: str,
    ) -> ExtractResponse:
        result = service.extract_classified_documents(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            documents=documents,
            extraction_schemas=extraction_schemas,
            extract_all_fields=extract_all_fields,
            **model_options.as_kwargs(),
        )
        return validate_model_response(
            result=result,
            response_model=ExtractResponse.model_validate,
            log_prefix=log_prefix,
        )


def _resolve_extraction_schemas(
    *,
    extraction_schemas: list[ExtractionSchema] | None = None,
    document_codes: list[str] | None = None,
    document_names: list[str] | None = None,
) -> list[ExtractionSchema]:
    if extraction_schemas:
        return extraction_schemas

    try:
        return resolve_default_extraction_schemas(
            document_codes=document_codes,
            document_names=document_names,
        )
    except SchemaSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _resolve_classification_schemas(
    *,
    extraction_schemas: list[ClassificationSchema] | None = None,
    document_codes: list[str] | None = None,
    document_names: list[str] | None = None,
) -> list[ClassificationSchema]:
    if extraction_schemas:
        return extraction_schemas

    schemas = _resolve_extraction_schemas(
        document_codes=document_codes,
        document_names=document_names,
    )
    return to_classification_schemas(schemas)
