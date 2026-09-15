# BIE-004 — preserved pre-physics test failure

The first attempt stopped before any physical system assembly, derivative,
factorization or RHS solve. Three algebra tests passed; one negative input test
failed because it supplied a position direction without the mandatory matching
first-derivative array. The existing `KressDirection` constructor correctly
rejected it before the intended component-grid-size check.

The single bounded correction supplied both malformed-size jet arrays. No
numerical formula, tolerance, case or scientific intervention changed.
[The continuation](../BIE-004-20260915-coupled-02/README.md) retains the global
budgets and charges this attempt's 1.88 seconds. Original tests, failure log,
manifest, command, frozen plan and source snapshot remain in this directory.
