# Coordinator review

## Questions

1. Does each implementation test its stated question with the saved states,
   accuracy thresholds and full costs specified in its plan?
2. Do the results support a useful next decision, including a negative answer?
3. What can be reported to a supervisor as established progress, and what
   remains unproved?

## Execution

The user requested three parallel GPT-6.1 agents with high reasoning and
coordinator review, with no time limit. The historical morning deadline does
not limit this execution. All work uses the existing `organised` checkout.

The three main studies run without new inverse fits. Production solver code
is not changed. Each agent owns its experiment and evidence paths; the
coordinator serializes commits and pushes after completed experiment steps.

CPU allocations are 0–5 for FI-001, 6–11 for TA-001 and 12–17 for IS-001,
with single-thread BLAS and less than 6 GB per track. IS-001 has initial GPU
priority for the production timing breakdown. Timings are compared within
tracks; machine load and backend must accompany the interpretation.

## Review criteria

- FI-001: fixed node selection, genuinely held-out frequencies, worst field
  and Jacobian-column errors, and setup included in any speed claim.
- TA-001: reproduction against saved refused coefficients, geometric
  classification beyond the failed certificate, round-trip and first-order
  agreement, and validity after projection to the stored Fourier band.
- IS-001: all source and receiver right-hand sides, production cost split,
  matched field accuracy, explicit iterative algorithm, and anchor cost
  included in crossover and reuse conclusions.
- Synthesis: distinguish measured results from explanations, component
  improvements from recovered fits, and scoped negative evidence from a
  claim that an entire mathematical approach cannot work.

## Findings

Pending completed evidence and implementation review.
