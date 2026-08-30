import yaml

import engine.architectures.agentic as agentic
from engine.config import QUESTIONS_PATH
from engine.graph_index import load_graph, seed_entities


def _all_questions() -> list[dict]:
    return yaml.safe_load(QUESTIONS_PATH.read_text())


def _question_of_type(qtype: str) -> str:
    for q in _all_questions():
        if q["type"] == qtype:
            return q["question"]
    raise AssertionError(f"no {qtype} question found in questions.yaml")


def _is_plan_prompt(prompt: str) -> bool:
    return "Decompose the following question" in prompt


def _is_reflect_prompt(prompt: str) -> bool:
    return "judging whether the retrieved evidence" in prompt


def _plan_response(sub_questions):
    return {
        "text": "",
        "json": {"sub_questions": sub_questions},
        "prompt_tokens": 20,
        "completion_tokens": 10,
    }


def _reflect_response(sufficient: bool):
    return {
        "text": "",
        "json": {
            "sufficient": sufficient,
            "reason": "mock reason",
            "next_action": "proceed" if sufficient else "retrieve_more",
        },
        "prompt_tokens": 15,
        "completion_tokens": 5,
    }


def _generate_response():
    return {"text": "mocked final answer", "prompt_tokens": 40, "completion_tokens": 20}


def _make_mock(sub_questions, reflect_sequence, plan_response=None):
    """reflect_sequence: list of bool, one per reflect call in order (extra
    calls beyond the list length reuse the last value). Returns (fn, calls)."""
    calls = []

    def _fake_complete(prompt, json_schema=None, **params):
        calls.append(prompt)
        if json_schema is not None and _is_plan_prompt(prompt):
            if plan_response is not None:
                return plan_response
            return _plan_response(sub_questions)
        if json_schema is not None and _is_reflect_prompt(prompt):
            idx = min(
                sum(1 for c in calls if _is_reflect_prompt(c)) - 1,
                len(reflect_sequence) - 1,
            )
            return _reflect_response(reflect_sequence[idx])
        return _generate_response()

    return _fake_complete, calls


# A sub-question confirmed (via seed_entities) to match a graph entity.
GRAPH_SUBQ = "What does LoRA freeze?"
# A sub-question confirmed to have zero graph entity matches but an
# ALL-CAPS acronym (MRR), so it should route to sparse.
SPARSE_SUBQ = "Explain RAG and MRR metrics briefly."


def test_agentic_produces_valid_trace_simple_case():
    mock_fn, calls = _make_mock([GRAPH_SUBQ], reflect_sequence=[True])

    import unittest.mock as mock

    with mock.patch.object(agentic, "complete", mock_fn):
        trace = agentic.AgenticArchitecture().run("some question")

    trace.validate()
    kinds = [n.kind for n in trace.nodes]
    assert kinds == ["plan", "route", "graph_seed", "graph_expand", "reflect", "generate"]
    assert trace.metrics.llm_calls == 3


def test_heuristic_route_picks_graph_when_entities_match():
    graph = load_graph()
    assert len(seed_entities(GRAPH_SUBQ, graph)) >= 1  # sanity check of fixture

    mock_fn, calls = _make_mock([GRAPH_SUBQ], reflect_sequence=[True])

    import unittest.mock as mock

    with mock.patch.object(agentic, "complete", mock_fn):
        trace = agentic.AgenticArchitecture().run("some question")

    route_nodes = [n for n in trace.nodes if n.kind == "route"]
    assert len(route_nodes) == 1
    assert route_nodes[0].payload["chosen"] == "graph"
    # heuristic route -- no LLM call attributable to it: only 3 completes
    # happened total (plan, reflect, generate), none of which are route work.
    assert trace.metrics.llm_calls == 3


def test_heuristic_route_picks_sparse_for_exact_tokens():
    graph = load_graph()
    assert seed_entities(SPARSE_SUBQ, graph) == []  # sanity check of fixture

    mock_fn, calls = _make_mock([SPARSE_SUBQ], reflect_sequence=[True])

    import unittest.mock as mock

    with mock.patch.object(agentic, "complete", mock_fn):
        trace = agentic.AgenticArchitecture().run("some question")

    route_nodes = [n for n in trace.nodes if n.kind == "route"]
    assert len(route_nodes) == 1
    assert route_nodes[0].payload["chosen"] == "sparse"


def test_retry_uses_a_different_tool_than_first_attempt():
    mock_fn, calls = _make_mock([GRAPH_SUBQ], reflect_sequence=[False, True])

    import unittest.mock as mock

    with mock.patch.object(agentic, "complete", mock_fn):
        trace = agentic.AgenticArchitecture().run("some question")

    trace.validate()
    route_nodes = [n for n in trace.nodes if n.kind == "route"]
    assert len(route_nodes) == 2
    assert route_nodes[0].payload["chosen"] != route_nodes[1].payload["chosen"]

    reflect_nodes = [n for n in trace.nodes if n.kind == "reflect"]
    assert len(reflect_nodes) == 2
    first_reflect_id = reflect_nodes[0].id

    # Find the retrieval node chained directly off the second route node,
    # and confirm the second route node's parent is the first reflect node
    # (not plan).
    assert route_nodes[1].parent_ids == [first_reflect_id]

    assert trace.metrics.llm_calls == 4  # plan + 2 reflects + generate


def test_worst_case_never_exceeds_caps():
    sub_questions = ["sub q 1 " + GRAPH_SUBQ, "sub q 2 " + SPARSE_SUBQ, "sub q 3 unrelated"]
    mock_fn, calls = _make_mock(sub_questions, reflect_sequence=[False] * 10)

    import unittest.mock as mock

    with mock.patch.object(agentic, "complete", mock_fn):
        trace = agentic.AgenticArchitecture().run("some worst-case question")

    trace.validate()

    route_nodes = [n for n in trace.nodes if n.kind == "route"]
    assert len(route_nodes) == 6

    generate_nodes = [n for n in trace.nodes if n.kind == "generate"]
    assert len(generate_nodes) == 1

    assert trace.metrics.llm_calls == 8


def test_generate_chains_to_every_subquestion_not_just_the_last():
    # generate's answer draws on chunks from every sub-question, so its
    # parent_ids must reflect that -- not just the last sub-question
    # processed, which would make earlier branches look like dead ends in
    # any DAG visualization even though their evidence feeds the answer.
    sub_questions = ["sub q 1 " + GRAPH_SUBQ, "sub q 2 " + SPARSE_SUBQ, "sub q 3 unrelated"]
    mock_fn, calls = _make_mock(sub_questions, reflect_sequence=[True, True, True])

    import unittest.mock as mock

    with mock.patch.object(agentic, "complete", mock_fn):
        trace = agentic.AgenticArchitecture().run("some multi-subquestion question")

    trace.validate()

    reflect_nodes = [n for n in trace.nodes if n.kind == "reflect"]
    generate_node = next(n for n in trace.nodes if n.kind == "generate")

    assert len(reflect_nodes) == 3  # one attempt per sub-question, all sufficient
    assert set(generate_node.parent_ids) == {n.id for n in reflect_nodes}
    assert len(generate_node.parent_ids) == len(set(generate_node.parent_ids))  # no dupes


def test_plan_survives_malformed_or_empty_response():
    malformed_responses = [
        {"text": "", "json": {}, "prompt_tokens": 5, "completion_tokens": 1},
        {"text": "", "json": [], "prompt_tokens": 5, "completion_tokens": 1},
        {"text": "", "json": "not a dict", "prompt_tokens": 5, "completion_tokens": 1},
        {"text": "", "json": {"sub_questions": []}, "prompt_tokens": 5, "completion_tokens": 1},
    ]

    import unittest.mock as mock

    for plan_response in malformed_responses:
        mock_fn, calls = _make_mock(
            [GRAPH_SUBQ], reflect_sequence=[True], plan_response=plan_response
        )
        with mock.patch.object(agentic, "complete", mock_fn):
            question = "What does LoRA freeze in fine-tuning?"
            trace = agentic.AgenticArchitecture().run(question)

        trace.validate()
        plan_node = next(n for n in trace.nodes if n.kind == "plan")
        assert plan_node.payload["sub_questions"] == [question]


def test_reflect_survives_malformed_or_non_dict_json():
    # Mirrors test_plan_survives_malformed_or_empty_response for _reflect's
    # own isinstance(parsed, dict) guard -- a malformed reflect response
    # must default sufficient=False (the safe default: if we can't tell,
    # assume insufficient and retry) rather than crashing or silently
    # treating garbage as a "sufficient" verdict. next_action is separately
    # defaulted based on whatever sufficient ends up being.
    cases = [
        # (reflect_json, expected_sufficient, expected_next_action)
        ([], False, "retrieve_more"),
        ("not a dict", False, "retrieve_more"),
        ({"sufficient": "not a bool"}, False, "retrieve_more"),
        # sufficient is a genuine bool here -- only next_action is malformed
        # and gets defaulted based on the (valid) sufficient value.
        ({"sufficient": True, "next_action": "not a valid action"}, True, "proceed"),
    ]

    import unittest.mock as mock

    for reflect_json, expected_sufficient, expected_next_action in cases:

        def _fake_complete(prompt, json_schema=None, rj=reflect_json, **params):
            if json_schema is not None and _is_plan_prompt(prompt):
                return _plan_response([GRAPH_SUBQ])
            if json_schema is not None and _is_reflect_prompt(prompt):
                return {"text": "", "json": rj, "prompt_tokens": 5, "completion_tokens": 1}
            return _generate_response()

        with mock.patch.object(agentic, "complete", _fake_complete):
            trace = agentic.AgenticArchitecture().run("some question")

        trace.validate()
        reflect_nodes = [n for n in trace.nodes if n.kind == "reflect"]
        assert reflect_nodes[0].payload["sufficient"] is expected_sufficient
        assert reflect_nodes[0].payload["next_action"] == expected_next_action
        # An insufficient judgement (malformed or not) triggers the retry
        # attempt (capped at 2, never crashing); a sufficient one stops at 1.
        assert len(reflect_nodes) == (1 if expected_sufficient else 2)


def test_duration_ms_is_populated():
    mock_fn, calls = _make_mock([GRAPH_SUBQ], reflect_sequence=[True])

    import unittest.mock as mock

    with mock.patch.object(agentic, "complete", mock_fn):
        trace = agentic.AgenticArchitecture().run("some question")

    for node in trace.nodes:
        assert node.duration_ms > 0, f"node {node.id} ({node.kind}) has duration_ms <= 0"
