"""Load and parse corpus notes from CORPUS_DIR.

Each note is a markdown file with YAML frontmatter:

    ---
    title: "Human-Readable Title"
    tags: [tag-one, tag-two]
    entities: [entity one, entity two, entity three]
    created: 2026-01-15
    ---
    body...

`note_id` is the filename stem (kebab-case).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

import yaml

_FRONTMATTER_DELIM = "---"


@dataclass
class Note:
    note_id: str
    title: str
    tags: list[str]
    entities: list[str]
    created: str
    body: str


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a note's raw text into (frontmatter dict, body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        raise ValueError("note is missing opening frontmatter delimiter '---'")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("note is missing closing frontmatter delimiter '---'")

    frontmatter_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")

    data = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter did not parse to a mapping")
    return data, body


def _coerce_created(value) -> str:
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return str(value)


def load_note(path: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    data, body = _parse_frontmatter(text)
    return Note(
        note_id=path.stem,
        title=str(data.get("title", "")),
        tags=list(data.get("tags", []) or []),
        entities=list(data.get("entities", []) or []),
        created=_coerce_created(data.get("created", "")),
        body=body,
    )


def load_corpus(corpus_dir: Path) -> list[Note]:
    """Load every .md note under corpus_dir, sorted deterministically by note_id."""
    paths = sorted(corpus_dir.glob("*.md"), key=lambda p: p.stem)
    return [load_note(p) for p in paths]
