// This file's setupFiles registration in vite.config.ts applies to every
// test file regardless of that file's own `@vitest-environment` pragma --
// including src/lib/data.test.ts, which deliberately runs in the default
// Node environment (reads real JSON off disk via node:fs) and has no
// `window` at all. Everything here is DOM-only, so it's a no-op there.
if (typeof window !== "undefined") {
  await import("@testing-library/jest-dom/vitest");
  const { cleanup } = await import("@testing-library/react");
  const { afterEach } = await import("vitest");

  // Without this, each test's render() mounts a new instance without
  // unmounting the previous one (no `globals: true` in vite.config.ts's
  // `test` block, so React Testing Library's own auto-cleanup detection
  // doesn't kick in), so a later test in the same file sees N accumulated
  // copies of every element from N earlier tests.
  afterEach(() => {
    cleanup();
  });
}
