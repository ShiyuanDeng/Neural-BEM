"""Bounded diagnostics: existing SPD fitter, unchanged observations and guards.

Only --bands, --constraint and --damping are interventions. This is not a
replacement benchmark. No topology controller or hybrid optimizer is run.
"""
import argparse
import inspect
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
import time
import numpy as np

from experiments.shape_continuation import spd_cases as bridge
from experiments.shape_continuation import atlas_cases as cases
from experiments.shape_continuation import atlas_strategy_tests as saved_inputs
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.radial_topology import MultiRadialFourierState
from sdf_inverse.topology_controller import zero_padded_component
from sdf_inverse.runtime import inverse_runtime
from gpr_bem_kress.execution import execution
from ordered_boundary.validation_cache import geometry_validation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('wrong_circle', 'circle_to_star'), required=True)
    parser.add_argument('--bands', type=int, nargs=4, default=(17,17,17,17))
    parser.add_argument('--constraint', choices=('true','fd_compatible'), default='fd_compatible')
    parser.add_argument('--damping', type=float, default=.001)
    parser.add_argument('--curvature', type=float, default=0.)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    inputs=bridge.load()
    top=inputs['top025']; p,m=top.p,top.m
    catalog=saved_inputs.catalog_only(args.case)
    observed=np.column_stack([catalog[cases.CATALOG_HZ.index(f)].scattered for f in p.TRAIN])
    state=MultiRadialFourierState((circle_cartesian_fourier_state(
        cases.START['center'], cases.START['radius'], 'comparison.circle', maximum_mode=args.bands[0]),))
    floor=inputs['control'].minimum_component_radius_m
    original=m.rt.run_multiradial_fd_inverse
    implementation=original
    if args.curvature:
        # Translate the legacy radial k**4 step penalty to the documented
        # orthonormal polar-gauge ordering: tx, ty, radius, cos/sin(2..K-1).
        # All original directions remain active. Change only the linear system.
        source=inspect.getsource(original)
        old='normal + trial_damping * np.diag(scaling), -gradient'
        new='normal + trial_damping * np.diag(scaling) + np.diag(_diagnostic_curvature * max(float(np.max(np.diag(normal))), 1.0) * np.array([0.,0.,0.] + [float(k) for k in range(2, accepted_state.components[0].maximum_mode) for _ in range(2)])**4), -gradient'
        assert source.count(old)==1
        namespace=dict(m.rt.__dict__,_diagnostic_curvature=args.curvature)
        exec(compile('from __future__ import annotations\n'+source.replace(old,new),'<diagnostic-legacy-curvature>','exec'),namespace)
        implementation=namespace['run_multiradial_fd_inverse']
    def invoke(*a,**kw):
        kw['analytic_constraint_policy']=args.constraint
        return implementation(*a,**kw)
    m.rt.run_multiradial_fd_inverse=invoke
    config=dict(case=args.case, bands=args.bands, constraint=args.constraint,
                damping=args.damping, curvature=args.curvature, nodes=[512,1024], floor_m=floor,
                source_input=str(saved_inputs.source_folder(args.case)/'observations.json'))
    bridge.write(args.output/'diagnostic_configuration.json',config)
    rows=[]; started=time.perf_counter()
    ledger=m.Ledger(cap=8012,seconds=900.)
    with inverse_runtime('compiled'), execution(kernels='real_bessel',device='cpu'), geometry_validation('certified'), ledger.instrument():
        for (number,quota),band in zip(top.follow.FULL_PLAN,args.bands):
            previous=state.components[0].maximum_mode
            if band != previous:
                state=MultiRadialFourierState((zero_padded_component(state.components[0],band),))
            optimizer=replace(p._optimizer_config(state,inputs['control']),loss_tolerance=1e-14,
                              initial_damping=args.damping)
            ledger.begin_stage(number,quota)
            data=p.training_data(p.TRAIN[:number],observed[:,:number])
            state,terminal=m.fit_stage(state,data,(512,1024),inputs['solve'],optimizer,floor,ledger,args.output/f'stage_{number}')
            rows.append({k:terminal[k] for k in ('stage_outcome','reason','accepted_steps','production_loss','one_sided_columns','unresolved_columns')})
            bridge.write(args.output/'checkpoint.json',dict(stages=rows,final_state=p.driver.serialize_state(state)))
            if terminal['stage_outcome'] not in ('NORMAL_OPTIMIZER_RETURN','STAGE_QUOTA_REACHED'):
                break
    seconds=time.perf_counter()-started
    m.rt.run_multiradial_fd_inverse=original
    # Independent endpoint evaluation after optimization is over; truth cannot
    # affect a step. Report analytic radial deviation for these two known truths.
    frequencies=(.5e9,.75e9,1e9,1.25e9,1.5e9,2.5e9)
    truth_observed=np.column_stack([catalog[cases.CATALOG_HZ.index(f)].scattered for f in frequencies])
    import sdf_bem_multicomponent.forward as physical
    predictions={}
    with execution(kernels='real_bessel',device='cpu'):
        for nodes in (512,1024):
            predictions[nodes]=physical.predict_multicomponent_kress_paired_boundary_response(
                state.boundary(p.driver.baseline._geometry_config(nodes)),
                p.driver.baseline._problem(np.asarray(frequencies)),solve_config=inputs['solve']).scattered_response
    points=p.boundary_points(state,16384)[0]
    offsets=points-np.array([.5,.5]); theta=np.arctan2(offsets[:,1],offsets[:,0])
    target_radius=.05 if args.case=='wrong_circle' else .05*(1+.25*np.cos(5*theta))
    error=np.linalg.norm(offsets,axis=1)-target_radius
    result=dict(config=config,stages=rows,inverse_seconds=seconds,
                final_state=p.driver.serialize_state(state),frequencies_hz=frequencies,
                relative_field_error=cases.relative(predictions[1024],truth_observed),
                cross_resolution=cases.relative(predictions[512],predictions[1024]),
                radial_rms_mm=1000*np.sqrt(np.mean(error**2)),radial_max_mm=1000*np.max(np.abs(error)),
                radius_certificate_mm=1000*state.components[0].minimum_radius_lower_bound_m,
                work=ledger.snapshot())
    bridge.write(args.output/'result.json',result)
    print('RESULT', {k:v for k,v in result.items() if k not in ('final_state','work')},flush=True)

if __name__=='__main__':
    main()
