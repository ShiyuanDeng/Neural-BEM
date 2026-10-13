# independent_four_control_research v0.1.0

Fitting budget: 13412 SPD work units, 120 seconds including localization.
Independent initial and final audits have separate budgets.

M controls the normal update. K_geometry stores the Cartesian curve. K_trace and assembly workspace belong to the selected physics service.

## 1. initial_audit (audit)

Qualify prescribed original start

Entry: before initialization.
Next: failure returns original start.
Controls and decision rules: {'seconds': 30.0}.

## 2. keep_start (localize)

Retain the prescribed centered start

Entry: initial audit passed.
Next: no data-based localization.
Controls and decision rules: None.

## 3. warmup (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25.
Wavenumbers: [(0.641718860444247+0.16042971511106174j)]; damping Im(k)/Re(k): [0.25].
Weights: (np.float64(1.0),).
M=1; K_geometry=4; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05,).
Budget: 44 iterations, 600 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 4. slot_1 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5.
Wavenumbers: [(0.641718860444247+0.16042971511106174j), (0.9625782906663704+0.2406445726665926j), (1.283437720888494+0.3208594302221235j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25].
Weights: (np.float64(0.3333333333333333), np.float64(0.3333333333333333), np.float64(0.3333333333333333)).
M=3; K_geometry=8; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 5. slot_2 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75.
Wavenumbers: [(0.641718860444247+0.16042971511106174j), (0.9625782906663704+0.2406445726665926j), (1.283437720888494+0.3208594302221235j), (1.6042971511106172+0.4010742877776543j), (1.9251565813327407+0.4812891453331852j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25, 0.25, 0.25].
Weights: (np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2), np.float64(0.2)).
M=5; K_geometry=12; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 6. slot_3 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.
Wavenumbers: [(0.641718860444247+0.16042971511106174j), (0.9625782906663704+0.2406445726665926j), (1.283437720888494+0.3208594302221235j), (1.6042971511106172+0.4010742877776543j), (1.9251565813327407+0.4812891453331852j), (2.246016011554864+0.561504002888716j), (2.566875441776988+0.641718860444247j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25].
Weights: (np.float64(0.14285714285714285), np.float64(0.14285714285714285), np.float64(0.14285714285714285), np.float64(0.14285714285714285), np.float64(0.14285714285714285), np.float64(0.14285714285714285), np.float64(0.14285714285714285)).
M=7; K_geometry=16; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 7. slot_4 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25.
Wavenumbers: [(0.641718860444247+0.16042971511106174j), (0.9625782906663704+0.2406445726665926j), (1.283437720888494+0.3208594302221235j), (1.6042971511106172+0.4010742877776543j), (1.9251565813327407+0.4812891453331852j), (2.246016011554864+0.561504002888716j), (2.566875441776988+0.641718860444247j), (2.887734871999111+0.7219337179997778j), (3.2085943022212344+0.8021485755553086j)]; damping Im(k)/Re(k): [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25].
Weights: (np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 8. bridge (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111), np.float64(0.1111111111111111)).
M=9; K_geometry=20; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 9. slot_5 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091), np.float64(0.09090909090909091)).
M=11; K_geometry=24; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 10. slot_6 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693), np.float64(0.07692307692307693)).
M=19; K_geometry=40; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 11. slot_7 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667), np.float64(0.06666666666666667)).
M=37; K_geometry=96; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 12. slot_8 (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842)).
M=37; K_geometry=192; resolution profile: {'production': 512, 'refined': 768, 'kind': 'modal_muller', 'K_trace': 64, 'K_trace_refined': 96, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 60 iterations, 3000 work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 13. terminal (fit)

Independent four-control research rung

Entry: previous operation completed or exhausted its stage quota.
Next: advance on normal/quota return; any hard/numerical failure goes to final audit; full real catalog at declared noise discrepancy goes directly to final audit.
Frequencies (GHz): 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 1.875, 2, 2.125, 2.25, 2.375, 2.5.
Wavenumbers: [0.641718860444247, 0.9625782906663704, 1.283437720888494, 1.6042971511106172, 1.9251565813327407, 2.246016011554864, 2.566875441776988, 2.887734871999111, 3.2085943022212344, 3.5294537324433577, 3.8503131626654814, 4.171172592887605, 4.492032023109728, 4.812891453331852, 5.133750883553976, 5.454610313776099, 5.775469743998222, 6.096329174220346, 6.417188604442469]; damping Im(k)/Re(k): [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0].
Weights: (np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842), np.float64(0.05263157894736842)).
M=37; K_geometry=192; resolution profile: {'production': 1536, 'refined': 1792, 'kind': 'modal_muller', 'K_trace': 192, 'K_trace_refined': 224, 'token': '8*K_trace', 'coefficient_workspace': {'production': 512, 'refined': 512}, 'refinement': 'fixed coefficient workspace; monotone trace qualification within cap'}.
Field agreement tolerances: (1e-05, 1e-05, 1e-05, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07, 1e-07).
Budget: 13412 iterations, None work units.
Update: z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial. Cleanup: none.
Stopping: ['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap', 'stage quota', 'global work/time cap', 'numerical refusal'].
Optimizer settings: {'initial_damping': 0.001, 'damping_increase': 10.0, 'damping_decrease': 0.3, 'max_damping_trials': 5, 'max_backtracks': 7, 'gradient_tolerance': 1e-07, 'loss_tolerance': 1e-14, 'relative_step_tolerance': 1e-07, 'scaling_floor': 1.0, 'step_bounds_m': (0.012, 0.018, 0.006), 'acceptance_absolute_margin': 1e-14, 'acceptance_relative_margin': 1e-08, 'cross_resolution_factor': 5.0, 'residual_floor': 1e-12, 'domain_box': ((np.float64(-5.999999999999999), np.float64(-5.999999999999999)), (np.float64(6.000000000000001), np.float64(6.000000000000001))), 'step_control': 'coefficient', 'physical_step_bound_m': 0.006, 'damping_rule': 'agreement', 'hanke_ratio': 0.7, 'metric': 'marquardt', 'detectability_factor': 2.5, 'log_model': True, 'reach_fraction': 0.0, 'resolution_gate': 'absolute', 'damping_floor_relative': 1e-06, 'geometry_proposal_cap': 2000, 'progress_window': 5, 'minimum_relative_progress': 0.01, 'avoid_terminal_linearization': True, 'plain_progress_exit': True}.

## 14. final_audit (audit)

Independent full-real-catalog endpoint audit

Entry: fit returned.
Next: score only returned endpoint.
Controls and decision rules: {'seconds': 30.0}.

