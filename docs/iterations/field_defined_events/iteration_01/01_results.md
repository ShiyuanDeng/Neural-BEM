# FDE-001 results — P0 FAILED; a corrected diagnostic located the real bottleneck

**P0 is false.** The median cancellation ratio `|sum g| / sum|g|` over
split-corridor regions is **0.8446**, not below 0.2: the signed sum retains 84%
of the available magnitude. Only **10.1%** of 1,332 corridor regions fall below
P0's threshold. The size prediction fails in the **opposite direction** to
AbsGS's mechanism — Spearman(component pixels, ratio) = **+0.132**, so larger
components cancel *less* and are admitted *more*. **M1 is closed as a negative
result.** (This measurement is on the TD fields directly and is unaffected by
the correction below.)

**Correction — an earlier version of this file was wrong.** It claimed the
polar-angle gauge rejects 52.2% of split attempts and that 2 of 3 completed
failing scenes could construct *no* split candidate. That came from a harness
that transcribed the corridor construction by hand and tested only the
contour-fit variant. `submit_mask` builds **two** variants per split mask
(`topology_controller.py:440-444`): a moment-matched **circle seed** that never
calls the polar-angle fit, and a contour fit that can fail. Counting a failed
contour fit as a dead corridor was a transcription error. Re-measured by
instrumenting the **production** `generate_topology_candidates` instead, the
real numbers are below, and the earlier claim is withdrawn.

## 1. Where split candidates actually die — three stages, measured on production code

Instrumented over the same 22 events (counters monkeypatched onto the module's
own globals; no production code changed):

| Stage | Measurement |
|---|---|
| Split candidates **selected** | **325** across 22 events (vs 432 birth, 44 merge, 41 death) |
| Contour-fit variant | **99 OK / 420 attempts — 321 fail (76.4%)**, every one the polar-angle gauge |
| Circle-seed variant | 1,098 OK, **0 failures** |
| Split candidates that can be **evaluated** at `far-two-stars` | **0 of 11, 0 of 14, 0 of 4** |
| Why | `MultiComponentTopologyError: components 't900.split1' and 't900.split2' intersect or touch.` |

So splits *are* proposed, in quantity. The failure is a two-stage collapse:

**Stage 1 — the accurate variant is unavailable.** The contour fit fails 76.4%
of the time, always with *"No gauge-fixed polar-angle contour represents this
mask"* (`:390`). A corridor cut through a star yields lobed pieces; probing 461
rejected pieces across two scenes, **375 (81.3%) are not star-shaped about their
centroid**, and **0 of 461** survive an ungauged fit, because
`fit_cartesian_fourier_curve_state` (`curve_updates.py:1032`) is *itself* a
polar-angle projection — it raises `Contour is not single-valued in polar angle
about the requested centre.` **Both charts are polar-angle parameterizations**,
so this is a representation limit, not a tolerance to loosen.

**Stage 2 — the fallback is geometrically invalid.** With the contour fit gone,
the only surviving split variant is a pair of moment-matched circles of radius
`sqrt(area/pi)`. Two equal-area circles replacing two halves of a cut blob
**intersect across the cut**, so the candidate cannot be evaluated at all. At
`far-two-stars` this removes every split candidate at every event — which is why
the earlier (wrongly-attributed) claim still matched the observed symptom.

**Stage 3 — the config knob exists, and fixing it is not enough.**
`split_seed_radius_factors` (`topology_controller.py:145`) defaults to `(1.,)`
and the TOP-025 spec leaves it there. Measured across **all 22 events** with a
config-only change to `(1., 0.7, 0.5)` — no code touched:

| Arm | splits proposed | evaluable | unscorable | events losing *every* split |
|---|---|---|---|---|
| baseline `(1.,)` — as shipped | 325 | **87 (26.8%)** | 238 (73.2%) | **9 of 22** |
| shrunk `(1., .7, .5)` | 765 | 436 (57.0%) | 329 (43.0%) | **0 of 22** |
| **raw winner changed** | | | | **0 of 22** |

So under the shipped configuration **73.2% of all split candidates cannot be
evaluated at all**, and at 9 of 22 events *every* split candidate is lost before
scoring. Shrinking the seed eliminates that failure completely — and changes no
raw winner anywhere. At `far-two-stars` cycle 0 the best split scores **0.839**
against `J_before = 0.580`: the split is worse than doing nothing, because two
circles are a poor model of two stars. **Stage 1 is the binding constraint** —
by removing the accurate representation, not by blocking construction as the
withdrawn claim asserted.

**Caveat on ranking.** The "raw winner" above is the best *unrefined* candidate
objective. The controller refines a shortlist before deciding, and in **3 of 22**
events the accepted event is not the raw-best kind — `central-ellipse-star` c0
accepted a split while birth was raw-best (and reached J = 0.0853 against the
raw birth's 0.417), `central-ellipse-star` c2 and `mixed` c1 likewise. So raw
rank under-states what refinement can recover, and "no raw winner changed" is
weaker than "no decision would change". A decision-level claim would need the
refinement stage re-run, which was not done.

An earlier version of this section said the accepted event is the raw-best
available "every time". That holds at the three `far-two-stars` events (rank 0
of 21, 18, 15) but **not** in general, per the 3 counterexamples above. Scoped
accordingly.

## 2. P0 — cancellation diagnostic

1,734 regions over 22 rebuilt pre-event workspaces, covering every family the
controller scores.

**Scope caveat.** This region enumeration is transcribed from the source, the
same harness class that produced the withdrawn claim. The transcription error
there was in *attribution* (which downstream variant a corridor reaches), not in
region geometry, and the statistics below depend only on the region shapes and
the TD field — the sign-pure control measuring exactly 1.0000 checks that. But
the absolute region **counts** here are the harness's, not production's, and
should not be compared against the production candidate counts in §1.

| family | regions | median ratio | frac < 0.2 | frac < 0.5 | gated on `score<0` |
|---|---|---|---|---|---|
| `birth_threshold` | 171 | 1.0000 | 0.000 | 0.000 | no |
| `interior_td_threshold` | 120 | 1.0000 | 0.000 | 0.000 | no |
| `death_component` | 41 | 0.6796 | 0.171 | 0.366 | no |
| `interior_td_corridor` (`:527`) | 1332 | 0.8446 | 0.101 | 0.276 | **yes** |
| `exterior_td_bridge` (`:556`) | 70 | 0.5308 | 0.229 | 0.486 | **yes** |

The two threshold families measure **exactly 1.0000** — sign-pure by
construction. That is the harness control: the statistic measures what it
claims before the negative result is read.

Cancellation against component size, corridors only — the prediction inverted:

| parent component | regions | median ratio | admitted |
|---|---|---|---|
| 0–300 px | 324 | 0.6876 | 47.5% |
| 300–600 px | 648 | 0.8470 | 60.2% |
| 1000+ px | 360 | 0.9398 | 95.3% |

What the gate rejects: 407 corridors (30.6%) and 29 bridges (41.4%) are
rejected while containing *some* favourable mass, but only **17** corridors and
**3** bridges carry more favourable mass than the median *admitted* region. 12
of those 17 lie in failing scenes. That is the whole residual case for M1, and
against the gauge's 751 it is not the lever.

Accepted events by construction, all 12 scenes: `exterior_td_region` (birth) 14,
`leave_one_component_out` (death) 5, `interior_td_corridor` (split) 3,
`exterior_td_bridge` (merge) 2.

## 3. P3 — topological optimality diagnostic at the terminal state

Convention: a negative addition TD means adding material helps, a negative
removal TD means removing helps, so Amstutz–Andrä local optimality is `g >= 0`
a.e. for `g` = addition on the void, removal on the material. `theta` is the L2
angle to a ±1 design indicator — a surrogate, since our geometry is an explicit
chart and not a level-set function, exactly as the proposal's risk section
flagged.

| scene | recovered | M | terminal loss | theta (deg) | violation frac | violation mass | relative mass |
|---|---|---|---|---|---|---|---|
| repeated-birth | yes | 3 | 0.000000 | 100.18 | 0.4727 | 4.587e-07 | 0.4397 |
| death | yes | 2 | 0.000000 | 113.25 | 0.4518 | 1.411e-07 | 0.3929 |
| split | yes | 2 | 0.000000 | 98.94 | 0.4169 | 1.936e-06 | 0.4109 |
| merge | yes | 1 | 0.000000 | 100.99 | 0.4013 | 1.437e-04 | 0.3217 |
| mixed | yes | 2 | 0.000000 | 99.46 | 0.4184 | 1.183e-05 | 0.3602 |
| far-two-circles | yes | 2 | 0.000000 | 107.52 | 0.4617 | 3.631e-06 | 0.4333 |
| central-ellipse-star | yes | 2 | 0.000123 | 87.43 | 0.5161 | 0.04549 | 0.5695 |
| far-two-stars | no | 2 | 0.000092 | 87.03 | 0.6228 | 0.04411 | **0.7621** |
| far-ellipse-star | no | 3 | 0.002082 | 96.53 | 0.5108 | 0.2181 | 0.4849 |
| empty-ellipse-star | no | 3 | 0.002082 | 96.53 | 0.5108 | 0.2181 | 0.4849 |
| far-three-shapes | no | 7 | 0.007840 | 86.32 | 0.5604 | 0.2853 | 0.6213 |
| enclosing-ellipse-star | no | 7 | 0.270288 | 72.95 | 0.5451 | 1.848 | 0.5618 |

`far-ellipse-star` and `empty-ellipse-star` agreeing to 4 s.f. is **not a bug**:
same truth (ellipse + star), byte-identical observations, and the two runs
converged from different starts (one circle, one empty) to the same
3-component terminal geometry; losses differ in the 8th digit (0.0020818110 vs
0.0020818122). Counted as one independent point below.

- **`theta` is dead as a trigger.** Pass [87.43, 113.3] and fail [72.95, 96.53]
  overlap heavily, and Spearman(theta, terminal loss) = **−0.8392** — inverted.
- **`violation_mass` is dead, decisively.** Spearman(violation mass, terminal
  loss) = **+1.0000** across all 12 scenes. It restates the residual and carries
  no independent information.
- **`relative_mass` partially survives.** Scale-free, Spearman with terminal
  loss **+0.6364**; best threshold 0.4849 misclassifies **1/12**
  (`central-ellipse-star`, passing at 0.5695). **This is an in-sample threshold
  fitted on the same 12 points, not a validated classifier** — with n=12 and one
  free parameter it is suggestive only.

## 4. Contrast exposure — M2/M3 are BLOCKED

**No.** The contrast enters as a global material property of the forward
problem: `radial_topology.py:443-444` takes `k_exterior` / `k_interior` from
`exterior.wavenumber(...)` / `interior.wavenumber(...)`, with no per-component
material. A per-component presence factor `tau` would require changing the
forward problem's material model — invasive, and out of scope for a side quest.
**The proposal's central "opacity := contrast factor" construction is not
reachable without that change.** Reported as instructed; no plumbing built.

## 5. P5 — the analytic Jacobian, and an accounting discrepancy

One full Jacobian on the terminal `split` state (2 components, 12 parameters,
48 residual rows), fast profile, resolved `analytic`:

| Quantity | Value |
|---|---|
| Wall time | **0.67 s** |
| `analytic_base_frequency_solve_count` | 1 |
| `factorization_count` | 1 |
| `tangent_solve_count` | 12 |
| `derivative_assembly_count` | 12 |

**P5 holds in the sense the proposal needs:** a post-event gradient is one
factorization plus one tangent solve per direction, sub-second at this size —
not `2 x directions` full forward solves.

**But the accounting unit disagrees with the cost model.** For 12 directions
`jacobian_work_bound` returns **25** for analytic against **24** for FD —
nominally *worse* — while the measured work is one factorization reused across
12 tangent solves. The bound charges a tangent solve at the same rate as a full
forward solve. No claim here depends on it, but anyone using
`jacobian_work_bound` as a cost proxy rather than a charge unit will mis-rank
the two paths. Flagged for the speed-up track; not this side quest's to fix.

## 6. Correction to an earlier reading

An earlier pass counted `enclosing-ellipse-star` and `far-three-shapes` as
having fired **zero** topology events and took that as a triggering failure.
Wrong. Both are `HARD_STOP` (2,362 and 2,862 completed solves) — truncated on
budget before closeout, so they never wrote `events.json`, though their
trajectories contain `BIRTH` and `SPLIT` frames. So of the five recovery
failures, **two are budget exhaustion** (which the SPD-002 analytic default
bears on directly, no new mechanism needed) and **three completed without
recovering**. All per-event analysis above covers the three completed failures.

## 7. Summary

| Quantity | Value |
|---|---|
| Events analysed | 22, over 10 scenes of TOP-025 |
| Workspaces rebuilt | 34 (22 pre-event, 12 terminal) |
| Candidate regions scored | 1,734 |
| **Split candidates selected by production code** | **325** (birth 432, merge 44, death 41) |
| **Contour-fit variant** | **99 OK / 420 — 321 fail (76.4%)**, all polar-angle gauge |
| Circle-seed variant | 1,098 OK, 0 failures |
| **Split candidates evaluable at far-two-stars** | **0 / 11, 0 / 14, 0 / 4** (seeds intersect) |
| Gauge-rejected *pieces* probed (2 scenes) | 461 |
| Of those, not star-shaped about the centroid | **375 (81.3%)** |
| Of those, representable by an ungauged fit | **0 / 461** |
| **Split candidates unevaluable, shipped config** | **238 / 325 (73.2%)** |
| **Events losing every split candidate, shipped config** | **9 / 22** |
| Shrinking `split_seed_radius_factors` to (1, .7, .5) | evaluable 26.8% -> 57.0%; events losing all splits 9 -> **0**; raw winners changed **0 / 22** |
| Accepted event differs from raw-best kind | 3 / 22 (refinement matters; raw rank under-states) |
| P0 — median corridor cancellation ratio | 0.8446 (predicted < 0.2) |
| P0 — corridor regions with ratio < 0.2 | 134 / 1332 (10.1%) |
| P0 — Spearman(component size, ratio) | **+0.132** (predicted negative) |
| P0 verdict | **FAILED** |
| P1 — negative-part rescoring | **not run**; its stated gate (P0) failed |
| P2 — state-preserving split | **blocked**; per-component contrast not exposed (§4) |
| P3 — theta separation | overlapping; Spearman(theta, loss) −0.8392 — **failed** |
| P3 — violation mass vs terminal loss | Spearman **+1.0000** — **failed** |
| P3 — relative mass, best in-sample threshold | 0.4849, 1/12 misclassified — **suggestive only** |
| P5 — one analytic Jacobian, 12 directions | 1 factorization + 12 tangent solves, 0.67 s — **holds** |
| Runtime profile / resolved jacobian mode | fast / **analytic**, asserted every arm |
| Production code modified | **none** |
| pytest | not run — nothing was changed, so nothing can regress |
| Withdrawn claim | "gauge rejects 52.2% of split attempts; 2 of 3 failing scenes construct no split" — harness transcription error, see the correction at the top |

## 8. Recommendation

**Close M1, the theta trigger, and M2/M3 as proposed.** Each was specific and
falsifiable; M1 and theta are false on this evidence, M2/M3 are unreachable
without a forward-problem change.

**Two defects were found, and they are not the ones the proposal predicted.**

1. *Config-level, cheap, real.* `split_seed_radius_factors` defaults to `(1.,)`,
   so the only surviving split variant is a pair of equal-area circles that
   intersect across the cut and cannot be evaluated. At `far-two-stars` this
   silently removes **every** split candidate at **every** event. A one-line
   config change makes them evaluable. It changes no decision here, but a
   candidate class that is silently unevaluable is worth fixing on its own
   terms, and the failure is invisible in the logs.
2. *Representational, and the binding one.* The contour fit — the only variant
   that can express a lobed split child — fails 76.4% of the time because both
   available charts are polar-angle parameterizations and 81.3% of split pieces
   are not star-shaped about their centroid. Dropping the gauge check is not an
   option: 0 of 461 rejected pieces survive an ungauged fit. Expressing these
   children needs a representation admitting arbitrary closed curves
   (arc-length or elliptic Fourier descriptors). That is the topology track's
   own research question, not a side quest's to answer.

This also retires the proposal's opening idea. Min-cut, geodesic and watershed
constructions would not have helped: a curved cut yields pieces at least as
lobed as a straight one, meeting the same wall. The template grid was never the
binding constraint.

If the 3DGS angle is to be pursued, the decision to put to the boss is narrow:
whether a per-component material factor is worth adding to the forward problem.
That is the gate for M2/M3, it is a real engineering commitment, and nothing
measured here argues it would pay off before the representation limit is
addressed.

## 9. Method note

The first pass of this work transcribed the corridor construction into a
standalone harness and drew a confident, wrong conclusion from it. The error was
caught by re-deriving the same numbers through the production
`generate_topology_candidates` with monkeypatched counters. Any future probe of
this controller should instrument the real function rather than reimplement its
inner loops: the two candidate variants per mask are exactly the kind of detail
a transcription drops.
