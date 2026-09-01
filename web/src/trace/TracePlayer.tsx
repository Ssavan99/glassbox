import {
  Background,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node as FlowNode,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { architectureColor } from "../lib/architectures";
import type { ChunkRecord, GraphData, Trace, TraceNode } from "../lib/types";
import { layoutNodes, NODE_HEIGHT, NODE_WIDTH } from "./layout";
import { KIND_GLYPH } from "./nodeMeta";
import { NodeInspector } from "./NodeInspector";

const PLAY_INTERVAL_MS = 1200;

type FlowNodeData = {
  traceNode: TraceNode;
  reached: boolean;
  active: boolean;
  color: string;
};

function TraceNodeCard({ data }: NodeProps<FlowNode<FlowNodeData>>) {
  const { traceNode, reached, active, color } = data;
  return (
    <div
      style={{
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        borderColor: reached ? color : "var(--border)",
        boxShadow: active ? `5px 5px 0 color-mix(in oklab, ${color} 58%, var(--shadow-ink))` : undefined,
      }}
      className={`trace-node-card flex h-full w-full flex-col justify-center gap-1 bg-surface px-3 py-2 text-left ${
        reached ? "opacity-100" : "opacity-40"
      }`}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="flex items-center gap-2 text-xs font-bold" style={{ color }}>
        <span aria-hidden="true" className="icon-badge" style={{ "--accent": color } as CSSProperties}><span>{KIND_GLYPH[traceNode.kind]}</span></span>
        <span className="truncate">{traceNode.label}</span>
      </div>
      {traceNode.duration_ms > 0 && (
        <div className="text-[10px] tabular-nums text-ink-muted">
          {traceNode.duration_ms < 1000
            ? `${traceNode.duration_ms.toFixed(0)}ms`
            : `${(traceNode.duration_ms / 1000).toFixed(1)}s`}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { traceNode: TraceNodeCard };

interface TracePlayerProps {
  trace: Trace;
  chunkIndex: Map<string, ChunkRecord>;
  graphData?: GraphData;
}

export function TracePlayer({ trace, chunkIndex, graphData }: TracePlayerProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const color = architectureColor(trace.architecture);

  // A trace's `nodes` array is already in real execution order (Python's
  // TraceBuilder appends each node as it runs, parent before child), so it
  // doubles as the step/scrub order -- no separate topological sort needed.
  useEffect(() => {
    setStepIndex(0);
    setPlaying(false);
  }, [trace.trace_id]);

  useEffect(() => {
    if (!playing) return;
    if (stepIndex >= trace.nodes.length - 1) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setStepIndex((i) => i + 1), PLAY_INTERVAL_MS);
    return () => clearTimeout(t);
  }, [playing, stepIndex, trace.nodes.length]);

  const { flowNodes, flowEdges } = useMemo(() => {
    const rawNodes: FlowNode<FlowNodeData>[] = trace.nodes.map((n, i) => ({
      id: n.id,
      type: "traceNode",
      position: { x: 0, y: 0 },
      data: { traceNode: n, reached: i <= stepIndex, active: i === stepIndex, color },
      draggable: false,
    }));
    const edges: Edge[] = trace.nodes.flatMap((n) =>
      n.parent_ids.map((pid) => ({
        id: `${pid}->${n.id}`,
        source: pid,
        target: n.id,
        animated: false,
        style: { stroke: "var(--gridline)" },
      })),
    );
    return { flowNodes: layoutNodes(rawNodes, edges), flowEdges: edges };
  }, [trace, stepIndex, color]);

  const activeNode = trace.nodes[stepIndex];

  function jumpTo(id: string) {
    const idx = trace.nodes.findIndex((n) => n.id === id);
    if (idx >= 0) {
      setPlaying(false);
      setStepIndex(idx);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="control-surface flex flex-wrap items-center gap-4 bg-surface px-5 py-4">
        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? "Pause" : "Play"}
          className="pill-button sticker-interactive flex h-11 w-11 shrink-0 items-center justify-center border-none text-white"
          style={{ background: color }}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <button
          type="button"
          onClick={() => {
            setPlaying(false);
            setStepIndex((i) => Math.max(0, i - 1));
          }}
          disabled={stepIndex === 0}
          aria-label="Previous step"
          className="pill-button sticker-interactive px-3 py-1 text-sm font-bold text-ink-secondary disabled:opacity-30"
        >
          ◀
        </button>
        <input
          type="range"
          min={0}
          max={trace.nodes.length - 1}
          value={stepIndex}
          onChange={(e) => {
            setPlaying(false);
            setStepIndex(Number(e.target.value));
          }}
          className="min-w-32 flex-1"
          aria-label="Scrub through trace steps"
        />
        <button
          type="button"
          onClick={() => {
            setPlaying(false);
            setStepIndex((i) => Math.min(trace.nodes.length - 1, i + 1));
          }}
          disabled={stepIndex === trace.nodes.length - 1}
          aria-label="Next step"
          className="pill-button sticker-interactive px-3 py-1 text-sm font-bold text-ink-secondary disabled:opacity-30"
        >
          ▶
        </button>
        <span className="shrink-0 font-mono text-xs tabular-nums text-ink-muted">
          Step {stepIndex + 1} / {trace.nodes.length}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="sandbox-canvas h-[420px] overflow-hidden bg-surface lg:h-[600px]">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, node) => jumpTo(node.id)}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            nodesConnectable={false}
            elementsSelectable
          >
            <Background gap={20} color="var(--gridline)" />
          </ReactFlow>
        </div>

        <div className="inspector-surface h-[420px] overflow-y-auto bg-surface p-5 lg:h-[600px]">
          <NodeInspector node={activeNode} chunkIndex={chunkIndex} graphData={graphData} />
        </div>
      </div>
    </div>
  );
}
