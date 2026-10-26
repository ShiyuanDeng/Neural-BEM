# shape_frequency_continuation v0.1.0

Fitting budget: 13412 SPD work units, 120 seconds including localization.

M controls the normal update. K_geometry stores the Cartesian curve. K_trace and assembly workspace belong to the selected physics service.

## 1. damped_localization (localize)

Find a data-supported circle using low-frequency damped data

Entry: fit start.
Next: warm-up at the refined best grid circle; failure ends the fit.
Controls and decision rules: {'frequencies': 3, 'center_min_m': 0.28, 'center_max_m': 0.72, 'center_step_m': 0.004, 'radius_min_m': 0.015, 'radius_max_m': 0.075, 'radius_step_m': 0.001, 'batch_centers': 800, 'refinement_steps_m': (0.004, 0.004, 0.001), 'refinement_iterations': 12, 'cutoff_padding': 30, 'gamma': 0.25, 'objective': '0.5*mean((norm(pred-data)/norm(data))^2); equal frequency weights', 'cutoff': 'ceil(max(abs(k))*sqrt(max(contrast,1))*max(radius/length_unit)+30)', 'refinement': 'best of six coordinate neighbors from the best grid point; halve steps if none improves', 'bounds_m': ((0.2, 0.2), (0.8, 0.8))}.

## 2. initialize_translation_scale (fit)

Fit centre and size at the lowest damped frequency, preserving circular shape

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.25.
Wavenumbers: [(0.641718860444247+0.16042971511106174j)]; damping Im(k)/Re(k): [0.25].
Weights: (np.float64(1.0),).
M=0; K_geometry=4; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 44 iterations, 600 work units.
Update: similarity. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 3. stage_1_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.5.
Wavenumbers: [(1.283437720888494+0.3208594302221235j)]; damping Im(k)/Re(k): [0.25].
Weights: (np.float64(1.0),).
M=3; K_geometry=8; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1000 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 4. stage_2_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.5, 0.75.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j)]; damping Im(k)/Re(k): [0.25, 0.25].
Weights: (np.float64(0.5), np.float64(0.5)).
M=5; K_geometry=12; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1250 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 5. stage_3_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.5, 0.75, 1.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j), (2.566875441776988+0.641718860444247j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25].
Weights: (np.float64(0.3333333333333333), np.float64(0.3333333333333333), np.float64(0.3333333333333333)).
M=7; K_geometry=16; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1750 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 6. stage_4_damped (fit)

Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.5, 0.75, 1, 1.25.
Wavenumbers: [(1.283437720888494+0.3208594302221235j), (1.9251565813327407+0.4812891453331852j), (2.566875441776988+0.641718860444247j), (3.2085943022212344+0.8021485755553086j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25, 0.25].
Weights: (np.float64(0.25), np.float64(0.25), np.float64(0.25), np.float64(0.25)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 4000 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 7. stage_4_undamped (fit)

Return explicitly to the measured real-frequency objective

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.5, 0.75, 1, 1.25.
Wavenumbers: [1.283437720888494, 1.9251565813327407, 2.566875441776988, 3.2085943022212344]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.25), np.float64(0.25), np.float64(0.25), np.float64(0.25)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 4000 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 8. shape_1_M11 (fit)

Additional shape release at the complete real-frequency catalog

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842)).
M=11; K_geometry=24; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 9. shape_2_M15 (fit)

Additional shape release at the complete real-frequency catalog

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842)).
M=15; K_geometry=32; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 10. shape_3_M19 (fit)

Additional shape release at the complete real-frequency catalog

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842)).
M=19; K_geometry=40; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 11. shape_4_M25 (fit)

Additional shape release at the complete real-frequency catalog

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842)).
M=25; K_geometry=52; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

## 12. full_release_M95 (fit)

Release the full configured validated shape bandwidth

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842)).
M=95; K_geometry=192; resolution profile: {'production': 1024, 'refined': 1280, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 128, 'K_trace_refined': 160, 'coefficient_workspace': {'production': 192, 'refined': 224}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': False, 'record_diagnostics': True}.

