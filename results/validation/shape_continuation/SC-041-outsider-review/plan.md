# SC-041 outsider review — frozen plan for the kite data-loss probe

2026-09-26. Written and committed before any field evaluation below.
Reviewer: Claude (outside the Codex/SC-041 authorship). Geometry survey
(`kite_feature_survey.py`) already run; it motivates this probe.

**Observation motivating the probe.** Every kite reconstruction that reaches
RMS < 0.6 mm (SC-037, SC-038, SC-040, SC-041) has its sharpest point on the
flank at about (-0.83, 0.30), 5 mm from the nearest true tip, where the true
radius is about 18 mm. At SC-041 M=22 its radius is 0.082 mm and it carries the
Hausdorff error. The feature first appears when the curve band is released
K=20 → 192. The true kite has Fourier band K=8.

**Question.** Does the SC-041 kite data (all 19 frequencies, the frozen
M=22 stage objective at 768 nodes) demand this feature?

**Evaluations (no fitting, no tolerance or setting changes).** Loss from the
unchanged SC-041 `setup('kite', 22)` objective, production path, for:

1. the truth curve (K=8, zero-padded as needed);
2. the SC-041 kite M=22 endpoint (control: must reproduce 2.7111400e-9);
3. that endpoint low-passed to |n| <= K for K in {8, 16, 32, 64};
4. the coefficient-space midpoint of endpoint and truth.

Plus the 1536-node refined loss for truth and the M=22 endpoint. Geometry per
curve: minimum radius, RMS (repository `symmetric_rms_distance`) and Hausdorff.
Truth is used only for this post-hoc scoring, as in SC-041.

**Decision rules, fixed now.**

- If loss(truth) <= 0.1 x loss(M=22 endpoint): the data do not require the
  feature; the kite stop is far from a data-consistent solution, and the
  feature is a path/representation artefact.
- If some low-pass K both removes the feature (minimum radius >= 1 mm) and
  has loss <= loss(M=22 endpoint): a spectral cap is a candidate lever for a
  later frozen inverse experiment (not run here).
- If neither holds: the feature is supported by the discretized data at this
  resolution, pointing at the forward model or observation design.

A control mismatch in item 2 above 1e-10 relative invalidates the probe.
Budget: at most 12 production evaluations.
