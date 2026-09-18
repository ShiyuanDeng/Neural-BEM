# Literature compression reproduction (LAU-002)

Independent implementation of the Jiang–Wang–Yu 2021 scalar convolution split
and Fourier index truncation, followed by an explicitly experimental transfer
to the existing Muller transmission operator. See the
[measured closeout](../../results/validation/laurent/LAU-002-20260917-closeout/README.md)
and [contract](../../docs/iterations/laurent/iteration_03/03_plan.md).

| File | Role |
|---|---|
| `scalar.py` | Exact published index mask, scalar ellipse amplitudes, log contraction, exact manufactured analytic density |
| `run_scalar.py` | Manufactured-density convergence and printed-count diagnostics; dense reference assembly, sparse masked LU |
| `transmission.py` | Three explicit protected splits, mask transfer and structural forward-slot counts |
| `run_transfer.py` | Independent Kress field/derivative qualification and frozen-mask comparisons |
| `evidence.py` | Fresh bundles, source/config/environment provenance, failure record and hard ceilings |
| `audit_bundle.py` | Read-back hashes, mask signs, count identities, derivative joins and gate checks |
| `test_literature.py` | Analytic and independently evaluated physical checks |

The paper uses `|m| < n`, so trace cutoff is `K=n-1` and dimension `2n-1`.
Double-kernel Fourier index `l` is negative matrix input mode `q`.
`mask_n > K+1` means the central restriction of a larger published mask; this
is an adaptation, not the paper's coupled trace/mask parameter choice.

All existing numerical packages are imported read-only. New evidence freezes
their hashes too. Do not edit numerical Python files during a campaign or
overwrite an existing result directory. Printed-table discrepancies and
failed arms are evidence, not targets to tune away. The final audit requires
the measured source revision; a later source change needs a new run or checkout
of the recorded revision, not a claim that old hashes still match.

No production integration, fast assembly, general transmission proof, or
inverse recovery claim is made. Forward slot counts are separate from actual
memory and wall-clock work. Reproduction commands are in the closeout.
