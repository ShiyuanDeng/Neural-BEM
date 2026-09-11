# Review diagnostics: is the gradient chain still correct at late states?

Probes run on 2026-09-09 by Claude to support
[`04_claude_gradient_diagnosis.md`](../../../../../docs/iterations/implicit_mlp/iteration_03/02_proposals/04_claude_gradient_diagnosis.md).
They exist because the long run validated its neural gradient **only at state
0**, and because the direct Method-B Fourier control proposed in
[`01_chatgpt_guide.md`](../../../../../docs/iterations/implicit_mlp/iteration_03/02_proposals/01_chatgpt_guide.md)
would **not** test the Kress shape gradient at all — it reuses it.

**No inverse is run, no optimizer step is taken, no production code is changed
and no saved artifact is modified.** Weights are restored after every
perturbation. The probes read saved accepted checkpoints, saved geometry
trajectories and the run's observations, and re-run correctness checks at
frozen states.

| File | Contents |
|---|---|
| `gradient_chain_audit.py` | Stage A and the composite, from saved weight checkpoints |
| `gradient_chain_audit_states.txt` | Stage A across nine states per arm |
| `gradient_chain_audit_step_sweep.txt` | Stage A at E0 26/30/31/42 over seven steps |
| `gradient_chain_audit_composite.txt` | Stage A and the composite at three states per arm |
| `kress_shape_gradient_audit.py` | Stage B, from saved contours, with no MLP |
| `kress_shape_gradient_audit.txt` | Its full-precision output |

Each output is reproducible from a checkout that retains the long run:

```text
python gradient_chain_audit.py --stage a --states 0,10,20,26,30,31,36,40,42
python gradient_chain_audit.py --stage a --arms E0 --states 26,30,31,42 \
    --steps 4e-4,2e-4,1e-4,5e-5,2e-5,1e-5,5e-6
python gradient_chain_audit.py --stage all --states 0,26,30
python kress_shape_gradient_audit.py
```

## The chain and where it is cut

```text
weights --[A] Method-B reverse--> curve jets --[B] Kress pullback--> dL
```

* **Stage B — the Kress objective adjoint and geometry pullback.** A saved
  `converted_contour` is re-expressed exactly as its bandwidth-96 Cartesian
  Fourier curve, perturbed coherently in coefficient space over modes 0..8, and
  `dL = sum q_i . d gamma_i + sum p_i . d gamma'_i` is compared with central
  differences of the same production objective. No MLP is loaded; no extraction,
  projection or Method-B fit runs. Because the contour has 194 nodes and
  bandwidth 96 is exactly `(194 - 2) / 2`, the DFT of those nodes recovers the
  curve exactly; the printed Nyquist bin and maximum node difference are the
  checks that it did.

* **Stage A — extraction, projection, Fourier fit and arc-length refit
  reverse.** The differentiable Method-B replay is contracted with one fixed
  random covector on points and first derivatives, backpropagated to the
  weights, and compared with central differences of the same scalar formed from
  the production `build_ordered_sdf_geometry` curve. **This needs no BEM solve
  at all.** The replay's own `maximum_replay_error` is reported beside it.

* **A o B — the composite** the inverse actually used: the production
  `implicit_mlp_data_gradient` against central differences of the data loss.
  This repeats the long run's `directional_gate` at states it never covered.

Cutting the chain is what makes the result attributable. The composite alone
cannot say which half is at fault; stages A and B can.

## Reading the numbers

Central differences carry a truncation error of order `h**2`. An analytic
derivative that is **correct** therefore shows a relative error that falls by
about **4x** each time the step is halved, and its size at any one step says
nothing on its own. An analytic derivative that is **wrong** shows a relative
error that flattens to a nonzero constant as `h` shrinks.

Read the trend across the three steps, not the magnitude. The summary tables
report the worst of the two smallest steps, which is the conservative reading.

## Caveats that travel with the numbers

Stage A's map is only **piecewise** smooth. `implicit_mlp_data_gradient` says so
in its own docstring: the conversion uses its current marching, interpolation
and projection branches, and the derivative does not claim smoothness across a
branch change. A larger step that crosses such a change produces an inflated
relative error at that step alone while the smaller steps stay clean; that
pattern is a branch crossing, not a wrong derivative, and it appears in the
output.

Both probes use one fixed random direction per state, seeded at 724. A single
direction can miss a defect confined to a subspace. These are correctness
checks on the derivative that was actually used, not a certificate over all
directions, and not a statement about conditioning — a derivative can be exact
and still be a poor search direction.

Stage B's perturbation is confined to Cartesian modes 0..8 so that every
perturbed curve stays admissible. It does not exercise the high-mode part of
the 386-coefficient chart.

Stage A and stage B use different step ranges because they finite-difference
different quantities: weights for A, Fourier coefficients in metres for B.

The states are the saved accepted states, which are the states the inverse
committed to. Rejected candidates and the terminal proposals are not audited
here.
