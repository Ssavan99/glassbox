import { Outlet } from "react-router-dom";
import { Nav } from "./Nav";

export function Layout() {
  return (
    <div className="flex min-h-full flex-col bg-page text-ink">
      <Nav />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-14 sm:px-6 sm:py-20">
        <Outlet />
      </main>
      <footer className="border-t-2 border-border px-4 py-8 text-center text-xs text-ink-muted sm:px-6">
        Seven RAG architectures, run for real, recorded and replayed — never live-called from this
        page.{" "}
        <a
          href="https://github.com/Ssavan99/glassbox"
          target="_blank"
          rel="noreferrer"
          className="underline decoration-dotted hover:text-ink-secondary"
        >
          Source on GitHub
        </a>
      </footer>
    </div>
  );
}
