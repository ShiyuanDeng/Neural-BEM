"""Recompute review comparisons from receipts and original stage archives."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parent
ARCHIVE = Path('results/validation/modal_atlas/MA-005/runs')


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for label, arm in [('stage_2_damped', 'D'), ('release_M11', 'D'), ('fixed_M43', 'DF')]:
        saved = read(ROOT/f'replay_{label}.json')
        actual = saved['native_result']
        expected = read(ARCHIVE/arm/'c13.3/shifted_rotated_c'/f'{label}.json')
        keys = ('iteration', 'damping', 'backtrack', 'status')
        trials_equal = ([tuple(r[k] for k in keys) for r in actual['trials']] ==
                        [tuple(r[k] for k in keys) for r in expected['trials']])
        accepted_indices_equal = ([r['iteration'] for r in actual['history']] ==
                                  [r['iteration'] for r in expected['history']])
        work = expected['work']
        solves = sum(v for k, v in work['solves'].items() if k.startswith(label+':'))
        derivatives = sum(v for k, v in work['reciprocal_batches'].items() if k.startswith(label+':'))
        counts = saved['comparison']['counts']
        work_equal = solves == counts['evaluations'] and derivatives == counts['derivatives']
        same_exit = actual['outcome'] == expected['outcome'] and actual['stop_reason'] == expected['stop']
        native_coeff = np.array([complex(v['real'], v['imag'])
                                 for v in actual['curve']['coefficients']])
        ref_coeff = np.asarray(expected['curve']['real'])+1j*np.asarray(expected['curve']['imag'])
        delta = native_coeff-ref_coeff
        band = len(delta)//2
        spectrum = np.zeros(8192, complex)
        spectrum[np.arange(-band, band+1)%8192] = delta
        endpoint = float(np.max(abs(np.fft.ifft(spectrum)*8192)))
        row = dict(stage=label, trials=len(actual['trials']), accepted_steps=actual['accepted_steps'],
                   trials_equal=trials_equal, accepted_indices_equal=accepted_indices_equal,
                   stage_work_equal=work_equal, same_exit=same_exit, solves=solves,
                   reciprocal_batches=derivatives, endpoint_maximum_difference_units=endpoint,
                   endpoint_maximum_difference_metres=.05*endpoint,
                   coefficient_difference=float(np.linalg.norm(delta)),
                   final_loss=actual['final_loss'], archived_loss=expected['final_loss'],
                   final_loss_relative=abs(actual['final_loss']/expected['final_loss']-1))
        assert trials_equal and accepted_indices_equal and work_equal and same_exit, row
        rows.append(row)
    claims = read(ROOT/'claims.json')['result']
    example = claims['parseval_counterexample']
    assert example['beta'] > 0 and example['exact_W_squared_minimum'] == 0
    assert example['max_norm_degrees_1_to_1000'] < 1
    upper = example['upper_counterexample']
    assert upper['max_norm_through_60'] < 1 and upper['padded_tau'] < upper['exact_R_maximum']
    # Every recorded local script digest resolves to an available source version.
    versions = {digest(p): str(p.relative_to(ROOT)) for p in ROOT.rglob('*.py')}
    for path in ROOT.glob('*.json'):
        if path.name in ('summary.json', 'manifest.json'):
            continue
        receipt = read(path)
        for name, value in receipt.get('source_hashes', {}).items():
            assert value in versions, (path, name, value)
        if 'script_sha256' in receipt:
            assert receipt['script_sha256'] in versions, path
    numeric = [
        'experiments/modal_muller_research/coefficient_operator.py',
        'experiments/modal_muller_research/coefficient_fields.py',
        'experiments/modal_muller_research/modal.py',
        'experiments/shape_continuation/forward.py',
        'experiments/shape_continuation/geometry.py',
        'experiments/shape_continuation/updates.py',
        'experiments/shape_continuation/lm_backend.py',
        'experiments/cleaned_interface/geometry.py',
        'solvers/gpr_bem_kress/system.py',
        'solvers/gpr_bem_kress/operators.py',
    ]
    numeric = [Path(p) for p in numeric if Path(p).exists()]
    summary = dict(
        verdict='Kernel fix independently supported; finite Parseval certificates disproved.',
        replays=rows, all_replay_decisions_and_work_match=True,
        all_endpoints_below_pdf_6e_minus13_units=all(r['endpoint_maximum_difference_units'] <= 6e-13 for r in rows),
        full_backend_qualification=False, matched_runtime_claim=False,
        baseline_native_tests=dict(passed=30, seconds=8.11),
        git_head=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                         blas_threads=1, frequency_threads=1, device='cpu',
                         timing_limitation='Some independent processes ran concurrently.'),
        pdf_sha256=digest(Path('docs/iterations/cleaned_interfaces/node_free_modal_muller_summary.pdf')),
        numerical_source_hashes={str(p): digest(p) for p in numeric},
        available_review_source_versions=versions,
        receipt_hashes={p.name: digest(p) for p in ROOT.glob('*.json') if p.name != 'summary.json'},
    )
    (ROOT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(replays=rows, all_decisions_and_work_match=True), indent=2))


if __name__ == '__main__':
    main()
