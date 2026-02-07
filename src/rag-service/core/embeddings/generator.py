"""Embedding generator using Google Gemini."""
from typing import List, Optional
import asyncio
import os

from app.config import settings


class EmbeddingGenerator:
    """Generator for text embeddings using Google Gemini."""

    def __init__(self):
        """Initialize Gemini client lazily."""
        self._client = None
        self.model = settings.GEMINI_EMBEDDING_MODEL
        self.dim = settings.MILVUS_DIM

    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not set")

            # Use the older google.generativeai library which is more stable
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._client = genai
        return self._client

    async def generate(self, text: str) -> List[float]:
        """Generate embedding for single text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        client = self._get_client()

        # Run synchronous call in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_document"
            )
        )
        return result['embedding']

    async def generate_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """Generate embeddings for batch of texts.

        Args:
            texts: List of input texts
            batch_size: Batch size for API calls

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Process each text in batch
            for text in batch:
                embedding = await self.generate(text)
                all_embeddings.append(embedding)

        return all_embeddings

    async def generate_with_retry(
        self,
        text: str,
        max_retries: int = 3
    ) -> List[float]:
        """Generate embedding with retry logic.

        Args:
            text: Input text
            max_retries: Maximum retry attempts

        Returns:
            Embedding vector
        """
        for attempt in range(max_retries):
            try:
                return await self.generate(text)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return []
