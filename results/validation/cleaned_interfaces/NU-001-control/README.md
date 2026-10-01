# NU-001 control: shape directions at saved nodal states

Pre-run control for the [NU-001 plan](../../../../docs/iterations/cleaned_interfaces/iteration_08/03_plan.md).
Reproduce from the repository root:

```bash
PYTHONPATH=solvers:. python -m experiments.cleaned_interface.n_update_audit control \
    --output results/validation/cleaned_interfaces/NU-001-control
```

States: the last accepted state of every stage of the six CI-001 core runs
(72 states, K = 4–192, M = 1–37, speed ratio 1.000–1.167). For each state
[`control.json`](control.json) records:

- `baseline_fd_vs_linearization`: CI-001 `ProjectedUpdate` FD columns against
  the exact first-order model `baseline_linearization` (worst column ≤ 2.3e-7);
- `baseline_weights_vs`: relative L2 difference of the Hadamard weights
  Re(V conj N) between the baseline FD columns and four closed forms
  (arclength hybrid cos(mα)σ, θ-harmonic unit normal cos(mθ)σ, arm A, arm B);
- `n_update_weights_vs_eq3`: arm A weights against φ_q S (eq. 3); non-zero only
  through the crop at K = 2M+2;
- `n_update_affine_fd_relative`: arms A/B trial differences against their
  exact derivative (≤ 1.6e-10);
- `crop_tail`: ℓ¹ fraction of each direction removed by P_K;
- `preparation_seconds` on this host (4 vCPU, no CUDA).

Summary and interpretation:
[review against the code](../../../../docs/iterations/cleaned_interfaces/iteration_08/02_proposals/02_review_against_code.md).
