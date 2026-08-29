import yaml

import engine.architectures.hyde as hyde
from engine.config import QUESTIONS_PATH

HYPOTHETICAL_PASSAGE = (
    "Quokkas are small marsupials native to Rottnest Island that photosynthesize "
    "sunlight through specialized dorsal chlorophyll patches, a trait unrelated "
    "to any retrieval-augmented generation architecture."
)


def _all_questions() -> list[dict]:
    return yaml.safe_load(QUESTIONS_PATH.read_text())


def _factual_question() -> str:
    for q in _all_questions():
        if q["type"] == "factual":
            return q["question"]
    raise AssertionError("no factual question found in questions.yaml")


def _mock_complete(monkeypatch, module, hypothetical=HYPOTHETICAL_PASSAGE, answer="mocked answer"):
    """Mock `complete` to distinguish the hyde-draft call from the final
    answer-generation call by inspecting the prompt text (the hyde prompt
    ends with 'Hypothetical passage:', the answer prompt ends with a
    citation instruction)."""
    calls = []

    def _fake_complete(prompt, **params):
        calls.append(prompt)
        if "Hypothetical passage:" in prompt:
            return {"text": hypothetical, "prompt_tokens": 10, "completion_tokens": 5}
        return {"text": answer, "prompt_tokens": 20, "completion_tokens": 8}

    monkeypatch.setattr(module, "complete", _fake_complete)
    return calls


def test_hyde_produces_valid_trace(monkeypatch):
    _mock_complete(monkeypatch, hyde)
    question = _factual_question()

    trace = hyde.HyDEArchitecture().run(question)

    kinds = [n.kind for n in trace.nodes]
    assert kinds == ["generate_hypothetical", "embed_query", "retrieve_dense", "generate"]
    trace.validate()


def test_hyde_embeds_the_hypothetical_not_the_question(monkeypatch):
    _mock_complete(monkeypatch, hyde)
    question = _factual_question()
    assert question != HYPOTHETICAL_PASSAGE

    embedded_texts = []
    real_embed_texts = hyde.embed_texts

    def _spy_embed_texts(texts):
        embedded_texts.append(list(texts))
        return real_embed_texts(texts)

    monkeypatch.setattr(hyde, "embed_texts", _spy_embed_texts)

    hyde.HyDEArchitecture().run(question)

    # exactly one embedding call happened (the hypothetical passage), and the
    # question itself was never passed to embed_texts.
    all_embedded = [t for call in embedded_texts for t in call]
    assert HYPOTHETICAL_PASSAGE in all_embedded
    assert question not in all_embedded


def test_hyde_llm_calls_is_two(monkeypatch):
    _mock_complete(monkeypatch, hyde)
    question = _factual_question()

    trace = hyde.HyDEArchitecture().run(question)

    assert trace.metrics.llm_calls == 2


def test_hyde_differs_from_naive_on_some_question():
    try:
        import engine.architectures.naive as naive
    except ImportError:
        import pytest

        pytest.skip("engine/architectures/naive.py not available yet")
        return

    import pytest

    questions = _all_questions()
    found_difference = False
    checked = []

    for q in questions:
        question = q["question"]

        # Drift the hypothetical passage away from the question's own
        # vocabulary so retrieval plausibly differs, while still mocking
        # complete() to distinguish the two call sites by prompt shape.
        def _fake_complete(prompt, **params):
            if "Hypothetical passage:" in prompt:
                return {
                    "text": HYPOTHETICAL_PASSAGE,
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                }
            return {"text": "mocked answer", "prompt_tokens": 20, "completion_tokens": 8}

        import pytest as _pytest

        mp = _pytest.MonkeyPatch()
        try:
            mp.setattr(naive, "complete", _fake_complete)
            mp.setattr(hyde, "complete", _fake_complete)

            naive_trace = naive.NaiveArchitecture().run(question)
            hyde_trace = hyde.HyDEArchitecture().run(question)
        finally:
            mp.undo()

        naive_ids = {
            r["chunk_id"]
            for n in naive_trace.nodes
            if n.kind == "retrieve_dense"
            for r in n.payload["results"]
        }
        hyde_ids = {
            r["chunk_id"]
            for n in hyde_trace.nodes
            if n.kind == "retrieve_dense"
            for r in n.payload["results"]
        }
        checked.append(question)
        if naive_ids != hyde_ids:
            found_difference = True
            break

    assert found_difference, (
        f"expected HyDE retrieval to differ from naive on at least one of "
        f"{len(checked)} questions tried, but it matched every time"
    )
