# FI-001 execution choices, frozen before measurements

Questions: do 4–14 exact frequencies meet the field and Jacobian tolerances,
and does their full per-curve setup leave a 25% saving?

- Use degree n−1 barycentric polynomial interpolation in real wavenumber.
  Nodes are a deterministic discrete Leja sequence: catalog endpoints first,
  then maximize the product of normalized distances to existing nodes,
  breaking ties by the lowest catalog index. Use prefixes 4, 6, 8, 10, 12, 14.
  No held-out output chooses a node or the interpolation family.
- Use CPU accuracy and timings, one frequency at a time, cores 0–5 and
  single-thread BLAS. Other parallel studies use the GPU. Each arm uses a
  fresh physics context, charging geometry and its lazy radial bases.
- Arm A interpolates complete matrices, then uses exact frequency-specific
  waves, LU, forward/reciprocal solves and Hadamard contraction. Arm B
  interpolates the paired fields and complete reciprocal Jacobian columns.
- The shared exact node evaluations serve both arms. Arm B time is their
  measured total plus output interpolation. Arm A adds matrix interpolation
  and the measured held-out waves/solves/derivatives. Reference time is one
  fresh 19-frequency production evaluation and derivative at that curve.
- Use the saved update coordinates: slider M11 and M67 for hook, spectral
  M37 for peanut. Their preparation is B6, outside per-curve physics, and is
  excluded equally from every timing. Normal-velocity weights are fixed.
- Record both worst held-out per-frequency column relative error and the
  benchmark's observed-normalized stacked column error. Passing requires
  the benchmark criterion; the per-frequency quantity shows local failures.
- Input correction: H3 `fixed_M67.json` actually stores K136/Ku128, not the
  plan's K192. It carries the last accepted M55 geometry through storage
  promotions; M61 and M67 accept no new step. Use that exact saved final
  state, without refitting or changing its resolution. Peanut is K192/Ku128.
- The historical 07:00 deadline was removed by the current user request.
  No inverse fits, production changes or extra curves are authorized here.

After the main table, a failing arm is interpreted from these same saved
outputs: error versus frequency and neighboring-frequency response changes.
No additional frequency solves are needed for that continuation.
