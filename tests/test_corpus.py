import pytest

from engine.corpus import load_corpus, load_note


def _write_note(tmp_path, filename: str, frontmatter: str, body: str = "Body text.") -> None:
    (tmp_path / filename).write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")


def test_load_note_accepts_a_real_list(tmp_path):
    _write_note(
        tmp_path,
        "good-note.md",
        'title: "Good Note"\ntags: [tag-one]\n'
        "entities: [entity one, entity two]\ncreated: 2026-01-01",
    )
    note = load_note(tmp_path / "good-note.md")
    assert note.entities == ["entity one", "entity two"]
    assert note.tags == ["tag-one"]


def test_load_note_rejects_bare_string_entities(tmp_path):
    # A missing `[...]` around a single entity parses as a bare YAML
    # scalar (a str), not a one-item list -- this must raise, not silently
    # split into characters via list(str).
    _write_note(
        tmp_path,
        "bad-note.md",
        'title: "Bad Note"\ntags: [tag-one]\nentities: some-term\ncreated: 2026-01-01',
    )
    with pytest.raises(ValueError, match="entities.*must be a YAML list"):
        load_note(tmp_path / "bad-note.md")


def test_load_note_rejects_bare_string_tags(tmp_path):
    _write_note(
        tmp_path,
        "bad-note.md",
        'title: "Bad Note"\ntags: some-tag\nentities: [entity one]\ncreated: 2026-01-01',
    )
    with pytest.raises(ValueError, match="tags.*must be a YAML list"):
        load_note(tmp_path / "bad-note.md")


def test_load_note_defaults_missing_entities_to_empty_list(tmp_path):
    _write_note(tmp_path, "sparse-note.md", 'title: "Sparse Note"\ncreated: 2026-01-01')
    note = load_note(tmp_path / "sparse-note.md")
    assert note.entities == []
    assert note.tags == []


def test_load_corpus_loads_the_real_corpus_without_error():
    from engine.config import CORPUS_DIR

    notes = load_corpus(CORPUS_DIR)
    assert len(notes) >= 55
    assert all(isinstance(n.entities, list) for n in notes)
    assert all(isinstance(n.tags, list) for n in notes)
