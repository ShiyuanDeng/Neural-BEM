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
M=1; K_geometry=4; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 44 iterations, 600 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.0424695157481223e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 4. stage_1_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5.
Wavenumbers: [(1.283437720888494+0.3208594302221235j)]; damping Im(k)/Re(k): [0.25].
Weights: (np.float64(1.0),).
M=3; K_geometry=8; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05,).
Budget: 22 iterations, 1000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.035820213939896e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 5. stage_2_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j)]; damping Im(k)/Re(k): [0.25, 0.25].
Weights: (np.float64(0.5001041189908992), np.float64(0.49989588100910065)).
M=5; K_geometry=12; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07).
Budget: 22 iterations, 1250 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.037077100959746e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 6. stage_3_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75, 1.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j), (2.566875441776988+0.641718860444247j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25].
Weights: (np.float64(0.3334614151152057), np.float64(0.3333225653648149), np.float64(0.33321601951997926)).
M=7; K_geometry=16; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07, 1e-07).
Budget: 22 iterations, 1750 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.038139449764085e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 7. stage_4_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75, 1, 1.25.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j), (2.566875441776988+0.641718860444247j), (3.2085943022212344+0.8021485755553086j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25, 0.25].
Weights: (np.float64(0.25030504151861865), np.float64(0.2502008171887231), np.float64(0.25012084103284304), np.float64(0.24937330025981516)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 4000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.043184916996574e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

## 8. stage_4_undamped (fit)

Return explicitly to the measured real-frequency objective

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.5, 0.75, 1, 1.25.
Wavenumbers: [1.283437720888494, 1.9251565813327407, 2.566875441776988, 3.2085943022212344]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.2506869283063584), np.float64(0.249215752003341), np.float64(0.24874498060533654), np.float64(0.251352339084964)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 4000 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.073202716690164e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

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
Weights: (np.float64(0.052350089676420464), np.float64(0.05277176308881462), np.float64(0.05254394213591978), np.float64(0.05246488716470665), np.float64(0.052235583806031056), np.float64(0.05274957227070863), np.float64(0.05213691019244015), np.float64(0.05278076447461627), np.float64(0.052683412134151765), np.float64(0.05275089165686514), np.float64(0.05282810959990306), np.float64(0.052528161144446125), np.float64(0.05250425957565351), np.float64(0.0528987600979787), np.float64(0.053001143929383425), np.float64(0.05264265804483411), np.float64(0.05250263078130949), np.float64(0.052921907683329335), np.float64(0.05270455254248774)).
M=11; K_geometry=192; resolution profile: {'production': 768, 'refined': 1024, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 96, 'K_trace_refined': 128, 'coefficient_workspace': {'production': 160, 'refined': 192}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.046476247631211e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

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
Weights: (np.float64(0.052350089676420464), np.float64(0.05277176308881462), np.float64(0.05254394213591978), np.float64(0.05246488716470665), np.float64(0.052235583806031056), np.float64(0.05274957227070863), np.float64(0.05213691019244015), np.float64(0.05278076447461627), np.float64(0.052683412134151765), np.float64(0.05275089165686514), np.float64(0.05282810959990306), np.float64(0.052528161144446125), np.float64(0.05250425957565351), np.float64(0.0528987600979787), np.float64(0.053001143929383425), np.float64(0.05264265804483411), np.float64(0.05250263078130949), np.float64(0.052921907683329335), np.float64(0.05270455254248774)).
M=15; K_geometry=192; resolution profile: {'production': 768, 'refined': 1024, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 96, 'K_trace_refined': 128, 'coefficient_workspace': {'production': 160, 'refined': 192}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.046476247631211e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

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
Weights: (np.float64(0.052350089676420464), np.float64(0.05277176308881462), np.float64(0.05254394213591978), np.float64(0.05246488716470665), np.float64(0.052235583806031056), np.float64(0.05274957227070863), np.float64(0.05213691019244015), np.float64(0.05278076447461627), np.float64(0.052683412134151765), np.float64(0.05275089165686514), np.float64(0.05282810959990306), np.float64(0.052528161144446125), np.float64(0.05250425957565351), np.float64(0.0528987600979787), np.float64(0.053001143929383425), np.float64(0.05264265804483411), np.float64(0.05250263078130949), np.float64(0.052921907683329335), np.float64(0.05270455254248774)).
M=19; K_geometry=192; resolution profile: {'production': 768, 'refined': 1024, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 96, 'K_trace_refined': 128, 'coefficient_workspace': {'production': 160, 'refined': 192}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 1500 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.046476247631211e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

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
Weights: (np.float64(0.052350089676420464), np.float64(0.05277176308881462), np.float64(0.05254394213591978), np.float64(0.05246488716470665), np.float64(0.052235583806031056), np.float64(0.05274957227070863), np.float64(0.05213691019244015), np.float64(0.05278076447461627), np.float64(0.052683412134151765), np.float64(0.05275089165686514), np.float64(0.05282810959990306), np.float64(0.052528161144446125), np.float64(0.05250425957565351), np.float64(0.0528987600979787), np.float64(0.053001143929383425), np.float64(0.05264265804483411), np.float64(0.05250263078130949), np.float64(0.052921907683329335), np.float64(0.05270455254248774)).
M=25; K_geometry=192; resolution profile: {'production': 768, 'refined': 1024, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 96, 'K_trace_refined': 128, 'coefficient_workspace': {'production': 160, 'refined': 192}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.046476247631211e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

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
Weights: (np.float64(0.052350089676420464), np.float64(0.05277176308881462), np.float64(0.05254394213591978), np.float64(0.05246488716470665), np.float64(0.052235583806031056), np.float64(0.05274957227070863), np.float64(0.05213691019244015), np.float64(0.05278076447461627), np.float64(0.052683412134151765), np.float64(0.05275089165686514), np.float64(0.05282810959990306), np.float64(0.052528161144446125), np.float64(0.05250425957565351), np.float64(0.0528987600979787), np.float64(0.053001143929383425), np.float64(0.05264265804483411), np.float64(0.05250263078130949), np.float64(0.052921907683329335), np.float64(0.05270455254248774)).
M=31; K_geometry=192; resolution profile: {'production': 768, 'refined': 1024, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 96, 'K_trace_refined': 128, 'coefficient_workspace': {'production': 160, 'refined': 192}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.046476247631211e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

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
Weights: (np.float64(0.052350089676420464), np.float64(0.05277176308881462), np.float64(0.05254394213591978), np.float64(0.05246488716470665), np.float64(0.052235583806031056), np.float64(0.05274957227070863), np.float64(0.05213691019244015), np.float64(0.05278076447461627), np.float64(0.052683412134151765), np.float64(0.05275089165686514), np.float64(0.05282810959990306), np.float64(0.052528161144446125), np.float64(0.05250425957565351), np.float64(0.0528987600979787), np.float64(0.053001143929383425), np.float64(0.05264265804483411), np.float64(0.05250263078130949), np.float64(0.052921907683329335), np.float64(0.05270455254248774)).
M=37; K_geometry=192; resolution profile: {'production': 768, 'refined': 1024, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 96, 'K_trace_refined': 128, 'coefficient_workspace': {'production': 160, 'refined': 192}, 'refinement': 'raise K_trace and coefficient window by 32; refuse candidates outside per-frequency tolerance'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 22 iterations, 304 work units.
Update: z + P_K[A(z+h*n)-A(z)], derivative of the complete trial. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': np.float64(6.046476247631211e-05), 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False}.

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

