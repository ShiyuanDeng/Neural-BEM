# Fit the remaining CSI tables at ten frequencies: plan

18 November 2026, 11:55 UTC. Written by the BEM coordinator (pane `w2:p1`)
before any result of this activity exists. Runner: `bem-ten` (Codex
`gpt-6.1-sol`, medium, full access). Authority:
[coordinate_bem_side.md](../../coordinate_bem_side.md).

## Why

[Activity 08](../08_fit_csi_tables_at_ten_frequencies/results.md) fitted
four shapes at ten frequencies. The user wants MF-CC-CSI fitted at ten
frequencies next ("after you are done you can talk to baseline side
coordinator and brief him to do csi fit"). A paired table then needs our
BEM on whichever shapes CSI fits. The ten tables are frozen and checked
already, and a fit takes one to three minutes.

Chosen by the coordinator: to run these six fits now, with every setting
of activity 08. The user asked for the ten-frequency test and for BEM
only; the shapes beyond the first four are the coordinator's addition.

## Question

What does our default BEM fit give on peanut, asymmetric, C-shape, cross,
cog and Aphex Twin with the ten-frequency CSI tables, beside the
five-frequency pass?

## Settings (unchanged from activity 08)

- Tables: `results/csi/tg002/2026-11-18_ten_frequency_data/<shape>/forward/synthetic_input.txt`,
  frozen, with passing checks in
  `results/bem/baseline_data/csi_ten_frequency/2026-11-18/adapter_checks/`.
- Default method, ten-stage ladder, quotas 1000, eight times 375, 4000;
  the same thin runner. No code change.
- Six GPU fits, one each, one pass, no tuning, no rerun. Failures stay in
  the table. No stop on elapsed time. Memory: 16.5 GiB available to start;
  at most two fits at a time.

## What to report

One table for all ten shapes: five-frequency and ten-frequency area error,
outcome, last stage, work units, seconds, contrast. The four rows of
activity 08 are copied, not rerun. Also the area error of every saved
stage outline for the six new fits, and one figure of the six outlines
over the truth with the five-frequency outlines.

## Reading the result (fixed now)

A clear gain is an area error at most half the five-frequency value
(references: peanut 1.54%, asymmetric 1.29%, C-shape 2.60%, cross 2.10%,
cog 2.86%, Aphex Twin 5.96%). Report the count over all ten shapes. A
shape above 5% is a miss by the report's rule.

## Budget and outputs

Six GPU fits. Fits in
`results/bem/baseline_data/csi_ten_frequency/2026-11-18/<shape>__c4/cuda/attempt_01/`.
This folder: `results.md`, `figures/`. Commit by path and push after each
fit; at most about 5 MB committed.

## Commands

The runner writes the exact commands here before its first run.
