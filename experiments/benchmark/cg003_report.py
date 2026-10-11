"""Read-only CG-003 validation and numerical report; no physics or fitting."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT/'results/validation/complex_geometry/CG-003/run-01'


def read(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def z(value):
    return complex(*value) if isinstance(value, list) else complex(value)


def validate(folder):
    outcome, manifest = read(folder/'outcome.json'), read(folder/'manifest.json')
    for name, digest in manifest['source_hashes'].items():
        assert hashlib.sha256((folder/'source_snapshot'/name).read_bytes()).hexdigest() == digest, name
    assert outcome['sources_unchanged']
    maximum_residual = 0.
    state_count = rejected = 0
    for name, summary in outcome['arms'].items():
        receipt = read(folder/summary['path'])
        states = receipt['states']
        assert len(states) == summary['accepted_states'], name
        assert len(receipt['rejected']) == summary['rejected_steps'], name
        state_count += len(states)
        rejected += len(receipt['rejected'])
        for row in states:
            q, t = z(row['q']), z(row['t'])
            assert .5-1e-12 <= q.real <= 2+1e-12 and abs(q.imag) < .5, name
            assert -2-1e-12 <= t.real <= 3+1e-12, name
            maximum_residual = max(maximum_residual, abs(z(row['F']))/row['scale'])
        if receipt['numerically_qualified']:
            checks = receipt['refined_checks']
            assert checks and all(max(c[k] for k in
                ('field', 'stationarity', 'coarse_stationarity', 'Fq_relative')) <= 1e-8 for c in checks), name
        if receipt['status'] == 'COMPLETED' and receipt.get('waypoints'):
            assert abs(z(states[-1]['t'])-z(receipt['waypoints'][-1])) <= 1e-10, name
    assert maximum_residual <= 1e-8
    if outcome['status'] == 'CONFIRMED_REAL_MINIMUM':
        check = outcome['success']
        assert check['passed'] and check['reverse_completed']
        assert max(check[k] for k in ('half_error', 'fine_error', 'half_fine_error', 'reverse_error')) <= 1e-7
        assert check['half_endpoint']['qualified_real_minimum'] and check['fine_endpoint']['qualified_real_minimum']
        assert check['nodal']['passed'] and max(check['nodal'][k] for k in
            ('nodal_error', 'refined_nodal_error', 'nodal_refinement')) <= 1e-8
        for name in check['ancestry']:
            arm = read(folder/outcome['arms'][name]['path'])
            assert arm['refinement_scope'] == 'every_accepted_state'
            assert len(arm['refined_checks']) == len(arm['states'])
    transitions = Counter()
    for edge in outcome['edges']:
        if edge['status'] in ('KNOWN_ROOT', 'NEW_QUALIFIED_ROOT'):
            target = edge.get('child', edge['nearest_node'])
            assert abs(z(edge['endpoint']['q'])-z(outcome['nodes'][target]['endpoint']['q'])) <= 1e-7
            transitions['identity' if edge['parent'] == target else 'changed_root'] += 1
    return outcome, dict(validated=True, source_snapshot_files=len(manifest['source_hashes']),
        arms=len(outcome['arms']), accepted_states=state_count, rejected_steps=rejected,
        maximum_stored_scaled_stationarity=maximum_residual,
        edge_status_counts=dict(Counter(e['status'] for e in outcome['edges'])),
        observed_transition_counts=dict(transitions),
        outcome_sha256=hashlib.sha256((folder/'outcome.json').read_bytes()).hexdigest())


def number(value):
    return '—' if value is None else f'{value:.9g}'


def report(folder=DEFAULT):
    folder = Path(folder)
    out, checked = validate(folder)
    lines = ['# CG-003 — measured loop-search results', '',
        f'**{out["status"]}**. Fixed-center TG-002 circle instrument, contrast 13.3, 1.5 GHz.', '',
        f'{out["discovery_loops"]} discovery loops; {out["expanded_roots"]} expanded roots; '
        f'{out["distinct_qualified_roots"]} distinct numerically qualified t=1 roots.', '',
        '| Endpoint | Re(radius), mm | Im(radius), mm | Measured loss | Relative residual | Hessian Fq |',
        '|---|---:|---:|---:|---:|---:|']
    initial = out['initial']
    lines.append(f'| Initial radius (not stationary at t=1) | 65 | 0 | '
        f'{number(initial["measured_data_loss"])} | {number(initial["relative_residual"])} | '
        f'{number(z(initial["measured_state"]["Fq"]).real)} |')
    for node in out['nodes']:
        row = node['endpoint']; radius = 50*z(row['q'])
        kind = 'minimum' if row['qualified_real_minimum'] else ('real stationary' if row['real'] else 'complex stationary')
        lines.append(f'| Root {node["id"]}: {kind} | {radius.real:.12g} | {radius.imag:.8g} | '
            f'{number(row["data_loss"])} | {number(row["relative_residual"])} | {number(row["hessian"])} |')
    lines += ['', 'Loss is the normalized measured-data objective at t=1. '
        'Its relative field residual is sqrt(2*loss); a nonreal radius has no reported physical loss.', '',
        '| Real control | Stop | Final radius, mm | Final t | Maximum sampled t | t=1 crossings |',
        '|---|---|---:|---:|---:|---:|']
    for name, control in out['controls'].items():
        if 'status' not in control:
            continue
        arm = read(folder/out['arms'][name]['path'])
        states = arm['states']
        count = sum(c.get('qualified', False) and not c.get('duplicate', False) for c in control['crossings'])
        lines.append(f'| {name} | {control["status"]} | {50*z(states[-1]["q"]).real:.12g} | '
            f'{z(states[-1]["t"]).real:.12g} | {max(z(s["t"]).real for s in states):.12g} | {count} |')
    lines += ['', 'Real controls follow the same start-connected graph in both radius directions, '
        'with original and half radius steps. They do not reconnect beyond a refusal.', '',
        'Edge outcomes: '+', '.join(f'{k}: {v}' for k, v in checked['edge_status_counts'].items())+'.']
    lines += ['', 'Observed transitions: '+', '.join(
        f'{k}: {v}' for k, v in checked['observed_transition_counts'].items())+'.', '',
        '| Nonidentity action | Fold-center t | Starting root | Ending root |',
        '|---|---:|---:|---:|']
    for edge in out['edges']:
        if edge['status'] not in ('KNOWN_ROOT', 'NEW_QUALIFIED_ROOT'):
            continue
        target = edge.get('child', edge['nearest_node'])
        if edge['parent'] != target:
            lines.append(f'| {edge["arm"]} | {edge["fold"]["t"]:.12g} | {edge["parent"]} | {target} |')
    lines += ['', 'These observed actions concern the fixed attachment paths and 1e-7 root '
        'deduplication threshold. They do not certify the full monodromy group or exclude '
        'other paths, complex critical values, or unresolved roots.']
    if out.get('success'):
        success = out['success']
        lines += ['', 'Successful ancestry: `'+' → '.join(success['ancestry'])+'`.', '',
            '| Verification | Error |', '|---|---:|']
        for label, key in (('Full half-step endpoint, q units', 'half_error'),
                           ('Full finer-cutoff endpoint, q units', 'fine_error'),
                           ('Full reversal to prescribed start, q units', 'reverse_error')):
            lines.append(f'| {label} | {success[key]:.4g} |')
        for key in ('nodal_error', 'nodal_refinement'):
            lines.append(f'| {key} | {success["nodal"][key]:.4g} |')
    lines += ['', f'Wall time including controls, failures and confirmation: **{out["seconds"]:.2f} s**. '
        f'Peak process RSS: {out["peak_rss_mib"]:.1f} MiB.',
        f'Production frequency/radius jets: {out["counters"]["frequency_evaluations"]:,}; '
        f'refinement jets: {out["refined_counters"]["frequency_evaluations"]:,}; '
        f'independent nodal solves: {out["nodal_solves"]}.', '',
        'These are complete search/verification costs, not a runtime comparison against a general inverse solver.', '',
        '[Frozen plan](../../../../../docs/iterations/complex_geometry/CG-003_plan.md) · '
        '[Raw outcome](outcome.json) · [Receipt validation](validation.json)', '',
        'Reproduce without field evaluations: `python -m experiments.benchmark.cg003_report`.', '']
    (folder/'report.md').write_text('\n'.join(lines))
    (folder/'validation.json').write_text(json.dumps(checked, indent=2)+'\n')
    print(json.dumps(checked, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT)
    report(parser.parse_args().output)
