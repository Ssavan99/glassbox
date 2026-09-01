from engine.chunking import chunk_note
from engine.corpus import Note


def _note(body: str, note_id: str = "test-note") -> Note:
    return Note(
        note_id=note_id,
        title="Test Note",
        tags=["tag-one"],
        entities=["entity one"],
        created="2026-01-15",
        body=body,
    )


def test_chunking_is_deterministic():
    body = (
        "## Intro\n\n"
        "This is the first paragraph of the intro section. " * 3
        + "\n\n"
        "This is a second paragraph in the intro section. " * 3
        + "\n\n"
        "## Details\n\n"
        "This is the details section body text here. " * 5
    )
    note = _note(body)

    chunks_a = chunk_note(note)
    chunks_b = chunk_note(note)

    assert [c.chunk_id for c in chunks_a] == [c.chunk_id for c in chunks_b]
    assert [c.text for c in chunks_a] == [c.text for c in chunks_b]


def test_heading_tracked_per_chunk_and_chunk_id_format():
    body = (
        "## First Section\n\n"
        "Paragraph in the first section.\n\n"
        "## Second Section\n\n"
        "Paragraph in the second section."
    )
    note = _note(body, note_id="my-note")

    chunks = chunk_note(note)

    assert len(chunks) == 2
    assert chunks[0].heading == "First Section"
    assert chunks[1].heading == "Second Section"

    for i, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"my-note::{i}"
        assert chunk.note_id == "my-note"


def test_note_with_no_headings_has_null_heading():
    body = "Just a plain paragraph with no heading at all."
    note = _note(body)

    chunks = chunk_note(note)

    assert len(chunks) == 1
    assert chunks[0].heading is None
    assert chunks[0].chunk_id == "test-note::0"


def test_long_section_splits_into_multiple_chunks_with_overlap():
    # Each paragraph is ~60 words; enough paragraphs to exceed the ~250
    # word target and force a split within one section.
    paragraph = "word " * 60
    body = "## Big Section\n\n" + "\n\n".join([paragraph] * 6)
    note = _note(body)

    chunks = chunk_note(note)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.heading == "Big Section"
    # chunk ids remain sequential and well-formed
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"test-note::{i}"
