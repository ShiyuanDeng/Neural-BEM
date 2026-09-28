# SPD-014 post-qualification review amendment — 2026-09-28

Claude's [review](../../../../docs/iterations/speedup/iteration_11/02_claude_review.md)
identified a real exact-reference defect at zero/sub-roundoff orientation tolerance.
The dense predicate can count remote collinear segment pairs as proper crossings
because of floating-point signs. A geometric broad phase can omit those pairs.
The implementation now falls back to the dense predicate below
`8*eps*longest_segment*bounding_box_diameter`, including nonfinite bounds.

The reviewed implementation and SC-049 are preserved at `b7173758` before this
amendment. Original source archives, manifests, outputs and timings remain
unchanged. Their live-source verification correctly detects this later amendment;
reproduction of old timings requires their archived sources. No timing claim has
been remeasured here. The guard is inactive at the production tolerance in the
review's nonzero-tolerance cases.

Validation: 375 broad regression tests pass; all 783 review fuzz comparisons
now agree with the dense reference. Four regressions cover subdivided {5/2}
and {9/4} stars at zero and tiny positive tolerance; another requires pruning
at production tolerance. The fuzz `pruned` field indicates candidate availability,
not guard dispatch. The review's separate guard check records 261 zero-tolerance
fallbacks and zero fallbacks at its nonzero tolerances.

Scope correction: all 36 original saved geometry-screen counts were zero.
Nonzero crossings/touches were covered by synthetic tests, strengthened by the
review fuzz corpus; they were not demonstrated by those saved reconstructions.

The 2.16x video-preparation benefit requires the SPD-014 wrapper that combines
`cache_diagnostic` with `geometry_acceleration('both')`. Ordinary historical
video commands remain unchanged. See the [usage guide](../../../../experiments/spd014_geometry/README.md)
for the explicit `run video` invocation and fresh-bundle gates.
