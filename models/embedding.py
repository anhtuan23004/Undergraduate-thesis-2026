from sentence_transformers import SentenceTransformer
from huggingface_hub import login
import os

# Login to HuggingFace
login(token=os.environ.get("HF_TOKEN", "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"))

# Lazy-loaded model singleton
_model = None


def get_model():
    """Get or create the embedding model (lazy loading).

    This function returns a singleton SentenceTransformer model.
    The model is loaded on first call, not at module import time.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer("AITeamVN/Vietnamese_Embedding_v2")
    return _model


# For direct encoding when needed
def encode_texts(sentences):
    """Encode sentences to embeddings."""
    return get_model().encode(sentences)
