"""Document extraction tool using OCR service.

This tool wraps the existing extract_documents function for use with the skill-based architecture.
"""

import json
import os
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import tool

OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "http://localhost:8001")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/tmp/agent-service/uploads")


@tool("extract-documents")
def extract_documents(
    extraction_type: str,
    file_path: Optional[str] = None,
    file_url: Optional[str] = None,
    prompt: Optional[str] = None,
    fields: Optional[List[str]] = None,
    **kwargs,
) -> str:
    """Extract text and structured data from documents.

    This tool uses the OCR service to extract text and fields from
    various document formats (PDF, images, etc.).

    Args:
        extraction_type: Type of extraction ('raw', 'fields', or 'document')
        file_path: Local path to document file
        file_url: URL to download document from
        prompt: Optional custom extraction prompt
        fields: Specific fields to extract (for 'fields' type)

    Returns:
        JSON string containing extraction results
    """
    if not file_path and not file_url:
        return json.dumps(
            {"success": False, "error": "Either file_path or file_url must be provided"}
        )

    # Validate file_path is within allowed directory
    if file_path:
        try:
            # Resolve to absolute path and check it's within allowed directory
            allowed_dir = os.path.abspath(os.path.expanduser(UPLOADS_DIR))
            requested_path = os.path.abspath(os.path.expanduser(file_path))

            # Ensure the allowed directory exists
            os.makedirs(allowed_dir, exist_ok=True)

            # Check if requested path is within allowed directory
            if not requested_path.startswith(allowed_dir):
                return json.dumps(
                    {
                        "success": False,
                        "error": f"File path outside allowed directory. Allowed: {allowed_dir}",
                        "source": file_path,
                    }
                )
        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Path validation failed: {str(e)}",
                    "source": file_path,
                }
            )

    endpoint = f"{OCR_SERVICE_URL}/api/v1/ocr/{extraction_type}"

    try:
        with requests.Session() as session:
            if file_path:
                if not os.path.exists(file_path):
                    return json.dumps({"success": False, "error": f"File not found: {file_path}"})

                with open(file_path, "rb") as f:
                    files = {"file": (os.path.basename(file_path), f)}
                    data = {}
                    if prompt:
                        data["prompt"] = prompt

                    response = session.post(endpoint, files=files, data=data, timeout=60.0)
            else:
                data = {"file_url": file_url}
                if prompt:
                    data["prompt"] = prompt

                response = session.post(endpoint, data=data, timeout=60.0)

            response.raise_for_status()
            result = response.json()

            # Handle different response formats
            if extraction_type == "raw":
                return json.dumps(
                    {
                        "success": True,
                        "extraction_type": extraction_type,
                        "text": result if isinstance(result, str) else result.get("text", ""),
                        "source": file_path or file_url,
                    }
                )
            else:
                # fields or document type - should be structured JSON
                extracted_data = result if isinstance(result, dict) else {"data": result}

                # If specific fields requested, filter result
                if fields and isinstance(extracted_data, dict):
                    filtered = {k: v for k, v in extracted_data.items() if k in fields}
                    missing = [f for f in fields if f not in extracted_data]
                    return json.dumps(
                        {
                            "success": True,
                            "extraction_type": extraction_type,
                            "data": filtered,
                            "missing_fields": missing,
                            "source": file_path or file_url,
                        }
                    )

                return json.dumps(
                    {
                        "success": True,
                        "extraction_type": extraction_type,
                        "data": extracted_data,
                        "source": file_path or file_url,
                    }
                )

    except requests.HTTPError as e:
        return json.dumps(
            {
                "success": False,
                "error": f"OCR service error: {e.response.status_code if e.response else str(e)}",
                "source": file_path or file_url,
            }
        )
    except requests.RequestException as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Failed to connect to OCR service: {str(e)}",
                "source": file_path or file_url,
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Extraction failed: {str(e)}",
                "source": file_path or file_url,
            }
        )


__all__ = ["extract_documents"]
