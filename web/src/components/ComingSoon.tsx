interface ComingSoonProps {
  title: string;
  phase: string;
  description: string;
}

/** Placeholder for the routes Phases 8-10 build out. Phase 7 only owns the
 * shell (nav, routing, 404, responsive layout) -- deliberately not faked
 * with mock content, per the project's "recorded from real runs" claim. */
export function ComingSoon({ title, phase, description }: ComingSoonProps) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center">
      <span className="rounded-full border border-border px-3 py-1 text-xs font-medium uppercase tracking-wide text-ink-muted">
        {phase}
      </span>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      <p className="max-w-md text-sm text-ink-secondary sm:text-base">{description}</p>
    </div>
  );
}
