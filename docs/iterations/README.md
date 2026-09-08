# Experiment iterations

One iteration = one research cycle. Results from a change always start the next
iteration, so a folder is never rewritten after its plan is executed.

```text
<project>/iteration_NN/
  01_results.md    measurements from the runs that opened this cycle, the
                   problems they expose, and the candidate fixes
  02_proposals/    ChatGPT's next-step guides and the reviews of them, numbered
                   in the order they were received
  03_plan.md       the agreed plan: decisions, what was validated, what is
                   deferred, and the experiment that opens the next iteration
```

Stages appear only once they exist — an iteration awaiting a proposal has just
`01_results.md`. Run reports, metrics and scripts stay with their artifacts
under `results/`; the stage files link to them rather than copying them.

## Implicit MLP

| Iteration | Cycle | State |
|---|---|---|
| [1](implicit_mlp/iteration_01/01_results.md) | Sept 7–8 failures, repairs, and the matched acquisition controls | Closed; see [03_plan.md](implicit_mlp/iteration_01/03_plan.md). Neural recovery unresolved |
| [2](implicit_mlp/iteration_02/01_results.md) | Sept 8 repaired 12-pair wrong-start suite | Stage 1 only; awaiting a proposal |
