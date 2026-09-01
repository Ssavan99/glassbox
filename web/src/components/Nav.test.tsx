// @vitest-environment jsdom
/**
 * Phase 7.1: asserts the actual click-triggered state change on the mobile
 * menu button, not just a screenshot. The original Phase 7 nav bug (an
 * overlap at ~611px) and its fix were both verified only visually, which is
 * exactly why a later report of "the button doesn't seem to open the menu"
 * couldn't be resolved from screenshots alone -- this closes that gap with
 * a real, user-event-driven interaction test that doesn't depend on a live
 * browser pane being visible (see the Phase 7.1 decision log entry: the
 * actual live-browser investigation found the button works correctly; a
 * browser-automation pane-visibility artifact, not a component bug,
 * produced the original report's symptom).
 *
 * The desktop nav's links stay in the DOM at all times (hidden purely via a
 * Tailwind `hidden md:flex` class), and this test environment doesn't load
 * the compiled stylesheet, so Testing Library's usual "hidden elements are
 * excluded from role queries" behavior doesn't kick in here the way it
 * would in a real browser -- every query below is scoped with `within()`
 * to the mobile `<nav aria-label="Mobile">` landmark specifically, rather
 * than relying on that.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Nav } from "./Nav";

function renderNav() {
  return render(
    <MemoryRouter>
      <Nav />
    </MemoryRouter>,
  );
}

function mobileMenu() {
  return within(screen.getByRole("navigation", { name: "Mobile" }));
}

describe("Nav mobile menu", () => {
  it("starts closed -- no mobile menu landmark in the document at all", () => {
    renderNav();
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByRole("navigation", { name: "Mobile" })).not.toBeInTheDocument();
  });

  it("opens on click: aria-expanded flips and every link becomes accessible", async () => {
    const user = userEvent.setup();
    renderNav();

    await user.click(screen.getByRole("button", { name: "Open menu" }));

    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    const menu = mobileMenu();
    for (const label of ["Home", "Explore", "Compare", "Tutorial", "Sandbox", "Eval", "GitHub"]) {
      expect(menu.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("closes on a second click of the same button (toggle, not one-way)", async () => {
    const user = userEvent.setup();
    renderNav();

    const toggle = () => screen.getByRole("button", { name: /menu/ });
    await user.click(toggle());
    expect(toggle()).toHaveAttribute("aria-expanded", "true");

    await user.click(toggle());
    expect(toggle()).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("navigation", { name: "Mobile" })).not.toBeInTheDocument();
  });

  it("clicking a link inside the open menu navigates and closes the menu", async () => {
    const user = userEvent.setup();
    renderNav();

    await user.click(screen.getByRole("button", { name: "Open menu" }));
    await user.click(mobileMenu().getByRole("link", { name: "Compare" }));

    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByRole("navigation", { name: "Mobile" })).not.toBeInTheDocument();
  });
});
