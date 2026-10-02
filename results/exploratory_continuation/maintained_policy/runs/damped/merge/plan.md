# cumulative_sc_ma v1.0.0

Fitting budget: 13412 SPD work units, 1800 seconds including localization.
Independent initial and final audits have separate budgets.

M controls the normal update. K_geometry stores the Cartesian curve. K_trace and assembly workspace belong to the selected physics service.

## 1. initial_audit (audit)

Qualify the prescribed original start

Entry: before localization.
Next: localize if qualified; otherwise final failure.
Controls and decision rules: {'scope': 'all real frequencies, complete-trial Jacobian/FD', 'seconds': 900.0}.

## 2. prescribed_td_initialization (localize)

Retain the common qualified TD seed configuration

Entry: original-start audit passed.
Next: same fixed-count seeds enter warmup; no single-circle localization.
Controls and decision rules: {'original_localization': 'single-circle Mie search', 'replacement': 'common archived TD seeds', 'reason': 'paired comparison requires identical data-only starts and component counts'}.

## 3. warmup_025_damped (fit)

Warm up localized circle at 0.25 GHz

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [(0.641718860444247+0.16042971511106174j)]; damping Im(k)/Re(k): [0.25].
Weights: (np.float64(1.0),).
M=1; K_geometry=4; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 44 iterations, 600 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 4. stage_1_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375.
Wavenumbers: [(0.9625782906663704+0.2406445726665926j)]; damping Im(k)/Re(k): [0.25].
Weights: (np.float64(1.0),).
M=2; K_geometry=6; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, 1000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 5. stage_2_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375, 0.5.
Wavenumbers: [(0.9625782906663704+0.2406445726665926j), (1.283437720888494+0.3208594302221235j)]; damping Im(k)/Re(k): [0.25, 0.25].
Weights: (np.float64(0.5), np.float64(0.5)).
M=3; K_geometry=8; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05).
Budget: 22 iterations, 1250 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 6. stage_3_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375, 0.5, 0.75.
Wavenumbers: [(0.9625782906663704+0.2406445726665926j), (1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25].
Weights: (np.float64(0.3333333333333333), np.float64(0.3333333333333333), np.float64(0.3333333333333333)).
M=5; K_geometry=12; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-07).
Budget: 22 iterations, 1750 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 7. stage_4_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375, 0.5, 0.75, 1.
Wavenumbers: [(0.9625782906663704+0.2406445726665926j), (1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j), (2.566875441776988+0.641718860444247j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25, 0.25].
Weights: (np.float64(0.25), np.float64(0.25), np.float64(0.25), np.float64(0.25)).
M=7; K_geometry=16; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 4000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 8. stage_4_undamped (fit)

Return explicitly to the measured real-frequency objective

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.375, 0.5, 0.75, 1.
Wavenumbers: [0.9625782906663704, 1.283437720888494, 1.9251565813327407, 2.566875441776988]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.25), np.float64(0.25), np.float64(0.25), np.float64(0.25)).
M=7; K_geometry=16; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 4000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 9. release_M11 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.75, 1.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.9251565813327407, 2.566875441776988]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2)).
M=11; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 10. release_M15 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.75, 1.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.9251565813327407, 2.566875441776988]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2)).
M=15; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 11. release_M19 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.75, 1.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.9251565813327407, 2.566875441776988]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2)).
M=19; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 12. fixed_M25_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter fixed_M25.
Next: fit fixed_M25.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 13. fixed_M25 (fit)

Full real catalog with one-time state cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.75, 1.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.9251565813327407, 2.566875441776988]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2)).
M=25; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 14. fixed_M31 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.75, 1.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.9251565813327407, 2.566875441776988]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2)).
M=31; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 15. fixed_M37 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.75, 1.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.9251565813327407, 2.566875441776988]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2)).
M=37; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 16. observable_frontier (frontier)

Measure the paired-Jacobian frontier at the current curve and highest real frequency

Entry: fixed schedule completed and real-catalog noise discrepancy not reached.
Next: append fixed stages up to frontier; otherwise final audit.
Controls and decision rules: {'formula': 'max(p: paired_column_norm[p] >= threshold*max(paired_column_norm))', 'threshold': 0.01, 'top': 95, 'step': 6, 'first': 43, 'K_geometry': 192, 'quota': 304, 'iterations': 22, 'work_units': 2, 'noise_rule': 'stop releases/tail once full real-catalog loss <= 1.1^2*expected noise loss', 'possible_bands': [43, 49, 55, 61, 67, 73, 79, 85, 91]}.

## 17. final_audit (audit)

Qualify the returned endpoint independently

Entry: every exit, including a hard stop or refusal.
Next: return unscored curve and diagnostics.
Controls and decision rules: {'scope': 'all real frequencies; last actual M; field/column Jacobian/complete-trial FD', 'field_tolerances': '1e-5 at <=0.5 GHz; 1e-7 otherwise', 'jacobian_tolerance': 0.001, 'fd_tolerance': 0.001, 'fd_step_m': 1e-07, 'fd_seed': 42001, 'seconds': 900.0, 'backend': 'selected solver'}.

