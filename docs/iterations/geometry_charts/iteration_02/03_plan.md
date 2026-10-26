# TA-001 continuation: four fresh chart fits

## Questions

1. Does the positive saved-step result survive a full TG-002 trajectory?
2. Which of the four previously failing cases recover, or stop differently?

The main replay was positive in three of four cases. After reviewing that
answer and the implementation, the coordinator authorized this pre-planned
conditional continuation on 2026-10-26. The historical deadline is removed.

## Fixed scope

Exactly four fresh centred TG-002 fits: aphex at contrasts 0.5, 4 and 13.3,
and hook at 13.3. No restarts, other cases, parameter search or control reruns.
Compare with saved NR-001 M1 results. Their Mac CPU timings are not a speed
control for this machine.

Use the default `CumulativePolicy()` unchanged: 13,412 work units and
1,800 s fit allowance. Use modal Müller CUDA physics, no localization,
one frequency worker, CPU B6 preparation and single-thread BLAS, cores 6–11.
Cap PyTorch's CUDA allocator at 5 GiB and retain memory receipts.

## Experimental map

Keep the adapter under `experiments/geometry_charts/`; do not promote it.
Its B6 tangent basis is the recorded spectral complete-map coefficient
derivative. The finite chart map exponentiates the induced log-speed and
tangent-angle increments, solves closure, integrates and crops to K.

Because closure has zero first derivative at a closed base, the chart's
actual B6 derivative is exactly this coefficient basis, retaining its
tangential gauge. Check the wrapper's zero step and central finite
difference on the four saved accepted states before fitting.

Treat failed closure and non-finite construction as `UpdateRefused`, so
the existing backtracking loop tries the next fraction. Run the usual
area, sampled-speed, intersection and domain checks on the cropped curve.
A modal physics refusal retains the default hard-stop behavior.

## Evidence and decision

Use the standard independent final field/Jacobian/full-trial check with
the actual chart adapter, then unchanged TG-002 truth scoring and recovery
limits. Preserve failed runs and failed final checks. Report recovery,
RMS, Hausdorff upper bound, maximum residual, final stage, stop, work and time.

The answer is positive only if at least one case newly recovers under the
unchanged TG-002 conditions. Lower loss or a later stage alone is progress,
not recovery. Any failure is a full result; it does not authorize another fit.

Save under `results/validation/cleaned_interfaces/TA-001/continuation/`.
After each fit, send its paths to the coordinator for serialized
commit, pull --rebase, push and status verification.
