---
title: "Citation Quality as an Evaluation Signal"
tags: [evaluation, prompting]
entities: [citation, grounding, hallucination, evaluation harness, retrieval-augmented generation]
created: 2026-01-07
---

Citation quality measures whether a system's cited source actually supports the claim it is attached to, which is a different and often more revealing signal than answer correctness alone. An answer can be factually correct while citing the wrong note, or citing a note that only tangentially relates to the claim — both are grounding failures even though the final text looks fine on the surface.

There are three distinct ways a citation can fail, and conflating them hides which part of the pipeline needs fixing. It can point to a real, retrieved note that does not actually support the specific claim next to it, which usually means the generation step is not carefully checking its own citations. It can point to a note that supports a related but different claim than the one being made, which often means retrieval pulled a near-miss chunk rather than the precise one. Or it can be entirely fabricated — a citation to a note that was never retrieved at all, or that does not exist in the corpus — which is a severe grounding failure, functionally a hallucination wearing a citation's clothing.

Measuring citation quality requires the golden dataset to record which notes actually support each answer, not just what the answer text should say. Given that, an evaluation harness can check a cited source against the recorded evidence set automatically, rather than relying on a human or a model to judge plausibility after the fact — plausibility judgments are exactly what a fabricated-but-confident citation is designed to survive.

High citation quality is also a leading indicator worth tracking independently of answer correctness, because it tends to degrade before overall answer quality does. A system that starts drifting toward fabricated or mismatched citations, while still producing correct-sounding answers most of the time, is showing an early warning sign of ungrounded generation that will eventually produce a wrong answer with just as much confidence — catching the citation drift first buys time to fix the underlying prompt or retrieval issue before user-visible answer quality actually drops.
