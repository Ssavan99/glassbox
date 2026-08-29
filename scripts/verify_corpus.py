#!/usr/bin/env python3
"""Standalone corpus verifier for corpus/notes/.

Parses YAML frontmatter on every note, checks the frontmatter shape, and
reports/enforces the structural guarantees the rest of the pipeline (and the
eval-question-writing pass) depend on:

  - total note count >= 55
  - entity-frequency table (which canonical entities recur across notes)
  - count of entities appearing in >= 3 distinct notes >= 40

Run: python scripts/verify_corpus.py
Exits non-zero with a clear message if either threshold is not met.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "corpus" / "notes"

MIN_NOTES = 55
MIN_ENTITIES_AT_3 = 40

REQUIRED_FIELDS = ("title", "tags", "entities", "created")


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: missing frontmatter delimiter '---' at top")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path.name}: malformed frontmatter block")
    raw = parts[1]
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: frontmatter did not parse to a mapping")
    for field in REQUIRED_FIELDS:
        if field not in data:
            raise ValueError(f"{path.name}: frontmatter missing required field '{field}'")
    if not isinstance(data["entities"], list) or not data["entities"]:
        raise ValueError(f"{path.name}: 'entities' must be a non-empty list")
    if not isinstance(data["tags"], list) or not data["tags"]:
        raise ValueError(f"{path.name}: 'tags' must be a non-empty list")
    body = parts[2].strip()
    word_count = len(body.split())
    return {
        "path": path,
        "title": data["title"],
        "tags": data["tags"],
        "entities": [str(e).strip().lower() for e in data["entities"]],
        "created": data["created"],
        "word_count": word_count,
    }


def main() -> int:
    if not NOTES_DIR.is_dir():
        print(f"FAIL: notes directory not found: {NOTES_DIR}")
        return 1

    note_paths = sorted(NOTES_DIR.glob("*.md"))
    notes = []
    errors = []
    for path in note_paths:
        try:
            notes.append(parse_frontmatter(path))
        except Exception as exc:  # noqa: BLE001 - we want to report every bad file
            errors.append(str(exc))

    if errors:
        print("FAIL: frontmatter errors found:")
        for e in errors:
            print(f"  - {e}")
        return 1

    total_notes = len(notes)

    entity_counter: Counter[str] = Counter()
    for note in notes:
        for entity in set(note["entities"]):  # count each entity once per note
            entity_counter[entity] += 1

    entities_at_3_plus = {e: c for e, c in entity_counter.items() if c >= 3}

    print("=" * 60)
    print("CORPUS VERIFICATION REPORT")
    print("=" * 60)
    print(f"Total notes:                    {total_notes}")
    print(f"Distinct entities:               {len(entity_counter)}")
    print(f"Entities appearing in >=3 notes: {len(entities_at_3_plus)}")
    print()

    low_word = [n for n in notes if n["word_count"] < 250 or n["word_count"] > 700]
    if low_word:
        print(f"Notes outside the ~300-600 word target ({len(low_word)}):")
        for n in low_word:
            print(f"  - {n['path'].name}: {n['word_count']} words")
        print()

    print("Entity frequency table (entity -> note count), sorted by count desc:")
    for entity, count in sorted(entity_counter.items(), key=lambda kv: (-kv[1], kv[0])):
        marker = " *" if count >= 3 else ""
        print(f"  {count:3d}  {entity}{marker}")
    print()

    ok = True
    if total_notes < MIN_NOTES:
        print(f"FAIL: total note count {total_notes} < required minimum {MIN_NOTES}")
        ok = False
    if len(entities_at_3_plus) < MIN_ENTITIES_AT_3:
        print(
            f"FAIL: entities appearing in >=3 notes = {len(entities_at_3_plus)} "
            f"< required minimum {MIN_ENTITIES_AT_3}"
        )
        ok = False

    if ok:
        print(
            f"PASS: {total_notes} notes, {len(entities_at_3_plus)} entities with >=3 occurrences."
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
