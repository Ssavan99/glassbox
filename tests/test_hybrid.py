import yaml

import engine.architectures.hybrid as hybrid
from engine.config import QUESTIONS_PATH, TOP_K
from engine.index import load_index


def _questions():
    return yaml.safe_load(QUESTIONS_PATH.read_text())


def _first_of_type(qtype: str) -> dict:
    for q in _questions():
        if q["type"] == qtype:
            return q
    raise AssertionError(f"no {qtype} question found in questions.yaml")


def _mock_complete(monkeypatch, text="mocked answer"):
    calls = []

    def _fake_complete(prompt, **params):
        calls.append(prompt)
        return {"text": text, "prompt_tokens": 10, "completion_tokens": 5}

    monkeypatch.setattr(hybrid, "complete", _fake_complete)
    return calls


def test_hybrid_produces_valid_trace(monkeypatch):
    _mock_complete(monkeypatch)
    question = _first_of_type("factual")["question"]

    trace = hybrid.HybridArchitecture().run(question)

    kinds = [n.kind for n in trace.nodes]
    assert kinds == [
        "embed_query",
        "retrieve_dense",
        "retrieve_sparse",
        "fuse",
        "rerank",
        "generate",
    ]
    trace.validate()


def test_fuse_node_has_two_parents(monkeypatch):
    _mock_complete(monkeypatch)
    question = _first_of_type("factual")["question"]

    trace = hybrid.HybridArchitecture().run(question)

    dense_id = next(n.id for n in trace.nodes if n.kind == "retrieve_dense")
    sparse_id = next(n.id for n in trace.nodes if n.kind == "retrieve_sparse")
    fuse_node = next(n for n in trace.nodes if n.kind == "fuse")

    assert len(fuse_node.parent_ids) == 2
    assert set(fuse_node.parent_ids) == {dense_id, sparse_id}


def test_fuse_genuinely_combines_both_lists():
    # Direct unit test of the RRF function: a chunk that only shows up in
    # the sparse list must still surface in the fused results with a
    # nonzero score, and same for a chunk that only shows up in the dense
    # list. Fusion must not silently drop a one-sided hit.
    dense_only = [("dense-only::0", 0.9), ("shared::0", 0.8), ("dense-only::1", 0.7)]
    sparse_only = [("sparse-only::0", 12.0), ("shared::0", 9.0), ("sparse-only::1", 5.0)]

    fused = hybrid.reciprocal_rank_fusion([dense_only, sparse_only])
    fused_ids = dict(fused)

    assert "dense-only::0" in fused_ids
    assert fused_ids["dense-only::0"] > 0
    assert "sparse-only::0" in fused_ids
    assert fused_ids["sparse-only::0"] > 0
    # the chunk found by both branches should outrank a chunk found by only one
    assert fused_ids["shared::0"] > fused_ids["dense-only::0"]
    assert fused_ids["shared::0"] > fused_ids["sparse-only::0"]


def test_hybrid_beats_naive_on_a_keyword_question(monkeypatch):
    """Phase 3 acceptance criterion: on a keyword-type question, Hybrid's
    final output contains a gold chunk that Naive's plain dense top-k misses.

    Question q21 ("What sampling flag and value should be set when running
    the golden dataset so evaluation scores stay comparable across runs?")
    paraphrases away from the literal terms ("temperature", "--temperature
    0.0") of note `temperature-and-sampling-controls`, and dense-only top-5
    retrieval misses that note entirely -- confirmed empirically below (this
    is exactly what NaiveArchitecture's retrieve_dense step would also
    return, since it's the same DenseStore.search call).

    BM25 catches it, RRF fusion folds that one-sided hit into the pool, and
    the cross-encoder reranks chunk ::1 to rank 1 of the final top-5 -- it
    independently contains "--temperature 0.0" (duplicated across the
    chunk-overlap boundary) *and* the "evaluation reproducibility ...
    comparable across runs" language the question is actually asking about,
    which is why the reranker prefers it over ::0. `gold_chunk_ids` for q21
    includes both chunks for exactly this reason.
    """
    _mock_complete(monkeypatch)
    q21 = next(q for q in _questions() if q["id"] == "q21")
    gold_ids = set(q21["gold_chunk_ids"])
    assert gold_ids == {
        "temperature-and-sampling-controls::0",
        "temperature-and-sampling-controls::1",
    }

    trace = hybrid.HybridArchitecture().run(q21["question"])

    # Confirm plain dense-only top-k (what NaiveArchitecture would return)
    # misses this note's chunks entirely.
    index = load_index()
    from engine.embedding import embed_texts

    query_vector = embed_texts([q21["question"]])[0]
    naive_dense_top5 = {cid for cid, _ in index.dense.search(query_vector, k=TOP_K)}
    assert not (gold_ids & naive_dense_top5), (
        "expected dense-only top-5 to miss both gold chunks for q21 -- if "
        "this fails, the corpus/embedding model changed and a different "
        "keyword question should be used for this test"
    )

    rerank_node = next(n for n in trace.nodes if n.kind == "rerank")
    final_ids = {r["chunk_id"] for r in rerank_node.payload["after"]}
    assert gold_ids & final_ids, (
        "expected Hybrid's final reranked output to contain at least one "
        "gold chunk for q21 that Naive's dense-only retrieval misses"
    )
