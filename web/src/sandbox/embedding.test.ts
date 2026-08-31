import { beforeEach, describe, expect, it, vi } from "vitest";

// Real inference is deliberately out of scope here: it needs a browser, WASM
// ONNX runtime and a multi-hundred-KB weights download, and is verified
// separately against Python-computed reference vectors. What this file covers
// is only this module's own plumbing -- singleton memoization, progress wiring,
// the pooling/normalize options it passes down, and the Float32Array wrapping.

// The real payload transformers.js dispatches to `progress_callback` (see its
// utils/hub.js): `progress` is present only on "progress" events.
interface RawProgressEvent {
  status: string;
  name?: string;
  file?: string;
  progress?: number;
  loaded?: number;
  total?: number;
}

interface FakePipelineOptions {
  quantized?: boolean;
  progress_callback?: (info: RawProgressEvent) => void;
}

const mocks = vi.hoisted(() => {
  // A deterministic stand-in for the pipeline: 3 numbers instead of 384, which
  // is enough to prove we wrap `.data` rather than to prove anything numeric.
  const extractor = vi.fn(
    async (_text: string, _options?: { pooling?: string; normalize?: boolean }) => ({
      data: new Float32Array([0.1, 0.2, 0.3]),
    }),
  );
  // Typing the parameters explicitly (rather than letting `async () => ...`
  // infer a zero-arity signature) is what makes `mock.calls[0][2]` below a
  // real options object instead of an out-of-range tuple index.
  const pipeline = vi.fn(
    async (_task: string, _model?: string, _options?: FakePipelineOptions) => extractor,
  );
  return { extractor, pipeline, env: { allowLocalModels: true } };
});

vi.mock("@xenova/transformers", () => ({
  pipeline: mocks.pipeline,
  env: mocks.env,
}));

// embedding.ts keeps its loaded pipeline in module-level state on purpose, so
// each test needs a genuinely fresh copy of the module rather than a shared one
// that is already "ready" from the previous test.
async function freshModule() {
  vi.resetModules();
  return await import("./embedding");
}

beforeEach(() => {
  mocks.pipeline.mockClear();
  mocks.extractor.mockClear();
  mocks.env.allowLocalModels = true;
});

describe("loadEmbedder", () => {
  it("loads the pipeline only once even when called concurrently", async () => {
    const { loadEmbedder } = await freshModule();

    // Both calls are made before either is awaited -- the second arrives while
    // the first load is still in flight, which is exactly the case that would
    // start a duplicate model download if the singleton held the resolved
    // pipeline instead of the in-flight promise.
    const first = loadEmbedder();
    const second = loadEmbedder();
    await Promise.all([first, second]);

    expect(mocks.pipeline).toHaveBeenCalledTimes(1);

    // And a third call after the load has fully settled still reuses it.
    await loadEmbedder();
    expect(mocks.pipeline).toHaveBeenCalledTimes(1);
  });

  it("requests the exact model the Python side uses, quantized", async () => {
    const { loadEmbedder } = await freshModule();
    await loadEmbedder();

    expect(mocks.pipeline).toHaveBeenCalledWith(
      "feature-extraction",
      "Xenova/all-MiniLM-L6-v2",
      expect.objectContaining({ quantized: true }),
    );
  });

  it("wires onProgress to the pipeline's progress_callback and maps the payload", async () => {
    const { loadEmbedder } = await freshModule();
    const onProgress = vi.fn();
    await loadEmbedder(onProgress);

    const options = mocks.pipeline.mock.calls[0][2]!;
    expect(options.progress_callback).toBeTypeOf("function");

    // A "progress" event: the only kind that carries a numeric percentage.
    options.progress_callback!({
      status: "progress",
      name: "Xenova/all-MiniLM-L6-v2",
      file: "onnx/model_quantized.onnx",
      progress: 42.5,
      loaded: 425,
      total: 1000,
    });
    expect(onProgress).toHaveBeenCalledWith({
      status: "progress",
      progress: 42.5,
      file: "onnx/model_quantized.onnx",
    });

    // "initiate"/"download"/"done" events carry no `progress` field, and it
    // must stay undefined rather than being invented as 0 or 100.
    options.progress_callback!({
      status: "done",
      name: "Xenova/all-MiniLM-L6-v2",
      file: "tokenizer.json",
    });
    expect(onProgress).toHaveBeenLastCalledWith({
      status: "done",
      progress: undefined,
      file: "tokenizer.json",
    });
  });

  it("passes no progress_callback when no onProgress is given", async () => {
    const { loadEmbedder } = await freshModule();
    await loadEmbedder();

    const options = mocks.pipeline.mock.calls[0][2]!;
    expect(options.progress_callback).toBeUndefined();
  });
});

describe("embedQuery", () => {
  it("lazily loads the pipeline itself when nothing pre-loaded it", async () => {
    const { embedQuery } = await freshModule();
    await embedQuery("what is LoRA?");

    expect(mocks.pipeline).toHaveBeenCalledTimes(1);
  });

  it("returns a real Float32Array wrapping the extractor's data", async () => {
    const { embedQuery } = await freshModule();
    const vector = await embedQuery("what is LoRA?");

    expect(vector).toBeInstanceOf(Float32Array);
    expect(Array.from(vector)).toHaveLength(3);
  });

  it("mean-pools and normalizes -- the options that must match the Python side", async () => {
    const { embedQuery } = await freshModule();
    await embedQuery("what is LoRA?");

    expect(mocks.extractor).toHaveBeenCalledWith("what is LoRA?", {
      pooling: "mean",
      normalize: true,
    });
  });
});

describe("isEmbedderReady", () => {
  it("is false before loading and true once loadEmbedder resolves", async () => {
    const { loadEmbedder, isEmbedderReady } = await freshModule();

    expect(isEmbedderReady()).toBe(false);
    await loadEmbedder();
    expect(isEmbedderReady()).toBe(true);
  });
});

describe("browser-only configuration", () => {
  it("disables local model probing so the first request goes straight to the CDN", async () => {
    await freshModule();
    expect(mocks.env.allowLocalModels).toBe(false);
  });
});
