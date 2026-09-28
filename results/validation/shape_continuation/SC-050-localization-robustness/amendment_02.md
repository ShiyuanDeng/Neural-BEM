# Transfer initial-domain preflight amendment — before any transfer fit

The corrected localization precheck exposed another fixture setup issue:
five proposed 65 mm starting circles enclose a known source or receiver.
The original and opposite-side C starts are valid. No transfer reconstruction
has run. All target shapes, observations and noise draws remain unchanged.

Apply one target-independent rule: retain every original center whose circle
has strictly positive analytic source/receiver clearance; for an invalid circle,
keep its radial direction from the fixed physical scene origin (0.5,0.5), but
set that offset's length to 0.20 m. This puts radius-65 mm circles inside the
acquisition ring with at least 35 mm clearance. Radius stays 65 mm. This rule
uses only known acquisition coordinates, the scene coordinate origin and the
requested starts; it does not use target geometry, fitting loss or any transfer
outcome. It also preserves the original C development and opposite-side starts.

`amend_initials.py` records old/new starts and exact clearances. Original sealed
initial.json files and the preceding manifest are retained in `pre_amendment/`.
The source archive chain records this script and note; input hashes explicitly
record the replacements. No solver, strategy, selection rule, budget, target,
observation, development result or selected policy changes. The corrected starts
are still spatially separated from their targets, checked only in post-run
geometric evaluation. Results refer to these feasible starts, not the invalid
requested positions. This is a disclosed setup correction, not a failed-scene
replacement chosen after observing reconstruction quality.
