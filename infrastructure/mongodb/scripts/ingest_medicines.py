"""Medicine data ingestion script for MongoDB with embeddings."""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer
from huggingface_hub import login

BATCH_SIZE = 100
PROGRESS_INTERVAL = 100
INPUT_FILE = Path(__file__).parent.parent / "merged_medicines.json"


def _get_model() -> SentenceTransformer:
    """Get or create the embedding model with HuggingFace authentication."""
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise ValueError(
            "HF_TOKEN environment variable is not set. "
            "Please set your HuggingFace token to access the embedding model."
        )
    login(token=hf_token)
    return SentenceTransformer("AITeamVN/Vietnamese_Embedding_v2")


def load_medicines(filepath: Path) -> List[Dict[str, Any]]:
    """Load medicine data from JSON file."""
    print(f"Loading medicines from {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        medicines = json.load(f)
    print(f"Loaded {len(medicines)} medicine records")
    return medicines


def generate_embeddings_batch(model: SentenceTransformer, names: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of medicine names."""
    embeddings = model.encode(names, convert_to_numpy=True)
    return [embedding.tolist() for embedding in embeddings]


def process_medicines(medicines: List[Dict[str, Any]]) -> None:
    """Process medicines and insert into MongoDB with embeddings."""
    sys.path.insert(0, str(PROJECT_ROOT / "src" / "agent-service"))
    from mongodb_client import get_medicine_collection

    print("Loading Vietnamese embedding model...")
    model = _get_model()
    print(f"Model loaded. Embedding dimension: {model.get_sentence_embedding_dimension()}")

    collection = get_medicine_collection()

    total = len(medicines)
    processed = 0

    print(f"Processing {total} medicines in batches of {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = medicines[i : i + BATCH_SIZE]
        batch_names = [medicine.get("name", "") for medicine in batch]

        embeddings = generate_embeddings_batch(model, batch_names)

        documents = []
        for medicine, embedding in zip(batch, embeddings):
            doc = medicine.copy()
            doc["search_vector"] = embedding
            documents.append(doc)

        collection.insert_many(documents)

        processed += len(batch)

        if processed % PROGRESS_INTERVAL == 0 or processed == total:
            print(f"Progress: {processed}/{total} ({100 * processed / total:.1f}%)")

    print(f"\nCompleted! Inserted {processed} medicines into MongoDB")

    count = collection.count_documents({})
    print(f"Total documents in 'medicine' collection: {count}")


def main():
    """Main entry point for the ingestion script."""
    if not INPUT_FILE.exists():
        print(f"Error: Input file not found: {INPUT_FILE}")
        sys.exit(1)

    medicines = load_medicines(INPUT_FILE)
    process_medicines(medicines)

    print("\nIngestion completed successfully!")


if __name__ == "__main__":
    main()
