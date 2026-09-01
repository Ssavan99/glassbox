import { splitAnswerCitations } from "../lib/citations";
import type {
  ChunkRecord,
  GraphData,
  RetrievalResult,
  TraceNode,
} from "../lib/types";
import { KIND_NAME } from "./nodeMeta";
import { GraphView } from "./GraphView";

interface NodeInspectorProps {
  node: TraceNode;
  chunkIndex: Map<string, ChunkRecord>;
  graphData?: GraphData;
}

export function NodeInspector({ node, chunkIndex, graphData }: NodeInspectorProps) {
  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">
          {KIND_NAME[node.kind]}
        </span>
        <h3 className="section-heading text-xl leading-snug">{node.label}</h3>
      </header>

      {/* The explain sentence is the actual teaching content this site
       * exists to deliver -- rendered first, full-width, at reading size,
       * not as a footnote. It already carries kind-specific nuance the
       * frontend doesn't need to duplicate in code (e.g. Agentic's `route`
       * vs Adaptive's `route` explain very differently what the same node
       * kind means in each context). */}
      <p className="rounded-xl border-2 border-border bg-page p-4 text-sm leading-relaxed text-ink">
        {node.explain}
      </p>

      <PayloadView node={node} chunkIndex={chunkIndex} graphData={graphData} />
    </div>
  );
}

function PayloadView({ node, chunkIndex, graphData }: NodeInspectorProps): React.ReactElement {
  switch (node.kind) {
    case "embed_query":
      return (
        <Field label={`Embedding preview (${node.payload.dims} dims, first 8 shown)`}>
          <code className="block break-all rounded bg-page p-2 text-xs text-ink-secondary">
            [{node.payload.preview.map((v) => v.toFixed(4)).join(", ")}, …]
          </code>
        </Field>
      );

    case "retrieve_dense":
    case "retrieve_sparse":
      return (
        <Field label={`Top-${node.payload.k} results`}>
          <RetrievalTable results={node.payload.results} chunkIndex={chunkIndex} />
        </Field>
      );

    case "fuse":
      return (
        <Field label={`Fused via ${node.payload.method} (k=${node.payload.k})`}>
          <RetrievalTable results={node.payload.results} chunkIndex={chunkIndex} />
        </Field>
      );

    case "rerank":
      return (
        <div className="flex flex-col gap-3">
          <Field label="Before rerank">
            <RetrievalTable results={node.payload.before} chunkIndex={chunkIndex} compact />
          </Field>
          <Field label={`After rerank (${node.payload.model})`}>
            <RetrievalTable results={node.payload.after} chunkIndex={chunkIndex} />
          </Field>
        </div>
      );

    case "grade":
      return (
        <Field label="Judgements">
          <ul className="flex flex-col gap-2">
            {node.payload.judgements.map((j) => (
              <li
                key={j.chunk_id}
                className="flex flex-col gap-1 rounded-md border border-border bg-page p-2"
              >
                <div className="flex items-center gap-2">
                  <VerdictChip verdict={j.verdict} />
                  <code className="truncate text-xs text-ink-secondary">{j.chunk_id}</code>
                </div>
                <p className="text-xs text-ink-secondary">{j.reason}</p>
              </li>
            ))}
          </ul>
        </Field>
      );

    case "rewrite":
      return (
        <Field label="Query rewrite">
          <div className="flex flex-col gap-2 text-sm">
            <div className="rounded-md border border-status-critical/40 bg-page p-2">
              <div className="mb-1 text-[10px] font-medium uppercase text-ink-muted">From</div>
              {node.payload.from}
            </div>
            <div className="rounded-md border border-status-good/40 bg-page p-2">
              <div className="mb-1 text-[10px] font-medium uppercase text-ink-muted">To</div>
              {node.payload.to}
            </div>
            <p className="text-xs text-ink-secondary">{node.payload.reason}</p>
          </div>
        </Field>
      );

    case "graph_seed":
      return (
        <Field label={`Matched entities (${node.payload.entities.length})`}>
          <ChipList items={node.payload.entities} empty="No entities matched in this text." />
        </Field>
      );

    case "graph_expand":
      return (
        <div className="flex flex-col gap-3">
          <Field label={`${node.payload.hops}-hop expansion — ${node.payload.chunk_ids.length} chunk(s) gathered`}>
            <ChunkIdList chunkIds={node.payload.chunk_ids} chunkIndex={chunkIndex} />
          </Field>
          <Field label={`Traversed edges (${node.payload.edges.length})`}>
            <ul className="flex max-h-40 flex-col gap-1 overflow-y-auto font-mono text-xs text-ink-secondary">
              {node.payload.edges.map((e, i) => (
                <li key={i} className="truncate">
                  {e.src} <span className="text-ink-muted">—{e.rel}→</span> {e.dst}
                </li>
              ))}
            </ul>
          </Field>
          {graphData && (
            <Field label="Knowledge graph traversal">
              <GraphView
                graphData={graphData}
                highlightEdges={node.payload.edges}
                highlightChunkIds={node.payload.chunk_ids}
                height={280}
              />
            </Field>
          )}
        </div>
      );

    case "plan":
      return (
        <Field label={`Sub-questions (${node.payload.sub_questions.length})`}>
          <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm">
            {node.payload.sub_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </Field>
      );

    case "reflect":
      return (
        <Field label="Sufficiency judgement">
          <div className="flex flex-col gap-2">
            <span
              className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${
                node.payload.sufficient
                  ? "border-status-good/40 text-status-good"
                  : "border-status-warning/40 text-status-warning"
              }`}
            >
              {node.payload.sufficient ? "Sufficient" : "Insufficient"}
            </span>
            <p className="text-sm text-ink-secondary">{node.payload.reason}</p>
            {!node.payload.sufficient && (
              <p className="text-xs text-ink-muted">Next: {node.payload.next_action}</p>
            )}
          </div>
        </Field>
      );

    case "route":
      return (
        <Field label="Routing decision">
          <div className="flex flex-col gap-2">
            <span className="inline-flex w-fit items-center rounded-full border border-arch-naive/40 px-2 py-0.5 text-xs font-medium text-arch-naive">
              chosen: {node.payload.chosen}
            </span>
            <p className="text-sm text-ink-secondary">{node.payload.reason}</p>
            {Object.keys(node.payload.scores).length > 0 && (
              <ul className="font-mono text-xs text-ink-muted">
                {Object.entries(node.payload.scores).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v.toFixed(3)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Field>
      );

    case "generate_hypothetical":
    case "generate":
      return (
        <div className="flex flex-col gap-3">
          <Field label={node.kind === "generate" ? "Answer" : "Hypothetical passage"}>
            <AnswerText text={node.payload.output} />
          </Field>
          <p className="text-xs text-ink-muted">{node.payload.tokens} completion tokens</p>
          <details className="text-xs">
            <summary className="cursor-pointer text-ink-secondary hover:text-ink">
              Show the actual prompt sent
            </summary>
            <pre className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded bg-page p-2 font-mono text-[11px] text-ink-secondary">
              {node.payload.prompt_preview}
            </pre>
          </details>
        </div>
      );
    default:
      // Exhaustiveness check: if TraceNode ever gains a 15th `kind`, this
      // becomes a real compile error (`node` narrows to `never` only when
      // every case above is handled) instead of a silently-blank payload
      // panel for the new kind. Verified this actually catches a removed
      // case, not just a stylistic convention.
      return assertNever(node);
  }
}

function assertNever(x: never): never {
  throw new Error(`unhandled node kind: ${JSON.stringify(x)}`);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs font-medium text-ink-muted">{label}</div>
      {children}
    </div>
  );
}

function VerdictChip({ verdict }: { verdict: "correct" | "ambiguous" | "incorrect" }) {
  const styles = {
    correct: "border-status-good/40 text-status-good",
    ambiguous: "border-status-warning/40 text-status-warning",
    incorrect: "border-status-critical/40 text-status-critical",
  } as const;
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${styles[verdict]}`}
    >
      {verdict}
    </span>
  );
}

function ChipList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) {
    return <p className="text-sm text-ink-muted">{empty}</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border border-border bg-page px-2 py-0.5 text-xs text-ink-secondary"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function chunkExcerpt(chunkIndex: Map<string, ChunkRecord>, chunkId: string, max = 90): string {
  const text = chunkIndex.get(chunkId)?.text;
  if (!text) return "(chunk text unavailable)";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function RetrievalTable({
  results,
  chunkIndex,
  compact = false,
}: {
  results: RetrievalResult[];
  chunkIndex: Map<string, ChunkRecord>;
  compact?: boolean;
}) {
  if (results.length === 0) {
    return <p className="text-sm text-ink-muted">No results.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-border bg-page text-ink-muted">
            <th className="px-2 py-1.5 font-medium">#</th>
            <th className="px-2 py-1.5 font-medium">Chunk</th>
            <th className="px-2 py-1.5 text-right font-medium">Score</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <tr key={r.chunk_id} className="border-b border-border last:border-0">
              <td className="px-2 py-1.5 tabular-nums text-ink-muted">{r.rank}</td>
              <td className="px-2 py-1.5">
                <div className="font-mono text-[11px] text-ink">{r.chunk_id}</div>
                {!compact && (
                  <div className="text-[11px] text-ink-muted">
                    {chunkExcerpt(chunkIndex, r.chunk_id)}
                  </div>
                )}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums text-ink-secondary">
                {r.score.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChunkIdList({
  chunkIds,
  chunkIndex,
  max = 8,
}: {
  chunkIds: string[];
  chunkIndex: Map<string, ChunkRecord>;
  max?: number;
}) {
  const shown = chunkIds.slice(0, max);
  return (
    <div className="flex flex-col gap-1">
      <ul className="flex flex-col gap-1">
        {shown.map((id) => (
          <li key={id} className="rounded bg-page px-2 py-1 text-xs">
            <div className="font-mono text-ink">{id}</div>
            <div className="text-ink-muted">{chunkExcerpt(chunkIndex, id, 70)}</div>
          </li>
        ))}
      </ul>
      {chunkIds.length > max && (
        <p className="text-xs text-ink-muted">and {chunkIds.length - max} more…</p>
      )}
    </div>
  );
}

/** Highlights `[chunk-id::n]`-style citations inline so the answer text's
 * grounding is visually scannable, without needing to cross-reference the
 * retrieval table by hand. */
function AnswerText({ text }: { text: string }) {
  const parts = splitAnswerCitations(text);
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
      {parts.map((part, i) =>
        part.citation ? (
          <span
            key={i}
            className="mx-0.5 rounded bg-arch-naive/15 px-1 py-0.5 font-mono text-xs text-arch-naive"
          >
            {part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </p>
  );
}
