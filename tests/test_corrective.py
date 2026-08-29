import time

import yaml

import engine.architectures.corrective as corrective
from engine.config import CORRECTIVE_MAX_CORRECTIONS, QUESTIONS_PATH


def _all_questions() -> list[dict]:
    return yaml.safe_load(QUESTIONS_PATH.read_text())


def _factual_question() -> str:
    for q in _all_questions():
        if q["type"] == "factual":
            return q["question"]
    raise AssertionError("no factual question found in questions.yaml")


def _unanswerable_question() -> str:
    for q in _all_questions():
        if q["type"] == "unanswerable":
            return q["question"]
    raise AssertionError("no unanswerable question found in questions.yaml")


def _is_grade_prompt(prompt: str) -> bool:
    return "Chunks:" in prompt and "grading whether each retrieved chunk" in prompt


def _is_rewrite_prompt(prompt: str) -> bool:
    return "Current query:" in prompt


def _make_mock(grade_verdicts_sequence):
    """grade_verdicts_sequence: list of "all_correct" | "mostly_incorrect" values,
    one per grade call (extra calls beyond the list length reuse the last value).
    Returns (mock_fn, calls_list)."""
    calls = []

    def _fake_complete(prompt, json_schema=None, **params):
        calls.append(prompt)
        if json_schema is not None and _is_grade_prompt(prompt):
            idx = min(
                sum(1 for c in calls if _is_grade_prompt(c)) - 1,
                len(grade_verdicts_sequence) - 1,
            )
            mode = grade_verdicts_sequence[idx]
            # extract chunk ids present in the prompt
            chunk_ids = [
                line.strip()[1:-1]
                for line in prompt.splitlines()
                if line.strip().startswith("[") and line.strip().endswith("]")
            ]
            if mode == "all_correct":
                judgements = [
                    {"chunk_id": cid, "verdict": "correct", "reason": "relevant"}
                    for cid in chunk_ids
                ]
            else:
                judgements = [
                    {"chunk_id": cid, "verdict": "incorrect", "reason": "off-topic"}
                    for cid in chunk_ids
                ]
            payload = {"judgements": judgements}
            return {
                "text": "",
                "json": payload,
                "prompt_tokens": 30,
                "completion_tokens": 15,
            }
        if json_schema is not None and _is_rewrite_prompt(prompt):
            return {
                "text": "",
                "json": {"to": "a better search query", "reason": "narrower"},
                "prompt_tokens": 20,
                "completion_tokens": 10,
            }
        # generate (final answer) call
        return {"text": "mocked answer", "prompt_tokens": 40, "completion_tokens": 20}

    return _fake_complete, calls


def test_corrective_produces_valid_trace_when_sufficient_immediately(monkeypatch):
    mock_fn, calls = _make_mock(["all_correct"])
    monkeypatch.setattr(corrective, "complete", mock_fn)

    question = _factual_question()
    trace = corrective.CorrectiveArchitecture().run(question)

    kinds = [n.kind for n in trace.nodes]
    assert kinds == ["embed_query", "retrieve_dense", "grade", "generate"]
    trace.validate()


def test_corrective_triggers_one_correction(monkeypatch):
    mock_fn, calls = _make_mock(["mostly_incorrect", "all_correct"])
    monkeypatch.setattr(corrective, "complete", mock_fn)

    question = _factual_question()
    trace = corrective.CorrectiveArchitecture().run(question)

    kinds = [n.kind for n in trace.nodes]
    assert kinds == [
        "embed_query",
        "retrieve_dense",
        "grade",
        "rewrite",
        "embed_query",
        "retrieve_dense",
        "grade",
        "generate",
    ]
    trace.validate()

    # parent chaining: second embed_query's parent must be the rewrite node
    rewrite_node = next(n for n in trace.nodes if n.kind == "rewrite")
    second_embed = [n for n in trace.nodes if n.kind == "embed_query"][1]
    assert second_embed.parent_ids == [rewrite_node.id]

    assert trace.metrics.llm_calls == len(calls)


def test_correction_loop_terminates_at_the_cap(monkeypatch):
    mock_fn, calls = _make_mock(["mostly_incorrect"] * 10)
    monkeypatch.setattr(corrective, "complete", mock_fn)

    question = _factual_question()

    started = time.perf_counter()
    trace = corrective.CorrectiveArchitecture().run(question)
    elapsed = time.perf_counter() - started
    assert elapsed < 60

    trace.validate()

    grade_nodes = [n for n in trace.nodes if n.kind == "grade"]
    rewrite_nodes = [n for n in trace.nodes if n.kind == "rewrite"]
    generate_nodes = [n for n in trace.nodes if n.kind == "generate"]

    assert len(grade_nodes) == CORRECTIVE_MAX_CORRECTIONS + 1
    assert len(rewrite_nodes) == CORRECTIVE_MAX_CORRECTIONS
    assert len(generate_nodes) == 1


def test_grader_survives_malformed_or_incomplete_json(monkeypatch):
    question = _factual_question()
    calls = []
    seen_retrieved_ids = {}

    def _fake_complete(prompt, json_schema=None, **params):
        calls.append(prompt)
        if json_schema is not None and _is_grade_prompt(prompt):
            chunk_ids = [
                line.strip()[1:-1]
                for line in prompt.splitlines()
                if line.strip().startswith("[") and line.strip().endswith("]")
            ]
            seen_retrieved_ids["ids"] = chunk_ids
            # drop the first chunk_id's judgement, and add a phantom one
            judgements = [
                {"chunk_id": cid, "verdict": "correct", "reason": "ok"}
                for cid in chunk_ids[1:]
            ]
            judgements.append(
                {"chunk_id": "phantom::nonexistent", "verdict": "correct", "reason": "fake"}
            )
            return {
                "text": "",
                "json": {"judgements": judgements},
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }
        return {"text": "mocked answer", "prompt_tokens": 10, "completion_tokens": 5}

    monkeypatch.setattr(corrective, "complete", _fake_complete)

    trace = corrective.CorrectiveArchitecture().run(question)
    trace.validate()

    grade_node = next(n for n in trace.nodes if n.kind == "grade")
    judgement_ids = {j["chunk_id"] for j in grade_node.payload["judgements"]}
    retrieved_ids = set(seen_retrieved_ids["ids"])

    assert judgement_ids == retrieved_ids
    assert "phantom::nonexistent" not in judgement_ids

    missing_cid = seen_retrieved_ids["ids"][0]
    missing_judgement = next(
        j for j in grade_node.payload["judgements"] if j["chunk_id"] == missing_cid
    )
    assert missing_judgement["verdict"] == "ambiguous"


def test_llm_calls_counted_not_hardcoded(monkeypatch):
    mock_fn, calls = _make_mock(["mostly_incorrect", "all_correct"])
    monkeypatch.setattr(corrective, "complete", mock_fn)

    question = _factual_question()
    trace = corrective.CorrectiveArchitecture().run(question)

    assert trace.metrics.llm_calls == len(calls)


def test_real_end_to_end_factual_question():
    question = _factual_question()
    trace = corrective.CorrectiveArchitecture().run(question)
    trace.validate()
    assert trace.answer
    grade_count = sum(1 for n in trace.nodes if n.kind == "grade")
    assert 1 <= grade_count <= CORRECTIVE_MAX_CORRECTIONS + 1


def test_real_end_to_end_unanswerable_question():
    question = _unanswerable_question()
    trace = corrective.CorrectiveArchitecture().run(question)
    trace.validate()
    assert trace.answer
    grade_count = sum(1 for n in trace.nodes if n.kind == "grade")
    rewrite_count = sum(1 for n in trace.nodes if n.kind == "rewrite")
    assert 1 <= grade_count <= CORRECTIVE_MAX_CORRECTIONS + 1
    assert rewrite_count <= CORRECTIVE_MAX_CORRECTIONS
    print(
        f"\n[unanswerable] corrections used={rewrite_count}, "
        f"final answer preview={trace.answer[:200]!r}"
    )
