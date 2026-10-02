# cumulative_sc_ma v1.0.0

Fitting budget: 512 SPD work units, 7200 seconds including localization.
Independent initial and final audits have separate budgets.

M controls the normal update. K_geometry stores the Cartesian curve. K_trace and assembly workspace belong to the selected physics service.

## 1. initial_audit (audit)

Qualify the prescribed original start

Entry: before localization.
Next: localize if qualified; otherwise final failure.
Controls and decision rules: {'scope': 'all real frequencies, complete-trial Jacobian/FD', 'seconds': 900.0, 'catalog_alias': True}.

## 2. prescribed_td_initialization (localize)

Retain the common qualified TD seed configuration

Entry: original-start audit passed.
Next: same fixed-count seeds enter warmup; no single-circle localization.
Controls and decision rules: {'original_localization': 'single-circle Mie search', 'replacement': 'common archived TD seeds', 'reason': 'paired comparison requires identical data-only starts and component counts', 'catalog_alias': True}.

## 3. scif_visit_00_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 4. scif_visit_01_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 5. scif_visit_02_frequency_1 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [0.9625782906663704]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 6. scif_visit_03_frequency_2 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5.
Wavenumbers: [1.283437720888494]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 7. scif_visit_04_frequency_3 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.75.
Wavenumbers: [1.9251565813327407]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=2; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-07,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 8. scif_visit_05_frequency_2 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5.
Wavenumbers: [1.283437720888494]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 9. scif_visit_06_frequency_1 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [0.9625782906663704]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 10. scif_visit_07_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 11. scif_visit_08_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 12. scif_visit_09_frequency_1 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [0.9625782906663704]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 13. scif_visit_10_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 14. scif_visit_11_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 15. scif_visit_12_frequency_1 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [0.9625782906663704]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 16. scif_visit_13_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 17. scif_visit_14_frequency_1 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [0.9625782906663704]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 18. scif_visit_15_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 19. scif_visit_16_frequency_1 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [0.9625782906663704]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 20. scif_visit_17_frequency_0 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [0.641718860444247]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 21. scif_visit_18_frequency_1 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [0.9625782906663704]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 22. scif_visit_19_frequency_2 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5.
Wavenumbers: [1.283437720888494]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 23. scif_visit_20_frequency_3 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.75.
Wavenumbers: [1.9251565813327407]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=2; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-07,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 24. scif_visit_21_frequency_4 (fit)

Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 1.
Wavenumbers: [2.566875441776988]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=2; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-07,).
Budget: 22 iterations, None work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 25. final_audit (audit)

Qualify the returned endpoint independently

Entry: every exit, including a hard stop or refusal.
Next: return unscored curve and diagnostics.
Controls and decision rules: {'scope': 'all real frequencies; last actual M; field/column Jacobian/complete-trial FD', 'field_tolerances': '1e-5 at <=0.5 GHz; 1e-7 otherwise', 'jacobian_tolerance': 0.001, 'fd_tolerance': 0.001, 'fd_step_m': 1e-07, 'fd_seed': 42001, 'seconds': 900.0, 'backend': 'selected solver', 'catalog_alias': True}.

