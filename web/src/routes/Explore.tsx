import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ARCHITECTURE_ORDER, ARCHITECTURES, architectureColor } from "../lib/architectures";
import { loadChunkIndex, loadGraph, loadQuestions, loadTrace } from "../lib/data";
import type { ArchitectureId, ChunkRecord, GraphData, Question, Trace } from "../lib/types";
import { ARCHITECTURE_IDS } from "../lib/types";
import { TracePlayer } from "../trace/TracePlayer";

function isArchitectureId(v: string | null): v is ArchitectureId {
  return !!v && (ARCHITECTURE_IDS as readonly string[]).includes(v);
}

export function Explore() {
  const [params, setParams] = useSearchParams();
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [chunkIndex, setChunkIndex] = useState<Map<string, ChunkRecord> | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [graphData, setGraphData] = useState<GraphData | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const architecture = isArchitectureId(params.get("arch")) ? (params.get("arch") as ArchitectureId) : "naive";
  const questionId = params.get("q") ?? "q01";

  // Static data (questions, chunk index) loads once.
  useEffect(() => {
    let cancelled = false;
    Promise.all([loadQuestions(), loadChunkIndex()])
      .then(([qs, chunks]) => {
        if (cancelled) return;
        setQuestions(qs);
        setChunkIndex(chunks);
      })
      .catch((err: unknown) => {
        console.error("Explore: failed to load questions/chunks", err);
        if (!cancelled) setError("Failed to load question list or corpus chunks.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The selected trace reloads whenever the picker changes.
  useEffect(() => {
    let cancelled = false;
    setTrace(null);
    loadTrace(architecture, questionId)
      .then((t) => {
        if (cancelled) return;
        setTrace(t);
        setError(null);
        // graph.json is only needed when this specific trace actually
        // touched the graph tool (graph_expand can appear in Agentic's
        // sub-questions too, not just the Graph architecture) -- lazy-load
        // rather than fetching it unconditionally for every trace.
        if (t.nodes.some((n) => n.kind === "graph_expand")) {
          loadGraph()
            .then((g) => {
              if (!cancelled) setGraphData(g);
            })
            .catch((err: unknown) => console.error("Explore: failed to load graph.json", err));
        } else {
          setGraphData(undefined);
        }
      })
      .catch((err: unknown) => {
        console.error(`Explore: failed to load trace ${architecture}::${questionId}`, err);
        if (!cancelled) setError(`No recorded trace found for ${architecture} on ${questionId}.`);
      });
    return () => {
      cancelled = true;
    };
  }, [architecture, questionId]);

  const questionsByType = useMemo(() => {
    if (!questions) return null;
    const groups = new Map<string, Question[]>();
    for (const q of questions) {
      const list = groups.get(q.type) ?? [];
      list.push(q);
      groups.set(q.type, list);
    }
    return groups;
  }, [questions]);

  function setArchitecture(id: ArchitectureId) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("arch", id);
      return next;
    });
  }

  function setQuestionId(id: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("q", id);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Explore</h1>
        <p className="mt-1 text-sm text-ink-secondary">
          Pick an architecture and a question, then scrub through exactly what it did, step by
          step.
        </p>
      </div>

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {ARCHITECTURE_ORDER.map((id) => {
            const meta = ARCHITECTURES[id];
            const active = id === architecture;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setArchitecture(id)}
                className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors"
                style={
                  active
                    ? { borderColor: architectureColor(id), color: architectureColor(id) }
                    : undefined
                }
              >
                <span
                  aria-hidden="true"
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: architectureColor(id) }}
                />
                {meta.name}
              </button>
            );
          })}
        </div>

        <select
          value={questionId}
          onChange={(e) => setQuestionId(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
          aria-label="Choose a question"
        >
          {questionsByType &&
            [...questionsByType.entries()].map(([type, qs]) => (
              <optgroup key={type} label={type}>
                {qs.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.id} — {q.question}
                  </option>
                ))}
              </optgroup>
            ))}
        </select>
      </section>

      {error && (
        <p className="rounded-md border border-status-critical/40 bg-status-critical/10 p-3 text-sm text-status-critical">
          {error}
        </p>
      )}

      {!error && (!trace || !chunkIndex) && (
        <div className="flex h-64 items-center justify-center text-sm text-ink-muted">
          Loading trace…
        </div>
      )}

      {trace && chunkIndex && (
        <TracePlayer trace={trace} chunkIndex={chunkIndex} graphData={graphData} />
      )}
    </div>
  );
}
