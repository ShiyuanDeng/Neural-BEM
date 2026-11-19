# real_only_csi v1.0.0

Fitting budget: 13412 SPD work units, 3600 seconds including localization.

M controls the normal update. K_geometry stores the Cartesian curve. K_trace and assembly workspace belong to the selected physics service.

## 1. warmup_1GHz_real (fit)

Narrow-band warm-up on the lowest measured frequency

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1.
Wavenumbers: [1.0479225109758408]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=1; K_geometry=4; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 44 iterations, 600 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 2. frontier_before_ladder_1_real (frontier)

Measure the paired-Jacobian frontier at the current curve and this stage's highest frequency

Entry: previous stage returned.
Next: enter ladder_1_real with band min(default, frontier), at least 1.
Controls and decision rules: {'observation_index': 0, 'frequency_hz': 1000000000.0, 'threshold': 0.01, 'top': 95, 'default_band': 3, 'cap': False}.

