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
    "nav-link px-3 py-1.5 text-sm font-semibold sticker-interactive",
    isActive ? "nav-link--active bg-arch-naive/15 text-arch-naive" : "text-ink-secondary hover:text-ink",
  ].join(" ");
}

function PipelineMark() {
  return (
    <span aria-hidden="true" className="logo-mark ambient-mark">
      <svg viewBox="0 0 32 32" fill="none">
        <path d="M8 11h16M10.5 17h11M16 17v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <circle cx="8" cy="11" r="2.4" fill="var(--arch-naive)" />
        <circle cx="16" cy="11" r="2.4" fill="var(--arch-hybrid)" />
        <circle cx="24" cy="11" r="2.4" fill="var(--arch-hyde)" />
        <circle cx="10.5" cy="17" r="2.4" fill="var(--arch-corrective)" />
        <circle cx="16" cy="17" r="2.4" fill="var(--arch-graph)" />
        <circle cx="21.5" cy="17" r="2.4" fill="var(--arch-agentic)" />
        <circle cx="16" cy="24" r="2.7" fill="var(--arch-adaptive)" />
      </svg>
    </span>
  );
}

export function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="nav-shell sticky top-0 z-20 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <NavLink
          to="/"
          className="flex shrink-0 items-center gap-2 text-base font-bold tracking-tight"
        >
          <PipelineMark />
          glassbox
        </NavLink>

        {/* Below md there isn't room for all six links plus the logo and
         * controls -- a horizontally-scrolling link row was tried first,
         * but it truncated "Eval" mid-word with only a faint scrollbar as
         * the sole hint that more links existed. A collapsible menu makes
         * every link fully visible and discoverable instead. */}
        <nav
          aria-label="Primary"
          className="hidden flex-1 items-center justify-center gap-1 md:flex"
        >
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
            className="hidden text-sm font-semibold text-ink-secondary transition-colors hover:text-ink md:inline"
          >
            GitHub
          </a>
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="pill-button sticker-interactive p-2 text-ink-secondary hover:border-arch-naive hover:text-ink md:hidden"
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
        <nav
          aria-label="Mobile"
          className="flex flex-col gap-2 border-t-2 border-border px-4 py-4 md:hidden"
        >
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
            className="nav-link px-3 py-1.5 text-sm font-semibold text-ink-secondary sticker-interactive hover:text-ink"
          >
            GitHub
          </a>
        </nav>
      )}
    </header>
  );
}
