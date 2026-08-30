from engine.index import ChunkRecord
from engine.prompts import SYSTEM_PREAMBLE, build_answer_prompt, build_hyde_prompt


def test_system_preamble_gives_no_fake_slug_shaped_example_to_echo():
    # Phase 6.2 regression: the old preamble's "e.g. [chunk-id::0]" was
    # sometimes echoed verbatim by the model as a fake citation instead of a
    # real chunk id. The fixed preamble must not contain any bracketed,
    # slug-shaped example the model could copy as a plausible-looking but
    # fake citation.
    assert "chunk-id::" not in SYSTEM_PREAMBLE
    assert "[" not in SYSTEM_PREAMBLE  # no bracketed example anywhere


def test_system_preamble_still_instructs_real_citation_behavior():
    assert "square brackets" in SYSTEM_PREAMBLE
    assert "never invent an id" in SYSTEM_PREAMBLE


def test_build_hyde_prompt_never_uses_the_citation_preamble():
    # HyDE's hypothetical-passage prompt isn't user-facing and was never
    # meant to instruct citation -- confirms fixing SYSTEM_PREAMBLE only
    # invalidates the cache for each architecture's final generate node
    # (and not HyDE's separate generate_hypothetical step).
    prompt = build_hyde_prompt("How does chunk size affect retrieval quality?")
    assert SYSTEM_PREAMBLE not in prompt
    assert "chunk-id" not in prompt


def test_build_answer_prompt_includes_the_fixed_preamble_and_real_chunk_labels():
    chunk = ChunkRecord(
        chunk_id="full-fine-tuning-vs-adapters::0",
        note_id="full-fine-tuning-vs-adapters",
        heading="",
        text="LoRA freezes the base model's weights.",
    )
    prompt = build_answer_prompt("What is LoRA?", [chunk])
    assert SYSTEM_PREAMBLE in prompt
    assert "[full-fine-tuning-vs-adapters::0]" in prompt
    assert "chunk-id::" not in prompt
