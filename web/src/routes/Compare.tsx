import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ARCHITECTURE_ORDER, ARCHITECTURES, architectureColor } from "../lib/architectures";
import { splitAnswerCitations } from "../lib/citations";
import { loadChunkIndex, loadEval, loadQuestions } from "../lib/data";
import type { ArchitectureId, ChunkRecord, EvalRow, Question } from "../lib/types";

/** q11 is the default on purpose: it's a real, already-diagnosed divergence
 * (Naive answers faithfully at 1.00 from the same corpus that Agentic
 * hallucinates against at 0.33), so landing on /compare with no ?q= shows a
 * genuine difference immediately instead of an arbitrary first question. */
const DEFAULT_QUESTION_ID = "q11";

/** How many retrieved chunks to show per column before collapsing the rest.
 * Graph/Agentic/Adaptive rows really do carry 40+ chunk ids on some
 * questions -- showing them all inline would bury the answer text. */
const CHUNKS_SHOWN = 6;

const TYPE_LABEL: Record<string, string> = {
  factual: "Factual",
  multi_hop: "Multi-hop",
  keyword: "Keyword",
  unanswerable: "Unanswerable",
};

export function Compare() {
  const [params, setParams] = useSearchParams();
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [rows, setRows] = useState<EvalRow[] | null>(null);
  const [chunkIndex, setChunkIndex] = useState<Map<string, ChunkRecord> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const questionId = params.get("q") ?? DEFAULT_QUESTION_ID;

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadQuestions(), loadEval(), loadChunkIndex()])
      .then(([qs, report, chunks]) => {
        if (cancelled) return;
        setQuestions(qs);
        setRows(report.rows);
        setChunkIndex(chunks);
      })
      .catch((err: unknown) => {
        console.error("Compare: failed to load comparison data", err);
        if (!cancelled) setError("Failed to load the evaluation report, questions, or corpus chunks.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const question = questions?.find((q) => q.id === questionId) ?? null;

  /** One row per architecture for the selected question (missing rows are
   * rendered as an explicit gap rather than silently dropping a column). */
  const rowsByArchitecture = useMemo(() => {
    const map = new Map<ArchitectureId, EvalRow>();
    for (const row of rows ?? []) {
      if (row.question_id === questionId) map.set(row.architecture, row);
    }
    return map;
  }, [rows, questionId]);

  /** chunk_id -> how many of the architectures retrieved it. This is the
   * retrieval-divergence signal the columns badge against: a chunk only one
   * or two architectures found is where they actually disagree. */
  const chunkFrequency = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of rowsByArchitecture.values()) {
      for (const id of new Set(row.retrieved_chunk_ids)) {
        counts.set(id, (counts.get(id) ?? 0) + 1);
      }
    }
    return counts;
  }, [rowsByArchitecture]);

  const architectureCount = rowsByArchitecture.size;

  /** The at-a-glance headline: the widest faithfulness gap between any two
   * architectures on this question. Computed from the data, so it stays true
   * for every question, not just the default one. */
  const faithfulnessSpread = useMemo(() => {
    const scored = ARCHITECTURE_ORDER.map((id) => rowsByArchitecture.get(id)).filter(
      (r): r is EvalRow => !!r && r.faithfulness !== null,
    );
    if (scored.length < 2) return null;
    let best = scored[0];
    let worst = scored[0];
    for (const row of scored) {
      if ((row.faithfulness ?? 0) > (best.faithfulness ?? 0)) best = row;
      if ((row.faithfulness ?? 0) < (worst.faithfulness ?? 0)) worst = row;
    }
    const gap = (best.faithfulness ?? 0) - (worst.faithfulness ?? 0);
    if (gap < 0.2) return null;
    return { best, worst, gap };
  }, [rowsByArchitecture]);

  const anyGraphTool = [...rowsByArchitecture.values()].some((r) => r.graph_tool_involved);

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
        <h1 className="text-2xl font-semibold tracking-tight">Compare</h1>
        <p className="mt-1 text-sm text-ink-secondary">
          One question, all seven architectures side by side — the same corpus, the same
          evaluation run. Where they retrieved different evidence, and where that changed the
          answer.
        </p>
      </div>

      <section className="flex flex-col gap-3">
        <select
          value={questionId}
          onChange={(e) => setQuestionId(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
          aria-label="Choose a question to compare"
        >
          {questionsByType &&
            [...questionsByType.entries()].map(([type, qs]) => (
              <optgroup key={type} label={TYPE_LABEL[type] ?? type}>
                {qs.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.id} — {q.question}
                  </option>
                ))}
              </optgroup>
            ))}
        </select>

        {question && (
          <div className="rounded-md border border-border bg-surface p-3">
            <div className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-muted">
              {question.id} · {TYPE_LABEL[question.type] ?? question.type}
            </div>
            <p className="text-base leading-snug text-ink">{question.question}</p>
          </div>
        )}
      </section>

      {error && (
        <p className="rounded-md border border-status-critical/40 bg-status-critical/10 p-3 text-sm text-status-critical">
          {error}
        </p>
      )}

      {!error && (!rows || !chunkIndex) && (
        <div className="flex h-64 items-center justify-center text-sm text-ink-muted">
          Loading comparison…
        </div>
      )}

      {rows && chunkIndex && architectureCount === 0 && (
        <p className="rounded-md border border-border bg-surface p-3 text-sm text-ink-secondary">
          No evaluation rows recorded for {questionId}.
        </p>
      )}

      {rows && chunkIndex && faithfulnessSpread && (
        <section className="rounded-md border border-border bg-surface p-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-muted">
            The divergence on this question
          </div>
          <p className="text-sm leading-relaxed text-ink">
            Same question, same corpus, same judge —{" "}
            <span className="font-medium" style={{ color: architectureColor(faithfulnessSpread.best.architecture) }}>
              {ARCHITECTURES[faithfulnessSpread.best.architecture].name}
            </span>{" "}
            was judged{" "}
            <span className="font-medium text-status-good">
              {formatScore(faithfulnessSpread.best.faithfulness)} faithful
            </span>
            , while{" "}
            <span className="font-medium" style={{ color: architectureColor(faithfulnessSpread.worst.architecture) }}>
              {ARCHITECTURES[faithfulnessSpread.worst.architecture].name}
            </span>{" "}
            scored{" "}
            <span className="font-medium text-status-critical">
              {formatScore(faithfulnessSpread.worst.faithfulness)}
            </span>{" "}
            on the same evidence. Read the two answers below and the difference is visible in the
            prose, not just the number.
          </p>
        </section>
      )}

      {rows && chunkIndex && architectureCount > 0 && (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3 rounded border border-status-warning/60 bg-status-warning/10"
              />
              retrieved by a minority of the architectures
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="text-status-good">✓ gold</span> = the question&rsquo;s correct chunk
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="tabular-nums">n/{architectureCount}</span> = how many retrieved it
            </span>
            <span className="md:hidden">Scroll sideways to compare all seven →</span>
          </div>
          <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:-mx-6 sm:px-6">
            <div className="flex min-w-max gap-3">
              {ARCHITECTURE_ORDER.map((id) => (
                <ArchitectureColumn
                  key={id}
                  architecture={id}
                  row={rowsByArchitecture.get(id)}
                  questionId={questionId}
                  chunkFrequency={chunkFrequency}
                  architectureCount={architectureCount}
                  chunkIndex={chunkIndex}
                />
              ))}
            </div>
          </div>
        </>
      )}

      {rows && (
        <p className="text-xs leading-relaxed text-ink-muted">
          Only <span className="font-medium text-ink-secondary">recall (full)</span> and{" "}
          <span className="font-medium text-ink-secondary">faithfulness</span> are shown here on
          purpose: recall@5, MRR@10 and nDCG@10 assume a single relevance-ranked list, which isn't
          true for rows where the graph tool was involved
          {anyGraphTool ? " — as it was for some rows on this question" : ""}, so those rank
          metrics would misread as retrieval failures. See{" "}
          <Link to="/eval" className="underline hover:text-ink">
            /eval
          </Link>{" "}
          for the full caveat. Faithfulness is LLM-judged, not ground truth.
        </p>
      )}
    </div>
  );
}

function ArchitectureColumn({
  architecture,
  row,
  questionId,
  chunkFrequency,
  architectureCount,
  chunkIndex,
}: {
  architecture: ArchitectureId;
  row: EvalRow | undefined;
  questionId: string;
  chunkFrequency: Map<string, number>;
  architectureCount: number;
  chunkIndex: Map<string, ChunkRecord>;
}) {
  const meta = ARCHITECTURES[architecture];
  const accent = architectureColor(architecture);

  return (
    <section className="flex w-[300px] min-w-[300px] flex-col gap-3 rounded-md border border-border bg-surface p-3">
      <header className="flex flex-col gap-1 border-b border-border pb-2">
        <div className="flex items-center gap-2">
          {/* Colour is never the only identity signal -- 3 of the 7 accents
           * fail 3:1 on the light surface by design, so the name always
           * rides alongside the swatch. */}
          <span
            aria-hidden="true"
            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ background: accent }}
          />
          <h2 className="text-sm font-semibold text-ink">{meta.name}</h2>
        </div>
        <Link
          to={`/explore?arch=${architecture}&q=${questionId}`}
          className="w-fit text-xs text-ink-secondary underline hover:text-ink"
        >
          View full trace
        </Link>
      </header>

      {!row ? (
        <p className="text-xs text-ink-muted">No recorded row for this question.</p>
      ) : (
        <>
          {row.architecture === "adaptive" && (
            <div className="rounded border border-border bg-page px-2 py-1 text-xs text-ink-secondary">
              Routed to{" "}
              <span className="font-medium text-ink">
                {row.adaptive_routed_to ? ARCHITECTURES[row.adaptive_routed_to].name : "—"}
              </span>
            </div>
          )}

          <div className="flex flex-wrap gap-1.5">
            <Metric label="Recall (full)" value={formatScore(row.recall_full)} tone={scoreTone(row.recall_full)} />
            <Metric label="Faithfulness" value={formatScore(row.faithfulness)} tone={scoreTone(row.faithfulness)} />
          </div>

          {row.reads_as_refusal && (
            <span className="w-fit rounded-full border border-status-warning/40 px-2 py-0.5 text-[10px] font-medium uppercase text-status-warning">
              Reads as a refusal
            </span>
          )}

          <div className="flex flex-col gap-1.5">
            <div className="text-xs font-medium text-ink-muted">Answer</div>
            <AnswerText text={row.answer} accent={accent} />
          </div>

          <RetrievedChunks
            row={row}
            chunkFrequency={chunkFrequency}
            architectureCount={architectureCount}
            chunkIndex={chunkIndex}
          />
        </>
      )}
    </section>
  );
}

function RetrievedChunks({
  row,
  chunkFrequency,
  architectureCount,
  chunkIndex,
}: {
  row: EvalRow;
  chunkFrequency: Map<string, number>;
  architectureCount: number;
  chunkIndex: Map<string, ChunkRecord>;
}) {
  const gold = new Set(row.gold_chunk_ids);
  const ids = row.retrieved_chunk_ids;
  const shown = ids.slice(0, CHUNKS_SHOWN);
  const rest = ids.slice(CHUNKS_SHOWN);

  const renderChunk = (id: string, index: number) => (
    <ChunkRow
      key={id}
      chunkId={id}
      rank={index + 1}
      isGold={gold.has(id)}
      count={chunkFrequency.get(id) ?? 1}
      architectureCount={architectureCount}
      chunkIndex={chunkIndex}
    />
  );

  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs font-medium text-ink-muted">
        Retrieved ({ids.length} chunk{ids.length === 1 ? "" : "s"})
      </div>
      {ids.length === 0 ? (
        <p className="text-xs text-ink-muted">Nothing retrieved.</p>
      ) : (
        <ul className="flex flex-col gap-1">{shown.map(renderChunk)}</ul>
      )}
      {rest.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-ink-secondary hover:text-ink">
            Show {rest.length} more
          </summary>
          <ul className="mt-1 flex max-h-64 flex-col gap-1 overflow-y-auto">
            {rest.map((id, i) => renderChunk(id, i + CHUNKS_SHOWN))}
          </ul>
        </details>
      )}
    </div>
  );
}

function ChunkRow({
  chunkId,
  rank,
  isGold,
  count,
  architectureCount,
  chunkIndex,
}: {
  chunkId: string;
  rank: number;
  isGold: boolean;
  count: number;
  architectureCount: number;
  chunkIndex: Map<string, ChunkRecord>;
}) {
  // A chunk fewer than half the architectures found is where they actually
  // disagree, so it gets a visible border and a filled badge rather than a
  // tooltip. A fixed "1-2 of 7" cut was tried first and turned out to fire on
  // nothing for the default question (q11's rarest chunk is retrieved by 3 of
  // 7) -- the relative threshold surfaces the real divergence there: Graph's
  // top results are shared by only the three graph-touching rows.
  const rare = count * 2 < architectureCount;
  return (
    <li
      className={`rounded border px-2 py-1 ${
        rare ? "border-status-warning/60 bg-status-warning/10" : "border-border bg-page"
      }`}
    >
      <div className="flex items-start gap-1.5">
        <span className="shrink-0 pt-px text-[10px] tabular-nums text-ink-muted">{rank}</span>
        <span className="min-w-0 flex-1 break-all font-mono text-[11px] text-ink">{chunkId}</span>
        {isGold && (
          <span
            className="shrink-0 rounded-full bg-status-good/15 px-1.5 text-[10px] font-medium text-status-good"
            title="In this row's gold chunk set"
          >
            ✓ gold
          </span>
        )}
        <span
          className={`shrink-0 rounded-full px-1.5 text-[10px] font-medium tabular-nums ${
            rare ? "bg-status-warning/25 text-ink" : "text-ink-muted"
          }`}
          title={`Retrieved by ${count} of ${architectureCount} architectures`}
        >
          {count}/{architectureCount}
        </span>
      </div>
      <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-ink-muted">
        {chunkExcerpt(chunkIndex, chunkId)}
      </div>
    </li>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex flex-col rounded border border-border bg-page px-2 py-1">
      <span className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${tone}`}>{value}</span>
    </div>
  );
}

function scoreTone(value: number | null): string {
  if (value === null) return "text-ink-muted";
  if (value >= 0.8) return "text-status-good";
  if (value >= 0.5) return "text-status-warning";
  return "text-status-critical";
}

function formatScore(value: number | null | undefined): string {
  return value === null || value === undefined ? "n/a" : value.toFixed(2);
}

function chunkExcerpt(chunkIndex: Map<string, ChunkRecord>, chunkId: string, max = 100): string {
  const text = chunkIndex.get(chunkId)?.text;
  if (!text) return "(chunk text unavailable)";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

/** `[chunk-id::n]` citation highlighting -- shared with the trace inspector
 * via `lib/citations.ts` (originally duplicated locally here; unified after
 * a Code Review pass found both copies shared the same real-corpus gaps:
 * a zero-width space, interior whitespace, or a `citation: ` prefix inside
 * the brackets, all confirmed present in real recorded answers, previously
 * rendered as unstyled plain text instead of a highlighted citation). */
function AnswerText({ text, accent }: { text: string; accent: string }) {
  const parts = splitAnswerCitations(text);
  return (
    <p className="max-h-96 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink">
      {parts.map((part, i) =>
        part.citation ? (
          <span
            key={i}
            className="mx-0.5 rounded px-1 py-0.5 font-mono text-[11px]"
            style={{ color: accent, background: `color-mix(in oklab, ${accent} 15%, transparent)` }}
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
