from typing import Optional

from schemas import ClassificationSchema, ExtractionSchema

# 2. PROMPT TEMPLATES

TEMPLATE_PHASE1_SEGMENTATION = """<role>You are an expert Document Segmentation System.</role>

<task>
Analyze the entire file, which may contain multiple distinct documents over multiple pages. Identify boundaries between documents and classify each one.
</task>

<document_schemas>
The following document types may be present in this file. Each entry includes the document_code.
{schema_description}
</document_schemas>

<guidelines>
1. MERGE pages into one document if: content is sequential/continuing, table rows continue from previous page, or pagination markers exist (e.g., "Trang 2/3").
2. SPLIT into separate documents if: a new document header appears (e.g., Hospital name, "HÓA ĐƠN", "CỘNG HÒA XÃ HỘI...") with no continuity markers.
</guidelines>

<critical_rules>
{all_documents_rule}
</critical_rules>

<output_requirements>
Do NOT extract any specific data fields. ONLY return the structured array of identified documents with `document_code`, `start_page`, and `end_page` (and suggested fields if unknown).
For each document, also return `page_ranges` as an array of [start_page, end_page] pairs and `page_order` as a flat array of page numbers in the exact logical reading order, not simply the physical PDF order. If pages from the same document are non-adjacent or scanned out of order, merge them into one document and express the correct reading sequence with `page_order`. Use printed pagination markers such as "Trang 1/2", "Trang 2/2", "Page 1 of 2", or "1/2" as strong evidence that separated physical pages belong to the same document.
Keep `page_ranges` in the same logical order as `page_order`. Never represent non-adjacent pages as one continuous range if intervening pages belong to other documents; use separate ranges such as [[8, 8], [16, 16]].
Also return `duplicate_pages` as an array of objects with `page` and `duplicate_of`. A duplicate page belongs to the same logical document but visually repeats another page, so exclude it from `page_order` and `page_ranges` unless it contains additional unique information. Use an empty array when there are no duplicates.
Keep `start_page` and `end_page` as the minimum and maximum physical pages covered by the document, including duplicate pages, for backward compatibility and traceability. If identity signals conflict, split them into separate documents.
</output_requirements>
"""

TEMPLATE_PHASE2_EXTRACTION = """<role>You are an expert Document Intelligence System.</role>

<task>
You have been provided a specific chunk of a document (`start_page` to `end_page`). Extract the required fields for the document type `{document_code}`.
</task>

<document_schema>
{schema_description}
</document_schema>

<guidelines>
1. Match the document to the corresponding keys.
{field_extraction_rule}
3. If a field_key or its corresponding value is not found in the document, its value MUST be null.
4. If a field includes "Hint", treat it as guidance for what to find that value.
5. IGNORE all watermarks and background patterns.
6. ONLY use stamps, seals, or digital signatures to verify info if printed text is missing.
    When checking for signatures, you MUST verify the actual presence of a mark/tick; if the area is empty or only contains a placeholder, return false.
7. MUST strictly verify the semantic label immediately preceding or associated with a value to ensure accurate field mapping.
    Never "borrow" values from neighboring rows if their specific label is missing.
    If a value lacks a matching label or the label is functionally blank, treat the field as null.
</guidelines>

<strict_type_coercion>
Convert all extracted values to the correct data type:
- string: Plain text, no conversion needed.
- date: Convert to ISO 8601 format "YYYY-MM-DD". Example: "10/03/2026" → "2026-03-10".
- number: A pure numeric value. Strip all currency symbols, units, and thousand separators. Example: "1.500.000 VNĐ" → 1500000, "2,5" → 2.5. Must be a JSON number, NOT a string.
- boolean: Must be JSON true or false. Convert: "Có"/"Yes"/"X" → true, "Không"/"No"/ empty → false.
- array: A JSON array of objects. Each object must follow the child_schema structure with exact field_keys.
</strict_type_coercion>
"""


# 3. PROMPT BUILDER CLASS
class PromptBuilder:
    """Class responsible for dynamically generating prompts based on Config and User Requests."""

    @staticmethod
    def _format_field_descriptor(field) -> str:
        descriptor = f"{field.field_key} ({field.data_type})"
        hint = field.description or field.field_name
        if hint:
            descriptor += f" - Hint: {hint}"
        return descriptor

    @classmethod
    def build_phase1_prompt(
        cls,
        extraction_schemas: list["ExtractionSchema | ClassificationSchema"] | None = None,
        extract_all_documents: bool = False,
    ) -> str:
        """Generates a prompt for Phase 1: Segmentation and Classification."""
        schema_lines = []
        if extraction_schemas:
            for schema in extraction_schemas:
                schema_lines.append(
                    f'- document_code: "{schema.document_code}" | Name: {schema.document_name}'
                )
            schema_description = "\n".join(schema_lines)
        else:
            schema_description = "None provided. Treat all documents as undefined."

        if extract_all_documents or not extraction_schemas:
            doc_rule = "- Extract EVERY document found in the file, including undefined document types that don't match document_code in the provided schema. For undefined documents, set document_code to 'unknown', leave document_name as empty string, and fill suggested_document_code and suggested_document_name with appropriate suggestions."
        else:
            doc_rule = (
                "- Only return documents whose document_code exists in the provided schema list."
            )

        return TEMPLATE_PHASE1_SEGMENTATION.format(
            schema_description=schema_description,
            all_documents_rule=doc_rule,
        )

    @classmethod
    def build_phase2_prompt(
        cls,
        schema: Optional["ExtractionSchema"],
        extract_all_fields: bool = False,
    ) -> str:
        """Generates a prompt for Phase 2 per-document extraction."""
        if schema:
            schema_lines = [
                f'- document_code: "{schema.document_code}" | Name: {schema.document_name}',
                "  Fields to extract:",
            ]
            for field in schema.fields:
                if field.data_type == "array" and field.child_schema:
                    child_keys = ", ".join(
                        cls._format_field_descriptor(f) for f in field.child_schema
                    )
                    array_descriptor = (
                        f"{field.field_key} (array of objects, each with: {child_keys})"
                    )
                    if field.field_name:
                        array_descriptor += f" - Hint: {field.field_name}"
                    schema_lines.append(f"    - {array_descriptor}")
                else:
                    schema_lines.append(f"    - {cls._format_field_descriptor(field)}")
            schema_description = "\n".join(schema_lines)
            document_code = schema.document_code
        else:
            schema_description = (
                "Undefined document (unknown). \n"
                "CRITICAL INSTRUCTIONS FOR UNKNOWN DOCUMENTS:\n"
                "1. Extract ALL texts, key-value pairs, and tables into the generic format.\n"
                "2. VERY IMPORTANT: All `field_key`, `table_key`, and `key` for columns MUST be thoughtfully translated into English and formatted strictly in snake_case.\n"
                "3. All `field_name`, `table_name`, and `label` for columns MUST remain in their original language (e.g., Vietnamese) as written on the document."
            )
            document_code = "unknown"

        if schema is None:
            field_rule = "2. Extract all visible fields and tables into the generic unknown-document structure."
        elif extract_all_fields:
            field_rule = "2. Extract ALL fields (everything) from each document segment"
        else:
            field_rule = "2. Extract ONLY the fields defined in that document's schema."

        return TEMPLATE_PHASE2_EXTRACTION.format(
            document_code=document_code,
            schema_description=schema_description,
            field_extraction_rule=field_rule,
        )
