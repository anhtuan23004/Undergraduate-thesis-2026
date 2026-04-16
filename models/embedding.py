import os

from huggingface_hub import login
from sentence_transformers import SentenceTransformer

_model = None


def get_model():
    """Get or create the embedding model (lazy loading).

    This function returns a singleton SentenceTransformer model.
    The model is loaded on first call, not at module import time.

    Raises:
        ValueError: If HF_TOKEN environment variable is not set.
    """
    global _model
    if _model is None:
        hf_token = os.environ.get("HF_TOKEN")
        if hf_token:
            login(token=hf_token)
        else:
            raise ValueError(
                "HF_TOKEN environment variable is not set. "
                "Please set your HuggingFace token to access the embedding model."
            )
        _model = SentenceTransformer("AITeamVN/Vietnamese_Embedding_v2")
    return _model


def encode_texts(sentences):
    """Encode sentences to embeddings."""
    return get_model().encode(sentences)
