import { useState } from "react";
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
  const [open, setOpen] = useState(false);

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

        {/* Below md there isn't room for all six links plus the logo and
         * controls -- a horizontally-scrolling link row was tried first,
         * but it truncated "Eval" mid-word with only a faint scrollbar as
         * the sole hint that more links existed. A collapsible menu makes
         * every link fully visible and discoverable instead. */}
        <nav className="hidden flex-1 items-center justify-center gap-1 md:flex">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => linkClasses(isActive)}
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
            className="hidden text-sm text-ink-secondary hover:text-ink md:inline"
          >
            GitHub
          </a>
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="rounded-full border border-border p-2 text-ink-secondary transition-colors hover:border-arch-naive hover:text-ink md:hidden"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              {open ? (
                <path
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  d="M3 3l10 10M13 3L3 13"
                />
              ) : (
                <path
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  d="M2 4h12M2 8h12M2 12h12"
                />
              )}
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <nav className="flex flex-col gap-1 border-t border-border px-4 py-3 md:hidden">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) => linkClasses(isActive)}
            >
              {link.label}
            </NavLink>
          ))}
          <a
            href="https://github.com/Ssavan99/glassbox"
            target="_blank"
            rel="noreferrer"
            className="rounded-md px-3 py-1.5 text-sm font-medium text-ink-secondary hover:text-ink"
          >
            GitHub
          </a>
        </nav>
      )}
    </header>
  );
}
