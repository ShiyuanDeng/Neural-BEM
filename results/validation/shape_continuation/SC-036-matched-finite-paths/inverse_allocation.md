# Conditional inverse dispatch allocation

2026-09-25, after the screen passed and before any full inverse dispatch.
The plan's 20,000-unit aggregate ceiling is enforced by reserving 2,400 inverse
units per path for eight paths (19,200), plus 19 evaluation fields each (152).
This is below the 8,012 per-path hard ceiling; exhausted allocations are
reported as budget-limited, never as convergence. Both arms receive the same
allocation. Two workers, each with one BLAS thread, 2,700 seconds per path.
Historical normal paths used 139–651 units. Timings are concurrent, not a
speedup claim. The driver and numerical sources are hashed in the manifest.
