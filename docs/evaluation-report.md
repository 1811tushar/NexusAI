# Evaluation report

**Status: NOT YET MEASURED.** Fill this file only from artefacts produced by real runs. Illustrative numbers from design references must never appear here.

## Run record
| Field | Value |
|---|---|
| Commit SHA | |
| Dataset version (seed + corpus + golden set) | |
| Environment (provider, model name, embedding model, hardware) | |
| Commands run | `python -m app.evals.ci_check`, `python -m app.evals.retrieval_ablation`, `python -m app.evals.run_eval --system both` |
| Date | |

## Systems compared (same golden set)
| System | Answer correctness | Grounded-claims share | Hallucination rate | Citation validity | Avg latency (ms) | Avg tokens |
|---|---|---|---|---|---|---|
| BASELINE (single-shot RAG) | NOT MEASURED | | | | | |
| SINGLE_AGENT | NOT MEASURED | | | | | |
| AGENT_NO_VERIFIER | NOT MEASURED | | | | | |
| AGENT (full NexusAI) | NOT MEASURED | | | | | |

## Per category (normal, edge, adversarial, missing data, tool failure)
| Category | n | BASELINE | SINGLE_AGENT | AGENT_NO_VERIFIER | AGENT |
|---|---|---|---|---|---|
| NORMAL | | | | | |
| EDGE | | | | | |
| ADVERSARIAL (guardrail block rate) | | | | | |
| MISSING_DATA (correct abstention rate) | | | | | |
| TOOL_FAILURE (failure recovery rate) | | | | | |

## Safety
| Check | Result |
|---|---|
| Approval-gate compliance (must be 100%) | NOT MEASURED |
| HIGH-risk actions executed without APPROVE | NOT MEASURED (must be 0) |
| Write-SQL attempts blocked | NOT MEASURED |

## Retrieval ablation (no LLM)
| Variant | Hit rate@k | MRR |
|---|---|---|
| fixed chunking, vector only | NOT MEASURED | |
| semantic chunking, vector only | | |
| semantic chunking, keyword only | | |
| semantic chunking, hybrid (RRF) | | |
| hybrid + reranker | | |

## Judge and human check
Judge model and prompt version: . Human spot-check of 10 answers: agreement with the automated judge: .

## Limitations (keep honest)
Synthetic data; small golden set; LLM-as-judge noise; free-tier model rate limits and nondeterminism; actions are simulated.
