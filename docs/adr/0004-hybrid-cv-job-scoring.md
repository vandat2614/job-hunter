# ADR-0004: Hybrid CV-to-job scoring (code for skills, LLM for experience)

**Status:** Accepted
**Deciders:** Project owner

## Context
We want a fit score between a user's CV and a job description. The initial idea was to send a system prompt, the full CV and the job description to an LLM and let it produce the evaluation. The server has 2 vCPUs, 15 GB RAM and no GPU, so only small models can run locally.

We benchmarked qwen2.5:1.5b and qwen2.5:3b through Ollama on one short CV/JD pair (227 prompt tokens), asking for JSON with matched and missing skills. Observations (a single sample per model, so indicative only):
- Latency: about 27 s (1.5b) and 33 s (3b) per call.
- Both models listed skills the CV does not contain (Kubernetes, AWS) as matched.
- The 3b model also reported Kafka as missing although the CV mentions it, and contradicted itself in the reason.
- The 3b output was well formed JSON; the 1.5b output was wrapped in markdown and verbose.

## Decision
Split the work by what each part does reliably:
1. Skill overlap is computed by code (keyword matching on the CV and the job).
2. The LLM receives the full CV and job description but only judges whether experience is below, meets or exceeds what the job asks, plus a one-sentence note. Its output is constrained to a JSON schema and validated again in code.
3. The final score is a formula: 70 x skill_ratio + 30 x experience_value (below 0.3, meets 0.8, exceeds 1.0).
4. If the LLM is unavailable or returns unusable output, the score falls back to skills only.

The LLM is behind a small client interface, so a hosted model can replace Ollama without changing the scoring logic.

## Options Considered

### Option A: LLM scores everything (original idea)
| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | Free locally, per-call fee if hosted |
| Reliability | Low with small local models |
| Explainability | Low |

**Pros:** simplest, can use context and wording that keywords miss.
**Cons:** small models invented skills in our test; the score cannot be explained or unit tested; the score can change between runs.

### Option B: Hybrid (chosen)
| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Cost | Free locally |
| Reliability | High for skills, bounded impact from the LLM |
| Explainability | High: the formula is visible |

**Pros:** the invented-skills failure cannot affect the score; deterministic and testable parts; graceful degradation.
**Cons:** keyword matching misses skills outside the list and synonyms; the weights are hand-picked, not validated.

### Option C: Keywords only, no LLM
**Pros:** fastest, no extra infrastructure.
**Cons:** cannot judge seniority or experience at all.

### Option D: Hosted LLM (Claude API) for free-form scoring
**Pros:** much better judgment than a small local model.
**Cons:** CV text leaves the server; per-call cost; needs an API key. Kept as a future option behind the client interface.

## Trade-off Analysis
The benchmark showed the weakness of small models is factual accuracy about lists, not general reading of seniority. Moving the factual part to code and keeping the LLM for the soft judgment removes the observed failure while still using the model for something keywords cannot do.

## Consequences
- Easier: unit testing (the LLM is faked), explaining a score, and degrading gracefully when the LLM is down.
- Harder: the skill list is duplicated in job-service and scoring-service and can drift.
- Scoring takes minutes on this CPU, so notifications are delayed; it runs asynchronously behind Kafka for this reason.
- To revisit: validate the weights against labelled examples, try a hosted model, and extract the skill list into a shared library.
