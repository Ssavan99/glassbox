import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { CodeBlock } from "../components/CodeBlock";
import { ARCHITECTURES, ARCHITECTURE_ORDER, architectureColor } from "../lib/architectures";
import { loadCodeExcerpts, loadEval } from "../lib/data";
import { TUTORIAL_CONTENT, type TutorialStep } from "../lib/tutorialContent";
import type {
  AdaptiveRoutingAccuracy,
  ArchitectureId,
  ArchitectureSummary,
  CodeExcerpts,
  EvalReport,
} from "../lib/types";
import { ARCHITECTURE_IDS } from "../lib/types";
import { KIND_GLYPH, KIND_NAME } from "../trace/nodeMeta";

function isArchitectureId(value: string | undefined): value is ArchitectureId {
  return !!value && (ARCHITECTURE_IDS as readonly string[]).includes(value);
}

export function Tutorial() {
  const { arch } = useParams<{ arch: string }>();

  if (!isArchitectureId(arch)) {
    return <Navigate to="/404" replace />;
  }

  return <TutorialPage archId={arch} />;
}

function TutorialPage({ archId }: { archId: ArchitectureId }) {
  const meta = ARCHITECTURES[archId];
  const content = TUTORIAL_CONTENT[archId];
  const color = architectureColor(archId);

  const [excerpts, setExcerpts] = useState<CodeExcerpts | null>(null);
  const [report, setReport] = useState<EvalReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadCodeExcerpts(), loadEval()])
      .then(([codeExcerpts, evalReport]) => {
        if (!cancelled) {
          setExcerpts(codeExcerpts);
          setReport(evalReport);
        }
      })
      .catch((err: unknown) => {
        console.error("failed to load tutorial data:", err);
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ordinal = ARCHITECTURE_ORDER.indexOf(archId) + 1;

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium"
            style={{ borderColor: `color-mix(in oklab, ${color} 40%, transparent)`, color }}
          >
            <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
            {ordinal} of {ARCHITECTURE_ORDER.length} — start here order
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{meta.name}</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-ink-secondary sm:text-base">{meta.tagline}</p>
      </header>

      <Section title="The problem it solves">
        {content.problem.map((p, i) => (
          <p key={i} className="text-sm leading-relaxed text-ink-secondary">
            {p}
          </p>
        ))}
      </Section>

      <Section title="How it works">
        <StepDiagram steps={content.steps} color={color} />
      </Section>

      <Section title="Real code, from source">
        <p className="text-sm leading-relaxed text-ink-secondary">
          This is <code className="font-mono text-xs">{meta.name}</code>'s actual{" "}
          <code className="font-mono text-xs">run()</code> method, extracted directly from{" "}
          <code className="font-mono text-xs">engine/architectures/{archId}.py</code> at build time —
          not a hand-copied summary that can quietly drift out of sync with what the code actually does.
        </p>
        {error && <ErrorNote error={error} what="code excerpt" />}
        {excerpts ? (
          <CodeBlock excerpt={excerpts[archId]} />
        ) : (
          !error && <p className="text-sm text-ink-muted">Loading real source…</p>
        )}
      </Section>

      {content.deviationNote && (
        <Callout title="Documented deviation from the CRAG paper (D7)" tone="warn">
          {content.deviationNote}
        </Callout>
      )}

      <Section title="When it wins">
        {content.whenItWins.map((p, i) => (
          <p key={i} className="text-sm leading-relaxed text-ink-secondary">
            {p}
          </p>
        ))}
      </Section>

      <Section title="When it loses">
        {content.whenItLoses.map((p, i) => (
          <p key={i} className="text-sm leading-relaxed text-ink-secondary">
            {p}
          </p>
        ))}
      </Section>

      <Section title="Its own eval row">
        {error && <ErrorNote error={error} what="evaluation report" />}
        {report ? (
          <div className="flex flex-col gap-3">
            <EvalRowSummary archId={archId} summary={report.by_architecture[archId]} />
            {archId === "adaptive" && (
              <RoutingAccuracy accuracy={report.adaptive_routing_accuracy} />
            )}
          </div>
        ) : (
          !error && <p className="text-sm text-ink-muted">Loading real evaluation data…</p>
        )}
      </Section>

      <TutorialNav current={archId} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pieces
// ---------------------------------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}

function ErrorNote({ error, what }: { error: string; what: string }) {
  return (
    <div className="rounded-lg border border-status-critical/40 bg-status-critical/5 p-4 text-sm text-ink-secondary">
      Couldn't load the real {what}. <span className="font-mono text-xs text-ink-muted">{error}</span>
    </div>
  );
}

function Callout({
  title,
  tone,
  children,
}: {
  title: string;
  tone: "warn" | "critical";
  children: React.ReactNode;
}) {
  const styles =
    tone === "warn"
      ? "border-status-warning/40 bg-status-warning/10 text-status-warning"
      : "border-status-critical/40 bg-status-critical/10 text-status-critical";
  return (
    <div className={`rounded-lg border p-4 ${styles.split(" ").slice(0, 2).join(" ")}`}>
      <div className={`mb-1.5 text-xs font-semibold uppercase tracking-wide ${styles.split(" ")[2]}`}>{title}</div>
      <p className="text-sm leading-relaxed text-ink-secondary">{children}</p>
    </div>
  );
}

/** A simplified, illustrative flow of the architecture's real step kinds --
 * see tutorialContent.ts's doc comment for why this isn't a literal DAG
 * render (that's /explore's job, against real recorded data). */
function StepDiagram({ steps, color }: { steps: TutorialStep[]; color: string }) {
  return (
    <div className="flex flex-wrap items-stretch gap-2" role="list" aria-label="Pipeline steps">
      {steps.map((step, i) => (
        <div key={i} className="flex items-stretch gap-2">
          <div
            role="listitem"
            className={`flex w-56 flex-col gap-1 rounded-lg border bg-surface p-3 ${
              step.repeat ? "border-dashed" : "border-solid"
            }`}
            style={{ borderColor: `color-mix(in oklab, ${color} 45%, var(--border))` }}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color }}>
                <span aria-hidden="true">{KIND_GLYPH[step.kind]}</span>
                {KIND_NAME[step.kind]}
              </span>
              {step.repeat && (
                <span aria-hidden="true" className="text-xs text-ink-muted" title="Can repeat">
                  ↻
                </span>
              )}
            </div>
            <div className="text-sm font-medium text-ink">{step.label}</div>
            <p className="text-xs leading-snug text-ink-muted">{step.note}</p>
          </div>
          {i < steps.length - 1 && (
            <span aria-hidden="true" className="flex items-center text-ink-muted">
              →
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function EvalRowSummary({ archId, summary }: { archId: ArchitectureId; summary: ArchitectureSummary }) {
  const tone = noteTone(summary.rank_metrics_note);
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="recall_full" sub="rank-insensitive" value={formatRatio(summary.recall_full_mean)} />
        <Stat label="faithfulness" sub="LLM judge" value={formatRatio(summary.faithfulness_mean)} />
        <Stat label="latency" sub="ms, mean" value={formatMs(summary.latency_ms_mean)} />
        <Stat label="LLM calls" sub="mean" value={formatCount(summary.llm_calls_mean)} />
      </div>
      <p className={`text-xs leading-snug ${NOTE_TONE_CLASS[tone]}`}>
        <span className="font-medium">Rank metrics: </span>
        {summary.rank_metrics_note}
      </p>
      <Link
        to={`/eval`}
        className="w-fit text-xs text-ink-secondary underline decoration-dotted hover:text-ink"
      >
        See {ARCHITECTURES[archId].name}'s full row, and every other architecture's, on /eval →
      </Link>
    </div>
  );
}

/** Renders the real, live routing-accuracy number from artifacts/eval.json
 * (the same field Eval.tsx's RoutingSummary shows) -- specifically so the
 * "when it loses" prose above can point at a real number on this page
 * instead of hardcoding one that could drift from a future eval re-run. */
function RoutingAccuracy({ accuracy }: { accuracy: AdaptiveRoutingAccuracy }) {
  const { correct, total, accuracy: rate } = accuracy;
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-lg border border-border bg-surface p-4">
      <span className="text-xs font-medium text-ink-muted">Real routing accuracy:</span>
      <span className="font-mono text-lg font-semibold tabular-nums text-ink">
        {rate === null ? "—" : `${(rate * 100).toFixed(1)}%`}
      </span>
      <span className="text-xs text-ink-muted">
        {correct}/{total} questions routed to an architecture the logged rubric accepts — full
        rubric on{" "}
        <Link to="/eval" className="underline decoration-dotted hover:text-ink">
          /eval
        </Link>
      </span>
    </div>
  );
}

function Stat({ label, sub, value }: { label: string; sub: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">
        {label} <span className="normal-case">· {sub}</span>
      </div>
      <div className="font-mono text-lg tabular-nums text-ink">{value}</div>
    </div>
  );
}

function formatRatio(v: number | null): string {
  return v === null || !Number.isFinite(v) ? "—" : v.toFixed(3);
}
function formatMs(v: number | null): string {
  return v === null || !Number.isFinite(v) ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
function formatCount(v: number | null): string {
  return v === null || !Number.isFinite(v) ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/** Same three-way classification Eval.tsx uses for the identical field. */
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

function TutorialNav({ current }: { current: ArchitectureId }) {
  const idx = ARCHITECTURE_ORDER.indexOf(current);
  const prev = idx > 0 ? ARCHITECTURE_ORDER[idx - 1] : null;
  const next = idx < ARCHITECTURE_ORDER.length - 1 ? ARCHITECTURE_ORDER[idx + 1] : null;

  return (
    <nav aria-label="Tutorial navigation" className="flex items-stretch justify-between gap-3 border-t border-border pt-6">
      {prev ? (
        <Link
          to={`/tutorial/${prev}`}
          className="flex flex-1 flex-col gap-0.5 rounded-lg border border-border bg-surface p-3 text-left transition-colors hover:border-ink/30 sm:flex-initial sm:min-w-[12rem]"
        >
          <span className="text-[10px] uppercase tracking-wide text-ink-muted">← Previous</span>
          <span className="text-sm font-medium text-ink">{ARCHITECTURES[prev].name}</span>
        </Link>
      ) : (
        <div className="flex-1 sm:flex-initial sm:min-w-[12rem]" />
      )}
      {next ? (
        <Link
          to={`/tutorial/${next}`}
          className="flex flex-1 flex-col items-end gap-0.5 rounded-lg border border-border bg-surface p-3 text-right transition-colors hover:border-ink/30 sm:flex-initial sm:min-w-[12rem]"
        >
          <span className="text-[10px] uppercase tracking-wide text-ink-muted">Next →</span>
          <span className="text-sm font-medium text-ink">{ARCHITECTURES[next].name}</span>
        </Link>
      ) : (
        <Link
          to="/compare"
          className="flex flex-1 flex-col items-end gap-0.5 rounded-lg border border-border bg-surface p-3 text-right transition-colors hover:border-ink/30 sm:flex-initial sm:min-w-[12rem]"
        >
          <span className="text-[10px] uppercase tracking-wide text-ink-muted">All seven read →</span>
          <span className="text-sm font-medium text-ink">See them compared</span>
        </Link>
      )}
    </nav>
  );
}
