import { useCallback, useMemo, useState } from "react";
import { NodeInspector } from "../trace/NodeInspector";
import { loadChunkIndex, loadTrace } from "../lib/data";
import type { ChunkRecord } from "../lib/types";
import { SandboxCanvas } from "../sandbox/Canvas";
import type { EmbedProgress } from "../sandbox/embedding";
import { isEmbedderReady, loadEmbedder } from "../sandbox/embedding";
import { executeGraph, type ActivePreset, type SandboxNodeResult } from "../sandbox/execute";
import { PALETTE } from "../sandbox/palette";
import { PRESETS, type SandboxPreset } from "../sandbox/presets";
import type { SandboxGraph } from "../sandbox/types";
import { validateGraph } from "../sandbox/validate";

const EMPTY_GRAPH: SandboxGraph = { nodes: [], edges: [] };

/** True if two graphs have the same nodes (by id+kind) and edges (by
 * source+target), ignoring node position -- used to decide whether an
 * active preset's exact-replay fidelity survives a change (dragging a node
 * around doesn't break it; adding/removing/rewiring does). */
function graphsStructurallyEqual(a: SandboxGraph, b: SandboxGraph): boolean {
  const nodesA = new Set(a.nodes.map((n) => `${n.id}:${n.kind}`));
  const nodesB = new Set(b.nodes.map((n) => `${n.id}:${n.kind}`));
  if (nodesA.size !== nodesB.size) return false;
  for (const n of nodesA) if (!nodesB.has(n)) return false;

  const edgesA = new Set(a.edges.map((e) => `${e.source}->${e.target}`));
  const edgesB = new Set(b.edges.map((e) => `${e.source}->${e.target}`));
  if (edgesA.size !== edgesB.size) return false;
  for (const e of edgesA) if (!edgesB.has(e)) return false;

  return true;
}

export function Sandbox() {
  const [graph, setGraph] = useState<SandboxGraph>(EMPTY_GRAPH);
  const [queryText, setQueryText] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [results, setResults] = useState<Map<string, SandboxNodeResult>>(new Map());
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [chunkIndex, setChunkIndex] = useState<Map<string, ChunkRecord> | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [embedProgress, setEmbedProgress] = useState<EmbedProgress | null>(null);

  const validation = useMemo(() => validateGraph(graph), [graph]);
  const activePreset = useMemo(
    () => PRESETS.find((p) => p.id === activePresetId) ?? null,
    [activePresetId],
  );

  const ensureChunkIndex = useCallback(async () => {
    if (chunkIndex) return chunkIndex;
    const loaded = await loadChunkIndex();
    setChunkIndex(loaded);
    return loaded;
  }, [chunkIndex]);

  function loadPreset(preset: SandboxPreset) {
    setGraph(preset.graph);
    setQueryText(preset.query);
    setActivePresetId(preset.id);
    setSelectedNodeId(null);
    setResults(new Map());
    setRunError(null);
  }

  function updateGraph(next: SandboxGraph) {
    setGraph(next);
    if (activePreset && !graphsStructurallyEqual(next, activePreset.graph)) {
      setActivePresetId(null);
    }
  }

  function updateQueryText(next: string) {
    setQueryText(next);
    if (activePreset && next !== activePreset.query) {
      setActivePresetId(null);
    }
  }

  async function handleRun() {
    if (!validation.valid || queryText.trim().length === 0 || running) return;
    setRunning(true);
    setRunError(null);
    setResults(new Map());
    try {
      const index = await ensureChunkIndex();

      if (!isEmbedderReady()) {
        await loadEmbedder(setEmbedProgress);
        setEmbedProgress(null);
      }

      let activePresetForRun: ActivePreset | null = null;
      if (
        activePreset &&
        graphsStructurallyEqual(graph, activePreset.graph) &&
        queryText === activePreset.query
      ) {
        const trace = await loadTrace(activePreset.architecture, activePreset.questionId);
        activePresetForRun = { trace, replayMap: activePreset.replayMap };
      }

      await executeGraph({
        graph,
        queryText,
        chunkIndex: index,
        activePreset: activePresetForRun,
        onNodeStart: (nodeId) => setSelectedNodeId(nodeId),
        onNodeComplete: (nodeId, result) => {
          setResults((prev) => new Map(prev).set(nodeId, result));
        },
      });
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  const selectedResult = selectedNodeId ? results.get(selectedNodeId) : undefined;
  const selectedKind = selectedNodeId ? graph.nodes.find((n) => n.id === selectedNodeId)?.kind : undefined;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">Sandbox</span>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Build your own pipeline</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-ink-secondary">
          Drag steps onto the canvas, wire them together, type your own question, and run it. Retrieval
          is genuinely live -- a real embedding model runs in your browser and searches the real corpus.
          Generation is not: this site never calls a live LLM, so outside the three presets below, the
          final step shows the real retrieved text instead of a fabricated answer, clearly labeled.
        </p>
      </header>

      <section aria-label="Presets" className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-ink-muted">Load a real preset:</span>
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => loadPreset(preset)}
            aria-pressed={activePresetId === preset.id}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              activePresetId === preset.id
                ? "border-ink bg-ink text-page"
                : "border-border text-ink-secondary hover:text-ink"
            }`}
            title={preset.description}
          >
            {preset.label}
          </button>
        ))}
        {activePresetId && (
          <span className="text-xs text-status-good">
            Unmodified -- Generate will replay the real recorded answer
          </span>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <label htmlFor="sandbox-query" className="text-xs font-medium text-ink-muted">
          Your question
        </label>
        <textarea
          id="sandbox-query"
          value={queryText}
          onChange={(e) => updateQueryText(e.target.value)}
          placeholder="Type any question -- retrieval runs live against the real corpus either way."
          rows={2}
          className="rounded-lg border border-border bg-surface p-3 text-sm text-ink placeholder:text-ink-muted focus:border-arch-naive focus:outline-none"
        />
      </section>

      <SandboxCanvas
        graph={graph}
        onChange={updateGraph}
        selectedNodeId={selectedNodeId}
        onSelectNode={setSelectedNodeId}
        errors={validation.errors}
      />

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleRun}
          disabled={!validation.valid || queryText.trim().length === 0 || running}
          className="min-h-9 rounded-md bg-arch-naive px-4 py-1.5 text-sm font-medium text-white transition-opacity enabled:hover:opacity-90 disabled:opacity-40"
        >
          {running ? "Running…" : "Run"}
        </button>
        {!validation.valid && (
          <span className="text-xs text-status-critical">Fix the errors above before running.</span>
        )}
        {queryText.trim().length === 0 && (
          <span className="text-xs text-ink-muted">Type a question first.</span>
        )}
      </div>

      {embedProgress && (
        <div className="rounded-lg border border-border bg-surface p-3 text-xs text-ink-secondary">
          Loading the embedding model{embedProgress.file ? ` (${embedProgress.file})` : ""} —{" "}
          {embedProgress.status}
          {typeof embedProgress.progress === "number" ? ` — ${embedProgress.progress.toFixed(0)}%` : ""}
        </div>
      )}

      {runError && (
        <div className="rounded-lg border border-status-critical/40 bg-status-critical/5 p-3 text-sm text-ink-secondary">
          {runError}
        </div>
      )}

      {(selectedResult || selectedKind) && (
        <section className="rounded-lg border border-border bg-surface p-4">
          {selectedResult ? (
            selectedResult.kind === "chunk" ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">Corpus</span>
                <p className="text-sm text-ink-secondary">{selectedResult.explain}</p>
              </div>
            ) : chunkIndex ? (
              <NodeInspector node={selectedResult} chunkIndex={chunkIndex} />
            ) : null
          ) : selectedKind ? (
            <p className="text-sm text-ink-muted">
              {PALETTE[selectedKind].label} — not run yet. Press Run to see a real result here.
            </p>
          ) : null}
        </section>
      )}
    </div>
  );
}
