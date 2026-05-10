from typing import Any

from schemas import ExtractionSchema, FieldSchema

# ============================================================================
# Schema Builder Utilities
# ============================================================================

# Maps extraction_schemas data_type values to JSON Schema types
DATA_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "number": "number",
    "boolean": "boolean",
    "date": "string",  # ISO 8601 date string
    "array": "array",
}


def _attach_description(schema_fragment: dict[str, Any], description: str | None) -> dict[str, Any]:
    if description:
        schema_fragment["description"] = description
    return schema_fragment


def build_field_schema(field: FieldSchema) -> dict[str, Any]:
    """Recursively build a JSON Schema fragment for a single FieldSchema.

    Args:
        field: A FieldSchema instance.

    Returns:
        A JSON Schema dict for this field.
    """
    dtype = DATA_TYPE_MAP.get(field.data_type, "string")

    schema: dict[str, Any] = {}
    if field.data_type == "date":
        schema = {"type": "string", "format": "date"}
    elif dtype == "array":
        child_props: dict[str, Any] = {}
        required_child_keys: list[str] = []
        if field.child_schema:
            child_props = {f.field_key: build_field_schema(f) for f in field.child_schema}
            required_child_keys = [f.field_key for f in field.child_schema if f.required]

        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": child_props,
                "required": required_child_keys,
                "additionalProperties": False,
            },
        }
    else:
        schema = {"type": dtype}

    if field.nullable:
        schema["nullable"] = True

    return _attach_description(schema, field.description or field.field_name)


def _build_unknown_document_extracted_data_schema(
    extract_all_fields: bool = False,
) -> dict[str, Any]:
    """Build extracted_data schema for unknown documents with fields/tables structure."""
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "description": "Each field is a JSON object with field_key, field_name, and value. Only extract content that are outside of any tables. For content inside tables, extract them in the tables structure.",
                    "properties": {
                        "field_key": {
                            "type": "string",
                            "description": "Unique key for the extracted field in English in snake_case",
                        },
                        "field_name": {
                            "type": "string",
                            "description": "Name of the extracted field in Vietnamese in normal language",
                        },
                        "value": {
                            "type": "string",
                            "description": "Extracted value for this field as a string",
                        },
                    },
                    "required": ["field_key", "field_name", "value"],
                    "additionalProperties": False,
                },
            },
            "tables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table_key": {
                            "type": "string",
                            "description": "Unique key for the extracted table in English in snake_case",
                        },
                        "table_name": {
                            "type": "string",
                            "description": "Name of the extracted table in Vietnamese in normal language",
                        },
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {
                                        "type": "string",
                                        "description": "Unique key for the column in English in snake_case",
                                    },
                                    "label": {
                                        "type": "string",
                                        "description": "Name of the column in Vietnamese in normal language",
                                    },
                                },
                                "required": ["key", "label"],
                                "additionalProperties": False,
                            },
                        },
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "description": "Each row is a JSON object with column keys and their corresponding cell values as strings",
                                "additionalProperties": extract_all_fields,
                            },
                        },
                    },
                    "required": ["table_key", "table_name", "columns", "rows"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["fields", "tables"],
        "additionalProperties": False,
    }


def build_phase1_response_schema(
    extraction_schemas: list[ExtractionSchema] | None = None,
    extract_all_documents: bool = False,
) -> dict[str, Any]:
    """Build a JSON Schema object for Phase 1: Segmentation."""
    if extraction_schemas is not None:
        valid_codes = [schema.document_code for schema in extraction_schemas]
    else:
        valid_codes = []

    if not extraction_schemas:
        extract_all_documents = True

    doc_code_schema: dict[str, Any] = {"type": "string"}
    if extract_all_documents:
        doc_code_schema["enum"] = valid_codes + ["unknown"]
        doc_code_schema[
            "description"
        ] = "Document code. Output 'unknown' if it does not match any known schemas."
    elif valid_codes:
        doc_code_schema["enum"] = valid_codes

    properties: dict[str, Any] = {
        "document_code": doc_code_schema,
        "document_name": {
            "type": "string",
            "description": "Human-readable name of the document type in Vietnamese. For known documents, use the name from the schema. For unknown documents, leave empty.",
        },
        "start_page": {"type": "integer"},
        "end_page": {"type": "integer"},
    }

    if extract_all_documents:
        properties["suggested_document_code"] = {
            "type": "string",
            "description": "ONLY output this field if document_code is 'unknown'. Suggested document code for the unknown document in English in snake_case.",
        }
        properties["suggested_document_name"] = {
            "type": "string",
            "description": "ONLY output this field if document_code is 'unknown'. Suggested document name for the unknown document in Vietnamese.",
        }

    document_item_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": ["document_code", "document_name", "start_page", "end_page"],
        "additionalProperties": False,
    }

    return {
        "type": "object",
        "properties": {
            "documents": {
                "type": "array",
                "items": document_item_schema,
            }
        },
        "required": ["documents"],
        "additionalProperties": False,
    }


def build_phase2_response_schema(
    schema: ExtractionSchema | None,
    extract_all_fields: bool = False,
) -> dict[str, Any]:
    """Build a JSON Schema object for Phase 2: Extraction of a single document."""
    combined_fields: dict[str, Any] = {}
    is_unknown = schema is None

    if schema:
        for field in schema.fields:
            combined_fields[field.field_key] = build_field_schema(field)

    if is_unknown:
        unknown_schema = _build_unknown_document_extracted_data_schema(extract_all_fields)
        combined_fields.update(unknown_schema.get("properties", {}))

    required_keys = [f.field_key for f in schema.fields if f.required] if schema else []

    return {
        "type": "object",
        "properties": combined_fields,
        "required": required_keys,
        "additionalProperties": extract_all_fields if not is_unknown else True,
    }


def build_phase2_batch_response_schema(
    schema: ExtractionSchema | None,
    extract_all_fields: bool = False,
) -> dict[str, Any]:
    """Build a JSON Schema array for Phase 2 batch extraction."""
    return {
        "type": "array",
        "items": build_phase2_response_schema(schema, extract_all_fields),
    }
