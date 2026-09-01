"""Heading-aware chunking.

Splits a note's body on `##` headings first, then packs paragraphs within
each section up to CHUNK_TARGET_TOKENS words (a whitespace-word-count proxy
for tokens), carrying CHUNK_OVERLAP_TOKENS words of overlap into the next
chunk whenever a section has to split across multiple chunks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.config import CHUNK_OVERLAP_TOKENS, CHUNK_TARGET_TOKENS
from engine.corpus import Note

_HEADING_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)


@dataclass
class Chunk:
    chunk_id: str
    note_id: str
    text: str
    heading: str | None


@dataclass
class _Section:
    heading: str | None
    text: str


def _split_sections(body: str) -> list[_Section]:
    """Split body text on `##` headings. Text before the first heading (if
    any) becomes a section with heading=None."""
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [_Section(heading=None, text=body.strip())] if body.strip() else []

    sections: list[_Section] = []
    preamble = body[: matches[0].start()].strip()
    if preamble:
        sections.append(_Section(heading=None, text=preamble))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_text = body[start:end].strip()
        sections.append(_Section(heading=heading, text=section_text))

    return sections


def _split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text)]
    return [p for p in paras if p]


def _pack_paragraphs(paragraphs: list[str]) -> list[str]:
    """Pack paragraphs into word-count-limited chunks with word overlap
    carried into the next chunk when a section spans multiple chunks."""
    chunks: list[str] = []
    current_words: list[str] = []

    for para in paragraphs:
        para_words = para.split()
        if current_words and len(current_words) + len(para_words) > CHUNK_TARGET_TOKENS:
            chunks.append(" ".join(current_words))
            overlap = (
                current_words[-CHUNK_OVERLAP_TOKENS:] if CHUNK_OVERLAP_TOKENS > 0 else []
            )
            current_words = list(overlap)
        current_words.extend(para_words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def chunk_note(note: Note) -> list[Chunk]:
    """Chunk a single note's body, heading-aware. Deterministic given the
    same note content: chunk_id = f"{note_id}::{index}" with a stable
    0-based index across the note's sections in order."""
    sections = _split_sections(note.body)
    chunks: list[Chunk] = []
    index = 0
    for section in sections:
        paragraphs = _split_paragraphs(section.text)
        if not paragraphs:
            continue
        for text in _pack_paragraphs(paragraphs):
            chunks.append(
                Chunk(
                    chunk_id=f"{note.note_id}::{index}",
                    note_id=note.note_id,
                    text=text,
                    heading=section.heading,
                )
            )
            index += 1
    return chunks


def chunk_notes(notes: list[Note]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for note in notes:
        chunks.extend(chunk_note(note))
    return chunks
