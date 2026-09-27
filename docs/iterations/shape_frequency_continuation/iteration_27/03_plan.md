# SC-048: exact global motions as a compact update-space enrichment

2026-09-27. Owner: Codex; no independent reviewer. Authorized by the user's
autonomous follow-through instruction. Runs only after SC-047's frozen
campaign finishes; no SC-047 numerical sources or settings change.

## Question and motivation

SC-047's first clean comparison showed no conditional-selection advantage.
A subsequent geometry-only probe found that its M=5 complete normal-update
space misses 23% of the C component's horizontal-translation velocity and
25% of its rotation velocity in boundary RMS norm. This is an expressibility
observation, not proof that it causes the reconstruction error.

Can exact global motions improve reconstruction more economically in parameter
count than a larger generic normal band? Translation, rotation and uniform
scaling are standard geometry coordinates. No novelty is claimed for them.
The experiment tests their value as extra directions beside local normal modes.

## Intervention and controls

Inject an experimental update wrapper around the unchanged SC-035 projected
update. The finite trial first applies that update, then an exact similarity
transform about the current parameter-mean centre. Differentiate that complete
construction. Orthogonalize added physical normal velocities against the
existing span. Admit a global motion only if at least 5% of its physical
normal velocity is outside the existing span, so nearly redundant directions
do not require large cancelling finite motions. Drop numerical null directions
with original norm <=1e-8. The original normal coordinates are retained.
This eligibility cutoff was set during implementation design, before SC-048
qualification or inversion; it uses current geometry, not truth or residuals.

Compare three arms using the unchanged shared LM backend:

- M=5 normal updates;
- M=9 normal updates (strong simple bandwidth control);
- M=5 plus independent translation-x, translation-y, rotation and dilation
  directions, at most four extra coordinates per object.

All objects update jointly. K=32, N=256/512, four inherited paired frequencies,
contrast and acquisition are SC-047's. Same physical 2 mm step cap, damping,
refined acceptance, six one-iteration dispatches, 200 solve units (including
eight endpoint solves and a 16-unit reserve), 900 seconds per arm. All trial,
geometry, Jacobian and validation costs remain visible. No production default
or topology action changes.

## Inputs, qualification and gates

The first scene is the 0.14 m ellipse/C pair. Start from SC-047's declared
initial family, with two extra fixed morphological perturbations: multiply
the ellipse's negative first Fourier coefficient by 1.12; apply a 1.5 mm a2
and 1.0 mm b3 projected normal displacement to the C component. These changes
make the starting shapes differ beyond similarity transforms. No truth-based
choice or best-iterate selection is allowed.

Before inversion: test zero-step identity, unchanged original normal columns,
rank/metric validity, and coupled complete-trial finite differences for each
object and both at eps=1e-6 and 5e-7 m, N=256, all four frequencies. Require
relative derivative error <=1e-3. Reserve 200 solves and 600 seconds for this
gate; refusal/failure stops the study.

The primary clean screen passes only when the enriched arm:

1. reduces worst-object RMS by >=25% against M=5 under the same 200-unit ceiling;
2. has worst-object RMS <=1.05 of M=9, neither object >1.10 of M=9, no greater
   solve work, and fewer active coordinates;
3. returns a geometrically valid, numerically qualified endpoint.

Only if that gate passes, run the same three arms on 1% complex noise (seed
4801) at the first separation, and clean/noisy data at 0.20 m separation.
No settings change after the first screen. These are development scenarios;
transfer requires the same gates, and no broad generalization claim follows.
If the primary screen fails, retain all evidence and stop this direction.

The weak M=5 control may spend less because it stalls. Its lower actual cost
is retained, not treated as equal work. The cost advantage gate applies to
the strong M=9 control; comparison with M=5 establishes attainable improvement
under the shared budget rather than strict cost dominance over a stalled fit.

Save complete inputs, configuration/source hashes, accepted states, endpoint
per-object RMS/Hausdorff/region errors, active dimensions, failures and costs.
This is a bounded test of update-space choice, not another atlas threshold
search. Results open iteration 28.
