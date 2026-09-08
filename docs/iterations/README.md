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

Start with the [implicit-MLP handoff](implicit_mlp/README.md) for the active
iteration, current stage, reading order, next expected action, execution status
and cycle history. That project README is the maintained entry point; proposal
numbering alone does not identify the agreed plan or authorize execution.
