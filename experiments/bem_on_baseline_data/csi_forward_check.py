"""Adapter checks for CSI tables, one resumable command (first used at review stop 2).

Truth is read here only. The mismatch is saved per frequency and never passed to a fit.
Checks (plan.md): calibration against CC-CSI's saved factors, conjugation and unit field on
the simulated table, the row permutation, mismatch per frequency at two resolutions, the
solver's own wave radius and series loss at 8 GHz, and one ragged-vs-rectangular B5/B8
evaluation at the start circle.
"""
from csi_runtime import ROOT, provenance, peak_memory_gib  # noqa: E402  first: pins BLAS/OpenMP threads before numpy loads
import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from bem_inverse import Execution, FourierCurve
from bem_inverse.a1_geometry import EPS, WaveArrays
from bem_inverse.b5_residual import evaluate, evaluate_blocks
from bem_inverse.b8_gauss_newton import block_jacobian, residual_jacobian
from bem_inverse.continuation.geometry import resize
from bem_inverse.data_blocks import FrequencyBlocks
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings, forward_solve
from bem_inverse.geometry_selection import make_update
from bem_inverse.material import MaterialUnknown
from bem_inverse.policy import CumulativePolicy
from bem_inverse.stage_types import BackendConfig
from scipy.special import h1vp, hankel1, i0e, jv, jvp

import csi_data as D
from experiments.benchmark import scenes as S

CSI_FACTORS = ROOT/'results/csi/fresnel/2026-11-17_diel_tm/source_calibration.csv'
STORAGE = CumulativePolicy().storage_band            # 192, the whole-catalog storage band
START = FourierCurve.circle(S.START_RADIUS_M/D.LENGTH_M, 0j)
CASES = dict(
    dielTM_dec8f=dict(path=D.MEASURED, truth=lambda: FourierCurve.circle(.015/D.LENGTH_M, .030j/D.LENGTH_M),
                      contrast=3., truth_note='nominal: centre (0,+30) mm, radius 15 mm, permittivity 3 +/- 0.3'),
    circle__c4=dict(path=ROOT/D.SIMULATED.format(shape='circle'), truth=lambda: S.truth_fixture('circle'),
                    contrast=4., truth_note='frozen TG-002 truth_fixture("circle"), permittivity 4'))


def relative(a, b):
    return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def series(curve, k_units):
    radius = WaveArrays(curve.coefficients, 1).radius
    x = abs(k_units)*radius
    return dict(wave_radius_mm=radius*D.LENGTH_M*1e3, k_times_radius=x,
                series_loss=float(EPS*i0e(x)*np.exp(x)), passes_1e9=bool(EPS*i0e(x)*np.exp(x) <= 1e-9))


def calibration_check(frequencies):
    rows = list(csv.DictReader(CSI_FACTORS.open()))
    errors = []
    for row in rows:
        entry = next(f for f in frequencies if f.frequency_hz == float(row['frequency_GHz'])*1e9)
        theirs = np.conj((float(row['factor_real'])+1j*float(row['factor_imag']))*float(row['normalized_omega'])**2)
        errors.append(abs(entry.factors[int(row['source'])-1]-theirs)/abs(theirs))
        assert int(row['receiver_within_source_1based'])-1 == entry.calibration_rows[0] % (len(entry.sources)//D.NTX)
    spread = [dict(frequency_ghz=f.frequency_hz/1e9, abs_min=float(abs(f.factors).min()),
                   abs_max=float(abs(f.factors).max()),
                   max_over_min=float(abs(f.factors).max()/abs(f.factors).min()),
                   std_over_mean=float(abs(f.factors).std()/abs(f.factors).mean()),
                   phase_spread_deg=float(np.ptp(np.degrees(np.angle(f.factors/f.factors.mean())))))
              for f in frequencies]
    return dict(rows=len(rows), max_relative_difference=float(max(errors)),
                passes=bool(len(rows) == 8*D.NTX and max(errors) <= 1e-10), abs_factor_spread=spread)


def simulated_unit_field_check(frequencies):
    tx, rx = D.source_positions_m(), D.receiver_positions_m()
    out = []
    for f in frequencies:
        ours = D.unit_field(f.k_m, np.linalg.norm(rx[f.receivers]-tx[f.sources], axis=1))
        out.append(dict(frequency_ghz=f.frequency_hz/1e9, conj_incident_vs_unit_field=relative(f.incident, ours),
                        factor_minus_one_max=float(abs(f.factors-1).max())))
    worst = max(max(o['conj_incident_vs_unit_field'], o['factor_minus_one_max']) for o in out)
    return dict(per_frequency=out, worst=worst, passes=bool(worst <= 1e-10))


def permutation_check(frequencies):
    worst = 0.
    for f in frequencies:
        back = D.to_file_order(f, f.data)*f.factors[f.sources]
        worst = max(worst, float(np.max(abs(back-(f.total-f.incident)))))
    return dict(max_abs_difference=worst, passes=worst == 0. or worst < 1e-15)


def is_circle(curve):
    return curve.band == 1 and abs(curve.coefficients[0]) <= 1e-12*abs(curve.coefficients[2])


def exact_circle(curve, contrast, obs):
    """Independent separation-of-variables solution for a penetrable circle (TM, equal density)."""
    c, a = curve.coefficients[curve.band], abs(curve.coefficients[curve.band+1])
    assert is_circle(curve), 'exact solution needs a circle'
    k = obs.wavenumber
    k1, acq = k*np.sqrt(contrast), obs.acquisition
    n = np.arange(-int(k*a+40), int(k*a+40)+1)[:, None]
    t = -((k*jvp(n, k*a)*jv(n, k1*a)-k1*jv(n, k*a)*jvp(n, k1*a)) /
          (k*h1vp(n, k*a)*jv(n, k1*a)-k1*hankel1(n, k*a)*jvp(n, k1*a)))
    zs = acq.sources[:, 0]+1j*acq.sources[:, 1]-c
    zr = acq.receivers[:, 0]+1j*acq.receivers[:, 1]-c
    incoming = .25j*hankel1(n, k*abs(zs)[None])*np.exp(-1j*n*np.angle(zs)[None])
    outgoing = hankel1(n, k*abs(zr)[None])*np.exp(1j*n*np.angle(zr)[None])
    return np.einsum('ns,nr->sr', t*incoming, outgoing)[acq.mask]


def forward_mismatch(name, spec, context, arrays):
    real, frequencies, source = D.observations(spec['path'])
    truth = spec['truth']()
    out = []
    for label, curve in (('truth_band', truth), ('storage_192', resize(truth, STORAGE))):
        nodes = context.resolution_profile(curve.band)['production']
        for obs in real:
            started = time.perf_counter()
            state = forward_solve(curve, obs, spec['contrast'], nodes, context=context)
            p, d = np.asarray(state.prediction).reshape(-1), obs.scattered
            alpha = np.vdot(p, d)/np.vdot(p, p)
            out.append(dict(resolution=label, nodes=nodes, frequency_ghz=obs.frequency_hz/1e9,
                            k_units=obs.wavenumber, relative_mismatch=relative(p, d),
                            info_best_scalar=dict(abs=float(abs(alpha)), phase_deg=float(np.degrees(np.angle(alpha))),
                                                  mismatch_after=relative(alpha*p, d)),
                            data_norm=float(np.linalg.norm(d)), seconds=time.perf_counter()-started,
                            diagnostics={k: v for k, v in state.diagnostics.items()
                                         if isinstance(v, (int, float, str, bool))}))
            if is_circle(truth):
                exact = exact_circle(truth, spec['contrast'], obs)
                out[-1]['exact_series'] = dict(ours_vs_exact=relative(p, exact), data_vs_exact=relative(d, exact))
            arrays[f'{name}_{label}_{obs.frequency_hz/1e9:g}GHz'] = p
    top = real[-1].wavenumber
    return dict(source=source, truth=spec['truth_note'], contrast=spec['contrast'], per_frequency=out,
                series_8ghz=dict(truth=series(truth, top), start=series(START, top)))


def layout_check(context):
    """One B5/B8 evaluation at the start circle: ragged blocks vs the default rectangular map."""
    real, _, _ = D.observations(D.MEASURED)
    curve = resize(START, STORAGE)
    nodes = context.resolution_profile(STORAGE)['production']
    weak = forward_solve(curve, real[0], 1.+1e-3, nodes, context=context)
    p, d = np.asarray(weak.prediction).reshape(-1), real[0].scattered
    contrast = max(1.+1e-3*float(np.real(np.vdot(p, d))/np.real(np.vdot(p, p))), .05)
    update, _ = make_update('slider', D.LENGTH_M, context.execution)
    band = CumulativePolicy().release_bands[0]
    space = update.prepare(curve, band, STORAGE)
    weights = tuple(np.ones(len(real))/len(real))
    floor = BackendConfig().residual_floor
    step = MaterialUnknown().derivative_step
    states, blocks = [], []
    for obs in real:
        state = forward_solve(curve, obs, contrast, nodes, context=context)
        shifted = forward_solve(curve, obs, contrast*np.exp(step), nodes, context=context)
        column = (np.asarray(shifted.prediction).reshape(-1)-np.asarray(state.prediction).reshape(-1))/step
        block = context.derivative(state, update, space)
        blocks.append(np.column_stack((block.reshape(-1, block.shape[-1]), column)))
        states.append(state)
    predictions = tuple(np.asarray(s.prediction).reshape(-1) for s in states)
    observed = np.column_stack([o.scattered for o in real])
    rect = evaluate(curve, np.column_stack(predictions), states, observed, weights, floor)
    layout = FrequencyBlocks.from_observations(real, weights, floor)
    ragged = evaluate_blocks(curve, predictions, states, layout)
    J_rect = residual_jacobian(blocks, observed, weights, floor)
    J_ragged = block_jacobian(blocks, layout)
    # Row orders differ by design: rectangular rows are (pair, frequency) C order, ragged rows
    # are frequency blocks. Both stack all real parts, then all imaginary parts.
    n, m = observed.shape
    order = np.arange(n*m).reshape(n, m).T.reshape(-1)
    order = np.concatenate((order, order+n*m))
    r_diff = float(np.max(abs(rect.residual[order]-ragged.residual))/np.max(abs(rect.residual)))
    J_diff = float(np.max(abs(J_rect[order]-J_ragged))/np.max(abs(J_rect)))
    return dict(case='dielTM_dec8f', curve='start circle 65 mm at storage band 192', update_band=band,
                weak_start_contrast=contrast, frequencies=len(real), parameters=int(J_rect.shape[1]),
                rectangular_branch_accepts_masked_table=True,
                loss=dict(rectangular=rect.loss, ragged=ragged.loss,
                          relative_difference=abs(rect.loss-ragged.loss)/rect.loss),
                residual_max_relative_difference=r_diff, jacobian_max_relative_difference=J_diff,
                gradient_relative_difference=relative(J_ragged.T@ragged.residual, J_rect.T@rect.residual),
                passes=bool(r_diff < 1e-12 and J_diff < 1e-12))


def case_spec(case):
    if case in CASES:
        return CASES[case]
    shape, contrast = case.split('__c')
    return dict(path=ROOT/D.SIMULATED.format(shape=shape), truth=lambda: S.truth_fixture(shape),
                contrast=float(contrast), truth_note=f'frozen TG-002 truth_fixture("{shape}"), permittivity {contrast}')


def check_case(case, context, out, layout):
    """All adapter checks for one table; resumable: an existing <case>.json is kept and skipped."""
    target = out/f'{case}.json'
    if target.exists():
        print(f'{case}: checked already, {target}', flush=True)
        return json.loads(target.read_text())
    started = time.perf_counter()
    spec = case_spec(case)
    frozen = None if case == 'dielTM_dec8f' else D.verify_sha256(spec['path'])
    _, frequencies, _ = D.read_table(spec['path'])
    record = dict(case=case, provenance=provenance(), input=str(spec['path']), frozen_sha256_verified=frozen,
                  permutation=permutation_check(frequencies))
    if case == 'dielTM_dec8f':
        record['calibration_vs_csi'] = calibration_check(frequencies)
    else:
        record['simulated_unit_field'] = simulated_unit_field_check(frequencies)
    arrays = {}
    record['mismatch'] = forward_mismatch(case, spec, context, arrays)
    if layout:
        record['layout'] = layout_check(context)
    from csi_fit import DATASETS, dataset
    selected = DATASETS[dataset(case)]['frequencies_ghz']
    rule = [r for r in record['mismatch']['per_frequency']
            if selected is None or r['frequency_ghz'] in selected]
    worst = max(r['relative_mismatch'] for r in rule)
    if selected is not None:
        top = max(selected)*1e9*2*np.pi/D.C0*D.LENGTH_M
        record['mismatch']['series_top_selected'] = dict(frequency_ghz=max(selected),
            truth=series(spec['truth'](), top), start=series(START, top))
    adapter = [record['permutation']['passes'],
               record.get('calibration_vs_csi', record.get('simulated_unit_field'))['passes'],
               *([record['layout']['passes']] if layout else []),
               record['mismatch']['series_8ghz']['truth']['passes_1e9'],
               record['mismatch']['series_8ghz']['start']['passes_1e9']]
    record['summary'] = dict(adapter_checks_pass=bool(all(adapter)), dataset=dataset(case),
                             rule_frequencies_ghz=selected, worst_truth_mismatch_on_rule_frequencies=worst,
                             one_percent_rule=None if case == 'dielTM_dec8f' else bool(worst <= .01),
                             wall_seconds=time.perf_counter()-started, peak_memory_gib=peak_memory_gib())
    target.write_text(json.dumps(record, indent=2, default=float)+'\n')
    np.savez_compressed(out/f'{case}_truth_predictions.npz', **arrays)
    print(case, json.dumps(record['summary'], default=float), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description='Adapter checks per CSI table, resumable per case.')
    parser.add_argument('--out', required=True)
    parser.add_argument('--cases', nargs='+', default=['dielTM_dec8f', 'circle__c4'],
                        help='dielTM_dec8f and/or simulated <shape>__c4')
    parser.add_argument('--layout', action='store_true', help='also the ragged-vs-rectangular B5/B8 check')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    context = ModalMuller(Execution(device='cpu', frequency_threads=1), ModalSettings(table_mode=True))
    summaries = {case: check_case(case, context, out, args.layout)['summary'] for case in args.cases}
    print(json.dumps(summaries, indent=1, default=float))
    if not all(s['adapter_checks_pass'] for s in summaries.values()):
        raise SystemExit('An adapter check failed; see the case files.')


if __name__ == '__main__':
    main()
