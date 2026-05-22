import json
from pathlib import Path
from sentence_transformers import SentenceTransformer

from chunk_notes import chunk_all_notes


DATA_DIR = Path("data")
EMBEDDINGS_FILE = DATA_DIR / "embeddings.json"

MODEL_NAME = "all-MiniLM-L6-v2"


def main():
    """
    Creates embeddings for all note chunks and stores them in JSON.
    """
    DATA_DIR.mkdir(exist_ok=True)

    print("Loading local embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    print("Chunking notes...")
    chunks = chunk_all_notes()

    print(f"Generating embeddings for {len(chunks)} chunks...")

    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts)

    stored_chunks = []

    for chunk, embedding in zip(chunks, embeddings):
        stored_chunks.append({
            "source": chunk["source"],
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "embedding": embedding.tolist()
        })

    with EMBEDDINGS_FILE.open("w", encoding="utf-8") as file:
        json.dump(stored_chunks, file, indent=2)

    print(f"Saved embeddings to {EMBEDDINGS_FILE}")


if __name__ == "__main__":
    main()