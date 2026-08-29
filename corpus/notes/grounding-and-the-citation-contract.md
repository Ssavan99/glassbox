---
title: "Grounding and the Citation Contract"
tags: [evaluation, prompting]
entities: [grounding, citation, hallucination, prompt template, refusal]
created: 2026-01-07
---

Grounding is the property that a model's claims are actually supported by the retrieved evidence it was given, rather than supplied from its own memorized parameters. It is easy to state and surprisingly hard to enforce, because a model that hallucinates and a model that is grounded can produce sentences that look identical in tone and confidence — grounding is a relationship between the answer and its evidence, not a property visible from the answer text alone.

The practical way to make grounding checkable, rather than just hoped for, is what can be called the citation contract: every substantive claim in an answer should be traceable to a specific retrieved chunk, and the system should be willing to say "I don't know" rather than answer once no chunk supports the claim. This turns grounding from a vague aspiration into something an evaluation harness can actually test — check each claim against its cited source, rather than asking a judge to guess whether the answer "feels" grounded.

Enforcing the citation contract is primarily a prompt template responsibility: the system prompt needs to explicitly instruct the model to cite the specific note behind each claim and to treat missing evidence as a reason to refuse rather than a gap to fill in. Models left to their own devices default toward being maximally helpful, which in a retrieval context means guessing when evidence runs short — refusal has to be explicitly permitted and even encouraged in the prompt, or the model will treat "I don't have enough information" as a failure to avoid rather than the correct answer to a genuinely unanswerable question.

The citation contract connects directly to two other concerns covered elsewhere: citation quality evaluation is what measures whether the contract is actually being honored in practice, and hallucination is what results when it is broken. Treating grounding as a single design contract, spanning the prompt, the evaluation harness, and the retrieval pipeline together, is more useful than treating it as a property of any one of those pieces in isolation — a perfectly grounded prompt still produces ungrounded answers if retrieval never surfaces the needed evidence in the first place.
