"""The trace schema — the contract between the Python engine and the frontend.

A trace is a DAG of nodes. Loops are unrolled into distinct nodes with real
parent edges, which is what lets one schema cover linear, branching, looping,
and graph-traversal pipelines uniformly. See repo-plans/glassbox_PLAN.md §3.2
for the full spec (the payload-shape-by-kind table lives there, not here,
since it documents architecture code rather than validating it).

Frozen after Phase 2. Changing NODE_KINDS or the Node/Trace shape means
migrating every recorded trace under artifacts/traces/ and every frontend
renderer that switches on `kind`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

NODE_KINDS = frozenset(
    {
        "embed_query",
        "retrieve_dense",
        "retrieve_sparse",
        "fuse",
        "rerank",
        "generate_hypothetical",
        "grade",
        "rewrite",
        "graph_seed",
        "graph_expand",
        "plan",
        "reflect",
        "route",
        "generate",
    }
)


class TraceValidationError(ValueError):
    pass


@dataclass
class Node:
    id: str
    kind: str
    label: str
    parent_ids: list[str]
    explain: str
    payload: dict
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "parent_ids": list(self.parent_ids),
            "duration_ms": self.duration_ms,
            "explain": self.explain,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Node:
        return cls(
            id=d["id"],
            kind=d["kind"],
            label=d["label"],
            parent_ids=list(d.get("parent_ids", [])),
            duration_ms=d.get("duration_ms", 0.0),
            explain=d["explain"],
            payload=d.get("payload", {}),
        )


@dataclass
class Metrics:
    latency_ms: float
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int

    def to_dict(self) -> dict:
        return {
            "latency_ms": self.latency_ms,
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Metrics:
        return cls(
            latency_ms=d["latency_ms"],
            llm_calls=d["llm_calls"],
            prompt_tokens=d["prompt_tokens"],
            completion_tokens=d["completion_tokens"],
        )


@dataclass
class Trace:
    trace_id: str
    architecture: str
    question: str
    answer: str
    metrics: Metrics
    nodes: list[Node]

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "architecture": self.architecture,
            "question": self.question,
            "answer": self.answer,
            "metrics": self.metrics.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Trace:
        return cls(
            trace_id=d["trace_id"],
            architecture=d["architecture"],
            question=d["question"],
            answer=d["answer"],
            metrics=Metrics.from_dict(d["metrics"]),
            nodes=[Node.from_dict(n) for n in d["nodes"]],
        )

    def validate(self) -> None:
        """Raise TraceValidationError on an unknown kind, a dangling parent,
        a duplicate node id, or a cycle. Called by TraceBuilder.build() and
        by anything deserializing a trace from disk."""
        if not self.nodes:
            raise TraceValidationError(f"{self.trace_id}: trace has no nodes")

        seen_ids: set[str] = set()
        for node in self.nodes:
            if node.id in seen_ids:
                raise TraceValidationError(f"{self.trace_id}: duplicate node id {node.id!r}")
            seen_ids.add(node.id)
            if node.kind not in NODE_KINDS:
                raise TraceValidationError(
                    f"{self.trace_id}: unknown node kind {node.kind!r} on {node.id!r}"
                )

        for node in self.nodes:
            for parent_id in node.parent_ids:
                if parent_id not in seen_ids:
                    raise TraceValidationError(
                        f"{self.trace_id}: {node.id!r} has dangling parent {parent_id!r}"
                    )

        self._check_acyclic()

    def _check_acyclic(self) -> None:
        children: dict[str, list[str]] = {n.id: [] for n in self.nodes}
        for node in self.nodes:
            for parent_id in node.parent_ids:
                children[parent_id].append(node.id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n.id: WHITE for n in self.nodes}

        def visit(node_id: str) -> None:
            color[node_id] = GRAY
            for child_id in children[node_id]:
                if color[child_id] == GRAY:
                    raise TraceValidationError(f"{self.trace_id}: cycle involving {child_id!r}")
                if color[child_id] == WHITE:
                    visit(child_id)
            color[node_id] = BLACK

        for node in self.nodes:
            if color[node.id] == WHITE:
                visit(node.id)


class TraceBuilder:
    """Incrementally assembles a Trace while an architecture runs.

    Usage:
        b = TraceBuilder(architecture="naive", question=question)
        n1 = b.node("embed_query", "Embed the question", parents=[], explain="...", dims=384)
        n2 = b.node("retrieve_dense", "Top-5 dense retrieval", parents=[n1], explain="...", results=[...], k=5)
        trace = b.build(answer=answer, metrics=metrics)
    """

    def __init__(self, architecture: str, question: str, trace_id: str | None = None):
        self.architecture = architecture
        self.question = question
        self.trace_id = trace_id
        self._nodes: list[Node] = []
        self._counter = 0

    def node(
        self,
        kind: str,
        label: str,
        parents: list[str],
        explain: str,
        node_id: str | None = None,
        duration_ms: float = 0.0,
        **payload,
    ) -> str:
        if kind not in NODE_KINDS:
            raise TraceValidationError(f"unknown node kind {kind!r}")
        self._counter += 1
        nid = node_id or f"n{self._counter}"
        self._nodes.append(
            Node(
                id=nid,
                kind=kind,
                label=label,
                parent_ids=list(parents),
                explain=explain,
                payload=payload,
                duration_ms=duration_ms,
            )
        )
        return nid

    def splice(self, nodes: list[Node], prefix: str, parent_id: str) -> list[Node]:
        """Splice a delegated trace's nodes in, prefixing ids to keep them
        unique and attaching the delegated trace's roots to `parent_id`.
        Used by adaptive.py to nest a delegated architecture's trace."""
        id_map = {n.id: f"{prefix}::{n.id}" for n in nodes}
        spliced: list[Node] = []
        for n in nodes:
            new_parents = [id_map[p] for p in n.parent_ids] or [parent_id]
            new_node = Node(
                id=id_map[n.id],
                kind=n.kind,
                label=n.label,
                parent_ids=new_parents,
                explain=n.explain,
                payload=n.payload,
                duration_ms=n.duration_ms,
            )
            self._nodes.append(new_node)
            spliced.append(new_node)
        return spliced

    def build(self, answer: str, metrics: Metrics) -> Trace:
        trace_id = self.trace_id or f"{self.architecture}::{abs(hash(self.question)) % 10**8}"
        trace = Trace(
            trace_id=trace_id,
            architecture=self.architecture,
            question=self.question,
            answer=answer,
            metrics=metrics,
            nodes=list(self._nodes),
        )
        trace.validate()
        return trace
