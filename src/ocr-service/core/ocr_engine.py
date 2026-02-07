import os
import tempfile
import json
import re
from typing import Optional, Tuple, Dict, Any, Union
import google.genai as genai
from google.genai import types

from app.config import settings
from utils.logging import get_logger
from core.utils import parse_markdown_json, build_generation_config

logger = get_logger(__name__)

class GeminiConfigError(Exception):
    """Exception raised for Gemini configuration errors."""
    pass

class GeminiOCRService:
    """Service for OCR operations using Google Gemini API.
    
    Args:
        api_key: Optional API key override.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise GeminiConfigError("Missing GEMINI_API_KEY. Set env var or pass via UI.")
        self.client = genai.Client(api_key=self.api_key)

    def _upload_temp_file(self, file_bytes: bytes, file_name: str, mime_type: str):
        """
        Upload file bytes to Gemini Files API.
        
        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            
        Returns:
            Uploaded file object.
        """
        # WHY: Preserve file extension for temporary file to ensure proper MIME type detection
        suffix = ""
        if "." in file_name:
            suffix = file_name[file_name.rfind("."):]
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            path = tmp.name
        
        try:
            # WHY: Truncate display_name to avoid API issues with excessively long filenames
            display_name = file_name[:150] if len(file_name) > 150 else file_name
            
            uploaded = self.client.files.upload(
                file=path,
                config=types.UploadFileConfig(display_name=display_name, mime_type=mime_type),
            )
            return uploaded
        finally:
            # WHY: Clean up temporary file to prevent disk space issues
            # Log failures instead of silently ignoring them
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Failed to remove temporary file {path}: {e}")


    def _call_model(
        self,
        uploaded_file,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        thinking_level: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Call Gemini model with uploaded file and prompt.
        
        Args:
            uploaded_file: Uploaded file object.
            prompt: Text prompt for the model.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
            thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).
            
        Returns:
            Tuple of (response text, usage info dict).
        """
        contents = [uploaded_file]
        if prompt:
            contents.append(types.Part.from_text(text=prompt))
        
        model = model_name or settings.GEMINI_MODEL
        
        # Build generation config using utility function
        config = build_generation_config(
            model_name=model,
            temperature=temperature if temperature is not None else settings.GEMINI_TEMPERATURE,
            top_p=top_p if top_p is not None else settings.GEMINI_TOP_P,
            top_k=top_k if top_k is not None else settings.GEMINI_TOP_K,
            max_output_tokens=max_output_tokens if max_output_tokens is not None else settings.GEMINI_MAX_OUTPUT_TOKENS,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            default_thinking_budget=settings.GEMINI_THINKING_BUDGET,
            default_thinking_level=settings.GEMINI_THINKING_LEVEL,
        )
        
        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        text = getattr(response, "text", "") or ""
        
        # WHY: Extract token usage for cost monitoring and optimization insights
        usage_metadata = getattr(response, "usage_metadata", None)
        usage_info = {}
        if usage_metadata:
            usage_info = {
                "input_tokens": getattr(usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(usage_metadata, "total_token_count", 0),
            }
        
        return text, usage_info

    def parse_raw(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        thinking_level: Optional[str] = None,
    ) -> str:
        """
        Run general OCR (raw text) via Gemini on an image or PDF.
        
        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            prompt: Optional user prompt.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
            thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).
            
        Returns:
            Extracted raw text.
        """
        uploaded = self._upload_temp_file(file_bytes, file_name, mime_type)
        base_prompt = (
            "You are an OCR engine. Read the document and output the raw text,\n"
            "preserving natural reading order as much as possible.\n"
        )
        full_prompt = f"{base_prompt}\nUser prompt (optional): {prompt}" if prompt else base_prompt
        
        text, usage_info = self._call_model(
            uploaded,
            full_prompt,
            model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )
        
        # Log token usage
        if usage_info:
            logger.info(f"Token Usage (parse_raw) - Input: {usage_info.get('input_tokens', 0):,}, "
                        f"Output: {usage_info.get('output_tokens', 0):,}, "
                        f"Total: {usage_info.get('total_tokens', 0):,}")
        
        return text

    def parse_fields(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        thinking_level: Optional[str] = None,
    ) -> str:
        """
        Run structured field extraction via Gemini using a user-provided prompt.
        
        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            prompt: User prompt for extraction.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
            thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).
            
        Returns:
            Extracted fields as text (typically JSON).
        """
        uploaded = self._upload_temp_file(file_bytes, file_name, mime_type)
        default_guidance = (
            "Extract key fields from the document. If not specified otherwise,\n"
            "return a concise JSON object with clearly named keys."
        )
        user_prompt = prompt or "Extract key fields and return JSON."
        full_prompt = f"{default_guidance}\n\nUser prompt: {user_prompt}"
        
        text, usage_info = self._call_model(
            uploaded,
            full_prompt,
            model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )
        
        # Log token usage
        if usage_info:
            logger.info(f"Token Usage (parse_fields) - Input: {usage_info.get('input_tokens', 0):,}, "
                        f"Output: {usage_info.get('output_tokens', 0):,}, "
                        f"Total: {usage_info.get('total_tokens', 0):,}")
        
        return parse_markdown_json(text)

    def parse_document(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        thinking_level: Optional[str] = None,
    ) -> str:
        """
        Run document structure extraction via Gemini.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            prompt: User prompt for extraction.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
            thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).

        Returns:
            Extracted document structure as text (typically JSON).
        """
        uploaded = self._upload_temp_file(file_bytes, file_name, mime_type)
        default_guidance = (
            "Analyze the document structure and return a structured JSON representation of its content."
        )
        user_prompt = prompt or "Extract document structure as JSON."
        full_prompt = f"{default_guidance}\n\nUser prompt: {user_prompt}"

        text, usage_info = self._call_model(
            uploaded,
            full_prompt,
            model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )

        # Log token usage
        if usage_info:
            logger.info(f"Token Usage (parse_document) - Input: {usage_info.get('input_tokens', 0):,}, "
                        f"Output: {usage_info.get('output_tokens', 0):,}, "
                        f"Total: {usage_info.get('total_tokens', 0):,}")

        return parse_markdown_json(text)
