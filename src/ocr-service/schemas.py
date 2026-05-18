"""Pydantic schemas for OCR service requests and responses."""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

SCHEMA_REGISTRY_PATH = Path(__file__).with_name("schemas.json")


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


class ClassifySegmentDocument(BaseModel):
    """Classification result for a single identified document."""

    document_code: str
    document_name: str | None = None
    suggested_document_code: str | None = None
    suggested_document_name: str | None = None
    start_page: int
    end_page: int
    page_ranges: list[tuple[int, int]] | None = None
    page_order: list[int] | None = None
    duplicate_pages: list["DuplicatePage"] | None = None


class ExtractRequest(FileSourceModel):
    """Request body for v2 schema-driven extraction."""

    documents: list[ClassifySegmentDocument]
    extraction_schemas: list[ExtractionSchema] | None = None
    document_codes: list[str] | None = None
    document_names: list[str] | None = None
    extract_all_fields: bool = False
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
    def validate_schemas_not_empty(
        cls, v: list[ExtractionSchema] | None
    ) -> list[ExtractionSchema] | None:
        if v is not None and not v:
            raise ValueError("extraction_schemas must contain at least one schema")
        return v

    @field_validator("documents")
    @classmethod
    def validate_documents_not_empty(
        cls, v: list[ClassifySegmentDocument]
    ) -> list[ClassifySegmentDocument]:
        if not v:
            raise ValueError("documents must contain at least one classified document")
        return v

    @field_validator("document_codes", "document_names")
    @classmethod
    def validate_schema_selectors(cls, v: list[str] | None) -> list[str] | None:
        return _validate_optional_selector_list(v)

    @field_validator("thinking_level")
    @classmethod
    def validate_thinking_level(cls, v: str | None) -> str | None:
        return _validate_thinking_level(v)

    @model_validator(mode="after")
    def validate_unique_document_codes(self):
        if self.extraction_schemas:
            _validate_unique_document_codes(self.extraction_schemas)
        return self


class ExtractFullRequest(FileSourceModel):
    """Request body for v2 full classify-then-extract pipeline."""

    extraction_schemas: list[ExtractionSchema] | None = None
    document_codes: list[str] | None = None
    document_names: list[str] | None = None
    extract_all_fields: bool = False
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
    def validate_schemas_not_empty(
        cls, v: list[ExtractionSchema] | None
    ) -> list[ExtractionSchema] | None:
        if v is not None and not v:
            raise ValueError("extraction_schemas must contain at least one schema")
        return v

    @field_validator("document_codes", "document_names")
    @classmethod
    def validate_schema_selectors(cls, v: list[str] | None) -> list[str] | None:
        return _validate_optional_selector_list(v)

    @field_validator("thinking_level")
    @classmethod
    def validate_thinking_level(cls, v: str | None) -> str | None:
        return _validate_thinking_level(v)

    @model_validator(mode="after")
    def validate_unique_document_codes(self):
        if self.extraction_schemas:
            _validate_unique_document_codes(self.extraction_schemas)
        return self


class ClassifySegmentRequest(FileSourceModel):
    """Request body for v2 classify and segment."""

    extraction_schemas: list[ClassificationSchema] | None = None
    document_codes: list[str] | None = None
    document_names: list[str] | None = None
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

    @field_validator("document_codes", "document_names")
    @classmethod
    def validate_schema_selectors(cls, v: list[str] | None) -> list[str] | None:
        return _validate_optional_selector_list(v)

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
    page_ranges: list[tuple[int, int]] | None = None
    page_order: list[int] | None = None
    duplicate_pages: list["DuplicatePage"] | None = None
    extracted_data: dict[str, Any]


class DuplicatePage(BaseModel):
    """Duplicate page metadata for page-aware segmentation."""

    page: int
    duplicate_of: int


class PrefilterResponse(BaseModel):
    """Response from the prefilter document check endpoint."""

    is_valid_document: bool


class ExtractResponse(BaseModel):
    """Response from the v2 schema-driven extraction endpoint."""

    documents: list[ExtractedDocument]


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


class SchemaSelectionError(ValueError):
    """Raised when requested document schema selectors do not match the registry."""


@lru_cache(maxsize=1)
def load_default_extraction_schemas() -> tuple[ExtractionSchema, ...]:
    """Load validated extraction schemas from schemas.json."""
    try:
        payload = json.loads(SCHEMA_REGISTRY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SchemaSelectionError(f"Schema registry not found: {SCHEMA_REGISTRY_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaSelectionError(f"Schema registry must be valid JSON: {exc}") from exc

    raw_schemas = payload.get("extraction_schemas")
    if not isinstance(raw_schemas, list) or not raw_schemas:
        raise SchemaSelectionError("Schema registry must contain extraction_schemas")

    schemas = [ExtractionSchema.model_validate(item) for item in raw_schemas]
    _validate_unique_document_codes(schemas)
    return tuple(schemas)


def resolve_default_extraction_schemas(
    *,
    document_codes: list[str] | None = None,
    document_names: list[str] | None = None,
) -> list[ExtractionSchema]:
    """Resolve extraction schemas from the default registry using optional selectors."""
    registry = list(load_default_extraction_schemas())
    codes = _normalize_selector_list(document_codes)
    names = _normalize_selector_list(document_names)

    if not codes and not names:
        return registry

    by_code = {schema.document_code: schema for schema in registry}
    by_name = {_normalize_text(schema.document_name): schema for schema in registry}

    selected: dict[str, ExtractionSchema] = {}
    missing_codes = [code for code in codes if code not in by_code]
    missing_names = [name for name in names if name not in by_name]

    for code in codes:
        schema = by_code.get(code)
        if schema:
            selected[schema.document_code] = schema

    for name in names:
        schema = by_name.get(name)
        if schema:
            selected[schema.document_code] = schema

    if missing_codes or missing_names:
        details = []
        if missing_codes:
            details.append(f"document_codes: {', '.join(missing_codes)}")
        if missing_names:
            details.append(f"document_names: {', '.join(missing_names)}")
        raise SchemaSelectionError("Unknown schema selectors - " + "; ".join(details))

    return list(selected.values())


def to_classification_schemas(schemas: list[ExtractionSchema]) -> list[ClassificationSchema]:
    """Convert extraction schemas into classification-only schemas."""
    return [
        ClassificationSchema(
            document_code=schema.document_code,
            document_name=schema.document_name,
        )
        for schema in schemas
    ]


def _validate_optional_selector_list(values: list[str] | None) -> list[str] | None:
    normalized = _normalize_selector_list(values)
    return normalized or None


def _normalize_selector_list(values: list[str] | None) -> list[str]:
    if not values:
        return []

    normalized = []
    seen = set()
    for value in values:
        item = _normalize_text(value)
        if item and item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def _normalize_text(value: str) -> str:
    return value.strip().lower()
