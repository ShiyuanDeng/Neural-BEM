# CI-001 implementation checks

2026-09-30. **61 tests passed; zero failures, errors or skips** on the final
focused run with CUDA available (NVIDIA GeForce RTX 5090, PyTorch 2.8.0+cu128).
Elapsed pytest time: 19.80 seconds. No full benchmark inverse, new benchmark
observation catalog, or complete SPD D pair was run.

Evidence: [final test receipt](tests.xml), [source hashes and command](verification.json).
The initial final-suite attempt found an unnecessary mandatory `threadpoolctl`
dependency in environment reporting (60 passed, one failed). That receipt is
retained in [tests_initial.xml](tests_initial.xml). Reporting now records the
configured BLAS environment when optional runtime introspection is unavailable;
the full focused suite was rerun successfully.

The checks establish:

- The inventory has 36 configurations and preserves original real-data/start
  references: 20 existing damped catalogs and 16 missing catalogs.
- All 12 noiseless stage definitions and optimizer settings equal the archived
  MA-004 configuration. The projected trial and its derivative equal the
  extracted SC-035 implementation; cleanup is the same centred crop/pad.
- CPU real/damped predictions equal the reference, complete-trial finite
  differences agree with the derivative, and backend injection preserves a
  bounded LM path and work bit for bit.
- A non-nodal opaque test state can drive the optimizer without hidden nodal
  calls. Missing observations and unsupported solver/material/device
  capabilities are explicit errors.
- SPD-016 CPU/GPU Mie-grid values/masks/ordering agree, damped CUDA predictions
  and derivatives agree at contrasts 0.5, 4 and 13.3, and reusable LU state
  is offloaded to host. Ray-envelope and OOM automatic/strict paths are checked.
- A small independent disk test traverses the actual runner from its initial
  curve through localization, fitting, cleanup, frontier, checkpoints and
  independent audit. It is an interface smoke test, not one of the 36 cases.
- Existing LM, real CUDA, frequency threading, geometry-runtime and CUDA
  assembly regressions pass alongside the new checks.
- Preparation freezes source/input hashes and comparison criteria, refuses
  unsealed missing damped data, and reports all 36 pending cases without a
  retention claim. Both archived SPD pair comparison parsers also pass
  identity checks on their own saved evidence.

The new noise whitening/discrepancy/recurrent-cleanup rules are explicitly
versioned policy changes, not numerically qualified reconstruction improvements.
Native modal Müller is still the subsequent backend integration; the current
selection fails preflight clearly. Historical hash manifests remain immutable;
the CI-001 campaign creates new snapshots for the modified shared sources.

Run instructions and the frozen numerical/runtime comparison conditions are
in the [package guide](../../../../experiments/cleaned_interface/README.md).
The three requirements remain acceptance gates: implementation checks alone
do not establish all-36 recovery retention or matched runtime retention.
