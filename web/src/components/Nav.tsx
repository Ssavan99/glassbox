import { NavLink } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/explore", label: "Explore" },
  { to: "/compare", label: "Compare" },
  { to: "/tutorial/naive", label: "Tutorial" },
  { to: "/sandbox", label: "Sandbox" },
  { to: "/eval", label: "Eval" },
];

function linkClasses(isActive: boolean): string {
  return [
    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
    isActive ? "bg-arch-naive/15 text-arch-naive" : "text-ink-secondary hover:text-ink",
  ].join(" ");
}

export function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <NavLink
          to="/"
          className="flex shrink-0 items-center gap-2 text-base font-semibold tracking-tight"
        >
          <span
            aria-hidden="true"
            className="inline-block h-3 w-3 rounded-full"
            style={{ background: "var(--arch-naive)" }}
          />
          glassbox
        </NavLink>

        <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto sm:justify-center">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => `shrink-0 ${linkClasses(isActive)}`}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-3">
          <a
            href="https://github.com/Ssavan99/glassbox"
            target="_blank"
            rel="noreferrer"
            className="hidden text-sm text-ink-secondary hover:text-ink sm:inline"
          >
            GitHub
          </a>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
