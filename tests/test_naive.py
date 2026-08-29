import yaml

import engine.architectures.naive as naive
from engine.config import QUESTIONS_PATH, TOP_K


def _factual_question() -> str:
    questions = yaml.safe_load(QUESTIONS_PATH.read_text())
    for q in questions:
        if q["type"] == "factual":
            return q["question"]
    raise AssertionError("no factual question found in questions.yaml")


def _mock_complete(monkeypatch, text="mocked answer"):
    calls = []

    def _fake_complete(prompt, **params):
        calls.append(prompt)
        return {"text": text, "prompt_tokens": 10, "completion_tokens": 5}

    monkeypatch.setattr(naive, "complete", _fake_complete)
    return calls


def test_naive_produces_valid_trace(monkeypatch):
    _mock_complete(monkeypatch)
    question = _factual_question()

    trace = naive.NaiveArchitecture().run(question)

    kinds = [n.kind for n in trace.nodes]
    assert kinds == ["embed_query", "retrieve_dense", "generate"]
    trace.validate()


def test_naive_retrieves_topk(monkeypatch):
    _mock_complete(monkeypatch)
    question = _factual_question()

    trace = naive.NaiveArchitecture().run(question)

    retrieve_node = next(n for n in trace.nodes if n.kind == "retrieve_dense")
    assert len(retrieve_node.payload["results"]) == TOP_K


def test_naive_cites_chunks_in_answer(monkeypatch):
    canned = "The answer is described in [some-note::0]."
    _mock_complete(monkeypatch, text=canned)
    question = _factual_question()

    trace = naive.NaiveArchitecture().run(question)

    assert trace.answer == canned
