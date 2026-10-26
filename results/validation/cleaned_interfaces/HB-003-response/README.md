# HB-003 physical response evidence

[Results and interpretation](../../../../docs/iterations/haibing_2026-10-26/response/01_results.md)
map these measurements directly to Haibing items 6–8 and Word §§13–18.

- `schur.json`: eight physical splits, full and exact Schur timings,
  high-mode dropping, diagonal inverse correction and convergence diagnostics.
- `rom.json`: both frequencies' basis costs, response errors, local orders,
  projection costs and dual-residual estimates.
- `rom_real/` and `rom_damped/`: saved A/B/R and exact source states for all
  eight physical path points, plus detailed result rows.
- `lm.json`: fifteen fixed-system CG iterates and LM defect bounds, using
  the saved FI-001 19-frequency physical Jacobian and residual.
- `manifest.json`: initial revision, source/plan hashes and machine state.
- `source_at_run.py`: exact executed source matching the manifest hash.
- `processing_note.txt`: clarification of the roundoff-aware coverage label.
- `run.log`: completed-stage record.

No fits were run. Small singular-value bounds are numerical estimates,
not rounding-controlled certificates. The exact-anchor bound fails to
cover roundoff; that limitation is preserved in `bound_norm_covers_error`.
