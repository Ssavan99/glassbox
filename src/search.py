import json
from pathlib import Path
from sentence_transformers import SentenceTransformer

from utils import cosine_similarity


DATA_FILE = Path("data/embeddings.json")
MODEL_NAME = "all-MiniLM-L6-v2"


def load_stored_chunks():
    """
    Loads chunks and embeddings from JSON storage.
    """
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            "No embeddings found. Run this first: python src/embed_notes.py"
        )

    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def search_notes(query, top_k=3):
    """
    Searches notes using semantic similarity.
    """
    model = SentenceTransformer(MODEL_NAME)

    stored_chunks = load_stored_chunks()

    query_embedding = model.encode(query).tolist()

    results = []

    for chunk in stored_chunks:
        score = cosine_similarity(query_embedding, chunk["embedding"])

        results.append({
            "score": score,
            "source": chunk["source"],
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"]
        })

    results.sort(key=lambda item: item["score"], reverse=True)

    return results[:top_k]


def main():
    print("Second Brain Semantic Search")
    print("Type 'exit' to quit.\n")

    while True:
        query = input("Ask something: ")

        if query.lower() == "exit":
            break

        results = search_notes(query)

        print("\nTop results:\n")

        for index, result in enumerate(results, start=1):
            print(f"{index}. Score: {result['score']:.4f}")
            print(f"Source: {result['source']} | Chunk: {result['chunk_id']}")
            print(result["text"])
            print("-" * 70)

        print()


if __name__ == "__main__":
    main()