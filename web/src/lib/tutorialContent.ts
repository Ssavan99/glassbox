import type { ArchitectureId, NodeKind } from "./types";

/** A simplified, illustrative step in the "how it works" diagram -- not a
 * literal 1:1 render of the real trace DAG (that's what /explore's
 * TracePlayer already does against real recorded data). `repeat` marks a
 * step that can loop (Corrective's grade/rewrite cycle, Agentic's per-
 * sub-question attempts) so the diagram can style it distinctly instead of
 * pretending the pipeline is purely linear. */
export interface TutorialStep {
  kind: NodeKind;
  label: string;
  note: string;
  repeat?: boolean;
}

export interface TutorialContent {
  problem: string[];
  steps: TutorialStep[];
  whenItWins: string[];
  whenItLoses: string[];
  /** Corrective only -- the D7 no-web-fallback disclosure, kept structurally
   * separate from whenItLoses per the plan's explicit instruction that this
   * is a distinct required disclosure, not folded into the faithfulness
   * finding. */
  deviationNote?: string;
}

export const TUTORIAL_CONTENT: Record<ArchitectureId, TutorialContent> = {
  naive: {
    problem: [
      "The core problem every architecture on this site answers is the same one: how do you get an LLM to answer questions about documents it was never trained on, without fine-tuning a model on them? Naive RAG is the minimal viable answer -- embed the question, find the chunks whose embeddings are closest, hand them to the LLM, and generate. Nothing else in the pipeline second-guesses itself.",
      "It's called \"naive\" not as a put-down -- it's the baseline every other architecture on this site is a deliberate, specific improvement on. If naive can't be beaten anywhere, the rest of the atlas has nothing to teach.",
    ],
    steps: [
      { kind: "embed_query", label: "Embed the question", note: "One vector, computed once. Naive never rewrites or decomposes the query." },
      { kind: "retrieve_dense", label: "Top-5 by cosine similarity", note: "No reranking, no fusion, no second look at what came back." },
      { kind: "generate", label: "Stuff chunks into one prompt", note: "Whatever retrieval found is trusted as-is." },
    ],
    whenItWins: [
      "Direct, single-fact questions where the question's own vocabulary is already close to how the corpus states the answer -- the common case, and exactly where the simplest possible pipeline is enough.",
      "It's also the cheapest and fastest architecture in the atlas by a wide margin: one embedding call, one retrieval pass, one generation call. Every other architecture is spending extra latency and LLM calls to buy something naive doesn't have.",
    ],
    whenItLoses: [
      "A question whose real answer hinges on an exact literal term, identifier, or number that the embedding model smooths over in favor of general topical similarity -- see the Hybrid page for a real, verified case where this exact failure happens.",
      "Anything genuinely multi-hop, where the answer is split across two or three notes and no single chunk contains it -- see the Agentic page.",
      "And structurally: naive has no way to notice when its own retrieval was wrong. Whatever the top-5 returns is what generation trusts, full stop.",
    ],
  },

  hybrid: {
    problem: [
      "Dense retrieval's real weakness: cosine similarity over embeddings generalizes well across paraphrase and synonymy, but it can genuinely miss a chunk whose relevance hinges on an exact literal term -- a config flag, a model identifier, an error string, a specific number -- because the embedding model smooths that specificity into a general topical neighborhood.",
      "Hybrid runs a second, orthogonal retrieval signal in parallel: BM25, which scores by exact term overlap and rewards literal matches dense retrieval can't see the way it does. The two ranked lists are combined with reciprocal rank fusion (which only needs each result's rank position, not its raw score, so two incomparable scoring scales merge fairly), and a cross-encoder reranks the small fused pool before generation.",
    ],
    steps: [
      { kind: "embed_query", label: "Embed the question", note: "Needed for the dense branch below." },
      { kind: "retrieve_dense", label: "Dense retrieval (parallel)", note: "Same cosine-similarity search naive uses." },
      { kind: "retrieve_sparse", label: "BM25 retrieval (parallel)", note: "Exact term overlap, over raw tokens -- not the embedding." },
      { kind: "fuse", label: "Reciprocal rank fusion", note: "Combines both ranked lists without normalizing incomparable score scales." },
      { kind: "rerank", label: "Cross-encoder rerank", note: "Query and each candidate attend to each other directly -- more accurate, but only affordable on the small fused pool." },
      { kind: "generate", label: "Generate answer", note: "One-shot, same as naive, from here on." },
    ],
    whenItWins: [
      "This is real, not hypothetical: on a keyword question in this eval where the term in the question is a paraphrase of the corpus's exact wording, Naive's dense-only retrieval misses the gold chunk entirely while Hybrid's BM25 branch catches it -- you can load this exact question on /compare and watch the retrieved chunks diverge. It's the single clearest, most reproducible win in the whole atlas.",
      "More broadly, across the full real eval, Hybrid is the strongest all-around performer of the seven -- best or near-best on both retrieval and answer faithfulness, not just the one keyword case above.",
    ],
    whenItLoses: [
      "Honestly: this corpus doesn't surface an obvious clean loss for Hybrid in the aggregate numbers -- it's the strongest performer end to end here, which is itself worth saying plainly rather than manufacturing a weakness for symmetry.",
      "What it still can't do, architecturally, is relational multi-hop reasoning -- fusing two flat ranked lists doesn't help when the answer is split across notes with no shared vocabulary. That's Agentic's and Graph's job, not Hybrid's.",
      "And the two extra retrieval/rerank passes aren't free: for the many questions Naive already answers correctly, Hybrid spends real extra latency to arrive at the same place.",
    ],
  },

  hyde: {
    problem: [
      "Dense retrieval implicitly assumes the question embeds close to its own answer. That's often false: a question is phrased as a question, and a corpus passage is phrased as prose that states a fact -- two different shapes of text that don't always land near each other in embedding space, even when one genuinely answers the other.",
      "HyDE's idea: have the LLM draft a plausible hypothetical answer first, and embed and retrieve using *that* draft instead of the bare question. The premise is that a fake answer sits closer, in embedding space, to real answer-shaped passages than a question does -- for better or worse depending on how good the draft is. The hypothetical passage is only ever a retrieval aid; the final answer is generated from the real question and whatever got retrieved, never from the fake draft itself.",
    ],
    steps: [
      { kind: "generate_hypothetical", label: "Draft a hypothetical answer", note: "An LLM call spent before retrieval even starts." },
      { kind: "embed_query", label: "Embed the hypothetical passage", note: "Not the question -- this is the entire mechanism HyDE relies on." },
      { kind: "retrieve_dense", label: "Top-5 by cosine similarity", note: "Against the hypothetical's embedding, not the question's." },
      { kind: "generate", label: "Generate the real answer", note: "From the original question, never the hypothetical draft." },
    ],
    whenItWins: [
      "Mechanistically, HyDE's designed strength is a question phrased very differently from how the corpus states the answer -- where a drafted answer's vocabulary lands closer to the real passage than the bare question's vocabulary would.",
    ],
    whenItLoses: [
      "Here's the honest, somewhat surprising finding from the real eval, worth stating plainly rather than glossing over: HyDE's aggregate retrieval quality on this corpus doesn't come out ahead of Naive's despite spending a second LLM call to get there -- and its answer faithfulness trails Hybrid's by a wide margin. See HyDE's own row on the eval page below.",
      "The likely reason: this corpus's factual questions don't have much of a phrasing gap between how they're asked and how the corpus states the answer, so HyDE's specific advantage isn't strongly exercised here. Worse, the drafted hypothetical passage appears to sometimes introduce its own phrasing or assumptions that don't survive into a well-grounded final answer -- a real cost, not just a wash, on this corpus.",
    ],
  },

  corrective: {
    problem: [
      "What happens when retrieval is confidently wrong? Naive has no way to notice -- whatever the top-5 returns is trusted outright. Corrective RAG adds a real check: an LLM grades each retrieved chunk as correct, ambiguous, or incorrect evidence for the actual question, and if the evidence looks mostly bad, the query is rewritten and retrieval is retried, capped at a fixed number of corrections so it can't loop forever.",
    ],
    steps: [
      { kind: "retrieve_dense", label: "Retrieve", note: "Standard top-5 dense retrieval, same as naive's first pass." },
      { kind: "grade", label: "Grade each chunk", note: "An LLM judges correct / ambiguous / incorrect -- this is what makes it \"corrective\".", repeat: true },
      { kind: "rewrite", label: "Rewrite query & retry", note: "Only if evidence graded mostly incorrect. Capped at 2 corrections.", repeat: true },
      { kind: "generate", label: "Generate answer", note: "From the original question, never a rewritten one -- rewriting was only ever a retrieval aid." },
    ],
    deviationNote:
      "Deliberate, documented deviation from the CRAG paper (plan decision D7): this project has no web-search fallback. The original CRAG paper falls back to a live web search when retrieval is judged bad; that needs a paid or signup API beyond what's justified for a $0 project. Here, the only correction available is rewriting the query and re-searching the same local corpus -- never fetching new external evidence. That's an honest, stated limitation of this implementation, not an oversight or a silent simplification.",
    whenItWins: [
      "Mechanistically: when the initial query is oddly phrased and a straightforward rewrite finds better evidence that was already sitting in the corpus the whole time, just not reachable by the first phrasing.",
    ],
    whenItLoses: [
      "The same honest, surprising finding as HyDE's page, worth stating plainly here too: Corrective's answer faithfulness trails Hybrid's by a wide margin in the real eval, despite retrieval quality that's statistically tied with Naive's -- a real cost for a lot of extra machinery, not a clear win.",
      "And precisely because of the D7 limitation above: on a genuinely unanswerable question, rewriting the query can't manufacture evidence the corpus doesn't contain. Correction burns two to six times Naive's LLM-call budget chasing evidence that, on this corpus, either wasn't there or was findable on the first pass anyway.",
    ],
  },

  graph: {
    problem: [
      "Chunk-similarity retrieval -- dense or sparse -- can only find text that is itself textually or semantically close to the question. It structurally cannot find a fact that's two relationship-hops away from the question's topic and shares no vocabulary with it at all. Graph RAG takes a different entry point entirely: offline, it extracts (entity, relation, entity) triples from the whole corpus and clusters them into communities; online, it matches entities in the question against that graph and traverses two hops out to gather connected chunks, with no embedding similarity involved in the traversal itself.",
    ],
    steps: [
      { kind: "graph_seed", label: "Seed entities from the query", note: "Pure string matching against the pre-built graph's vocabulary -- no LLM call, no embedding." },
      { kind: "graph_expand", label: "2-hop expansion", note: "Walks src → rel → dst → rel → dst, reaching facts that share no chunk with the question at all." },
      { kind: "generate", label: "Generate answer", note: "From the gathered chunks plus any touched community summaries -- the only LLM call this architecture spends online." },
    ],
    whenItWins: [
      "Mechanistically, Graph's structural advantage is real: a multi-hop relational fact connected to the question only through an intermediate entity, which embedding-based retrieval cannot reach no matter how good the embedding model is, since there's no direct textual or semantic similarity to find.",
    ],
    whenItLoses: [
      "This needs to be said plainly, not softened: on this corpus, Graph is substantially weaker than every other architecture in the atlas, on both retrieval and answer faithfulness -- see Graph's own row on the eval page below, and note the caveat next to it. This isn't just the standard rank-metric unfairness that affects Graph's degree-ordered (not relevance-ordered) chunk lists at k=5 -- even using recall_full, the fair rank-insensitive number that removes that specific unfairness, Graph's numbers remain the lowest in the atlas by a wide margin.",
      "That's a genuine finding about this specific corpus and graph-extraction pipeline -- likely some combination of graph density, entity-normalization quality, and how much of this corpus's real content is actually relational versus simply topical -- not evidence that graph-based retrieval doesn't work in general. Overselling Graph RAG's typical promise here would be dishonest given what the real eval actually shows; this page says so directly instead.",
    ],
  },

  agentic: {
    problem: [
      "Some questions genuinely can't be answered by one retrieval pass, however good -- the evidence needed is split across independent facts that no single query captures at once. Agentic decomposes the question into up to three sub-questions, picks a retrieval tool per sub-question with a zero-cost heuristic (not an LLM call -- this is what keeps its LLM-call budget provably bounded), and spends the one genuine agentic judgment in the pipeline -- `reflect` -- deciding whether each sub-question's evidence is actually sufficient before optionally retrying with a different tool.",
    ],
    steps: [
      { kind: "plan", label: "Decompose into sub-questions", note: "Up to 3, in the order they should be investigated." },
      { kind: "route", label: "Pick a tool per sub-question", note: "Deterministic heuristic -- graph if entities match, sparse for exact tokens, dense otherwise. Zero LLM cost.", repeat: true },
      { kind: "reflect", label: "Judge sufficiency", note: "The one real LLM judgment: is this sub-question's evidence enough? Retry once with a different tool if not.", repeat: true },
      { kind: "generate", label: "Synthesize final answer", note: "From the deduplicated evidence gathered across every sub-question." },
    ],
    whenItWins: [
      "Mechanistically and in the real eval: decomposition genuinely broadens what gets gathered for a multi-hop question -- Agentic's recall_full closes most of the gap to Naive's, which a single-pass retrieval structurally can't do for a question needing several independent pieces of evidence.",
    ],
    whenItLoses: [
      "This is the real, fully-diagnosed finding this page exists to teach, not a vague caveat: on one real multi-hop question in the eval set, two of Agentic's three sub-questions routed to the graph tool and each came back with a large, degree-ordered chunk dump. The correct gold evidence was genuinely present in what reached the final generate step -- verified directly, side by side, against Naive's answer to the exact same question, which grounds correctly on that same evidence. Yet Agentic's synthesis invented terminology that appears nowhere in the corpus (\"behavioral coherence\", \"spillover effects\") instead of quoting the real chunk text the way Naive did.",
      "This is characterized as a genuine, understood limitation, not a bug and not a metrics artifact: synthesizing across several independently-investigated sub-questions' worth of evidence -- even when each sub-question's own evidence-gathering succeeded on its own terms -- seems to invite plausible-sounding elaboration that isn't actually grounded in any retrieved source. It's the real cost of decomposition: broader coverage, but a harder synthesis step at the end that can drift from what the evidence actually says.",
    ],
  },

  adaptive: {
    problem: [
      "Every other architecture on this site is a fixed bet on one strategy, applied to every question the same way. Adaptive asks a different question: what if an LLM router picked the best-suited architecture per question, so a keyword question gets Hybrid's exact-term strength and a multi-hop question gets Agentic's decomposition, without a human hand-classifying every question first? This is the one place in the whole project where an LLM -- not a heuristic -- picks which entire pipeline to run, not just which retrieval tool.",
    ],
    steps: [
      { kind: "route", label: "LLM classifies and routes", note: "A real LLM judgment picking one whole architecture, weighing keyword-sensitivity, multi-hop complexity, and likely-unanswerability." },
      { kind: "generate", label: "Delegate's full trace runs", note: "The chosen architecture runs its entire real pipeline, spliced in beneath the routing decision." },
    ],
    whenItWins: [
      "When it routes correctly, Adaptive inherits whatever the delegated architecture is best at, for the cost of one extra LLM call -- and its own aggregate numbers in the real eval land close to Hybrid's near-best numbers, specifically because the router correctly delegates a meaningful share of keyword and factual questions to Hybrid.",
    ],
    whenItLoses: [
      "The real number from the logged rubric, stated plainly rather than rounded up: routing accuracy is well under 100%, not \"it routes correctly\" -- see the live number rendered below, read straight from the same evaluation report every other number on this site comes from.",
      "During development, fixing the router prompt to correctly catch keyword questions (which went from missing every single one to catching all seven) caused multi-hop routing to regress in the very same eval sweep, from correctly routing most multi-hop questions down to less than half. That's a real, logged tradeoff between two routing objectives that was never fully resolved -- not a solved problem dressed up as one.",
    ],
  },
};
