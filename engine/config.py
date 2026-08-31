"""Single source of truth for paths, model ids, and tunable constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CORPUS_DIR = ROOT / "corpus" / "notes"
ARTIFACTS_DIR = ROOT / "artifacts"
TRACES_DIR = ARTIFACTS_DIR / "traces"
LLM_CACHE_DIR = ROOT / ".llm_cache"
QUESTIONS_PATH = ROOT / "evaluation" / "questions.yaml"
WEB_DATA_DIR = ROOT / "web" / "public" / "data"

CHUNKS_PATH = ARTIFACTS_DIR / "chunks.json"
VECTORS_PATH = ARTIFACTS_DIR / "vectors.f32"
BM25_PATH = ARTIFACTS_DIR / "bm25.json"
GRAPH_PATH = ARTIFACTS_DIR / "graph.json"
EVAL_PATH = ARTIFACTS_DIR / "eval.json"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

GROQ_MODEL = "openai/gpt-oss-120b"
OLLAMA_MODEL = "qwen2.5:7b-instruct"

CHUNK_TARGET_TOKENS = 250
CHUNK_OVERLAP_TOKENS = 50

TOP_K = 5
RRF_K = 60
HYBRID_POOL_K = 20  # candidate pool size feeding fusion/rerank, before trimming to TOP_K

GRAPH_MAX_HOP_CHUNKS = 40
AGENTIC_MAX_SUBQUESTIONS = 3
AGENTIC_MAX_STEPS = 6
AGENTIC_MAX_LLM_CALLS = 9
CORRECTIVE_MAX_CORRECTIONS = 2
