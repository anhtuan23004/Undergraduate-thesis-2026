import httpx
import mimetypes
import re
import json
from urllib.parse import urlparse
from typing import Dict, Any, Union, Optional
from fastapi import HTTPException
import google.genai as genai
from google.genai import types

from utils.logging import get_logger

logger = get_logger(__name__)

# Limit allowed file types to prevent malicious file uploads
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/pdf",
}

# Limit file size
MAX_FILE_SIZE = 50 * 1024 * 1024


def _validate_url(url: str) -> None:
    """Validate URL format and scheme.
    
    Args:
        url: The URL to validate.
        
    Raises:
        HTTPException: If URL is invalid.
    """
    # WHY: Prevent SSRF attacks by validating URL scheme
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(
                status_code=400, detail="Only HTTP and HTTPS URLs are allowed"
            )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")


def _sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Sanitize and truncate filename to prevent path traversal and length issues.
    
    Args:
        filename: The filename to sanitize.
        max_length: Maximum length for the filename (default: 100).
        
    Returns:
        Sanitized and truncated filename.
    """
    # WHY: Remove path traversal characters and keep only safe characters
    filename = re.sub(r"[^\w\s\-\.]", "", filename)
    
    if not filename:
        return "downloaded_file"
    
    # Truncate long filenames while preserving extension to avoid filesystem and API limits
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
        # Ensure extension is reasonable length (max 10 chars)
        ext = ext[:10]
        # Calculate max name length (reserve space for extension + dot)
        max_name_length = max_length - len(ext) - 1
        # Truncate name if needed
        if len(name) > max_name_length:
            name = name[:max_name_length]
        return f"{name}.{ext}"
    else:
        # No extension, just truncate
        return filename[:max_length]


async def download_file_from_url(url: str) -> tuple[bytes, str, str]:
    """Download a file from a URL with security validations.
    
    Args:
        url: The URL to download from.
        
    Returns:
        tuple[bytes, str, str]: (content, filename, content_type)
        
    Raises:
        HTTPException: If download fails or validation fails.
    """
    _validate_url(url)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            
            # WHY: Check file size before reading entire content to prevent memory exhaustion
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024}MB",
                )
            
            content = response.content
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024}MB",
                )
            
            content_type = response.headers.get("content-type")
            if not content_type:
                content_type, _ = mimetypes.guess_type(url)
            
            if not content_type:
                content_type = "application/octet-stream"
            
            # WHY: Validate MIME type to prevent processing of malicious files
            if content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {content_type}. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}",
                )

            # WHY: Remove query parameters (e.g., CloudFront signed URLs) before extracting filename
            # to prevent extremely long filenames from signatures and keys
            parsed_url = urlparse(url)
            filename = parsed_url.path.split("/")[-1]
            filename = _sanitize_filename(filename)
                
            return content, filename, content_type
            
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=400, detail=f"Error downloading file from URL: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error downloading file from URL: Status {e.response.status_code}",
            )


def parse_markdown_json(text: str) -> Union[Dict[str, Any], str]:
    """
    Parse JSON string that might be wrapped in markdown code blocks.
    
    Args:
        text: Text that might contain markdown-wrapped JSON.
        
    Returns:
        Parsed JSON as dict if successful, otherwise returns the original text.
    """
    if not text or not isinstance(text, str):
        return text
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Pattern to match JSON wrapped in markdown code blocks
    # Matches ```json ... ``` or ``` ... ``` or just JSON without wrapper
    markdown_patterns = [
        r'```(?:json)?\s*\n?(.*?)\n?```',  # ```json ... ``` or ``` ... ```
        r'`([^`]+)`',  # Single backticks `...`
    ]
    
    extracted_json = None
    
    # Try to extract JSON from markdown code blocks
    for pattern in markdown_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            extracted_json = match.group(1).strip()
            break
    
    # If no markdown wrapper found, try the whole text
    if not extracted_json:
        extracted_json = text
    
    # Try to parse as JSON
    try:
        return json.loads(extracted_json)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON from text: {e}")
        # Return original text if JSON parsing fails
        return text


# ============================================================================
# Gemini Model Utilities
# ============================================================================

def is_gemini_3_model(model_name: str) -> bool:
    """
    Detect if model is Gemini 3.x series.
    
    Args:
        model_name: Name of the model.
        
    Returns:
        True if Gemini 3.x, False if Gemini 2.5 or earlier.
    """
    model_lower = model_name.lower()
    return any(pattern in model_lower for pattern in [
        'gemini-3',
        'gemini3',
        'gemini-exp-',  # Experimental 3.x models
    ])



def _get_thinking_config_support() -> Dict[str, bool]:
    """Check which thinking features are supported by the installed SDK."""
    supported = {
        "thinking_level": False,
        "include_thoughts": False,
        "thinking_budget": False
    }
    try:
        model_fields = types.ThinkingConfig.model_fields.keys()
        supported["thinking_level"] = "thinking_level" in model_fields
        supported["include_thoughts"] = "include_thoughts" in model_fields
        supported["thinking_budget"] = "thinking_budget" in model_fields
    except Exception as e:
        logger.warning(f"Failed to inspect ThinkingConfig fields: {e}")
    return supported

# Cache supported features
_THINKING_SUPPORT = _get_thinking_config_support()

def _build_thinking_config(
    is_gemini_3: bool,
    thinking_budget: Optional[int],
    thinking_level: Optional[str],
    default_thinking_budget: int,
    default_thinking_level: str
) -> Optional[types.ThinkingConfig]:
    """Helper to build ThinkingConfig based on model version and SDK support."""
    
    if is_gemini_3:
        # Gemini 3.x Logic
        level = thinking_level if thinking_level is not None else default_thinking_level
        
        if level is None:
            logger.info("Using default Gemini 3 thinking behavior (high)")
            return None

        # Case 1: SDK supports thinking_level (Preferred)
        if _THINKING_SUPPORT["thinking_level"]:
            try:
                logger.info(f"Gemini 3 thinking mode: {level}")
                return types.ThinkingConfig(thinking_level=level)
            except Exception as e:
                logger.warning(f"Failed to set thinking_level: {e}")
        
        # Case 2: SDK fallback to include_thoughts
        if _THINKING_SUPPORT["include_thoughts"]:
            logger.info(f"Gemini 3 thinking mode: {level} (requested) -> include_thoughts=True (SDK fallback)")
            return types.ThinkingConfig(include_thoughts=True)
            
        # Case 3: No support found
        logger.warning(f"ThinkingLevel not supported in current SDK version. Requested: {level}")
        logger.info("Using default Gemini 3 thinking behavior (high)")
        return None

    else:
        # Gemini 2.5 Logic
        budget = thinking_budget if thinking_budget is not None else default_thinking_budget
        
        if budget == 0:
            logger.info("Gemini 2.5 thinking mode disabled")
            return None
            
        if budget is not None and budget != -1: # >0 specific budget
             logger.info(f"Gemini 2.5 thinking mode with budget: {budget} tokens")
             return types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=budget
            )
        
        logger.info("Using default Gemini 2.5 thinking behavior")
        return None

def build_generation_config(
    model_name: str,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    thinking_budget: Optional[int] = None,
    thinking_level: Optional[str] = None,
    default_thinking_budget: int = -1,
    default_thinking_level: str = "low",
) -> Optional[types.GenerateContentConfig]:
    """
    Build GenerateContentConfig with version-specific thinking support.
    
    Args:
        model_name: Name of the Gemini model.
        temperature: Controls randomness (0.0-2.0).
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum tokens to generate.
        thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
        thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).
        default_thinking_budget: Default thinking budget for Gemini 2.5.
        default_thinking_level: Default thinking level for Gemini 3.
        
    Returns:
        GenerateContentConfig if any parameters are set, None otherwise.
    """
    config_dict = {}
    
    # Standard generation parameters
    if temperature is not None:
        config_dict["temperature"] = temperature
    if top_p is not None:
        config_dict["top_p"] = top_p
    if top_k is not None:
        config_dict["top_k"] = top_k
    if max_output_tokens is not None:
        config_dict["max_output_tokens"] = max_output_tokens
    
    # Version-specific thinking config
    is_gemini_3 = is_gemini_3_model(model_name)
    
    thinking_config = _build_thinking_config(
        is_gemini_3=is_gemini_3,
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
        default_thinking_budget=default_thinking_budget,
        default_thinking_level=default_thinking_level
    )
    
    if thinking_config:
        config_dict["thinking_config"] = thinking_config
    
    # Create config if we have any parameters
    return types.GenerateContentConfig(**config_dict) if config_dict else None
