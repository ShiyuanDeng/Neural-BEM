# SPD-006 saved-state qualification

PASS: 33 checks across 11 saved states, full gauge directions, four training frequencies, 256/512 nodes, and fresh directional finite differences.

See [qualification.json](qualification.json) for errors, work and source/input hashes. The snapshot contains all 220 recorded sources and every consumed input.

Maximum prediction discrepancy: 5.126e-14. Maximum Jacobian column discrepancy: 2.838e-13. Maximum FD discrepancy: 8.422e-9. Elapsed: 103.02 s; 352 budget units.

The raw single-object compiler was qualified here; production keeps its predeclared single-component full-Kress fallback.
