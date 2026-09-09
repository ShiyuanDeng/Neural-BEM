# Proposal 01 — full topology treatment for the explicit Fourier inverse

**Project:** radial-Fourier topology  
**Iteration:** 02  
**Status:** proposal, not yet the agreed `03_plan.md`  
**Baseline:** iteration 01 closed with a full G0–G5 pass and a working one-component TD birth path.

## Verdict

Iteration 02 should stop treating topology as a special one-off birth experiment and make it a first-class part of the inverse loop.

The expected end state is one automatic controller that can run

\[
\boxed{
\text{fixed-topology Fourier refinement}
\;\longrightarrow\;
\text{topology reconsideration}
\;\longrightarrow\;
\text{birth / death / split / merge}
\;\longrightarrow\;
\text{restart refinement}
}
\]

repeatedly, with no target object count and no predeclared event type.

For this project, **full topology treatment** means topology of separated/connected material components:

- component birth;
- repeated births, hence unknown `M > 2`;
- component death;
- one component splitting into several;
- several components merging into one;
- automatic triggering and restart of the fixed-topology optimizer.

Nested holes remain a different forward-model problem because the current Kress path assumes disjoint, non-nested inclusions. Do not hold up birth/death/split/merge waiting for a nested-domain BIE extension.

---

# 1. Start from what already works

Iteration 01 established all of the expensive foundations:

- `MultiRadialFourierState` is an immutable variable-component geometry state;
- direct one-/multi-component Kress objective evaluation works without SDF extraction;
- current-domain topological derivative evaluation is implemented and numerically qualified;
- the TD raster and connected-region machinery already produce a useful component centre/scale;
- a finite birth is scored by the actual Kress objective rather than accepted from an asymptotic indicator alone;
- the multi-radial central-FD LM optimizer can refine the new topology;
- persistent component IDs and exact rollback already exist.

So iteration 02 should be mostly **control logic and topology proposal construction**, not another solver rewrite.

The iteration-01 result already demonstrates the basic literature pattern:

```text
wrong fixed topology
    -> smooth parametric optimization stalls
    -> current-domain topological sensitivity
    -> topology event
    -> restart smooth optimization
```

The next step is to generalize that pattern instead of adding another bespoke driver.

---

# 2. The main new object: a topology controller

Add one high-level controller around the current multi-radial optimizer, conceptually:

```text
TopologyAwareFourierInverse

state:
    current explicit component state
    optimizer state for the current topology
    topology-event history / lineage

loop:
    if initial geometry is empty:
        request topology immediately
    else:
        run fixed-topology optimizer to its ordinary stationary/stall condition

    if residual/objective is already satisfactory:
        finish

    construct topology proposal field
    generate all plausible topology events
    score finite candidate geometries with the real Kress objective

    if no topology event improves the state:
        finish as topology_stationary

    accept the best event
    rebuild component parameterization / IDs
    restart the fixed-topology optimizer
    repeat
```

The controller should not know in advance whether the next event is a birth, split, merge or deletion.

It should also not run the topological derivative at every LM iteration. The mature hybrid pattern is still the right one: let the smooth optimizer do what it can first, then ask whether the topology is wrong.

The existing optimizer stop reasons (`loss_change_tolerance`, gradient/step stationarity, exhausted useful progress, etc.) are enough to define the first automatic trigger. A more elaborate stall detector is optional; it should not become the centre of iteration 02.

---

# 3. Use one temporary topology workspace for every event

The cleanest way to avoid four unrelated topology heuristics is to introduce a **temporary implicit/raster topology workspace**.

This workspace is not the canonical reconstruction. The canonical reconstruction remains explicit Fourier components.

At a topology event:

1. rasterize the current material union onto the existing interior inspection grid;
2. evaluate a material-addition sensitivity in the exterior;
3. evaluate a material-removal sensitivity in the current interior;
4. threshold / rank favourable add and remove regions;
5. form candidate modified binary material masks;
6. classify the change in connected components;
7. extract smooth component boundaries from the candidate mask;
8. convert them back to explicit Fourier component states;
9. score the candidate with the actual Kress objective;
10. discard the raster and continue in explicit geometry.

Conceptually, for current material indicator \(\chi\), a topology proposal creates

\[
\chi'
=
(\chi \cup A_{+})\setminus A_{-},
\]

where \(A_{+}\) contains favourable material-addition regions and \(A_{-}\) favourable material-removal regions.

Connected-component analysis of \(\chi'\) automatically tells us what happened.

This is the key architectural proposal for iteration 02.

---

# 4. Two complementary topological sensitivities

## 4.1 Exterior material addition

Keep the already implemented current-domain TD used in iteration 01:

\[
D_T^{+}J(z;\Omega)
\]

for replacing exterior material by inclusion material at exterior point \(z\).

It drives:

- birth of a disconnected component;
- material bridges that can merge existing components.

The existing field-product implementation and source/reciprocal batching should be reused unchanged where possible.

## 4.2 Interior material removal

Add the complementary sensitivity

\[
D_T^{-}J(z;\Omega)
\]

for replacing a small region of the current inclusion material by the exterior material.

For the present scalar nonmagnetic TMz transmission model, its local structure should mirror the already validated insertion derivative, with the local material contrast reversed and with the **current interior forward/adjoint fields** at the probe point.

The exact project-convention expression should be derived once from the same objective and Kress conventions; this should not become another research cycle. Add whatever interior field-evaluation helper is needed to the current multi-component Kress solution.

It drives:

- removal of spurious material;
- deletion of an entire component;
- cutting a neck to split one component.

Do not commit isolated interior removal regions that would create nested holes in iteration 02. If a favourable removal patch is fully enclosed and creates a hole, record it as `unsupported_nested_hole` and continue considering the other event candidates.

---

# 5. Event classification should emerge from connectivity

The controller should classify candidate material masks by comparing current and proposed connected components.

## Birth

```text
old component set: M
candidate mask: one new disconnected material island
new component set: M + 1
```

Use the current iteration-01 birth logic as the seed mechanism:

- connected favourable exterior TD region;
- region centroid;
- equivalent-area scale;
- small finite size/radius proposal search;
- actual objective decides the finite birth.

Do not stop at one birth. After refinement stalls again, the same controller can add another component.

## Death

```text
old component set: M
candidate mask: one existing component removed
new component set: M - 1
```

There are two cheap sources of death proposals:

1. interior removal sensitivity strongly supports erasing a component;
2. direct leave-one-component-out scoring of the current `MultiRadialFourierState`.

The latter is especially attractive because the state already has persistent IDs and the real objective is cheap enough at the current small `M`.

A component should be deleted atomically; do not make the optimizer shrink it through arbitrarily tiny radii before allowing death.

## Split

```text
old: one component C_i
candidate removal mask cuts C_i into C_i,a and C_i,b (or more)
new: component count increases, but no disconnected exterior birth was added
```

This is where the interior removal TD matters most.

If a favourable removal corridor crosses a narrow neck and the proposed material mask changes one connected component into two, treat this as a split proposal:

\[
C_i \longrightarrow \{C_{i,a},C_{i,b}\}.
\]

Extract each child boundary, fit an explicit Fourier state to each, retire the parent ID, and record lineage such as

```text
parent: C_i
children: C_i.s1, C_i.s2
```

Then evaluate the complete new multi-component state with Kress and, if accepted, restart the optimizer.

Do not try to drive a radial component through the singular pinch itself. The event is deliberately discrete.

## Merge

```text
old: two or more components
candidate addition mask connects them
new: one connected component replaces them
```

A favourable exterior TD bridge between two components should be allowed to propose

\[
\{C_i,C_j\}\longrightarrow C_{ij}.
\]

Construct the union plus proposed bridge in the topology workspace, extract its **single outer contour**, remove the two old components, and fit one explicit component state to the merged contour.

This avoids asking the multi-Kress solver to march two components all the way to contact; the close-component configuration is replaced by a single boundary before the next forward solve.

Record parent lineage on the merged component.

---

# 6. Do not let the radial chart block topology

The topology logic should operate on **components**, not on the assumption that every future component will always be representable by one positive radial graph.

The preferred implementation is:

```text
ExplicitComponentState protocol
    -> current RadialFourierCurveState as the default implementation
    -> optional Cartesian/periodic Fourier state when a topology event produces
       a valid smooth closed curve that is not radial about a useful centre
```

For circles, ellipses and ordinary lobes, continue using `RadialFourierCurveState` and the current fast optimizer.

For a split/merge contour that fails the radial projection but is otherwise a perfectly valid smooth simple component, **do not reject the topology event solely because of the radial chart**. Promote that component to a periodic Cartesian Fourier representation using the same Fourier/Method-B machinery already present in the repository.

The fixed-topology optimizer should therefore be generalized one level upward: optimize a collection of explicit component states through a common parameter-vector/rebuild interface, with direct Kress as the evaluator.

This also aligns with the broader direction already visible in the repository: the useful physics state is a smooth explicit periodic boundary; radial Fourier is one convenient chart, not a topological law.

If this representation generalization is judged too invasive for the first implementation pass, support split/merge for radially admissible event contours first, but structure the controller so a Cartesian Fourier component can be added without redesigning the topology logic.

---

# 7. Candidate generation and acceptance

Topology sensitivity should propose and rank events; the actual forward objective should still decide them.

At each topology reconsideration:

```text
compute add/remove sensitivity fields
    -> identify candidate regions / bridges / cuts / removable components
    -> construct a small candidate set
    -> convert each to explicit component state
    -> run actual Kress objective
    -> accept the best improving event
```

Important expectations:

- compare multiple event types in the same topology pass;
- do not accept the first merely feasible event;
- one topology event at a time is sufficient — repeated controller cycles give arbitrary changes in object count without combinatorial batch search;
- preserve the iteration-01 production/refined acceptance idea, but do not build another elaborate gate hierarchy around every event;
- after acceptance, all optimizer/Jacobian/damping state is restarted because the parameterization or dimension may have changed.

For noisy data later, the event acceptance rule can include a discrepancy principle or small complexity penalty. For the current synthetic development path, strict real-objective improvement plus a meaningful numerical margin is enough.

---

# 8. Expected automatic inverse behaviour

The goal is that the user-facing algorithm looks like this, not like a collection of test-specific scripts:

```text
input:
    data
    initial explicit geometry (possibly empty, wrong count, wrong shapes)

if empty:
    topology pass

repeat:
    optimize current explicit components until stationary

    if fit is satisfactory:
        stop recovered

    topology pass:
        D_plus outside
        D_minus inside
        generate birth/death/split/merge candidates
        evaluate real objective

    if no event improves:
        stop topology_stationary

    accept best event
    restart explicit optimizer
```

The code should support trajectories such as

```text
0 -> 1 -> 2 -> 3 components
3 -> 2 components
1 -> split -> 2
2 -> merge -> 1
1 -> birth -> 2 -> delete -> 1 -> birth -> 2
```

without the driver being told which event is expected next.

---

# 9. Demonstrations expected in iteration 02

Do not create a separate research cycle for every event. Implement the controller, then demonstrate the four event classes with a compact suite.

## A. Repeated unknown-count birth

Start with one or zero component and reconstruct a three-component same-material scene.

Expectation:

```text
fixed topology stalls
-> birth
-> refine
-> stalls
-> second birth
-> refine
-> finish
```

No target `M=3` is supplied to the controller.

## B. Death

Start with truth components plus one spurious component.

Expectation: fixed-topology refinement cannot justify it; the topology pass removes it and refinement continues.

## C. Split

Use one connected dumbbell/peanut-like component where the data favour two separated components.

Expectation: smooth refinement narrows/misfits the neck, interior removal sensitivity proposes a cut, the topology workspace produces two child contours, and the optimizer restarts with two components.

## D. Merge

Start from two separated components where the truth is one connected smooth component.

Expectation: exterior addition sensitivity identifies the bridge, the topology workspace replaces both boundaries with one outer contour, and refinement continues as one component.

## E. Mixed automatic case

If A–D work, run one mixed wrong-count/wrong-shape case through the same controller without specifying event types. This is the useful headline demonstration; it is not necessary to invent another gate system around it.

Keep acquisition and material conditions close to the already-qualified iteration-01 regime so iteration 02 measures topology control rather than a new forward-model problem.

---

# 10. Code expectations

Prefer additions around the existing topology module rather than another isolated package.

Conceptual pieces:

```text
sdf_inverse/radial_topology.py
    existing state / TD / birth / optimizer pieces

new or extended:
    topology controller
    interior-field / removal-TD evaluation
    topology workspace / material-mask operations
    event candidate classes:
        BirthEvent
        DeathEvent
        SplitEvent
        MergeEvent
    event-to-explicit-boundary conversion
    component lineage bookkeeping
```

Potentially introduce:

```text
ExplicitComponentState
MultiExplicitFourierState
```

if Cartesian Fourier promotion is implemented.

Reuse:

- `OrderedBoundary2D`;
- multi-component Kress;
- existing automatic multi-component contour extraction / Method B where useful;
- `fit_radial_fourier_curve_state` for topology-event child/merged contours;
- the current direct objective seam;
- current FD/LM numerical policy;
- persistent component IDs and result trajectory infrastructure.

The topology event layer should never duplicate BIE kernels or create a second forward solver.

---

# 11. Literature alignment

This proposal is intentionally closer to the mature hybrid topology literature than a pure geometric surgery algorithm.

The main practice retained from Carpio / Le Louër / Rapún and related topological-sensitivity work is:

- use topological sensitivity to change material topology;
- use smooth explicit/parametric optimization between topology events;
- recompute topology information on the **current** domain after fixed-topology progress is exhausted;
- allow both insertion and removal of material;
- restart parametric refinement after topology changes;
- let the full forward-data objective judge finite changes.

The temporary topology workspace also plays the same role that a level-set representation normally plays in topology-changing methods, but without making a level set or neural field the accepted reconstruction state between events.

That is a good fit to this repository: topology is easiest to reason about implicitly, while Kress and the current inverse are strongest on explicit smooth periodic boundaries.

---

# 12. What not to spend iteration 02 on

Do not slow this cycle down with another long sequence of single-feature qualification iterations.

In particular, do not make these prerequisites for implementing the full controller:

- a new adjoint for radial coefficients;
- noisy-data theory;
- automatic frequency selection;
- multi-material regions;
- nested holes;
- half-space GPR;
- touching-boundary quadrature;
- differentiating through topology transitions;
- perfect tuning of every threshold.

Use the already qualified low-frequency synthetic setting to get the **complete topology state machine** in place first.

Once the controller exists, later cycles can stress it rather than still adding basic event types.

---

# 13. Expected iteration-02 outcome

By the end of this cycle, `run_radial_fourier_topology_inverse.py` or its successor should no longer mean “perform one scripted birth experiment.”

It should mean:

> optimize an explicit Fourier reconstruction with unknown component count, periodically reconsider topology, perform birth/death/split/merge when supported by current-domain sensitivities and the actual Kress objective, restart the smooth optimizer after each accepted event, and stop only when both shape and topology are stationary.

That is the target abstraction.

If that is implemented, the radial/explicit route has a genuine topology mechanism rather than merely a multi-object initialization trick.
