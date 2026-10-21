# Decisions and implementation details for geometry updates

These concerns about [the plan](03_plan.md) were recorded on 2026-10-20 and
classified after discussion. The original item IDs are retained so they can be
discussed one at a time. Original code line references use commit `4084457e3`.

## Decisions resolved on 2026-10-21

1. **Preparation scope — A1 and D1: delivered.** Each method owns preparation,
   measurements, metrics and its local stored-data record in its own file.
   Flat classes replace the nested update hierarchy; no shared `Prepared`
   interface was introduced. Duplication is acceptable for readability now.
2. **Delivery scope — B: delivered.** Move every retained method now, including
   optional certificates, similarity and the original Borges interface.
   Old paths retain compatibility exports instead of a second implementation.

The user chose these options after discussing which quantities depend only on
curves and which depend on update coordinates. Ordinary curve functions stay
in `continuation/geometry.py`; deduplicating method logic is deferred.

The active spectral method uses direct area, speed and intersection checks,
retains batched preparation, and does not run certificates. The certificate
method and its mathematics remain available separately for explicit selection.

These decisions supersede the earlier alternatives below. Technical observations
and old line references describe commit `4084457e3` unless marked **DELIVERED**.
Implementation verification is recorded separately; this document adds no runs.

**OBVIOUS** means implementation work implied by that structure, not another
decision for the user. **FACT** supplies or corrects context. **OPTIONAL** means
additional cleanup that is not required for the agreed structure.

## A. Gaps in the plan

**A1 — DELIVERED. What `geometry_update()` replaces.** Each method file now
owns its trial entry point, `prepare`, `velocities`, `measure`, `metric`,
`regauge` and local stored-data record, without inheriting another update class.

The earlier smaller option would have moved only the finite trial. The user
chose method-local ownership for all these responsibilities, while retaining
their mathematical behavior and old caller interfaces.

**A2 — OBVIOUS. Preserve diagnostics.** The trial record's `maximum_normal_m`
and `rms_normal_m` come from `update.measure` (`geometry.py:96`). Keep these
values without passing the update object into the mathematical checks.

Adding them in `fit_stage()` is one implementation option. Measure the actual
applied step (`a_used` when supplied), preserve method-specific diagnostics,
and retain useful information from refused trials.

**A3 — OBVIOUS. Preserve work counters.** `geometry_work` in every result file comes from
`update.counts` (`runner.py:412`). The fields are trial count, refusals,
seconds and projection count.

Count calls, refusals, time and projections consistently across all callers.
Counting only in `fit_stage()` would miss endpoint and resolution-check calls.
Choose one owner for each counter to avoid omissions or double counting.

The active spectral method has no certificate time. Removing sampled-test and
projection timings is not required; useful measurements can be retained without
callbacks or timing wrappers inside the mathematical checks.

**A4 — OBVIOUS. Preserve refusal reasons.** Rejected trials record `exc.reason`
(`fit_stage.py:417`). The checks should raise `UpdateRefused` directly with
the existing labels: `irregular_parameterization`, `self_intersection` and
`unresolved_projection`.

Today the final-candidate check raises `ValueError`. `_refusal` then guesses
the label by searching the message text (`continuation/updates.py:29`).

Also handle failures before the explicit checks: constructing sampled nodes
already rejects zero speed and nonpositive area (`ordered_boundary/curve.py:88–99`).
Keep compatibility handling while retained methods still need it.

**A5 — OBVIOUS. Route callers consistently.** These sites also call `update.trial()`:

- `endpoint.py:116`
- `modal_accuracy.py:230`
- `pytest/bem_inverse/test_continuation_policy.py:75`
- `pytest/bem_inverse/refactor_reference.py:186`
- `experiments/trial_curves/`

Live callers must reach the selected geometry implementation. They can call the
new function directly, or an old `trial()` can delegate to that same function;
retaining an interface does not require duplicate numerical code.

Reference captures that explicitly select the old certified method should retain
that meaning. Do not change historical reference data to follow the new default.

**A6 — FACT. Area source is already chosen.** The plan uses coefficient area.
The existing sampled calculation integrates positions crossed with exact curve
derivatives, rather than polygon area (`ordered_boundary/curve.py:95`).

On the current resolved Fourier grids it agrees with coefficient area up to
rounding. Near-zero cases can differ; this does not require a new design choice.

**A7 — FACT CORRECTED. Avoid unnecessary grid construction.** The base grids
are cached lazily on the first trial (`c10_geometry_trial.py:188`). The plan
requires reusable data, not that every cache must be filled during `prepare`.

Some prepared curves meet stopping conditions before another trial
(`fit_stage.py:312–319,529–547`). Eager construction is therefore not necessarily
the same cost. Reuse existing arrays and keep remaining caches lazy.

## B. Method coverage and delivery scope

- **DELIVERED — `analytic_spectral`.** Its own flat class and local data record
  replace the old certified inheritance (`analytic_projection.py:64`). Its
  analytic preparation uses `spectral.geometry_update()` for the same finite map.
- **DELIVERED — `certified_spectral`.** Its own file retains increment/full
  tiers, both orders (`certificate_first`, `sampled_first`) and shadow mode.
  Certificate mathematics lives in `certificates.py`; the active method does
  not depend on it. The old class trial is only a compatibility entry.
- **DELIVERED — `spline`.** Preparation and trial construction now live in
  `geometry_update_methods/spline.py`; the upper `geometry.py` re-exports them.
- **DELIVERED — `gaussian_lipschitz`.** Its preparation, stored data,
  measurements and finite trial now live in `gaussian_lipschitz.py`.
- **DELIVERED — `similarity`.** It has its own method file and selector entry.
  Its coordinates represent translation and scaling, not normal harmonics.
- **DELIVERED — `borges`.** The retained original update API has its own file;
  `continuation/updates.py` contains compatibility exports.

**DELIVERED:** every retained method moved. Old paths and `trial()` remain
compatible, but do not retain separate mathematical implementations.

## C. Names and the default method

**OBVIOUS — consequences of the agreed sampled spectral method.** These are
implementation updates, not a request to reconsider dropping certificates.

- Without the certificate, the active method is the spectral construction with
  sampled checks and batched `prepare` (b6). The existing `spectral` selection
  (`SpectralProjectedUpdate`) is the same construction with a one-at-a-time
  `prepare` (`geometry.py:79`). The two could merge.
- `pipelines.py:56-60`, `AGENTS.md` ("Default method: `modal_muller` +
  `certified_spectral`") and `experiments/benchmark/README.md` name the default.
  Update the intended experiment and pipeline selections to `spectral`.
  Bare `fit()` currently defaults to spline; changing that separate default is
  outside this plan. Preserve historical records with their original names.
- On CUDA, `certified_spectral` currently builds `DeviceCertifiedUpdate`
  (`geometry_selection.py:19`). That class exists to run the certificate on the
  GPU. It belongs with the optional certificate method.
- `validity_order` (`physics.py:38`) and the `validity_first` / `exact_fast`
  policies (`policies.py:124-134`) include certificate-order settings. Those
  settings apply only to the optional certificate method; preserve the policies'
  other behavior. The recorded PS-001 candidate screen was never run.

## D. `geometry.py` and `continuation/updates.py`

**DELIVERED scope.** Both old files now contain compatibility exports. The
user chose to move maintained implementations and retain existing caller APIs.
The table records the resulting ownership, without deleting retained methods.

| Piece | Status | Implemented home |
|---|---|---|
| `UpdateRefused`, refusal conversion | DELIVERED | `errors.py`; old exports retained |
| `LocalSpace`, `ProjectedSpace`, `CertifiedSpace` | DELIVERED D1 | Method-local data records; old exports retained |
| `speed_ratio`, `values`, `resize`, `cleanup` | DELIVERED | `continuation/geometry.py` |
| `BorgesUpdate.regauge/prepare/velocities/measure/metric/trial` | DELIVERED | `geometry_update_methods/borges.py`; retained API |
| `ProjectedUpdate.prepare/velocities/measure/metric` | DELIVERED D1 | `geometry_update_methods/spline.py` |
| `project` + `ProjectedUpdate.trial` | DELIVERED | `geometry_update_methods/spline.py` |

**D1 — RESOLVED: method-local records, shared redesign deferred.**
`velocities`, `measure` and `metric` cannot
be `FourierCurve` properties. They depend on the B6 derivative columns, which
depend on the update method and on M, not only on the curve.

They are one matrix used three ways: the normal move of each node per metre of
each coordinate. The earlier proposal was one shared record, holding
the curve, coordinates, derivative columns and base projections, with
`normal_velocities(nodes)`, `measure(a)` and `mass_metric()` as methods.

`similarity` has its own coordinates and exact coefficient columns. Gaussian
updates also need centres, width and interpolation weights. A common interface
would need to accommodate these differences. The user instead chose local
records and flat classes within each method file; duplication can be addressed
later, after the individual methods are readable.

**D2 — OPTIONAL, separate work. Two routes for the normal velocity.** In the default modal path, B7 never
calls `update.velocities`. It takes the normal part of the derivative columns
on the coefficients (`a_forward.py:312`, `b7_data_jacobian.py:13`).

Node-sampled velocities serve nodal Kress physics (`physics.py:256`), displacement
measurements and the mass metric. Preserve both working routes here; merging
them is not a decision needed for this refactor.

**D3 — FACT CORRECTED. Where the spline refit runs.** `regauge()` uses spline
`reparameterize`, but the main `runner.fit()` starts by resizing coefficients
(`runner.py:94`); it does not universally refit the starting curve with splines.

The separate `run_policy()` calls `regauge()` initially and when reducing the
storage band (`fit_stage.py:590,598`). Preserve that behavior; no starting-curve
change is required by the new geometry-update interface.

## E. Tests and checks that change

**OBVIOUS — focused implementation checks and preservation of earlier evidence.**

- `test_validity_order.py` stays if the certificate method is kept.
- `refactor_reference.py` explicitly selects `BatchedCertifiedUpdate` for its
  certified capture. Keep that reference and its stored records. The control-path
  test in `test_refactor_contract.py` does not require replacing those records.
- `test_refactor_contract.py:21` checks that `certified`, `spectral` and
  `c10_geometry_trial` are the same module. Preserve compatibility exports or
  update the import-layout assertion to the intended structure, without rewriting
  the numerical reference evidence.
- Suggested comparison: new `spectral.geometry_update()` against the old
  certified trial on the reference case and a few larger steps. The constructed
  coefficients should match exactly where both accept if prepared arrays, backend
  and arithmetic order remain identical. Otherwise use the relevant existing
  numerical tolerance; preserve exact zero-step identity in either case.

Keep these checks within the plan's small component scope. This classification
adds no inverse experiments or runtime comparisons.
