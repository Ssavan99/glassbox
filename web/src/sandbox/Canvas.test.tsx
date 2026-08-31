// @vitest-environment jsdom
/**
 * Phase 10: interaction tests for the sandbox canvas. These exist for the
 * same reason Nav.test.tsx does -- the mobile-critical paths here (tap a
 * palette entry to add a step, tap a node to select it, tap the delete
 * affordance) can't be verified by looking at a screenshot, and the two
 * things this component must never quietly lose (a *readable* validation
 * error, and the live/not-live badge) are content assertions, not CSS ones.
 * Every error/badge assertion below queries by visible text on purpose: a
 * class-name assertion would still pass if the text were hover-only.
 *
 * React Flow needs browser APIs jsdom doesn't ship (ResizeObserver,
 * DOMMatrixReadOnly, non-zero element boxes, SVGElement.getBBox), so they're
 * stubbed here -- this is the documented pattern for testing @xyflow/react
 * under jsdom, not a workaround for anything in Canvas.tsx.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { SandboxCanvas } from "./Canvas";
import type { SandboxGraph } from "./types";
import type { ValidationError } from "./validate";

beforeAll(() => {
  // The stub reports a size back immediately on observe(): React Flow keeps
  // a node `visibility: hidden` until it has been measured once, and an
  // invisible node is excluded from Testing Library's role queries -- so an
  // inert ResizeObserver would make every on-card assertion below vacuous.
  globalThis.ResizeObserver = class {
    cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
    }
    observe(target: Element) {
      this.cb(
        [{ target, contentRect: { width: 208, height: 90 } } as unknown as ResizeObserverEntry],
        this as unknown as ResizeObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;

  globalThis.DOMMatrixReadOnly = class {
    m22 = 1;
    constructor(_transform?: string) {}
  } as unknown as typeof DOMMatrixReadOnly;

  for (const prop of ["offsetWidth", "offsetHeight"] as const) {
    Object.defineProperty(HTMLElement.prototype, prop, {
      configurable: true,
      value: 208,
    });
  }
  (SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () =>
    ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect;
});

const EMPTY: SandboxGraph = { nodes: [], edges: [] };

function renderCanvas(overrides: {
  graph?: SandboxGraph;
  errors?: ValidationError[];
  selectedNodeId?: string | null;
}) {
  const onChange = vi.fn();
  const onSelectNode = vi.fn();
  render(
    <SandboxCanvas
      graph={overrides.graph ?? EMPTY}
      onChange={onChange}
      selectedNodeId={overrides.selectedNodeId ?? null}
      onSelectNode={onSelectNode}
      errors={overrides.errors ?? []}
    />,
  );
  return { onChange, onSelectNode };
}

describe("SandboxCanvas palette", () => {
  it("tap-to-add: clicking a palette entry adds that kind to the graph", async () => {
    const user = userEvent.setup();
    const { onChange, onSelectNode } = renderCanvas({});

    await user.click(screen.getByRole("button", { name: "Add Dense Retrieve" }));

    expect(onChange).toHaveBeenCalledTimes(1);
    const next = onChange.mock.calls[0][0] as SandboxGraph;
    expect(next.nodes).toHaveLength(1);
    expect(next.nodes[0].kind).toBe("retrieve_dense");
    expect(next.nodes[0].id).toBeTruthy();
    expect(typeof next.nodes[0].position.x).toBe("number");
    expect(typeof next.nodes[0].position.y).toBe("number");
    // The freshly-added node becomes the selection, so the inspector the
    // parent renders is pointed at what the user just created.
    expect(onSelectNode).toHaveBeenCalledWith(next.nodes[0].id);
  });

  it("every palette entry is present and labels itself live or not-live", () => {
    renderCanvas({});
    for (const label of [
      "Chunk",
      "Embed Query",
      "Dense Retrieve",
      "Sparse Retrieve",
      "Fuse",
      "Rerank",
      "Grade",
      "Rewrite",
      "Generate",
    ]) {
      expect(screen.getByRole("button", { name: `Add ${label}` })).toBeInTheDocument();
    }
    // 6 live kinds, 3 not-live kinds -- as text on the card face, no hover.
    expect(screen.getAllByText("Live")).toHaveLength(6);
    expect(screen.getAllByText(/Recorded \/ extractive/)).toHaveLength(3);
  });
});

describe("SandboxCanvas nodes", () => {
  const graph: SandboxGraph = {
    nodes: [
      { id: "n1", kind: "generate", position: { x: 0, y: 0 } },
      { id: "n2", kind: "rerank", position: { x: 0, y: 200 } },
    ],
    edges: [],
  };

  it("clicking a node calls onSelectNode with its id", () => {
    const { onSelectNode } = renderCanvas({ graph });

    // Two "Generate" texts exist (palette entry + canvas node); the node is
    // the one inside React Flow's node wrapper.
    const nodeLabels = screen.getAllByText("Generate");
    const onCanvas = nodeLabels.find((el) => el.closest(".react-flow__node"));
    expect(onCanvas).toBeDefined();

    // fireEvent, not userEvent, for this one interaction only: a full
    // user-event click also fires mousedown, which reaches d3-drag (React
    // Flow's node dragger) with `event.view === null` -- jsdom's default for
    // any MouseEvent user-event constructs -- and d3-drag dereferences
    // `view.document` unconditionally. That's a jsdom/user-event interop
    // gap, not a Canvas.tsx behavior, and selection itself is a plain click
    // handler, so a click event exercises the real code path.
    fireEvent.click(onCanvas as HTMLElement);

    expect(onSelectNode).toHaveBeenCalledWith("n1");
  });

  it("a node's validation error renders as readable text, not a tooltip", () => {
    const message = "Generate needs an input from Fuse or Rerank (has 0).";
    renderCanvas({ graph, errors: [{ nodeId: "n1", message }] });

    const shown = screen.getByText(message, { exact: false });
    expect(shown).toBeVisible();
    expect(shown.closest(".react-flow__node")).not.toBeNull();
  });

  it("a graph-wide error (nodeId null) renders as an alert banner", () => {
    const message = "This pipeline has a cycle -- a step can't depend on its own output.";
    renderCanvas({ graph, errors: [{ nodeId: null, message }] });

    expect(screen.getByRole("alert")).toHaveTextContent(message);
  });

  it("the selected node exposes a tappable delete affordance that removes it and its edges", async () => {
    const user = userEvent.setup();
    const wired: SandboxGraph = {
      nodes: graph.nodes,
      edges: [{ id: "n2->n1", source: "n2", target: "n1" }],
    };
    const { onChange } = renderCanvas({ graph: wired, selectedNodeId: "n1" });

    await user.click(screen.getByRole("button", { name: "Delete Generate" }));

    const next = onChange.mock.calls[0][0] as SandboxGraph;
    expect(next.nodes.map((n) => n.id)).toEqual(["n2"]);
    expect(next.edges).toHaveLength(0);
  });

  it("the toolbar delete button is disabled with no selection and deletes with one", async () => {
    const user = userEvent.setup();
    const { onChange } = renderCanvas({ graph, selectedNodeId: "n2" });

    await user.click(screen.getByRole("button", { name: "Delete selected step" }));
    expect((onChange.mock.calls[0][0] as SandboxGraph).nodes.map((n) => n.id)).toEqual(["n1"]);

    renderCanvas({ graph });
    const buttons = screen.getAllByRole("button", { name: "Delete selected step" });
    expect(buttons[buttons.length - 1]).toBeDisabled();
  });

  it("a live node with a disclosed caveat shows the caveat when selected", () => {
    renderCanvas({ graph, selectedNodeId: "n2" });
    expect(screen.getByText(/doesn't load live/)).toBeInTheDocument();
  });
});
