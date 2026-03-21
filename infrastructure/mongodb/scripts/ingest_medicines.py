"""Medicine data ingestion script for MongoDB with embeddings."""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer
from huggingface_hub import login

# Constants
BATCH_SIZE = 100
PROGRESS_INTERVAL = 100
INPUT_FILE = Path(__file__).parent.parent / "merged_medicines.json"

# Login to HuggingFace
login(token="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")

# Load embedding model
print("Loading Vietnamese embedding model...")
model = SentenceTransformer("AITeamVN/Vietnamese_Embedding_v2")
print(f"Model loaded. Embedding dimension: {model.get_sentence_embedding_dimension()}")


def load_medicines(filepath: Path) -> List[Dict[str, Any]]:
    """Load medicine data from JSON file."""
    print(f"Loading medicines from {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        medicines = json.load(f)
    print(f"Loaded {len(medicines)} medicine records")
    return medicines


def generate_embeddings_batch(names: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of medicine names."""
    embeddings = model.encode(names, convert_to_numpy=True)
    return [embedding.tolist() for embedding in embeddings]


def process_medicines(medicines: List[Dict[str, Any]]) -> None:
    """Process medicines and insert into MongoDB with embeddings."""
    from src.mongodb_client import get_medicine_collection

    collection = get_medicine_collection()

    total = len(medicines)
    processed = 0

    print(f"Processing {total} medicines in batches of {BATCH_SIZE}...")

    # Process in batches
    for i in range(0, total, BATCH_SIZE):
        batch = medicines[i : i + BATCH_SIZE]
        batch_names = [medicine.get("name", "") for medicine in batch]

        # Generate embeddings for the batch
        embeddings = generate_embeddings_batch(batch_names)

        # Prepare documents
        documents = []
        for medicine, embedding in zip(batch, embeddings):
            doc = medicine.copy()
            doc["search_vector"] = embedding
            documents.append(doc)

        # Insert batch into MongoDB
        collection.insert_many(documents)

        processed += len(batch)

        # Print progress
        if processed % PROGRESS_INTERVAL == 0 or processed == total:
            print(f"Progress: {processed}/{total} ({100*processed/total:.1f}%)")

    print(f"\nCompleted! Inserted {processed} medicines into MongoDB")

    # Verify insertion
    count = collection.count_documents({})
    print(f"Total documents in 'medicine' collection: {count}")


def main():
    """Main entry point for the ingestion script."""
    # Check if input file exists
    if not INPUT_FILE.exists():
        print(f"Error: Input file not found: {INPUT_FILE}")
        sys.exit(1)

    # Load medicines
    medicines = load_medicines(INPUT_FILE)

    # Process and insert
    process_medicines(medicines)

    print("\nIngestion completed successfully!")


if __name__ == "__main__":
    main()
