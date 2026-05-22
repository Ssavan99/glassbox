from pathlib import Path


NOTES_DIR = Path("notes")


def read_note_files():
    """
    Reads all .txt and .md files inside the notes folder.
    """
    note_files = list(NOTES_DIR.glob("*.md")) + list(NOTES_DIR.glob("*.txt"))

    notes = []

    for file_path in note_files:
        text = file_path.read_text(encoding="utf-8")

        notes.append({
            "source": file_path.name,
            "text": text
        })

    return notes


def chunk_text(text):
    """
    Splits text into chunks.

    For Day 1, we keep chunking simple:
    one paragraph = one chunk.

    Later, we can improve this with:
    - max token limits
    - overlapping chunks
    - headings
    - metadata
    """
    paragraphs = text.split("\n\n")

    chunks = []

    for paragraph in paragraphs:
        cleaned = paragraph.strip()

        if cleaned:
            chunks.append(cleaned)

    return chunks


def chunk_all_notes():
    """
    Reads all notes and converts them into searchable chunks.
    """
    notes = read_note_files()
    all_chunks = []

    for note in notes:
        chunks = chunk_text(note["text"])

        for index, chunk in enumerate(chunks):
            all_chunks.append({
                "source": note["source"],
                "chunk_id": index,
                "text": chunk
            })

    return all_chunks


if __name__ == "__main__":
    chunks = chunk_all_notes()

    print(f"Created {len(chunks)} chunks:\n")

    for chunk in chunks:
        print(f"[{chunk['source']} - chunk {chunk['chunk_id']}]")
        print(chunk["text"])
        print("-" * 50)