/**
 * Mirrors the real, current shape of artifacts/*.json, inspected directly
 * (python -m json.tool) rather than derived from §3.2's original design
 * sketch alone — eval.json in particular grew fields during Phase 6/6.1/6.2
 * (recall_full, graph_tool_involved, rank_metrics_note/caveat, backend_mix,
 * adaptive_routing*) that the original sketch didn't have. Asserted against
 * a real exported file in src/lib/data.test.ts.
 */

// ---------------------------------------------------------------------------
// Trace schema (engine/trace.py) — the frozen Python/frontend contract
// ---------------------------------------------------------------------------

export type NodeKind =
  | "embed_query"
  | "retrieve_dense"
  | "retrieve_sparse"
  | "fuse"
  | "rerank"
  | "generate_hypothetical"
  | "grade"
  | "rewrite"
  | "graph_seed"
  | "graph_expand"
  | "plan"
  | "reflect"
  | "route"
  | "generate";

export interface RetrievalResult {
  chunk_id: string;
  score: number;
  rank: number;
}

export interface EmbedQueryPayload {
  dims: number;
  preview: number[];
}

export interface RetrievePayload {
  results: RetrievalResult[];
  k: number;
}

export interface FusePayload {
  method: string;
  k: number;
  inputs: string[];
  results: RetrievalResult[];
}

export interface RerankPayload {
  model: string;
  before: RetrievalResult[];
  after: RetrievalResult[];
}

export type GradeVerdict = "correct" | "ambiguous" | "incorrect";

export interface GradeJudgement {
  chunk_id: string;
  verdict: GradeVerdict;
  reason: string;
}

export interface GradePayload {
  judgements: GradeJudgement[];
}

export interface RewritePayload {
  from: string;
  to: string;
  reason: string;
}

export interface GraphSeedPayload {
  entities: string[];
}

export interface GraphEdgeRef {
  src: string;
  rel: string;
  dst: string;
}

export interface GraphExpandPayload {
  hops: number;
  edges: GraphEdgeRef[];
  chunk_ids: string[];
}

export interface PlanPayload {
  sub_questions: string[];
}

export interface ReflectPayload {
  sufficient: boolean;
  reason: string;
  next_action: string;
}

export interface RoutePayload {
  chosen: string;
  scores: Record<string, number>;
  reason: string;
}

export interface GeneratePayload {
  output: string;
  prompt_preview: string;
  tokens: number;
}

/** Discriminated on `kind` — see engine/trace.py's payload table (§3.2). */
export type TraceNode =
  | (NodeBase & { kind: "embed_query"; payload: EmbedQueryPayload })
  | (NodeBase & { kind: "retrieve_dense"; payload: RetrievePayload })
  | (NodeBase & { kind: "retrieve_sparse"; payload: RetrievePayload })
  | (NodeBase & { kind: "fuse"; payload: FusePayload })
  | (NodeBase & { kind: "rerank"; payload: RerankPayload })
  | (NodeBase & { kind: "generate_hypothetical"; payload: GeneratePayload })
  | (NodeBase & { kind: "grade"; payload: GradePayload })
  | (NodeBase & { kind: "rewrite"; payload: RewritePayload })
  | (NodeBase & { kind: "graph_seed"; payload: GraphSeedPayload })
  | (NodeBase & { kind: "graph_expand"; payload: GraphExpandPayload })
  | (NodeBase & { kind: "plan"; payload: PlanPayload })
  | (NodeBase & { kind: "reflect"; payload: ReflectPayload })
  | (NodeBase & { kind: "route"; payload: RoutePayload })
  | (NodeBase & { kind: "generate"; payload: GeneratePayload });

interface NodeBase {
  id: string;
  label: string;
  parent_ids: string[];
  duration_ms: number;
  explain: string;
}

export interface TraceMetrics {
  latency_ms: number;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export const ARCHITECTURE_IDS = [
  "naive",
  "hybrid",
  "hyde",
  "corrective",
  "graph",
  "agentic",
  "adaptive",
] as const;

export type ArchitectureId = (typeof ARCHITECTURE_IDS)[number];

export interface Trace {
  trace_id: string;
  architecture: ArchitectureId;
  question: string;
  answer: string;
  metrics: TraceMetrics;
  nodes: TraceNode[];
}

// ---------------------------------------------------------------------------
// Corpus (artifacts/chunks.json)
// ---------------------------------------------------------------------------

export interface ChunkRecord {
  chunk_id: string;
  note_id: string;
  text: string;
  heading: string | null;
}

// ---------------------------------------------------------------------------
// Knowledge graph (artifacts/graph.json)
// ---------------------------------------------------------------------------

export interface GraphEntity {
  id: string;
  chunk_ids: string[];
}

export interface GraphEdge {
  src: string;
  rel: string;
  dst: string;
  chunk_id: string;
}

export interface GraphCommunity {
  id: number;
  entity_ids: string[];
  summary: string;
}

export interface GraphData {
  entities: GraphEntity[];
  edges: GraphEdge[];
  communities: GraphCommunity[];
}

// ---------------------------------------------------------------------------
// Evaluation report (artifacts/eval.json) — real shape as of Phase 6.2
// ---------------------------------------------------------------------------

export type QuestionType = "factual" | "multi_hop" | "keyword" | "unanswerable";

export interface EvalRow {
  architecture: ArchitectureId;
  question_id: string;
  question_type: QuestionType;
  trace_id: string;
  answer: string;
  retrieved_chunk_ids: string[];
  gold_chunk_ids: string[];
  recall_at_5: number | null;
  mrr_at_10: number | null;
  ndcg_at_10: number | null;
  recall_full: number | null;
  graph_tool_involved: boolean;
  faithfulness: number | null;
  reads_as_refusal: boolean;
  refusal_correctness: boolean | null;
  judge_reasoning: string;
  latency_ms: number;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  backend_calls: string[];
  judge_backend: string;
  /** Present only on `architecture: "adaptive"` rows. */
  adaptive_routed_to?: ArchitectureId;
}

export interface ArchitectureSummary {
  n_questions: number;
  recall_at_5_mean: number | null;
  mrr_at_10_mean: number | null;
  ndcg_at_10_mean: number | null;
  recall_full_mean: number | null;
  rank_metrics_note: string;
  faithfulness_mean: number | null;
  refusal_correctness_rate: number | null;
  latency_ms_mean: number | null;
  llm_calls_mean: number | null;
  prompt_tokens_mean: number | null;
  completion_tokens_mean: number | null;
  backend_mix: Record<string, number>;
}

export interface AdaptiveRoutingEntry {
  question_id: string;
  question_type: QuestionType;
  routed_to: ArchitectureId | null;
  correct: boolean | null;
}

export interface AdaptiveRoutingAccuracy {
  rubric: Record<QuestionType, ArchitectureId[]>;
  correct: number;
  total: number;
  accuracy: number | null;
}

export interface EvalReport {
  llm_judge_caveat: string;
  rank_metrics_caveat: string;
  n_architectures: number;
  n_questions: number;
  rows: EvalRow[];
  by_architecture: Record<ArchitectureId, ArchitectureSummary>;
  by_architecture_and_type: Record<ArchitectureId, Record<QuestionType, ArchitectureSummary>>;
  adaptive_routing: AdaptiveRoutingEntry[];
  adaptive_routing_accuracy: AdaptiveRoutingAccuracy;
}
