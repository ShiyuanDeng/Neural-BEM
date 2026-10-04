"""Read-only PC-002 receipt validation; no inverse solves or truth loading."""
import hashlib
import json
import subprocess
from pathlib import Path
from statistics import median
from . import campaign as c, scenes as S
from .pc002 import OUTPUT


def validate():
    manifest = json.loads((OUTPUT/'NS/manifest.json').read_text())
    protocol = json.loads((OUTPUT/'protocol.json').read_text())
    assert c.verify(require_inputs=True)['inputs_sealed']
    assert manifest['cases'] == list(S.CASES)
    for path, digest in protocol['numerical_sources'].items():
        content = subprocess.check_output(['git', 'show', manifest['commit']+':'+path], cwd=c.ROOT)
        assert hashlib.sha256(content).hexdigest() == digest, path
    rows = {p.parent.name: json.loads(p.read_text()) for p in (OUTPUT/'NS/runs').glob('*/result.json')}
    assert set(rows) == set(S.CASES)
    reference_passes, native_passes, failures = 0, 0, []
    for case, result in rows.items():
        assert result['case']['id'] == case and result['settings'] == manifest['settings']
        assert result['outcome'] != 'WORKER_EXCEPTION'
        assert result['fit_and_localization_units'] == result['fit_work']['work_units']
        assert result['total_units'] == result['fit_and_localization_units']+result['audit_units']
        counts = result['physics']['counts']
        assert counts['evaluation_attempts']+counts['derivative_attempts'] == result['total_units'], case
        assert not result['physics']['fallback_reasons']
        assert result['physics']['component_devices']['LU']['cpu'] == 0
        assert result['physics']['geometry_cache']['entries'] == 0
        for stage in result['stages']:
            selected = stage['resolution_selection']
            assert selected['selected'] == stage['nodes']
            assert selected['attempts'][-1]['passed'] and stage['nodes'] in (130, 386)
            assert stage['nodes'] > 2*stage['K_geometry']
            assert max(selected['attempts'][-1]['jacobian_relative']) <= 1e-3
        tolerances = [1e-5 if o.frequency_hz <= .5e9 else 1e-7 for o in c.problem(case).real]
        for name in ('initial_audit.json', 'final_audit.json'):
            audit = json.loads((OUTPUT/'NS/runs'/case/name).read_text())
            assert (audit['reference_nodes'], audit['reference_refined_nodes']) == (1024, 2048)
            assert all(x <= t for x,t in zip(audit['reference_field_relative'], tolerances)), (case,name)
            assert max(audit['reference_jacobian_relative']) <= 1e-3
            assert audit['full_trial_fd_relative'] <= 1e-3
            reference_passes += 1
            native_passes += bool(audit['passed'])
        if not result['recovered']:
            failures.append(dict(case=case, outcome=result['outcome'], detail=result['detail'],
                final_audit_passed=result['final_audit_passed'], rms_mm=result['metrics']['rms_mm']))
    recovered = {case for case,r in rows.items() if r['recovered']}
    comparisons = {}
    for arm in ('M1', 'N1', 'N0'):
        oldroot = c.ROOT/'results/validation/cleaned_interfaces/PC-001'/arm/'runs'
        old = {p.parent.name: json.loads(p.read_text()) for p in oldroot.glob('*/result.json')}
        if arm in ('M1', 'N1'):
            assert recovered == {k for k,v in old.items() if v['recovered']}
        common = sorted(set(rows)&set(old))
        comparisons[arm] = dict(compared=len(common), historical_case_workers=2, current_case_workers=1,
            old_median_fit_seconds=median(old[k]['fit_and_localization_seconds'] for k in common),
            new_median_fit_seconds=median(rows[k]['fit_and_localization_seconds'] for k in common),
            same_recovery_set=all(rows[k]['recovered'] == old[k]['recovered'] for k in common),
            controlled_speedup=False)
    result = dict(passed=True, cases=30, recovered=len(recovered),
        initial_and_final_reference_audits_passed=reference_passes,
        initial_and_final_native_audits_passed=native_passes, accounting_matches_all_cases=True,
        numerical_source_hashes_match_fit_commit=True, inputs_seal_verified=True,
        failures=failures, historical_fit_comparisons=comparisons)
    (OUTPUT/'validation/result-bundle.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    validate()
