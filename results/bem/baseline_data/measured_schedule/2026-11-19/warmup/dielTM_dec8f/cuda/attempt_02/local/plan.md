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

## 2. ladder_1_real (fit)

Real frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1.
Wavenumbers: [1.0479225109758408]; damping Im(k)/Re(k): [0.0].
Weights: (np.float64(1.0),).
M=3; K_geometry=8; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1000 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 3. ladder_2_real (fit)

Real frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2.
Wavenumbers: [1.0479225109758408, 2.0958450219516815]; damping Im(k)/Re(k): [0.0, 0.0].
Weights: (np.float64(0.5), np.float64(0.5)).
M=6; K_geometry=14; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1250 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 4. ladder_3_real (fit)

Real frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225]; damping Im(k)/Re(k): [0.0, 0.0, 0.0].
Weights: (np.float64(0.3333333333333333), np.float64(0.3333333333333333), np.float64(0.3333333333333333)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1750 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 5. ladder_4_real (fit)

Real frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3, 4.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225, 4.191690043903363]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.25), np.float64(0.25), np.float64(0.25), np.float64(0.25)).
M=12; K_geometry=26; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 64, 'K_trace_refined': 96, 'coefficient_workspace': {'production': 128, 'refined': 160}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 4000 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 6. full_1_M11 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3, 4, 5, 6, 7, 8.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225, 4.191690043903363, 5.239612554879205, 6.287535065855045, 7.335457576830887, 8.383380087806726]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125)).
M=11; K_geometry=192; resolution profile: {'production': 1024, 'refined': 1280, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 128, 'K_trace_refined': 160, 'coefficient_workspace': {'production': 192, 'refined': 224}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 7. full_2_M15 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3, 4, 5, 6, 7, 8.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225, 4.191690043903363, 5.239612554879205, 6.287535065855045, 7.335457576830887, 8.383380087806726]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125)).
M=15; K_geometry=192; resolution profile: {'production': 1024, 'refined': 1280, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 128, 'K_trace_refined': 160, 'coefficient_workspace': {'production': 192, 'refined': 224}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 8. full_3_M19 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3, 4, 5, 6, 7, 8.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225, 4.191690043903363, 5.239612554879205, 6.287535065855045, 7.335457576830887, 8.383380087806726]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125)).
M=19; K_geometry=192; resolution profile: {'production': 1024, 'refined': 1280, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 128, 'K_trace_refined': 160, 'coefficient_workspace': {'production': 192, 'refined': 224}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 1500 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 9. full_4_M25_cleanup (cleanup)

Remove stored high Cartesian harmonics before this release

Entry: enter full_4_M25.
Next: fit full_4_M25.
Controls and decision rules: {'retained_band': 64, 'storage_band': 192, 'construction': 'centered coefficient crop, then zero-pad; no refit'}.

## 10. full_4_M25 (fit)

Full real catalog with one-time state cleanup

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3, 4, 5, 6, 7, 8.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225, 4.191690043903363, 5.239612554879205, 6.287535065855045, 7.335457576830887, 8.383380087806726]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125)).
M=25; K_geometry=192; resolution profile: {'production': 1024, 'refined': 1280, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 128, 'K_trace_refined': 160, 'coefficient_workspace': {'production': 192, 'refined': 224}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 304 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: crop coefficients then pad; no arclength refit.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 11. full_5_M31 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3, 4, 5, 6, 7, 8.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225, 4.191690043903363, 5.239612554879205, 6.287535065855045, 7.335457576830887, 8.383380087806726]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125)).
M=31; K_geometry=192; resolution profile: {'production': 1024, 'refined': 1280, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 128, 'K_trace_refined': 160, 'coefficient_workspace': {'production': 192, 'refined': 224}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 304 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 12. full_6_M37 (fit)

Full real catalog with shape-band release

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure ends the fit; full real catalog at declared noise discrepancy ends the fit.
Frequencies (GHz): 1, 2, 3, 4, 5, 6, 7, 8.
Wavenumbers: [1.0479225109758408, 2.0958450219516815, 3.1437675329275225, 4.191690043903363, 5.239612554879205, 6.287535065855045, 7.335457576830887, 8.383380087806726]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125), np.float64(0.125)).
M=37; K_geometry=192; resolution profile: {'production': 1024, 'refined': 1280, 'kind': 'modal_muller', 'nodal_resolution': None, 'token': '8*K_trace', 'K_trace': 128, 'K_trace_refined': 160, 'coefficient_workspace': {'production': 192, 'refined': 224}, 'refinement': 'raise K_trace by 32; raise coefficient window by 32; frontier and endpoint audit only'}.
Budget: 22 iterations, 304 work units.
Update: z + A a, A = (B^T B + xi U^T U)^+ B^T H: normal velocity h, even relative speed change; no refit. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(5.999999999999999), np.float64(5.999999999999999))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'schedule', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': False, 'reach_fraction': 0.0, 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': False, 'plain_progress_exit': False, 'record_diagnostics': False}.

## 13. observable_frontier (frontier)

Measure the paired-Jacobian frontier at the current curve and highest real frequency

Entry: scheduled stages completed and real-catalog noise discrepancy not reached.
Next: append stages up to frontier; otherwise the fit returns.
Controls and decision rules: {'formula': 'max(p: paired_column_norm[p] >= threshold*max(paired_column_norm))', 'threshold': 0.01, 'top': 95, 'step': 6, 'first': 43, 'K_geometry': 192, 'iterations': 22, 'work_units': 2, 'noise_rule': 'stop releases/tail once full real-catalog loss <= 1.1^2*expected noise loss', 'possible_bands': [43, 49, 55, 61, 67, 73, 79, 85, 91]}.

