import { useEffect, useMemo, useState } from "react";
import { ARCHITECTURES, ARCHITECTURE_ORDER, architectureColor } from "../lib/architectures";
import { loadEval } from "../lib/data";
import type {
  ArchitectureId,
  ArchitectureSummary,
  EvalReport,
  QuestionType,
} from "../lib/types";

// ---------------------------------------------------------------------------
// Column model
// ---------------------------------------------------------------------------

type ColumnId =
  | "architecture"
  | "n_questions"
  | "recall_at_5_mean"
  | "mrr_at_10_mean"
  | "ndcg_at_10_mean"
  | "recall_full_mean"
  | "faithfulness_mean"
  | "refusal_correctness_rate"
  | "latency_ms_mean"
  | "llm_calls_mean";

type Format = "int" | "ratio" | "ms" | "count";

interface Column {
  id: ColumnId;
  label: string;
  /** Short note under the header, e.g. the "rank" grouping hint. */
  sub?: string;
  format?: Format;
  /** True for the three rank-sensitive metrics the caveat is about. */
  rankSensitive?: boolean;
}

const COLUMNS: Column[] = [
  { id: "architecture", label: "Architecture" },
  { id: "n_questions", label: "n", sub: "questions", format: "int" },
  { id: "recall_at_5_mean", label: "recall@5", sub: "rank-sensitive", format: "ratio", rankSensitive: true },
  { id: "mrr_at_10_mean", label: "MRR@10", sub: "rank-sensitive", format: "ratio", rankSensitive: true },
  { id: "ndcg_at_10_mean", label: "nDCG@10", sub: "rank-sensitive", format: "ratio", rankSensitive: true },
  { id: "recall_full_mean", label: "recall_full", sub: "rank-insensitive", format: "ratio" },
  { id: "faithfulness_mean", label: "faithfulness", sub: "LLM judge", format: "ratio" },
  { id: "refusal_correctness_rate", label: "refusal correct.", sub: "LLM judge", format: "ratio" },
  { id: "latency_ms_mean", label: "latency", sub: "ms, mean", format: "ms" },
  { id: "llm_calls_mean", label: "LLM calls", sub: "mean", format: "count" },
];

type MetricColumnId = Exclude<ColumnId, "architecture">;
type MetricColumn = Column & { id: MetricColumnId };

/** Every column except the architecture label — i.e. the ones that index
 * straight into ArchitectureSummary. */
const METRIC_COLUMNS = COLUMNS.filter((c): c is MetricColumn => c.id !== "architecture");

interface SortState {
  column: ColumnId;
  direction: "asc" | "desc";
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

function formatValue(value: number | null, format: Format | undefined): string {
  if (value === null || !Number.isFinite(value)) return "—";
  switch (format) {
    case "int":
      return String(value);
    case "ms":
      return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    case "count":
      return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    case "ratio":
    default:
      return value.toFixed(3);
  }
}

const QUESTION_TYPES: QuestionType[] = ["factual", "multi_hop", "keyword", "unanswerable"];

const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  factual: "Factual",
  multi_hop: "Multi-hop",
  keyword: "Keyword",
  unanswerable: "Unanswerable",
};

/** "NOT meaningful" / "reduced meaning" / "reliable" — the three shapes the
 * per-row rank_metrics_note actually takes (Phase 6.2). Used only to tint the
 * note; the note's own text is always rendered in full. */
function noteTone(note: string): "bad" | "warn" | "ok" {
  const lower = note.toLowerCase();
  if (lower.startsWith("not meaningful")) return "bad";
  if (lower.includes("reduced meaning")) return "warn";
  return "ok";
}

const NOTE_TONE_CLASS: Record<"bad" | "warn" | "ok", string> = {
  bad: "text-status-critical",
  warn: "text-status-warning",
  ok: "text-ink-muted",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function Eval() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState>({ column: "architecture", direction: "asc" });
  /** null = aggregated across all questions (the default view). */
  const [questionType, setQuestionType] = useState<QuestionType | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadEval()
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err: unknown) => {
        console.error("failed to load eval data:", err);
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const rows = useMemo(() => {
    if (!report) return [];
    const base = ARCHITECTURE_ORDER.map((id) => ({
      id,
      summary: questionType
        ? report.by_architecture_and_type[id][questionType]
        : report.by_architecture[id],
    })).filter((r): r is { id: ArchitectureId; summary: ArchitectureSummary } => Boolean(r.summary));

    const dir = sort.direction === "asc" ? 1 : -1;
    return [...base].sort((a, b) => {
      if (sort.column === "architecture") {
        return (
          dir * (ARCHITECTURE_ORDER.indexOf(a.id) - ARCHITECTURE_ORDER.indexOf(b.id))
        );
      }
      const av = a.summary[sort.column];
      const bv = b.summary[sort.column];
      // Nulls always sort last, regardless of direction — a missing metric
      // isn't "worst", it's absent, and burying it keeps the top of the
      // table meaningful in both directions.
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      if (av === bv) return ARCHITECTURE_ORDER.indexOf(a.id) - ARCHITECTURE_ORDER.indexOf(b.id);
      return dir * (av - bv);
    });
  }, [report, sort, questionType]);

  function toggleSort(column: ColumnId) {
    setSort((prev) =>
      prev.column === column
        ? { column, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { column, direction: column === "architecture" ? "asc" : "desc" },
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">
          Evaluation
        </span>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          How the seven architectures actually scored
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-ink-secondary">
          {report
            ? `${report.n_architectures} architectures × ${report.n_questions} questions = ${report.rows.length} recorded runs, scored offline. Read the two methodology notes below before reading the table — some of these numbers mean less than they look like they do.`
            : "Real, offline evaluation runs scored across every architecture and question."}
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-status-critical/40 bg-status-critical/5 p-4 text-sm text-ink-secondary">
          Couldn't load the evaluation report.{" "}
          <span className="font-mono text-xs text-ink-muted">{error}</span>
        </div>
      )}

      {/* Permanently visible — never collapsed, never hover-only. These two
       * caveats are the point of the page as much as the table is. */}
      {report && (
        <section aria-label="Methodology notes" className="flex flex-col gap-3">
          <Callout title="Methodology note — rank metrics">
            {report.rank_metrics_caveat}
          </Callout>
          <Callout title="Methodology note — LLM judge">{report.llm_judge_caveat}</Callout>
        </section>
      )}

      {report && <RoutingSummary report={report} />}

      {report && (
        <section aria-label="Metrics" className="flex flex-col gap-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex flex-col gap-1">
              <h2 className="text-lg font-semibold tracking-tight">Metrics by architecture</h2>
              <p className="text-xs text-ink-muted">
                Click a column header to sort. Every value is a mean over the questions in view.
              </p>
            </div>
            <div
              role="group"
              aria-label="Question type filter"
              className="flex flex-wrap gap-1.5"
            >
              <TypeChip
                label="All questions"
                active={questionType === null}
                onClick={() => setQuestionType(null)}
              />
              {QUESTION_TYPES.map((type) => (
                <TypeChip
                  key={type}
                  label={QUESTION_TYPE_LABEL[type]}
                  active={questionType === type}
                  onClick={() => setQuestionType(type)}
                />
              ))}
            </div>
          </div>

          {/* Wide content scrolls inside its own container so the page body
           * never scrolls horizontally at 375px. */}
          <div className="overflow-x-auto rounded-lg border border-border bg-surface">
            <table className="w-full min-w-[64rem] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-page align-bottom">
                  {COLUMNS.map((col) => {
                    const isSorted = sort.column === col.id;
                    const numeric = col.id !== "architecture";
                    return (
                      <th
                        key={col.id}
                        scope="col"
                        aria-sort={
                          isSorted
                            ? sort.direction === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                        className={`px-3 py-2 font-medium ${numeric ? "text-right" : "text-left"}`}
                      >
                        <button
                          type="button"
                          onClick={() => toggleSort(col.id)}
                          className={`flex w-full flex-col gap-0.5 ${
                            numeric ? "items-end" : "items-start"
                          } cursor-pointer transition-colors hover:text-ink ${
                            isSorted ? "text-ink" : "text-ink-secondary"
                          }`}
                        >
                          <span className="whitespace-nowrap text-xs font-semibold">
                            {col.label}
                            <span aria-hidden="true" className="ml-1 text-ink-muted">
                              {isSorted ? (sort.direction === "asc" ? "▲" : "▼") : "↕"}
                            </span>
                          </span>
                          {col.sub && (
                            <span className="whitespace-nowrap text-[10px] font-normal text-ink-muted">
                              {col.sub}
                            </span>
                          )}
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {rows.map(({ id, summary }) => {
                  const meta = ARCHITECTURES[id];
                  const tone = noteTone(summary.rank_metrics_note);
                  return (
                    <tr key={id} className="border-b border-border align-top last:border-0">
                      <th scope="row" className="px-3 py-3 text-left font-normal">
                        <div className="flex items-center gap-2">
                          <span
                            aria-hidden="true"
                            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ background: architectureColor(id) }}
                          />
                          <span className="font-medium text-ink">{meta.name}</span>
                        </div>
                        {/* Always visible, never truncated or hover-gated:
                         * which rows the rank-metrics caveat actually bites
                         * on, and how hard, differs per architecture. */}
                        <p
                          className={`mt-1 max-w-[22rem] text-[11px] leading-snug ${NOTE_TONE_CLASS[tone]}`}
                        >
                          <span className="font-medium">Rank metrics: </span>
                          {summary.rank_metrics_note}
                        </p>
                      </th>
                      {METRIC_COLUMNS.map((col) => {
                        const value = summary[col.id];
                        const dimmed = col.rankSensitive && tone !== "ok";
                        return (
                          <td
                            key={col.id}
                            className={`px-3 py-3 text-right font-mono text-xs tabular-nums ${
                              dimmed ? "text-ink-muted line-through decoration-1" : "text-ink"
                            }`}
                            title={
                              dimmed
                                ? "Struck through: this architecture's rank_metrics_note says this number is not trustworthy — see the note in the first column."
                                : undefined
                            }
                          >
                            {formatValue(value, col.format)}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-ink-muted">
            Struck-through rank metrics are the ones that architecture's own note flags as not
            meaningful or reduced — read <span className="font-mono">recall_full</span> instead
            for those rows.
          </p>
        </section>
      )}

      {!report && !error && <p className="text-sm text-ink-muted">Loading evaluation report…</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pieces
// ---------------------------------------------------------------------------

function Callout({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-status-warning/40 bg-status-warning/10 p-4">
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-status-warning">
        {title}
      </div>
      <p className="text-sm leading-relaxed text-ink-secondary">{children}</p>
    </div>
  );
}

function TypeChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`cursor-pointer rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? "border-ink bg-ink text-page"
          : "border-border text-ink-secondary hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

function RoutingSummary({ report }: { report: EvalReport }) {
  const { rubric, correct, total, accuracy } = report.adaptive_routing_accuracy;
  return (
    <section
      aria-label="Adaptive routing accuracy"
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-sm font-semibold tracking-tight">Adaptive routing accuracy</h2>
        <span className="font-mono text-lg font-semibold tabular-nums text-ink">
          {accuracy === null ? "—" : `${(accuracy * 100).toFixed(1)}%`}
        </span>
        <span className="text-xs text-ink-muted">
          {correct}/{total} questions routed to an architecture the rubric accepts
        </span>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="text-xs font-medium text-ink-muted">
          Rubric — which architectures count as a correct route per question type
        </div>
        <ul className="flex flex-col gap-1.5 sm:flex-row sm:flex-wrap sm:gap-3">
          {QUESTION_TYPES.map((type) => (
            <li key={type} className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-ink-secondary">{QUESTION_TYPE_LABEL[type]}:</span>
              {(rubric[type] ?? []).map((id) => (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-[11px] text-ink-secondary"
                >
                  <span
                    aria-hidden="true"
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: architectureColor(id) }}
                  />
                  {ARCHITECTURES[id].name}
                </span>
              ))}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
