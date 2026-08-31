import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center">
      <div className="font-mono text-5xl font-semibold text-ink-muted">404</div>
      <h1 className="text-2xl font-semibold tracking-tight">This page doesn't exist</h1>
      <p className="max-w-sm text-sm text-ink-secondary">
        Nothing was recorded at this route. Try one of the seven architectures instead.
      </p>
      <Link
        to="/"
        className="rounded-md bg-arch-naive px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
      >
        Back to home
      </Link>
    </div>
  );
}
