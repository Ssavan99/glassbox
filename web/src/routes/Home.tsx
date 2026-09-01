import { useEffect, useState, type CSSProperties } from "react";
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

const STAT_ACCENTS = [
  "var(--arch-naive)",
  "var(--arch-hybrid)",
  "var(--arch-graph)",
  "var(--arch-adaptive)",
] as const;

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
      .catch((err: unknown) => {
        // Surfaced in devtools even though the UI just shows "—" for each
        // stat -- see data.ts's fetchJson for the most common cause
        // (public/data/ missing in a fresh dev checkout).
        console.error("failed to load stats data:", err);
        if (!cancelled) setStats("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-20 sm:gap-24">
      <section className="reveal-up flex flex-col items-center gap-6 pt-6 text-center sm:pt-12">
        <span
          className="hero-eyebrow bg-surface px-4 py-1.5 text-xs font-bold uppercase tracking-[0.14em]"
          style={{ borderColor: "var(--arch-hybrid)", color: "var(--arch-hybrid)" }}
        >
          See inside RAG
        </span>
        <h1 className="display-type max-w-4xl text-5xl sm:text-6xl lg:text-7xl">
          Seven retrieval-augmented generation architectures, run for real.
        </h1>
        <p className="max-w-xl text-base text-ink-secondary sm:text-lg">
          Every intermediate step recorded offline and replayed here — not animated mock-ups.
          Explore one trace at a time, or compare all seven against the same question.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4 pt-3">
          <Link
            to="/compare"
            className="pill-button sticker-interactive bg-arch-naive px-5 py-2.5 text-sm font-bold text-white"
          >
            Compare all seven
          </Link>
          <Link
            to="/tutorial/naive"
            className="pill-button sticker-interactive bg-surface px-5 py-2.5 text-sm font-bold hover:text-ink"
            style={{ borderColor: "var(--arch-adaptive)", color: "var(--arch-adaptive)" }}
          >
            Read the tutorials
          </Link>
        </div>
      </section>

      <section aria-label="Dataset stats" className="reveal-grid grid grid-cols-2 gap-5 sm:grid-cols-4">
        <StatTile label="Architectures" value={stats} pick="nArchitectures" accent={STAT_ACCENTS[0]} />
        <StatTile label="Eval questions" value={stats} pick="nQuestions" accent={STAT_ACCENTS[1]} />
        <StatTile label="Recorded traces" value={stats} pick="nTraces" accent={STAT_ACCENTS[2]} />
        <StatTile label="Corpus chunks" value={stats} pick="nChunks" accent={STAT_ACCENTS[3]} />
      </section>

      <section aria-label="The seven architectures">
        <h2 className="section-heading mb-7 text-2xl">The seven architectures</h2>
        <div className="reveal-grid grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {ARCHITECTURE_ORDER.map((id) => {
            const meta = ARCHITECTURES[id];
            return (
              <Link
                key={id}
                to={`/tutorial/${id}`}
                className="architecture-card sticker-interactive group flex flex-col gap-3 p-5"
                style={{ "--accent": architectureColor(id) } as CSSProperties}
              >
                <div className="flex items-center gap-2">
                  <span aria-hidden="true" className="icon-badge" style={{ "--accent": architectureColor(id) } as CSSProperties}>
                    <span>{ARCHITECTURE_ORDER.indexOf(id) + 1}</span>
                  </span>
                  <span className="text-lg font-bold">{meta.name}</span>
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
  accent,
}: {
  label: string;
  value: Stats | "error" | null;
  pick: keyof Stats;
  accent: string;
}) {
  const display =
    value === null ? "…" : value === "error" ? "—" : value[pick].toLocaleString();
  return (
    <div className="sticker-surface stat-tile flex flex-col justify-between p-5" style={{ "--stat-accent": accent } as CSSProperties}>
      <div className="font-mono text-3xl font-bold tabular-nums">{display}</div>
      <div className="mt-2 text-xs font-bold uppercase tracking-wide text-ink-muted">{label}</div>
    </div>
  );
}
