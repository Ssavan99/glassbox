// Live, in-browser sentence embeddings via transformers.js.
//
// This is the JS half of a two-sided contract: the Python backend embeds the
// corpus with `sentence-transformers/all-MiniLM-L6-v2` (see engine/embedding.py),
// and this module embeds the user's typed query with `Xenova/all-MiniLM-L6-v2`,
// the transformers.js port of that exact same model. Both sides mean-pool the
// token embeddings and L2-normalize the result to a 384-dim unit vector, so
// cosine similarity between a query vector from here and a chunk vector from
// there is just a dot product.
//
// The pooling/normalization options below are therefore load-bearing, not
// stylistic: any other choice would still produce a plausible-looking 384-dim
// vector that silently disagrees with the Python-side vectors.

import { pipeline, env, type FeatureExtractionPipeline } from "@xenova/transformers";

// transformers.js defaults `env.allowLocalModels` to `true`, which makes it
// probe `${env.localModelPath}` (i.e. `/models/Xenova/all-MiniLM-L6-v2/...`)
// on this site's own origin before falling back to the Hugging Face CDN. This
// app ships no such directory, and its SPA host answers unknown paths with
// index.html rather than a 404 -- so the probe doesn't just waste a round trip,
// it hands the loader HTML where it expects JSON. Disabling local models makes
// the very first request go straight to the remote weights.
env.allowLocalModels = false;

/** A progress event from the model download/initialization, normalized for UI use. */
export interface EmbedProgress {
  status: string; // whatever transformers.js reports: "initiate" | "download" | "progress" | "done"
  progress?: number; // 0-100, only present on "progress" events
  file?: string; // which file is being fetched
}

/**
 * The real shape of the payload transformers.js hands to `progress_callback`.
 *
 * `PretrainedOptions.progress_callback` is typed as the bare `Function` in the
 * package's own .d.ts, so there is no exported type to reuse here. These fields
 * are the ones actually dispatched from `utils/hub.js`: `initiate`, `download`
 * and `done` carry only `{ status, name, file }`, while `progress` additionally
 * carries `{ progress, loaded, total }`. Hence `progress` is optional -- it is
 * genuinely absent for three of the four event types, and must stay `undefined`
 * rather than being defaulted to 0 (which a progress bar would misread as
 * "restarted from the beginning").
 */
interface RawProgressEvent {
  status: string;
  name?: string;
  file?: string;
  progress?: number;
  loaded?: number;
  total?: number;
}

function toEmbedProgress(info: RawProgressEvent): EmbedProgress {
  return {
    status: info.status,
    progress: info.progress,
    file: info.file,
  };
}

/**
 * Module-level singleton. Holding the *promise* (not the resolved pipeline) is
 * what makes concurrent callers share one download: the second caller arriving
 * mid-flight awaits the same in-flight promise instead of kicking off a second
 * multi-hundred-KB fetch of the same weights.
 */
let extractorPromise: Promise<FeatureExtractionPipeline> | null = null;
let ready = false;

function getExtractor(
  onProgress?: (p: EmbedProgress) => void,
): Promise<FeatureExtractionPipeline> {
  extractorPromise ??= pipeline("feature-extraction", "Xenova/all-MiniLM-L6-v2", {
    quantized: true,
    progress_callback: onProgress
      ? (info: RawProgressEvent) => onProgress(toEmbedProgress(info))
      : undefined,
  }).then((extractor) => {
    ready = true;
    return extractor;
  });
  return extractorPromise;
}

/**
 * Lazily loads the embedding pipeline exactly once. Never runs at module import
 * time -- only when a caller first needs an embedding. `onProgress`, if given,
 * fires for every progress event transformers.js reports during the (possibly
 * first-ever, uncached) model download and initialization.
 */
export function loadEmbedder(onProgress?: (p: EmbedProgress) => void): Promise<void> {
  return getExtractor(onProgress).then(() => undefined);
}

/**
 * Embeds `text` with the real, loaded model, loading it first if needed -- so a
 * caller can either pre-load with a progress UI and then embed instantly, or
 * just call this directly and accept a silent first-call wait.
 *
 * Returns a 384-dim, L2-normalized Float32Array.
 */
export async function embedQuery(text: string): Promise<Float32Array> {
  const extractor = await getExtractor();
  const output = await extractor(text, { pooling: "mean", normalize: true });
  // `output.data` is already the mean-pooled, L2-normalized 384-dim vector.
  // The Tensor's `data` is typed as the union `DataArray`; a feature-extraction
  // tensor is always float32, and copying into a fresh Float32Array detaches the
  // result from the pipeline's internal buffer.
  return new Float32Array(output.data as Float32Array);
}

/**
 * True once the embedder has finished loading, i.e. once `embedQuery` will
 * resolve without any further model download. Lets a UI decide up front whether
 * to show a loading state.
 */
export function isEmbedderReady(): boolean {
  return ready;
}
