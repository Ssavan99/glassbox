import {
  Background,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
  type Edge,
  type Node as FlowNode,
  type IsValidConnection,
  type NodeChange,
  type EdgeChange,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useMemo, useRef, type DragEvent, type JSX } from "react";
import { PALETTE, PALETTE_ORDER } from "./palette";
import type { SandboxEdge, SandboxGraph, SandboxNode, SandboxNodeKind } from "./types";
import type { ValidationError } from "./validate";

const NODE_WIDTH = 208;
const DRAG_MIME = "application/glassbox-sandbox-kind";

/** Data carried on each React Flow node. Declared as a `type` (not an
 * `interface`) deliberately: React Flow v12's `Node<T>` constrains `T` to
 * `Record<string, unknown>`, which only type aliases satisfy implicitly. */
type SandboxNodeData = {
  kind: SandboxNodeKind;
  /** Messages from the *parent's* validateGraph run that belong to this
   * node -- rendered as readable text on the card face, never a tooltip. */
  errors: string[];
  isSelected: boolean;
  onDelete: (id: string) => void;
};

type SandboxFlowNode = FlowNode<SandboxNodeData>;

/**
 * The live/not-live badge. This is the single most important thing on the
 * card: a first-time viewer has to be able to tell a genuinely-computed step
 * from a replayed/extractive one at a glance, with no hover, no tap, and no
 * documentation. So it renders as a filled, always-visible pill with both a
 * color and a word -- never color alone (see index.css's "relief rule").
 */
function LiveBadge({ kind }: { kind: SandboxNodeKind }) {
  const entry = PALETTE[kind];
  const live = entry.live === "live";
  const color = live ? "var(--status-good)" : "var(--status-warning)";
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-bold tracking-wide uppercase"
      style={{
        color,
        borderColor: color,
        background: `color-mix(in oklab, ${color} 14%, transparent)`,
      }}
    >
      <span
        aria-hidden="true"
        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: color }}
      />
      {live ? "Live" : "Recorded / extractive"}
      {entry.liveCaveat ? (
        <span
          className="font-bold"
          title="Simplified -- select this node to read how"
          aria-label="simplified"
        >
          *
        </span>
      ) : null}
    </span>
  );
}

function SandboxNodeCard({ id, data }: NodeProps<SandboxFlowNode>) {
  const entry = PALETTE[data.kind];
  const hasError = data.errors.length > 0;
  const ring = hasError
    ? "0 0 0 3px color-mix(in oklab, var(--status-critical) 30%, transparent)"
    : data.isSelected
      ? "0 0 0 3px color-mix(in oklab, var(--arch-naive) 35%, transparent)"
      : undefined;

  return (
    <div
      style={{
        width: NODE_WIDTH,
        borderColor: hasError ? "var(--status-critical)" : "var(--border)",
        boxShadow: ring,
      }}
      className="flex flex-col gap-1.5 rounded-lg border-2 bg-surface px-3 py-2 text-left"
    >
      <Handle type="target" position={Position.Top} style={{ width: 10, height: 10 }} />

      <div className="flex items-start gap-2">
        <span aria-hidden="true" className="text-sm text-ink-secondary">
          {entry.glyph}
        </span>
        <span className="flex-1 text-xs font-semibold text-ink">{entry.label}</span>
        {data.isSelected ? (
          <button
            type="button"
            aria-label={`Delete ${entry.label}`}
            onClick={(e) => {
              e.stopPropagation();
              data.onDelete(id);
            }}
            className="nodrag -my-1 -mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border text-ink-secondary hover:border-status-critical hover:text-status-critical"
          >
            ×
          </button>
        ) : null}
      </div>

      <div>
        <LiveBadge kind={data.kind} />
      </div>

      {hasError ? (
        <ul className="flex flex-col gap-0.5">
          {data.errors.map((message) => (
            <li key={message} className="text-[10px] leading-snug text-status-critical">
              ⚠ {message}
            </li>
          ))}
        </ul>
      ) : null}

      {data.isSelected && entry.liveCaveat ? (
        <p className="text-[10px] leading-snug text-ink-muted">{entry.liveCaveat}</p>
      ) : null}

      <Handle type="source" position={Position.Bottom} style={{ width: 10, height: 10 }} />
    </div>
  );
}

const nodeTypes = { sandboxNode: SandboxNodeCard };

export interface SandboxCanvasProps {
  graph: SandboxGraph;
  onChange: (graph: SandboxGraph) => void;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  /** Computed by the parent with validateGraph -- this component only
   * renders what it is handed, it never validates on its own. */
  errors: ValidationError[];
}

function newNodeId(kind: SandboxNodeKind, seq: number): string {
  const uuid =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().slice(0, 8)
      : `${seq}-${Math.random().toString(36).slice(2, 8)}`;
  return `${kind}-${uuid}`;
}

function edgeId(source: string, target: string): string {
  return `${source}->${target}`;
}

function SandboxCanvasInner({
  graph,
  onChange,
  selectedNodeId,
  onSelectNode,
  errors,
}: SandboxCanvasProps) {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const addCountRef = useRef(0);
  const { screenToFlowPosition } = useReactFlow();

  const graphErrors = useMemo(() => errors.filter((e) => e.nodeId === null), [errors]);

  const errorsByNode = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const error of errors) {
      if (error.nodeId === null) continue;
      const existing = map.get(error.nodeId);
      if (existing) existing.push(error.message);
      else map.set(error.nodeId, [error.message]);
    }
    return map;
  }, [errors]);

  const deleteNode = useCallback(
    (id: string) => {
      onChange({
        nodes: graph.nodes.filter((n) => n.id !== id),
        edges: graph.edges.filter((e) => e.source !== id && e.target !== id),
      });
      if (selectedNodeId === id) onSelectNode(null);
    },
    [graph, onChange, selectedNodeId, onSelectNode],
  );

  const flowNodes = useMemo<SandboxFlowNode[]>(
    () =>
      graph.nodes.map((node) => ({
        id: node.id,
        type: "sandboxNode",
        position: node.position,
        selected: node.id === selectedNodeId,
        data: {
          kind: node.kind,
          errors: errorsByNode.get(node.id) ?? [],
          isSelected: node.id === selectedNodeId,
          onDelete: deleteNode,
        },
      })),
    [graph.nodes, selectedNodeId, errorsByNode, deleteNode],
  );

  const flowEdges = useMemo<Edge[]>(
    () =>
      graph.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        style: { stroke: "var(--gridline)", strokeWidth: 2 },
      })),
    [graph.edges],
  );

  /** Where a tapped-to-add node lands: the middle of whatever the user is
   * currently looking at, plus a small cascade so repeated taps don't stack
   * into one indistinguishable pile. Falls back to a fixed cascade when the
   * wrapper has no measured size yet (first paint, or jsdom under test),
   * because screenToFlowPosition is meaningless against a 0x0 rect. */
  const nextPosition = useCallback((): { x: number; y: number } => {
    const seq = addCountRef.current;
    const cascade = { x: (seq % 6) * 32, y: (seq % 6) * 28 };
    const rect = wrapperRef.current?.getBoundingClientRect();
    if (rect && rect.width > 0 && rect.height > 0) {
      const center = screenToFlowPosition({
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
      });
      return { x: center.x - NODE_WIDTH / 2 + cascade.x, y: center.y - 40 + cascade.y };
    }
    return { x: 40 + cascade.x, y: 40 + cascade.y };
  }, [screenToFlowPosition]);

  const addNode = useCallback(
    (kind: SandboxNodeKind, position: { x: number; y: number }) => {
      const node: SandboxNode = {
        id: newNodeId(kind, addCountRef.current),
        kind,
        position,
      };
      addCountRef.current += 1;
      onChange({ nodes: [...graph.nodes, node], edges: graph.edges });
      onSelectNode(node.id);
    },
    [graph, onChange, onSelectNode],
  );

  const handleNodesChange = useCallback(
    (changes: NodeChange<SandboxFlowNode>[]) => {
      let nodes = graph.nodes;
      let edges = graph.edges;
      let dirty = false;
      let deselect = false;

      for (const change of changes) {
        if (change.type === "position" && change.position) {
          const position = change.position;
          nodes = nodes.map((n) => (n.id === change.id ? { ...n, position } : n));
          dirty = true;
        } else if (change.type === "remove") {
          nodes = nodes.filter((n) => n.id !== change.id);
          edges = edges.filter((e) => e.source !== change.id && e.target !== change.id);
          dirty = true;
          if (selectedNodeId === change.id) deselect = true;
        }
      }

      if (dirty) onChange({ nodes, edges });
      if (deselect) onSelectNode(null);
    },
    [graph, onChange, selectedNodeId, onSelectNode],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<Edge>[]) => {
      const removed = new Set(
        changes.filter((c) => c.type === "remove").map((c) => c.id),
      );
      if (removed.size === 0) return;
      onChange({ nodes: graph.nodes, edges: graph.edges.filter((e) => !removed.has(e.id)) });
    },
    [graph, onChange],
  );

  /** A light drag-time guard only: no self-loops, no duplicate edges. Every
   * other notion of "is this connection sensible?" is left to validateGraph,
   * whose errors render right on the node cards -- a wrong-kind wire that
   * explains itself beats a wire that silently refuses to attach. */
  const isValidConnection = useCallback<IsValidConnection<Edge>>(
    (connection) => {
      const { source, target } = connection;
      if (!source || !target || source === target) return false;
      return !graph.edges.some((e) => e.source === source && e.target === target);
    },
    [graph.edges],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const { source, target } = connection;
      if (!source || !target || source === target) return;
      if (graph.edges.some((e) => e.source === source && e.target === target)) return;
      const edge: SandboxEdge = { id: edgeId(source, target), source, target };
      onChange({ nodes: graph.nodes, edges: [...graph.edges, edge] });
    },
    [graph, onChange],
  );

  function handleDragStart(event: DragEvent<HTMLButtonElement>, kind: SandboxNodeKind) {
    event.dataTransfer.setData(DRAG_MIME, kind);
    event.dataTransfer.effectAllowed = "copy";
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const kind = event.dataTransfer.getData(DRAG_MIME) as SandboxNodeKind | "";
    if (!kind || !(kind in PALETTE)) return;
    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    addNode(kind, { x: position.x - NODE_WIDTH / 2, y: position.y - 40 });
  }

  return (
    <div className="flex flex-col gap-3 lg:flex-row">
      {/* Palette: a horizontal, self-scrolling strip on narrow screens (so it
          can never push the page itself sideways at 375px), a column on wide
          ones. Every entry is both a drag source and a real button. */}
      <div className="shrink-0 lg:w-52">
        <p className="mb-1.5 text-xs font-semibold tracking-wide text-ink-muted uppercase">
          Steps
        </p>
        <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-x-visible lg:pb-0">
          {PALETTE_ORDER.map((kind) => {
            const entry = PALETTE[kind];
            return (
              <button
                key={kind}
                type="button"
                draggable
                onDragStart={(e) => handleDragStart(e, kind)}
                onClick={() => addNode(kind, nextPosition())}
                aria-label={`Add ${entry.label}`}
                title={entry.description}
                className="flex min-h-9 w-40 shrink-0 cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-2 text-left transition-colors hover:border-arch-naive lg:w-full"
              >
                <span aria-hidden="true" className="text-sm text-ink-secondary">
                  {entry.glyph}
                </span>
                <span className="flex flex-1 flex-col gap-1">
                  <span className="text-xs font-medium text-ink">{entry.label}</span>
                  <LiveBadge kind={kind} />
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {graphErrors.length > 0 ? (
          <div
            role="alert"
            className="flex flex-col gap-1 rounded-lg border-2 border-status-critical bg-surface px-3 py-2"
          >
            {graphErrors.map((error) => (
              <p key={error.message} className="text-xs font-medium text-status-critical">
                ⚠ {error.message}
              </p>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              if (selectedNodeId) deleteNode(selectedNodeId);
            }}
            disabled={!selectedNodeId}
            className="min-h-9 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-ink-secondary transition-colors enabled:hover:border-status-critical enabled:hover:text-status-critical disabled:opacity-40"
          >
            Delete selected step
          </button>
          <span className="text-[11px] text-ink-muted">
            Tap a step to add it, drag between the dots to wire steps together.
          </span>
        </div>

        <div
          ref={wrapperRef}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          className="h-[420px] overflow-hidden rounded-lg border border-border bg-surface lg:h-[600px]"
        >
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onNodeClick={(_, node) => onSelectNode(node.id)}
            onPaneClick={() => onSelectNode(null)}
            deleteKeyCode={["Delete", "Backspace"]}
            proOptions={{ hideAttribution: true }}
            fitView
            fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
          >
            <Background gap={20} color="var(--gridline)" />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}

export function SandboxCanvas(props: SandboxCanvasProps): JSX.Element {
  // useReactFlow (for screenToFlowPosition, which both tap-to-add and
  // drop-to-add need) is only legal under a provider, and the palette lives
  // outside the <ReactFlow> element itself -- so the provider wraps both.
  return (
    <ReactFlowProvider>
      <SandboxCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
