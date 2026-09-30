# SC-051: frequency continuation with full discretization bands

User request, 2026-09-29: run a vanilla frequency ladder without M/K restrictions
on every current SC and modal-atlas scene and compare with the strongest existing
strategies. The user explicitly included the modal-atlas contrast/noise cases.

The vanilla arm uses cumulative available real frequencies in ascending order:
0.25:0.125:2.5 GHz on single objects, and the four available frequencies on the
coupled cases. Both normal update M and Cartesian state K equal N/2−1=255 from
the first stage, with N=512 and independent 1024-node acceptance checks. This
means no policy restriction below the finite mesh's Fourier band; it does not
mean an infinite-dimensional calculation. There is no localization, state
cleanup, band ladder, atlas selection, complex-frequency damping, or tail pass.
The complete projected update and LM optimizer are unchanged, including step
controls and numerical refusal gates. SC-044 retains its noise discrepancy stop.
All components move together in coupled trials; no topology actions are used.

Each path has 13,412 work units, 1,800 fitting seconds, 44 iterations per
frequency, and an equal per-frequency share of the work cap. Endpoints are the
last accepted states, including failed attempts. Full-catalog field, all active
Jacobian columns, and complete-trial FD audits run after fitting (300 s each).
The original numerical tolerances are retained. Truth is used only afterwards
for boundary scores. Clean recovery uses RMS <=1 mm, Hausdorff upper <=2 mm,
max catalog residual <=0.003 and a passing audit. Noisy cases replace the
residual ceiling with max(0.003, 3 times the realized noise).

The 41 configurations cover six original single-object scenes, six fresh
shape/noise configurations, seven far-start configurations, seventeen additional
modal-atlas contrast configurations, four coupled shape/noise configurations,
and the single executed intrinsic-perturbation coupled scene. The three MA
development cases at contrast 0.5 duplicate SC-050 and are run once. Opposite-C
starts remain distinct initialization tests despite sharing the target/data.
Historical plane-wave paper-replication runs, topology insertion diagnostics,
and alternate algorithm trajectories of these same scenes are not extra scenes.

Comparators are selected before the new fits: SC-043 fixed release (the best
aggregate control) and stagnation (the better tested adaptive rule), SC-044
recurrent cleanup, SC-050 localization/warm-up, MA-005 DF, SC-047 joint M3→M5,
and SC-048 compact M5. These are archived end-to-end outcomes, not matched
one-variable ablations. SC-043/044 artifacts record suffix cost only; do not
misreport that cost as full reconstruction cost. Older wall times use different
runtimes, so no wall-time speedup is claimed. Coupled panels have different
acquisition and local starts and are reported separately.

All inputs, reference results, and numerical sources are hashed before running.
No existing result is overwritten, and no production default is changed.
