"""Run the frozen BIE-002 campaign with persistent hard work limits.

No shared files are written; all physical kernels come from existing factories.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import argparse
import gc
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import time
import traceback

for thread_variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                        'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[thread_variable] = '1'

import numpy as np
import scipy
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1
try:
    from threadpoolctl import threadpool_info
except ImportError:
    def threadpool_info():
        return dict(runtime_threadpool_query=None,
                    reason='threadpoolctl is not installed; no dependency installation required',
                    requested_threads={k: os.environ[k] for k in
                                       ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')})
from ordered_boundary import OrderedBoundary2D
from gpr_bem_kress import Material, KressSolveConfig, solve_kress_tmz_total_field_batch
from gpr_bem_kress.system import build_kress_tmz_frequency_system
from gpr_bem_kress.forward import (KressTMzForwardResult, kress_incident_trace_on_boundary,
                                  build_exterior_receiver_operator)
from gpr_bem_kress.multicomponent import (
    build_multicomponent_kress_tmz_frequency_system,
    multicomponent_incident_trace_on_boundary,
    build_multicomponent_exterior_receiver_operator,
)
from gpr_bem_kress.shape_derivative import KressDirection, _directional_operators
from .fixtures import inputs, parameterizations, direction_jets, perturb
from .metrics import (Ledger, BudgetStop, LIMITS, digest, write_json, write_csv,
                      error_metrics, trace_errors)
from .modal_projection import (synthesis, project, scale_maps, centered_mask,
                               mask_operator, oracle_retention)

FRACTIONS = [1.0, .25, .5, .75]
THRESHOLDS = dict(full_mode=1e-10, forward=1e-6, reference=2e-7,
                  sensitivity=1e-4, sensitivity_reference=2e-5, residual=1e-6)


def paired(y):
    # y is receiver x source; production transposes before acquisition selection.
    return np.diag(y.T)


class Campaign:
    def __init__(self, output, ledger, acquisition):
        self.output, self.ledger, self.acq = output, ledger, acquisition
        self.sources = np.array(acquisition['source_points'])
        self.receivers = np.array(acquisition['receiver_points'])
        self.strengths = np.full(len(self.sources), acquisition['source_strength'], complex)
        self.materials = {name: Material(**acquisition[name]) for name in ('exterior', 'interior')}
        self.constants = {name: acquisition[name] for name in ('eps0', 'mu0')}
        self.accuracy, self.timings, self.tails = [], [], []
        self.structure, self.taylor, self.controls, self.cases = [], [], [], []
        self.finalist = None

    def checkpoint(self):
        for name in ('accuracy', 'timings', 'tails', 'structure', 'taylor'):
            write_csv(self.output / (name + '.csv'), getattr(self, name))
        write_json(self.output / 'controls.json', self.controls)
        write_json(self.output / 'case_summary.json', self.cases)

    def assemble(self, curves, frequency, ell):
        single = len(curves) == 1
        geometry = curves[0] if single else OrderedBoundary2D(tuple(curves))
        system_fn = build_kress_tmz_frequency_system if single else build_multicomponent_kress_tmz_frequency_system
        incident_fn = kress_incident_trace_on_boundary if single else multicomponent_incident_trace_on_boundary
        receiver_fn = build_exterior_receiver_operator if single else build_multicomponent_exterior_receiver_operator
        system, assembly_time = self.ledger.call('system_assembly',
            lambda: system_fn(geometry, 2*np.pi*frequency, **self.materials, **self.constants),
            costs=dict(assemblies=1), n=2*geometry.num_nodes)
        (bd, bn), rhs_time = self.ledger.call('incident_rhs',
            lambda: incident_fn(geometry, self.sources, system.k_exterior, self.strengths))
        receiver, receiver_time = self.ledger.call('receiver_operator',
            lambda: receiver_fn(geometry, self.receivers, system.k_exterior))
        b = np.concatenate((bd, bn), axis=1).T
        (a, bscaled, c, s), scale_time = self.ledger.call('dimensional_scaling',
            lambda: scale_maps(system.system_matrix, b, receiver.state_rows, ell))
        direct, direct_time = self.ledger.call('incident_receiver', lambda:
            self.strengths[:, None] * .25j * hankel1(0, system.k_exterior *
                np.linalg.norm(self.receivers[None, :, :] - self.sources[:, None, :], axis=-1)))
        return dict(curves=curves, system=system, receiver=receiver, bphysical=b,
                    a=a, b=bscaled, c=c, s=s, direct=direct, bd=bd, bn=bn,
                    ell=ell, frequency=frequency, geometry_seconds=0.0,
                    assembly_seconds=assembly_time, rhs_seconds=rhs_time,
                    receiver_operator_seconds=receiver_time, scaling_seconds=scale_time,
                    incident_receiver_seconds=direct_time)

    def solve_arm(self, base, fraction=None, mask_width=None):
        projection_seconds = 0.0
        if fraction is None:
            p = None
            a, b, c = base['a'], base['b'], base['c']
            method = 'nodal'
        else:
            def transform():
                p, labels, components = synthesis(base['curves'], fraction)
                return p, labels, components, project(base['a'], base['b'], base['c'], p)
            (p, labels, components, (a, b, c)), projection_seconds = self.ledger.call('projection', transform)
            method = 'modal'
            if mask_width is not None:
                mask, seconds = self.ledger.call('mask_construction',
                    lambda: centered_mask(labels, components, mask_width))
                a, seconds2 = self.ledger.call('mask_operator', lambda: mask_operator(a, mask))
                projection_seconds += seconds + seconds2
                method = 'band'
        factors, factor_seconds = self.ledger.call('lu_factorization',
            lambda: lu_factor(a, check_finite=True), costs=dict(factorizations=1),
            n=base['a'].shape[0], r=a.shape[0])
        z, solve_seconds = self.ledger.call('rhs_solve',
            lambda: lu_solve(factors, b), costs=dict(solves=1), rhs_count=b.shape[1],
            n=base['a'].shape[0], r=a.shape[0])
        y, evaluation_seconds = self.ledger.call('receiver_evaluation', lambda: c @ z)
        u = z if p is None else p @ z
        residual = float(np.linalg.norm(base['a'] @ u - base['b']) / np.linalg.norm(base['b']))
        times = {key: base[key] for key in ('geometry_seconds', 'assembly_seconds', 'rhs_seconds',
                 'receiver_operator_seconds', 'scaling_seconds', 'incident_receiver_seconds')}
        times.update(projection_seconds=projection_seconds, factorization_seconds=factor_seconds,
                     solve_seconds=solve_seconds, receiver_evaluation_seconds=evaluation_seconds)
        # Conservative model includes full parent, retained blocks, transform temporaries,
        # LU and three full directional arrays; RSS is independently measured.
        n, r = base['a'].shape[0], a.shape[0]
        storage_bound = 16 * (16*n*n + 5*r*r + 4*n*r + 12*n*b.shape[1])
        if storage_bound >= 4 * 1024**3:
            raise BudgetStop('Planned live-array budget >=4 GiB')
        arm = dict(method=method, fraction=fraction, width=mask_width, p=p, a=a, b=b, c=c,
                   factors=factors, z=z, u=u, physical=u/base['s'][:, None], y=y,
                   residual=residual, timings=times, total_seconds=sum(times.values()),
                   array_storage_bound_bytes=storage_bound, n=n, r=r)
        if mask_width is not None:
            arm['mask'] = mask
        return arm

    def forward_base(self, base, arm):
        if len(base['curves']) != 1:
            return None
        count = base['curves'][0].num_nodes
        u = arm['physical']
        single = (base['receiver'].single_layer_rows @ u[count:]).T
        double = (base['receiver'].double_layer_rows @ u[:count]).T
        y = arm['y'].T
        return KressTMzForwardResult(
            system=base['system'], solve_config=KressSolveConfig(),
            exterior_material=self.materials['exterior'], interior_material=self.materials['interior'],
            **self.constants, receiver_operator=base['receiver'], source_points=self.sources,
            receiver_points=self.receivers, source_strengths=self.strengths,
            right_hand_side=base['bphysical'], solution=u,
            dirichlet_incident=base['bd'], neumann_incident=base['bn'],
            dirichlet_total=u[:count].T, neumann_total=u[count:].T,
            incident_receiver=base['direct'], single_receiver=single, double_receiver=double,
            scattered_receiver=y, total_receiver=y+base['direct'],
            linear_system_relative_residual=arm['residual'],
            per_source_relative_residual=np.linalg.norm(base['system'].system_matrix @ u-base['bphysical'], axis=0)
                / np.linalg.norm(base['bphysical'], axis=0),
            incident_representation_leak=float(np.linalg.norm(base['receiver'].state_rows @ base['bphysical']) /
                max(np.linalg.norm(base['direct']), 1e-300)),
            solve_seconds=arm['timings']['factorization_seconds']+arm['timings']['solve_seconds'],
            receiver_evaluation_seconds=arm['timings']['receiver_evaluation_seconds'],
            total_seconds=arm['total_seconds'], diagnostics={})

    def derivative(self, base, nodal, kind):
        direction = KressDirection(*direction_jets(base['curves'][0].parameters, kind))
        operators, seconds = self.ledger.call('analytic_directional_operators',
            lambda: _directional_operators(self.forward_base(base, nodal), direction),
            costs=dict(assemblies=1, derivatives=1),
            primal_kernel_recomputations=1, direction=kind, n=base['a'].shape[0])
        values, scaling_seconds = self.ledger.call('directional_scaling', lambda:
            scale_maps(operators.d_system_matrix, operators.d_right_hand_side,
                       operators.d_receiver_matrix, base['ell'])[:3])
        self.controls.append(dict(**self.ledger.context, direction=kind,
                                  derivative_diagnostics=dict(operators.diagnostics)))
        return values, seconds + scaling_seconds

    def tangent(self, arm, values):
        da, db, dc = values
        projection_seconds = 0.0
        if arm['p'] is not None:
            (da, db, dc), projection_seconds = self.ledger.call('directional_projection',
                lambda: project(da, db, dc, arm['p']))
        if arm['width'] is not None:
            da = da * arm['mask']
        self.ledger.reuse('base_lu', n=arm['n'], r=arm['r'])
        dz, solve_seconds = self.ledger.call('tangent_rhs_solve',
            lambda: lu_solve(arm['factors'], db-da @ arm['z']),
            costs=dict(solves=1), rhs_count=db.shape[1], n=arm['n'], r=arm['r'])
        dy, evaluation_seconds = self.ledger.call('tangent_receiver_evaluation',
            lambda: dc @ arm['z'] + arm['c'] @ dz)
        return dy, dict(derivative_projection_seconds=projection_seconds,
                        tangent_solve_seconds=solve_seconds,
                        tangent_receiver_evaluation_seconds=evaluation_seconds)

    def accuracy_row(self, base, arm, reference, ref_qualified, reference_discrepancy, *,
                     direction=None, dy=None, derivative_reference=None,
                     derivative_qualified=None, derivative_discrepancy=None):
        sy = float(np.linalg.norm(np.diag(base['direct'])))
        e = error_metrics(paired(arm['y']), paired(reference['y']), 1e-12*sy)
        eraw = error_metrics(arm['y'], reference['y'], 1e-12*sy)
        row = dict(**self.ledger.context, method=arm['method'], fraction=arm['fraction'],
                   width=arm['width'], nodes_per_component=base['curves'][0].num_nodes,
                   retained_modes_per_trace_component=arm['r']//(2*len(base['curves'])),
                   n=arm['n'], r=arm['r'], dimension_fraction=arm['r']/arm['n'],
                   reference_qualified=ref_qualified, reference_discrepancy=reference_discrepancy,
                   reference_id=f"{self.ledger.context['case']}-{base['frequency']}-N{reference['r']//(2*len(base['curves']))}",
                   data_relative=e['relative'], data_absolute=e['absolute'],
                   transformed_absolute=e['absolute']/max(np.linalg.norm(paired(reference['y'])), 1e-12*sy),
                   full_receiver_relative=eraw['relative'], full_receiver_absolute=eraw['absolute'],
                   floor_dominated=e['floor_dominated'], source_scale=sy,
                   lifted_residual=arm['residual'], direction=direction,
                   sensitivity_qualified=derivative_qualified,
                   sensitivity_reason=None if derivative_qualified is not None else 'not tested on this row / multi-interface unsupported',
                   sensitivity_reference_discrepancy=derivative_discrepancy,
                   sensitivity_relative=None, sensitivity_absolute=None)
        # Native grids are nested: sample the finer trace at the candidate grid.
        fine_count = reference['n']//2
        per_fine = fine_count//len(base['curves'])
        per_coarse = base['curves'][0].num_nodes
        indices = np.concatenate([np.arange(i*per_fine, (i+1)*per_fine, per_fine//per_coarse)
                                  for i in range(len(base['curves']))])
        trace_reference = reference['physical'][np.r_[indices, indices+fine_count]]
        row.update(trace_errors(arm['physical'], trace_reference, base['curves']))
        if dy is not None:
            ed = error_metrics(paired(dy), paired(derivative_reference), 1e-12*sy/base['ell'])
            row.update(sensitivity_relative=ed['relative'], sensitivity_absolute=ed['absolute'],
                       sensitivity_floor_dominated=ed['floor_dominated'])
        row['forward_pass'] = bool(ref_qualified and e['relative'] <= 1e-6 and arm['residual'] <= 1e-6)
        row['sensitivity_pass'] = (None if dy is None else bool(derivative_qualified and
                                   row['sensitivity_relative'] <= 1e-4))
        self.accuracy.append(row)
        return row

    def record_timing(self, base, arm, *, classification='cold_profile', repetition=None,
                      eligible=None, derivative_seconds=None, tangent_times=None):
        row = dict(**self.ledger.context, method=arm['method'], fraction=arm['fraction'], width=arm['width'],
                   nodes_per_component=base['curves'][0].num_nodes, n=arm['n'], r=arm['r'],
                   rhs_count=len(self.sources), classification=classification, repetition=repetition,
                   **arm['timings'], forward_total_seconds=arm['total_seconds'],
                   derivative_assembly_seconds=derivative_seconds,
                   peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                   array_storage_bound_bytes=arm['array_storage_bound_bytes'],
                   comparison_eligible=eligible, measured_parent_assembly=True,
                   derivative_storage_note='conservative bound includes three full directional arrays')
        if tangent_times:
            row.update(tangent_times)
            row['forward_plus_one_jvp_seconds'] = arm['total_seconds']+derivative_seconds+sum(tangent_times.values())
        self.timings.append(row)
        return row

    def structure_profiles(self, base, full):
        h = full['a'] - np.eye(full['n'])
        nodes = base['curves'][0].num_nodes
        components = len(base['curves'])
        for trace_row in range(2):
            for trace_column in range(2):
                for i in range(components):
                    for j in range(components):
                        rr = slice((trace_row*components+i)*nodes, (trace_row*components+i+1)*nodes)
                        cc = slice((trace_column*components+j)*nodes, (trace_column*components+j+1)*nodes)
                        block = h[rr, cc]
                        for tail in (1e-2, 1e-4, 1e-6):
                            retained = oracle_retention(block, tail)
                            self.structure.append(dict(**self.ledger.context, profile='oracle',
                                block=[['-DeltaK', '+DeltaV'], ['-DeltaT', '+DeltaKp']][trace_row][trace_column],
                                target_component=i, source_component=j, interaction='self' if i==j else 'cross',
                                tail_target=tail, retained_entries=retained, total_entries=block.size,
                                retention_fraction=retained/block.size, block_frobenius=float(np.linalg.norm(block)),
                                construction='full dense parent and full transform required'))

    def run_case(self, scene, frequency):
        self.ledger.check_source()
        params = parameterizations(scene)
        multiple = len(params) > 1
        ladder = [64, 128, 256, 512] if multiple else [64, 128, 256]
        integration = 256 if multiple else 128
        sample = np.concatenate([p.discretize(2048).points for p in params])
        ell = float(np.linalg.norm(np.ptp(sample, axis=0)))
        self.ledger.context = dict(stage='reference_and_reduction', case=scene['id'], frequency_hz=frequency)
        bases, nodal = {}, {}
        for count in ladder:
            curves, geom_seconds = self.ledger.call('geometry', lambda: [p.discretize(count) for p in params])
            bases[count] = self.assemble(curves, frequency, ell)
            bases[count]['geometry_seconds'] = geom_seconds
            nodal[count] = self.solve_arm(bases[count])
        base, nbase, reference = bases[integration], nodal[integration], nodal[ladder[-1]]
        sy = float(np.linalg.norm(np.diag(base['direct'])))
        discrepancy = error_metrics(paired(nbase['y']), paired(reference['y']), 1e-12*sy)['relative']
        qualified = discrepancy <= THRESHOLDS['reference']
        nodal_rows = {}
        for count in ladder:
            nodal_rows[count] = self.accuracy_row(bases[count], nodal[count], reference, qualified, discrepancy)
            self.record_timing(bases[count], nodal[count], eligible=qualified and count != ladder[-1])
        arms = []
        for fraction in FRACTIONS:
            arm = self.solve_arm(base, fraction)
            row = self.accuracy_row(base, arm, reference, qualified, discrepancy)
            self.record_timing(base, arm, classification='parent_reused_profile', eligible=row['forward_pass'])
            arms.append(arm)
            if fraction == 1:
                equivalence = dict(**self.ledger.context,
                    scaled_state_relative=float(np.linalg.norm(arm['u']-nbase['u'])/np.linalg.norm(nbase['u'])),
                    data_relative=error_metrics(arm['y'], nbase['y'], 1e-12*sy)['relative'],
                    lifted_residual=arm['residual'],
                    unitary_relative=float(np.linalg.norm(arm['p'].conj().T @ arm['p']-np.eye(arm['n']))/np.sqrt(arm['n'])))
                self.controls.append(equivalence)
                if max(equivalence[k] for k in ('scaled_state_relative', 'data_relative', 'lifted_residual', 'unitary_relative')) > 1e-10:
                    raise RuntimeError('Full-mode wiring control failed')
            else:
                projected = arm['p'] @ (arm['p'].conj().T @ nbase['u'])
                weights = np.concatenate([c.arc_length_weights for c in base['curves']])
                for trace, offset in [('dirichlet', 0), ('neumann', len(weights))]:
                    for component in range(len(params)):
                        sl = slice(offset+component*integration, offset+(component+1)*integration)
                        for source in range(len(self.sources)):
                            v = nbase['u'][sl, source]
                            self.tails.append(dict(**self.ledger.context, fraction=fraction, trace=trace,
                                component=component, transmitter=source,
                                native_l2_tail=float(np.linalg.norm(v-projected[sl, source])/np.linalg.norm(v))))
        full = arms[0]
        self.ledger.call('oracle_structure_validation', lambda: self.structure_profiles(base, full))
        patterns = []
        if scene['id'] in ('ellipse', 'star'):
            for width in (4, 8, 16, 32):
                arm = self.solve_arm(base, 1.0, width)
                self.accuracy_row(base, arm, reference, qualified, discrepancy)
                self.record_timing(base, arm, classification='parent_reused_profile')
                h = full['a']-np.eye(full['n'])
                removed = h*(~arm['mask'])
                self.structure.append(dict(**self.ledger.context, profile='fixed', width=width,
                    retained_entries=int(arm['mask'].sum()), total_entries=arm['n']**2,
                    retention_fraction=float(arm['mask'].mean()), identity_entries=arm['n'],
                    whole_system_entries=int(arm['mask'].sum())+arm['n'],
                    relative_frobenius_tail=float(np.linalg.norm(removed)/np.linalg.norm(h)),
                    correction_action_relative=float(np.linalg.norm(removed @ full['z']) /
                        max(np.linalg.norm(h @ full['z']), 1e-300)),
                    storage='complex values only; index overhead and dense parent separately reported'))
                patterns.append(arm)
        derivative_passes = {arm['fraction']: [] for arm in arms}
        nodal_derivative_passes = {count: [] for count in ladder}
        if not multiple:
            kinds = ['translation'] if scene['id']=='circle' else ['translation', 'shape5']
            for kind in kinds:
                derivatives, base_values, assembly_seconds = {}, None, None
                for count in ladder:
                    values, seconds = self.derivative(bases[count], nodal[count], kind)
                    derivatives[count], tangent_times = self.tangent(nodal[count], values)
                    self.record_timing(bases[count], nodal[count], classification='analytic_profile',
                                       derivative_seconds=seconds, tangent_times=tangent_times)
                    if count == integration:
                        base_values, assembly_seconds = values, seconds
                dref = derivatives[ladder[-1]]
                ddiscrepancy = error_metrics(paired(derivatives[integration]), paired(dref), 1e-12*sy/ell)['relative']
                dqualified = qualified and ddiscrepancy <= 2e-5
                for count in ladder:
                    row = self.accuracy_row(bases[count], nodal[count], reference, qualified, discrepancy,
                        direction=kind, dy=derivatives[count], derivative_reference=dref,
                        derivative_qualified=dqualified, derivative_discrepancy=ddiscrepancy)
                    nodal_derivative_passes[count].append(row['sensitivity_pass'])
                for arm in arms+patterns:
                    dy, tangent_times = self.tangent(arm, base_values)
                    row = self.accuracy_row(base, arm, reference, qualified, discrepancy,
                        direction=kind, dy=dy, derivative_reference=dref,
                        derivative_qualified=dqualified, derivative_discrepancy=ddiscrepancy)
                    self.record_timing(base, arm, classification='analytic_profile',
                                       derivative_seconds=assembly_seconds, tangent_times=tangent_times)
                    if arm['method'] == 'modal':
                        derivative_passes[arm['fraction']].append(row['sensitivity_pass'])
                    if kind == 'shape5' and arm['method']=='modal' and arm['fraction']==.5:
                        half_dy = dy
                if kind=='shape5' and frequency==1_250_000_000:
                    half = next(a for a in arms if a['fraction']==.5)
                    self.taylor_probe(base, nbase, half, derivatives[integration], half_dy)
                del values, base_values
        eligible_nodes = [count for count in ladder[:-1] if nodal_rows[count]['forward_pass'] and
                          (multiple or all(nodal_derivative_passes[count]))]
        cheapest = min(eligible_nodes, key=lambda count: nodal[count]['total_seconds']) if eligible_nodes else None
        passing_modal = [a for a in arms if a['fraction'] != 1 and a['residual']<=1e-6 and qualified and
                         error_metrics(paired(a['y']), paired(reference['y']), 1e-12*sy)['relative']<=1e-6 and
                         (multiple or all(derivative_passes[a['fraction']]))]
        best = min(passing_modal, key=lambda a:a['r']) if passing_modal else None
        case = dict(case=scene['id'], frequency_hz=frequency, ell_m=ell,
            component_count=len(params), component_ids=[p.component_id for p in params],
            wavelength_exterior_m=2*np.pi/abs(base['system'].k_exterior),
            object_size_wavelengths=ell*abs(base['system'].k_exterior)/(2*np.pi),
            minimum_gap_m=(None if not multiple else float(min(
                np.min(np.linalg.norm(params[i].discretize(2048).points[:, None, :]-
                                     params[j].discretize(2048).points[None, :, :], axis=-1))
                for i in range(len(params)) for j in range(i)))),
            minimum_gap_method='2048 native samples, Euclidean pair distance; admission checked by production adapter',
            reference_qualified=qualified, reference_discrepancy=discrepancy,
            sensitivity_status='FORWARD_ONLY / SENSITIVITY_UNQUALIFIED' if multiple else 'sampled analytic directions tested',
            cheapest_qualified_nodal_nodes=cheapest,
            smallest_qualified_modal_fraction=None if best is None else best['r']/best['n'],
            smallest_qualified_modal_modes=None if best is None else best['r']//(2*len(params)),
            modal_to_cheapest_nodal_profile_ratio=None if best is None or cheapest is None else
                best['total_seconds']/nodal[cheapest]['total_seconds'])
        self.cases.append(case)
        if self.finalist is None and scene['id'] in ('ellipse', 'star') and frequency==1_250_000_000 and best and cheapest:
            self.finalist = dict(scene=scene, frequency=frequency, ell=ell,
                                 nodes=cheapest, fraction=best['fraction'])
        if scene['id']=='circle' and frequency==500_000_000:
            self.wiring_production_check(bases[64], nodal[64])
        self.checkpoint()
        print(json.dumps(case), flush=True)
        gc.collect()

    def wiring_production_check(self, base, nodal):
        production, seconds = self.ledger.call('production_forward_control', lambda:
            solve_kress_tmz_total_field_batch(base['curves'][0], self.sources, self.receivers,
                2*np.pi*base['frequency'], self.strengths, **self.materials, **self.constants),
            costs=dict(assemblies=1, factorizations=1, solves=1), rhs_count=len(self.sources))
        error = error_metrics(nodal['physical'], production.solution, 1e-300)['relative']
        q, _, _ = synthesis(base['curves'])
        singular, _ = self.ledger.call('small_fixture_singular_value_control', lambda:
            (np.linalg.svd(base['a'], compute_uv=False),
             np.linalg.svd(q.conj().T @ base['a'] @ q, compute_uv=False)))
        sv_error = error_metrics(singular[1], singular[0], 1e-300)['relative']
        self.controls.append(dict(**self.ledger.context, production_state_relative=error,
                                   singular_values_relative=sv_error,
                                   scaled_condition_number=float(singular[0][0]/singular[0][-1])))
        if max(error, sv_error)>1e-10:
            raise RuntimeError('Production assembly/LU or unitary-spectrum wiring failed')

    def taylor_probe(self, base, nodal, half, nodal_dy, half_dy):
        previous = {}
        for amplitude in (1e-4, 5e-5, 2.5e-5, 1.25e-5):
            new_curve = perturb(base['curves'][0], amplitude, 'shape5')
            shifted = self.assemble([new_curve], base['frequency'], base['ell'])
            for method, original, dy, fraction in [('nodal', nodal, nodal_dy, None),
                                                  ('modal_half', half, half_dy, .5)]:
                trial = self.solve_arm(shifted, fraction)
                remainder = float(np.linalg.norm(paired(trial['y']-original['y']-amplitude*dy)))
                ratio = None if method not in previous else previous[method]/remainder
                self.taylor.append(dict(**self.ledger.context, method=method,
                    direction='shape5', amplitude_m=amplitude, absolute_remainder=remainder,
                    previous_to_current_ratio=ratio, expected_ratio=4.0,
                    fixed_scaling_and_basis=True, no_gauge_retraction=True))
                previous[method] = remainder

    def repeat_finalist(self):
        if self.finalist is None:
            self.ledger.emit('finalist_timing', 'skipped', None, reason='No qualified noncircular candidate')
            return
        f = self.finalist
        params = parameterizations(f['scene'])
        # Discovery provided identical prior warm-up. Alternate pair order to reduce drift.
        for repetition in range(3):
            order = ['nodal', 'modal'] if repetition%2==0 else ['modal', 'nodal']
            for method in order:
                self.ledger.context = dict(stage='paired_cold_timing', case=f['scene']['id'], frequency_hz=f['frequency'])
                count = f['nodes'] if method=='nodal' else 128
                curves, geometry_seconds = self.ledger.call('geometry', lambda:[p.discretize(count) for p in params])
                base = self.assemble(curves, f['frequency'], f['ell'])
                base['geometry_seconds'] = geometry_seconds
                arm = self.solve_arm(base, None if method=='nodal' else f['fraction'])
                # Operator assembly needs an actual full base state. For a modal-only
                # cold evaluation that validation state costs an extra nodal LU/solve.
                # Measure and expose this wrapper overhead; never hide it in speed claims.
                if method=='modal':
                    control = self.solve_arm(base)
                    wrapper_seconds = control['timings']['factorization_seconds']+control['timings']['solve_seconds']+control['timings']['receiver_evaluation_seconds']
                else:
                    control, wrapper_seconds = arm, 0.0
                values, derivative_seconds = self.derivative(base, control, 'shape5')
                dy, tangent_times = self.tangent(arm, values)
                row = self.record_timing(base, arm, classification='paired_cold', repetition=repetition,
                    eligible=True, derivative_seconds=derivative_seconds, tangent_times=tangent_times)
                row['validation_base_wrapper_seconds'] = wrapper_seconds
                row['forward_plus_one_jvp_seconds'] += wrapper_seconds
                row['load_average_1m'] = os.getloadavg()[0]
                del base, arm, control, values, dy
                gc.collect()
        self.checkpoint()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    snapshot = json.loads(Path('experiments/bie002_modal_diagnostic/workspace_before.json').read_text())
    acquisition, scenes = inputs()
    source_hashes = snapshot['numerical_sha256']
    ledger = Ledger(output, source_hashes)
    # Import/metadata-only startup failures preceded this run. Conservatively
    # reserve two seconds; no physical operators or algebra tests executed.
    ledger.started -= 2.0
    ledger.emit('startup_metadata', 'failed', 2.0,
                reason='Two startup attempts: threadpoolctl unavailable, then NumPy get_info unavailable; zero assemblies/factors/solves. See sibling bundle -01.')
    campaign = Campaign(output, ledger, acquisition)
    manifest = dict(run_id=output.name, contract='BIE-002', approval='APPROVED',
        approval_source='User: follow new ZIP; go as far as possible; all permission except creating git branches',
        execution_status='IN PROGRESS', workspace_before=snapshot,
        experiment_sha256={str(p):digest(p) for p in Path('experiments/bie002_modal_diagnostic').glob('*.py')},
        plan_sha256=digest('docs/iterations/boundary_bie/iteration_01/03_plan.md'),
        acquisition=acquisition, scenes=scenes, thresholds=THRESHOLDS, limits=LIMITS,
        numerical_seconds_cap=1800, rss_cap_bytes=8*1024**3, seed=20260915,
        numpy=np.__version__, scipy=scipy.__version__, python=sys.version,
        machine=platform.uname()._asdict(), blas=threadpool_info(),
        cpu=subprocess.check_output(['lscpu'], text=True),
        initial_load=os.getloadavg(), numerical_workers=1,
        reference_ladders=dict(single=[64,128,256], multiple=[64,128,256,512]),
        integration_nodes=dict(single=128, multiple=256), retained_fractions=FRACTIONS,
        directions=dict(circle=['translation'], noncircular_single=['translation','shape5']),
        source_scale='norm of paired incident receiver response per scene/frequency',
        residual_transform='paired scattered field; concatenate real/imag; scalar normalization fixed by finest response norm',
        multi_component_derivatives='UNSUPPORTED; SENSITIVITY_UNQUALIFIED',
        source_guard='Read-only numerical modules; stop on source hash drift',
        timing_note='parent-reused profile sums measured parent assembly; paired_cold rebuilds parent every time')
    write_json(output/'manifest.json', manifest)
    command = 'OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.bie002_modal_diagnostic.run_diagnostic --output '+str(output)
    (output/'commands.md').write_text('# Actual campaign command\n\n```bash\n'+command+'\n```\n\nThe runner executes the algebra tests before physical assemblies. All numerical work is in this process except that counted test subprocess.\n')
    def time_limit(signum, frame):
        raise BudgetStop('1800-second numerical wall-clock cap reached')
    signal.signal(signal.SIGALRM, time_limit)
    signal.setitimer(signal.ITIMER_REAL, 1800)
    failure = None
    try:
        tests, seconds = ledger.call('algebra_tests', lambda: subprocess.run(
            [sys.executable,'-m','pytest','-q','experiments/bie002_modal_diagnostic/test_modal_projection.py'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
        (output/'tests.log').write_text(tests.stdout)
        if tests.returncode:
            raise RuntimeError('Algebra tests failed before physical execution')
        for scene in scenes:
            for frequency in acquisition['frequencies_hz']:
                campaign.run_case(scene, frequency)
        campaign.repeat_finalist()
        ledger.check_source()
    except BaseException as exc:
        failure = repr(exc)
        (output/'failure.log').write_text(traceback.format_exc())
        print(traceback.format_exc(), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        campaign.checkpoint()
        manifest.update(execution_status='COMPLETE' if failure is None else 'STOPPED', failure=failure,
            counts=ledger.counts, numerical_seconds=ledger.elapsed(), final_load=os.getloadavg(),
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            source_hashes_after={p:digest(p) for p in source_hashes})
        write_json(output/'manifest.json', manifest)
        print(json.dumps(dict(status=manifest['execution_status'], failure=failure,
                              counts=ledger.counts, seconds=ledger.elapsed())), flush=True)
    return 0 if failure is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
