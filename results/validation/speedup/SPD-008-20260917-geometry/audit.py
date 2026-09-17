"""File-only SPD-008 closeout checks. Never imports or calls a numerical solver."""
import hashlib
import json
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
ROOT = BUNDLE.parents[3]
SCENES = ('death', 'merge', 'central-ellipse-star', 'far-two-stars')


def read(path):
    return json.loads(path.read_text())


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def verify_hashes(mapping, base):
    for name, expected in mapping.items():
        assert digest(base / name) == expected, str(base / name)
    return len(mapping)


def verify_archived_attempt_inputs():
    count = 0
    for manifest in sorted(BUNDLE.glob('*_attempt_*/manifest.json')):
        suffix = manifest.parent.name.split('_attempt_')[1]
        for name, expected in read(manifest)['input_sha256'].items():
            path = ROOT / name
            if name == 'docs/iterations/speedup/iteration_07/03_plan.md':
                path = BUNDLE / f'campaign_attempt_{suffix}' / 'approved_plan.md'
            elif path.is_relative_to(BUNDLE):
                relative = path.relative_to(BUNDLE)
                if relative.parts[0] in ('geometry', 'updates', 'campaign'):
                    path = BUNDLE / (relative.parts[0] + '_attempt_' + suffix) / Path(*relative.parts[1:])
                elif relative.name in ('tests.json', 'tests.log'):
                    path = BUNDLE / (relative.name + '_attempt_' + suffix)
            assert digest(path) == expected, str(path)
            count += 1
    return count


def reconcile(work):
    total = 0
    assert work['total_attempted'] == sum(work['attempted'].values())
    for prefix in ('', 'derivative_assemblies_', 'reciprocal_batches_', 'compiled_batches_'):
        attempted = sum(work.get(prefix + 'attempted', {}).values())
        assert attempted == sum(work.get(prefix + 'completed', {}).values()) + sum(work.get(prefix + 'failed', {}).values())
        total += attempted
    assert total == work['budget_work_units']
    assert work['within_solve_cap']
    for part in work.get('parts', []):
        reconcile(part)


def without_wall_times(value):
    if isinstance(value, dict):
        return {key: without_wall_times(item) for key, item in value.items() if key != 'active_wall_seconds'}
    if isinstance(value, list):
        return [without_wall_times(item) for item in value]
    return value


def audit():
    out = BUNDLE / 'campaign'
    summary = read(out / 'summary.json')
    assert summary['status'] == 'PASS'
    assert len(summary['rows']) == 16 and len(summary['comparisons']) == 8
    current_sources = read(out / 'manifest.json')['source_sha256']
    source_count = verify_hashes(current_sources, ROOT)
    frozen_count = 0
    for manifest in sorted(BUNDLE.glob('*/manifest.json')):
        data = read(manifest)
        if 'source_sha256' in data and (manifest.parent / 'sources').exists():
            frozen_count += verify_hashes(data['source_sha256'], manifest.parent / 'sources')
    frozen_count += verify_hashes(read(BUNDLE / 'baseline.json')['source_sha256'], BUNDLE / 'baseline_sources')
    input_count = 0
    for phase in ('geometry', 'updates', 'campaign'):
        data = read(BUNDLE / phase / 'manifest.json')
        assert data['source_sha256'] == current_sources
        input_count += verify_hashes(data['input_sha256'], ROOT)
    tests = read(BUNDLE / 'tests.json')
    assert tests['status'] == 'PASS' and tests['source_sha256'] == current_sources
    assert tests['log_sha256'] == digest(BUNDLE / 'tests.log')
    for rep in range(2):
        for arm in ('reference', 'certified'):
            base = out / f'{arm}_{rep}'
            manifest = read(base / 'manifest.json')
            input_count += verify_hashes(manifest['input_sha256'], base)
            input_count += verify_hashes(manifest['historical_input_sha256'], ROOT)
            verify_hashes(manifest['source_sha256'], ROOT)

    old = ROOT / read(BUNDLE / 'baseline.json')['prior_campaign']
    old_count = verify_hashes(read(old / 'artifact_manifest.json'), old)
    assert read(old / 'verification.json') == read(BUNDLE / 'baseline.json')['prior_verification']
    archived_input_count = verify_archived_attempt_inputs()
    timing_context = read(BUNDLE / 'timing_context.json')
    concurrent_evidence_count = verify_hashes({name: row['sha256'] for name, row in timing_context['evidence'].items()},
                                              BUNDLE / 'concurrent_work_evidence')
    diagnostic_budgets = {}
    for phase, wall_limit, unit_limit in (('geometry', 300, 0), ('updates', 1800, 2000)):
        paths = [BUNDLE / phase / 'qualification.json', *sorted(BUNDLE.glob(phase + '_attempt_*/qualification.json'))]
        records = [read(path) for path in paths]
        seconds = sum(record['seconds'] for record in records)
        units = sum(record.get('work', {}).get('budget_work_units', 0) for record in records)
        assert all(record['status'] == 'PASS' for record in records)
        assert seconds <= wall_limit and units <= unit_limit
        if phase == 'geometry':
            assert all(record['physical_solves'] == 0 for record in records)
        diagnostic_budgets[phase] = dict(attempts=len(paths), seconds=seconds, work_units=units,
                                      wall_limit=wall_limit, work_limit=unit_limit)
    full_seconds = sum(read(path)['seconds'] for path in
                       [out / 'execution_status.json', *sorted(BUNDLE.glob('campaign_attempt_*/execution_status.json'))])
    assert full_seconds <= 10800
    timings = read(out / 'timings.json')
    assert len(timings) == 16 and all(row['seconds'] <= 2400 and row['returncode'] == 0 for row in timings)
    pair_details = []
    maximum_cache_bytes = 0
    for rep in range(2):
        for scene in SCENES:
            folders = [out / f'{arm}_{rep}' / 'runs' / scene for arm in ('reference', 'certified')]
            results = [read(folder / 'result.json') for folder in folders]
            diagnostics = [read(folder / 'geometry_validation.json') for folder in folders]
            topology = [read(folder / 'topology/terminal.json') for folder in folders]
            assert diagnostics[0]['physical_work'] == diagnostics[1]['physical_work']
            assert diagnostics[0]['kernel_counts'] == diagnostics[1]['kernel_counts']
            assert topology[0]['controller_work'] == topology[1]['controller_work']
            assert without_wall_times(results[0]['topology_work']) == without_wall_times(results[1]['topology_work'])
            assert without_wall_times(results[0]['continuation']['work']) == without_wall_times(results[1]['continuation']['work'])
            for result, diagnostic, terminal in zip(results, diagnostics, topology):
                assert result['fresh_recovery_pass'] and result['sources_and_inputs_unchanged']
                works = (result['topology_work'], result['continuation']['work'])
                for work in works:
                    reconcile(work)
                assert result['actual_attempted_calls'] == sum(work['total_attempted'] for work in works)
                assert result['actual_completed_solves'] == sum(sum(work['completed'].values()) for work in works)
                assert result['actual_failed_or_refused_calls'] == sum(sum(work['failed'].values()) for work in works)
                assert result['geometry_refused_calls'] == sum(work['calls'].get('preserved_candidate_refusals', 0) for work in works)
                passive = terminal['controller_work']['totals']
                assert passive['bie_frequency_solve_count'] == sum(result['topology_work']['completed'].values())
                assert passive['derivative_assembly_count'] == sum(result['topology_work']['derivative_assemblies_completed'].values())
                for fit in diagnostic['fits']:
                    assert fit['peak_bytes'] <= fit['max_bytes'] == 16 * 1024 * 1024
                    maximum_cache_bytes = max(maximum_cache_bytes, fit['peak_bytes'])
            predictions = [sorted(str(path.relative_to(folder)) for path in folder.glob('F/**/*predictions.json'))
                           for folder in folders]
            assert predictions[0] and predictions[0] == predictions[1]
            for name in predictions[0]:
                assert read(folders[0] / name) == read(folders[1] / name), (scene, rep, name)
            readiness = [read(folder / 'readiness.json') for folder in folders]
            for record in readiness:
                record.pop('work')
            assert readiness[0] == readiness[1]
            metrics = [read(folder / 'F/metrics.json') for folder in folders]
            assert metrics[0]['final'] == metrics[1]['final']
            pair_details.append(dict(scene=scene, repetition=rep, prediction_files=len(predictions[0]),
                                     endpoint_readiness_and_physical_work_equal=True))
    verification = dict(status='PASS', new_physical_solves=0, source_hashes=source_count,
                        archived_source_hashes=frozen_count, input_hashes=input_count,
                        archived_input_hashes=archived_input_count,
                        concurrent_evidence_hashes=concurrent_evidence_count,
                        preserved_top025_artifact_hashes=old_count, diagnostic_budgets=diagnostic_budgets,
                        full_campaign_seconds_all_attempts=full_seconds, full_campaign_ceiling_seconds=10800,
                        pairs=pair_details, maximum_cache_bytes=maximum_cache_bytes,
                        work_note='Topology passive counters are scoped by the controller; outer worker counters cover remaining work. Budget ledgers count both.',
                        monitor_note='A file-only monitor sampled saved logs every 55 seconds. SPD-008 launched no additional numerical workers beyond its sequential campaign.',
                        timing_context=timing_context)
    (BUNDLE / 'verification.json').write_text(json.dumps(verification, indent=2, sort_keys=True) + '\n')
    print(json.dumps(verification, indent=2))


if __name__ == '__main__':
    audit()
