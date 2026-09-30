# cumulative_sc_ma v1.0.0

Fitting budget: 13412 SPD work units, 1800 seconds including localization.
Independent initial and final audits have separate budgets.

M controls the normal update. K_geometry stores the Cartesian curve. K_trace and assembly workspace belong to the selected physics service.

## 1. initial_audit (audit)

Qualify the prescribed original start

Entry: before localization.
Next: localize if qualified; otherwise final failure.
Controls and decision rules: {'scope': 'all real frequencies, complete-trial Jacobian/FD', 'seconds': 300.0}.

## 2. damped_localization (localize)

Find a data-supported circle using low-frequency damped data

Entry: original-start audit passed.
Next: warm-up at first qualified refined circle; failure goes to final audit.
Controls and decision rules: {'frequencies': 3, 'center_min_m': 0.28, 'center_max_m': 0.72, 'center_step_m': 0.004, 'radius_min_m': 0.015, 'radius_max_m': 0.075, 'radius_step_m': 0.001, 'batch_centers': 800, 'max_ranked': 5000, 'max_starts': 5, 'distinct_center_m': 0.008, 'distinct_radius_m': 0.004, 'refinement_steps_m': (0.004, 0.004, 0.001), 'refinement_iterations': 12, 'qualification_tolerance': 1e-07, 'cutoff_padding': 30, 'gamma': 0.25, 'objective': '0.5*mean((norm(pred-data)/norm(data))^2); equal frequency weights', 'cutoff': 'ceil(max(abs(k))*sqrt(max(contrast,1))*max(radius/length_unit)+30)', 'refinement': 'best of six coordinate neighbors; halve steps if none improves', 'qualification': 'selected backend, production/refined circle predictions; first qualified start', 'bounds_m': ((0.2, 0.2), (0.8, 0.8))}.

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
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.028076392332433e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 4. stage_1_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5.
Wavenumbers: [(1.283437720888494+0.3208594302221235j)]; damping Im(k)/Re(k): [0.25].
Weights: (np.float64(1.0),).
M=3; K_geometry=8; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, 1000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.071713446689949e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 5. stage_2_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j)]; damping Im(k)/Re(k): [0.25, 0.25].
Weights: (np.float64(0.4993687544538823), np.float64(0.5006312455461177)).
M=5; K_geometry=12; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07).
Budget: 22 iterations, 1250 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.0640479625488965e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 6. stage_3_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75, 1.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j), (2.566875441776988+0.641718860444247j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25].
Weights: (np.float64(0.33292402110115615), np.float64(0.33376571094915447), np.float64(0.3333102679496894)).
M=7; K_geometry=16; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 1750 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.0642577669379345e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 7. stage_4_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75, 1, 1.25.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j), (2.566875441776988+0.641718860444247j), (3.2085943022212344+0.8021485755553086j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25, 0.25].
Weights: (np.float64(0.2496840131304263), np.float64(0.25031525775604463), np.float64(0.24997368782221263), np.float64(0.2500270412913165)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 4000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.0640391197900756e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 8. stage_4_undamped (fit)

Return explicitly to the measured real-frequency objective

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75, 1, 1.25.
Wavenumbers: [1.283437720888494, 1.9251565813327407, 2.566875441776988, 3.2085943022212344]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.25085284442660294), np.float64(0.24999300788072432), np.float64(0.24878223093001806), np.float64(0.2503719167626547)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 4000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.034711420630187e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 9. release_M11_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter release_M11.
Next: fit release_M11.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 10. release_M11 (fit)

Full real catalog with recurrent noise cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.052720541383493094), np.float64(0.05253985468621538), np.float64(0.05293633880046133), np.float64(0.052468361036263754), np.float64(0.05275489139128528), np.float64(0.0525004583677751), np.float64(0.05249938661907159), np.float64(0.05242641433200808), np.float64(0.052834850815282317), np.float64(0.05243721604003462), np.float64(0.05257264045531301), np.float64(0.052507884238295485), np.float64(0.052664831749776486), np.float64(0.052697693145154316), np.float64(0.05251955959783116), np.float64(0.052676282132595474), np.float64(0.052692840025175165), np.float64(0.0526971439241135), np.float64(0.052852811259854846)).
M=11; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.049019547753509e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 11. release_M15_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter release_M15.
Next: fit release_M15.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 12. release_M15 (fit)

Full real catalog with recurrent noise cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.052720541383493094), np.float64(0.05253985468621538), np.float64(0.05293633880046133), np.float64(0.052468361036263754), np.float64(0.05275489139128528), np.float64(0.0525004583677751), np.float64(0.05249938661907159), np.float64(0.05242641433200808), np.float64(0.052834850815282317), np.float64(0.05243721604003462), np.float64(0.05257264045531301), np.float64(0.052507884238295485), np.float64(0.052664831749776486), np.float64(0.052697693145154316), np.float64(0.05251955959783116), np.float64(0.052676282132595474), np.float64(0.052692840025175165), np.float64(0.0526971439241135), np.float64(0.052852811259854846)).
M=15; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.049019547753509e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 13. release_M19_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter release_M19.
Next: fit release_M19.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 14. release_M19 (fit)

Full real catalog with recurrent noise cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.052720541383493094), np.float64(0.05253985468621538), np.float64(0.05293633880046133), np.float64(0.052468361036263754), np.float64(0.05275489139128528), np.float64(0.0525004583677751), np.float64(0.05249938661907159), np.float64(0.05242641433200808), np.float64(0.052834850815282317), np.float64(0.05243721604003462), np.float64(0.05257264045531301), np.float64(0.052507884238295485), np.float64(0.052664831749776486), np.float64(0.052697693145154316), np.float64(0.05251955959783116), np.float64(0.052676282132595474), np.float64(0.052692840025175165), np.float64(0.0526971439241135), np.float64(0.052852811259854846)).
M=19; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.049019547753509e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 15. fixed_M25_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter fixed_M25.
Next: fit fixed_M25.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 16. fixed_M25 (fit)

Full real catalog with recurrent noise cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.052720541383493094), np.float64(0.05253985468621538), np.float64(0.05293633880046133), np.float64(0.052468361036263754), np.float64(0.05275489139128528), np.float64(0.0525004583677751), np.float64(0.05249938661907159), np.float64(0.05242641433200808), np.float64(0.052834850815282317), np.float64(0.05243721604003462), np.float64(0.05257264045531301), np.float64(0.052507884238295485), np.float64(0.052664831749776486), np.float64(0.052697693145154316), np.float64(0.05251955959783116), np.float64(0.052676282132595474), np.float64(0.052692840025175165), np.float64(0.0526971439241135), np.float64(0.052852811259854846)).
M=25; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.049019547753509e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 17. fixed_M31_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter fixed_M31.
Next: fit fixed_M31.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 18. fixed_M31 (fit)

Full real catalog with recurrent noise cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.052720541383493094), np.float64(0.05253985468621538), np.float64(0.05293633880046133), np.float64(0.052468361036263754), np.float64(0.05275489139128528), np.float64(0.0525004583677751), np.float64(0.05249938661907159), np.float64(0.05242641433200808), np.float64(0.052834850815282317), np.float64(0.05243721604003462), np.float64(0.05257264045531301), np.float64(0.052507884238295485), np.float64(0.052664831749776486), np.float64(0.052697693145154316), np.float64(0.05251955959783116), np.float64(0.052676282132595474), np.float64(0.052692840025175165), np.float64(0.0526971439241135), np.float64(0.052852811259854846)).
M=31; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.049019547753509e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 19. fixed_M37_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter fixed_M37.
Next: fit fixed_M37.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 20. fixed_M37 (fit)

Full real catalog with recurrent noise cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.052720541383493094), np.float64(0.05253985468621538), np.float64(0.05293633880046133), np.float64(0.052468361036263754), np.float64(0.05275489139128528), np.float64(0.0525004583677751), np.float64(0.05249938661907159), np.float64(0.05242641433200808), np.float64(0.052834850815282317), np.float64(0.05243721604003462), np.float64(0.05257264045531301), np.float64(0.052507884238295485), np.float64(0.052664831749776486), np.float64(0.052697693145154316), np.float64(0.05251955959783116), np.float64(0.052676282132595474), np.float64(0.052692840025175165), np.float64(0.0526971439241135), np.float64(0.052852811259854846)).
M=37; K_geometry=192; resolution profile: {'production': 512, 'refined': 1024, 'kind': 'nodal_kress', 'nodal_resolution': 512, 'K_trace': None, 'coefficient_workspace': None, 'refinement': 'double nodes; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.049019547753509e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 21. observable_frontier (frontier)

Measure the paired-Jacobian frontier at the current curve and highest real frequency

Entry: fixed schedule completed and real-catalog noise discrepancy not reached.
Next: append fixed stages up to frontier; otherwise final audit.
Controls and decision rules: {'formula': 'max(p: paired_column_norm[p] >= threshold*max(paired_column_norm))', 'threshold': 0.01, 'top': 95, 'step': 6, 'first': 43, 'K_geometry': 192, 'quota': 304, 'iterations': 22, 'work_units': 2, 'noise_rule': 'stop releases/tail once full real-catalog loss <= 1.1^2*expected noise loss', 'possible_bands': [43, 49, 55, 61, 67, 73, 79, 85, 91]}.

## 22. final_audit (audit)

Qualify the returned endpoint independently

Entry: every exit, including a hard stop or refusal.
Next: return unscored curve and diagnostics.
Controls and decision rules: {'scope': 'all real frequencies; last actual M; field/column Jacobian/complete-trial FD', 'field_tolerances': '1e-5 at <=0.5 GHz; 1e-7 otherwise', 'jacobian_tolerance': 0.001, 'fd_tolerance': 0.001, 'fd_step_m': 1e-07, 'fd_seed': 42001, 'seconds': 300.0, 'backend': 'selected solver'}.

