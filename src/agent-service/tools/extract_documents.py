"""Document extraction tool using OCR service.

This module provides a tool for extracting text and structured fields
from documents using the OCR service API.
"""

import os
from typing import Any, Dict, List, Optional

import httpx

from tools.base import BaseTool


OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "http://localhost:8001")


class ExtractDocumentsTool(BaseTool):
    """Tool for extracting text and structured data from documents.

    Uses the OCR service to perform raw text extraction, field extraction,
    or full document structure extraction from uploaded files or URLs.
    """

    name = "extract_documents"
    description = (
        "Extract text and structured data from claim documents (invoices, "
        "medical records, prescriptions). Supports raw text extraction, "
        "structured field extraction, and full document parsing."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the document file to extract from"
            },
            "file_url": {
                "type": "string",
                "description": "URL to download the document from (alternative to file_path)"
            },
            "extraction_type": {
                "type": "string",
                "enum": ["raw", "fields", "document"],
                "description": (
                    "Type of extraction: 'raw' for plain text, 'fields' for structured "
                    "key-value pairs, 'document' for full document structure"
                )
            },
            "prompt": {
                "type": "string",
                "description": "Optional custom prompt to guide the extraction"
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of specific fields to extract (for 'fields' type)"
            }
        },
        "required": ["extraction_type"],
        "oneOf": [
            {"required": ["file_path"]},
            {"required": ["file_url"]}
        ]
    }

    async def execute(
        self,
        extraction_type: str,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        prompt: Optional[str] = None,
        fields: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute document extraction.

        Args:
            extraction_type: Type of extraction ('raw', 'fields', or 'document')
            file_path: Local path to the document file
            file_url: URL to download the document from
            prompt: Optional custom extraction prompt
            fields: Specific fields to extract (for 'fields' type)

        Returns:
            Dictionary containing extraction results with success status
        """
        if not file_path and not file_url:
            return {
                "success": False,
                "error": "Either file_path or file_url must be provided"
            }

        endpoint = f"{OCR_SERVICE_URL}/api/v1/ocr/{extraction_type}"

        try:
            async with httpx.AsyncClient() as client:
                if file_path:
                    if not os.path.exists(file_path):
                        return {
                            "success": False,
                            "error": f"File not found: {file_path}"
                        }

                    with open(file_path, "rb") as f:
                        files = {"file": (os.path.basename(file_path), f)}
                        data = {}
                        if prompt:
                            data["prompt"] = prompt

                        response = await client.post(
                            endpoint,
                            files=files,
                            data=data,
                            timeout=60.0
                        )
                else:
                    data = {"file_url": file_url}
                    if prompt:
                        data["prompt"] = prompt

                    response = await client.post(
                        endpoint,
                        data=data,
                        timeout=60.0
                    )

                response.raise_for_status()
                result = response.json()

                # Handle different response formats
                if extraction_type == "raw":
                    return {
                        "success": True,
                        "extraction_type": extraction_type,
                        "text": result if isinstance(result, str) else result.get("text", ""),
                        "source": file_path or file_url
                    }
                else:
                    # fields or document type - should be structured JSON
                    extracted_data = result if isinstance(result, dict) else {"data": result}

                    # If specific fields requested, filter the result
                    if fields and isinstance(extracted_data, dict):
                        filtered = {
                            k: v for k, v in extracted_data.items()
                            if k in fields
                        }
                        missing = [f for f in fields if f not in extracted_data]
                        return {
                            "success": True,
                            "extraction_type": extraction_type,
                            "data": filtered,
                            "missing_fields": missing,
                            "source": file_path or file_url
                        }

                    return {
                        "success": True,
                        "extraction_type": extraction_type,
                        "data": extracted_data,
                        "source": file_path or file_url
                    }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"OCR service error: {e.response.status_code} - {e.response.text}",
                "source": file_path or file_url
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"Failed to connect to OCR service: {str(e)}",
                "source": file_path or file_url
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Extraction failed: {str(e)}",
                "source": file_path or file_url
            }
