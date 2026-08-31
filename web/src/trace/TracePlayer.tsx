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
import { useEffect, useMemo, useState } from "react";
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
        boxShadow: active ? `0 0 0 3px color-mix(in oklab, ${color} 35%, transparent)` : undefined,
      }}
      className={`flex h-full w-full flex-col justify-center gap-0.5 rounded-lg border-2 bg-surface px-3 py-1.5 text-left transition-all ${
        reached ? "opacity-100" : "opacity-40"
      }`}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color }}>
        <span aria-hidden="true">{KIND_GLYPH[traceNode.kind]}</span>
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
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? "Pause" : "Play"}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white transition-opacity hover:opacity-90"
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
          className="rounded-md border border-border px-2 py-1 text-sm text-ink-secondary disabled:opacity-30"
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
          className="rounded-md border border-border px-2 py-1 text-sm text-ink-secondary disabled:opacity-30"
        >
          ▶
        </button>
        <span className="shrink-0 font-mono text-xs tabular-nums text-ink-muted">
          Step {stepIndex + 1} / {trace.nodes.length}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="h-[420px] overflow-hidden rounded-lg border border-border bg-surface lg:h-[600px]">
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

        <div className="h-[420px] overflow-y-auto rounded-lg border border-border bg-surface p-4 lg:h-[600px]">
          <NodeInspector node={activeNode} chunkIndex={chunkIndex} graphData={graphData} />
        </div>
      </div>
    </div>
  );
}
