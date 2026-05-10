"""Pydantic schemas for OCR service requests and responses."""

import re
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator


class FieldSchema(BaseModel):
    """Defines a single field to extract from a document."""

    field_key: str
    data_type: Literal["string", "number", "boolean", "date", "array"]
    field_name: str | None = None
    description: str | None = None
    nullable: bool = True
    required: bool = True
    child_schema: list["FieldSchema"] | None = None

    @field_validator("field_key")
    @classmethod
    def validate_field_key(cls, v: str) -> str:
        field_key = v.strip()
        if not field_key:
            raise ValueError("field_key must not be empty")
        return field_key

    @field_validator("field_name", "description")
    @classmethod
    def validate_optional_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @model_validator(mode="after")
    def validate_array_shape(self):
        if self.data_type == "array":
            if not self.child_schema:
                raise ValueError("child_schema is required when data_type is 'array'")
        elif self.child_schema is not None:
            raise ValueError("child_schema is only allowed when data_type is 'array'")
        return self


class ExtractionSchema(BaseModel):
    """Defines the extraction schema for one document type."""

    document_code: str
    document_name: str
    fields: list[FieldSchema]

    @field_validator("document_code")
    @classmethod
    def validate_document_code(cls, v: str) -> str:
        return _validate_document_code(v)

    @field_validator("document_name")
    @classmethod
    def validate_document_name(cls, v: str) -> str:
        return _validate_required_text(v, "document_name")

    @field_validator("fields")
    @classmethod
    def validate_fields_not_empty(cls, v: list[FieldSchema]) -> list[FieldSchema]:
        if not v:
            raise ValueError("fields must contain at least one field")
        return v

    @model_validator(mode="after")
    def validate_unique_field_keys(self):
        _validate_unique_values([field.field_key for field in self.fields], "field_key", "fields")
        return self


class ClassificationSchema(BaseModel):
    """Defines a document schema for classification without extraction fields."""

    document_code: str
    document_name: str

    @field_validator("document_code")
    @classmethod
    def validate_document_code(cls, v: str) -> str:
        return _validate_document_code(v)

    @field_validator("document_name")
    @classmethod
    def validate_document_name(cls, v: str) -> str:
        return _validate_required_text(v, "document_name")


class FileSourceModel(BaseModel):
    """Common JSON file source fields for v2 endpoints."""

    file_url: str | None = None
    file_data: str | None = None

    @field_validator("file_url")
    @classmethod
    def validate_file_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError("file_url must be a valid HTTP/HTTPS URL")
        return v

    @model_validator(mode="after")
    def validate_exactly_one_file_source(self):
        provided = sum(bool(x) for x in (self.file_url, self.file_data))
        if provided != 1:
            raise ValueError("Provide exactly one source: file_url or file_data")
        return self


class ExtractRequest(FileSourceModel):
    """Request body for v2 schema-driven extraction."""

    extraction_schemas: list[ExtractionSchema]
    extract_all_fields: bool = False
    extract_all_documents: bool = False
    model_name: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_output_tokens: int | None = None
    thinking_budget: int | None = None
    thinking_level: str | None = None
    api_key: str | None = None

    @field_validator("extraction_schemas")
    @classmethod
    def validate_schemas_not_empty(cls, v: list[ExtractionSchema]) -> list[ExtractionSchema]:
        if not v:
            raise ValueError("extraction_schemas must contain at least one schema")
        return v

    @field_validator("thinking_level")
    @classmethod
    def validate_thinking_level(cls, v: str | None) -> str | None:
        return _validate_thinking_level(v)

    @model_validator(mode="after")
    def validate_unique_document_codes(self):
        _validate_unique_document_codes(self.extraction_schemas)
        return self


class ClassifySegmentRequest(FileSourceModel):
    """Request body for v2 classify and segment."""

    extraction_schemas: list[ClassificationSchema] | None = None
    extract_all_documents: bool = False
    model_name: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_output_tokens: int | None = None
    thinking_budget: int | None = None
    thinking_level: str | None = None
    api_key: str | None = None

    @field_validator("thinking_level")
    @classmethod
    def validate_thinking_level(cls, v: str | None) -> str | None:
        return _validate_thinking_level(v)

    @model_validator(mode="after")
    def validate_unique_document_codes(self):
        if self.extraction_schemas:
            _validate_unique_document_codes(self.extraction_schemas)
        return self


class PrefilterRequest(FileSourceModel):
    """Request body for the prefilter document check endpoint."""

    model_name: str | None = None
    api_key: str | None = None


class ExtractedDocument(BaseModel):
    """Extraction result for a single identified document."""

    document_code: str
    document_name: str | None = None
    suggested_document_code: str | None = None
    suggested_document_name: str | None = None
    start_page: int
    end_page: int
    extracted_data: dict[str, Any]


class PrefilterResponse(BaseModel):
    """Response from the prefilter document check endpoint."""

    is_valid_document: bool


class ExtractResponse(BaseModel):
    """Response from the v2 schema-driven extraction endpoint."""

    documents: list[ExtractedDocument]


class ClassifySegmentDocument(BaseModel):
    """Classification result for a single identified document."""

    document_code: str
    document_name: str | None = None
    suggested_document_code: str | None = None
    suggested_document_name: str | None = None
    start_page: int
    end_page: int


class ClassifySegmentResponse(BaseModel):
    """Response from the v2 classify and segment endpoint."""

    documents: list[ClassifySegmentDocument]


def _validate_document_code(value: str) -> str:
    document_code = _validate_required_text(value, "document_code")
    if not re.fullmatch(r"[a-z0-9_]+", document_code):
        raise ValueError("document_code must match pattern ^[a-z0-9_]+$")
    return document_code


def _validate_required_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _validate_thinking_level(value: str | None) -> str | None:
    if value is None:
        return value
    normalized = value.strip().lower()
    allowed_levels = {"minimal", "low", "medium", "high"}
    if normalized not in allowed_levels:
        raise ValueError("thinking_level must be one of: minimal, low, medium, high")
    return normalized


def _validate_unique_document_codes(schemas: list[ExtractionSchema | ClassificationSchema]) -> None:
    _validate_unique_values(
        [schema.document_code for schema in schemas],
        "document_code",
        "extraction_schemas",
    )


def _validate_unique_values(values: list[str], value_name: str, container_name: str) -> None:
    seen = set()
    duplicates = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)

    if duplicates:
        duplicate_values = ", ".join(sorted(duplicates))
        raise ValueError(f"Duplicate {value_name} values in {container_name}: {duplicate_values}")
