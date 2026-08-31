import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ARCHITECTURES, ARCHITECTURE_ORDER, architectureColor } from "../lib/architectures";
import { loadChunks, loadEval } from "../lib/data";
import type { EvalReport } from "../lib/types";

interface Stats {
  nArchitectures: number;
  nQuestions: number;
  nTraces: number;
  nChunks: number;
}

export function Home() {
  const [stats, setStats] = useState<Stats | "error" | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadEval(), loadChunks()])
      .then(([report, chunks]: [EvalReport, unknown[]]) => {
        if (cancelled) return;
        setStats({
          nArchitectures: report.n_architectures,
          nQuestions: report.n_questions,
          nTraces: report.rows.length,
          nChunks: chunks.length,
        });
      })
      .catch(() => {
        if (!cancelled) setStats("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-16">
      <section className="flex flex-col items-center gap-5 pt-6 text-center sm:pt-12">
        <span className="rounded-full border border-border px-3 py-1 text-xs font-medium uppercase tracking-wide text-ink-muted">
          See inside RAG
        </span>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
          Seven retrieval-augmented generation architectures, run for real.
        </h1>
        <p className="max-w-xl text-base text-ink-secondary sm:text-lg">
          Every intermediate step recorded offline and replayed here — not animated mock-ups.
          Explore one trace at a time, or compare all seven against the same question.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            to="/compare"
            className="rounded-md bg-arch-naive px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Compare all seven
          </Link>
          <Link
            to="/tutorial/naive"
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-ink-secondary transition-colors hover:text-ink"
          >
            Read the tutorials
          </Link>
        </div>
      </section>

      <section aria-label="Dataset stats" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Architectures" value={stats} pick="nArchitectures" />
        <StatTile label="Eval questions" value={stats} pick="nQuestions" />
        <StatTile label="Recorded traces" value={stats} pick="nTraces" />
        <StatTile label="Corpus chunks" value={stats} pick="nChunks" />
      </section>

      <section aria-label="The seven architectures">
        <h2 className="mb-5 text-lg font-semibold tracking-tight">The seven architectures</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ARCHITECTURE_ORDER.map((id) => {
            const meta = ARCHITECTURES[id];
            return (
              <Link
                key={id}
                to={`/tutorial/${id}`}
                className="group flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 transition-colors hover:border-ink-muted"
              >
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ background: architectureColor(id) }}
                  />
                  <span className="font-medium">{meta.name}</span>
                </div>
                <p className="text-sm text-ink-secondary">{meta.tagline}</p>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function StatTile({
  label,
  value,
  pick,
}: {
  label: string;
  value: Stats | "error" | null;
  pick: keyof Stats;
}) {
  const display =
    value === null ? "…" : value === "error" ? "—" : value[pick].toLocaleString();
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="font-mono text-2xl font-semibold tabular-nums">{display}</div>
      <div className="mt-1 text-xs text-ink-muted">{label}</div>
    </div>
  );
}
