"""Embedding generator using Google Gemini."""
import asyncio
from typing import List

import google.generativeai as genai

from app.config import settings


class EmbeddingGenerator:
    """Generator for text embeddings using Google Gemini."""

    def __init__(self) -> None:
        """Initialize Gemini client lazily."""
        self._client: genai | None = None
        self._model = settings.GEMINI_EMBEDDING_MODEL
        self._dimension = settings.MILVUS_DIM

    def _initialize_client(self) -> genai:
        """Lazy initialization of Gemini client."""
        if self._client is not None:
            return self._client

        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")

        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._client = genai
        return self._client

    async def generate(
        self,
        text: str,
        task_type: str = "retrieval_document"
    ) -> List[float]:
        """Generate embedding for single text.

        Args:
            text: Input text
            task_type: Type of embedding task

        Returns:
            Embedding vector
        """
        client = self._initialize_client()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.embed_content(
                model=self._model,
                content=text,
                task_type=task_type
            )
        )
        return result["embedding"]

    async def generate_batch(
        self,
        texts: List[str],
        task_type: str = "retrieval_document"
    ) -> List[List[float]]:
        """Generate embeddings for batch of texts.

        Args:
            texts: List of input texts
            task_type: Type of embedding task

        Returns:
            List of embedding vectors
        """
        tasks = [
            self.generate(text, task_type=task_type)
            for text in texts
        ]
        return await asyncio.gather(*tasks)

    async def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        return await self.generate(query, task_type="retrieval_query")
