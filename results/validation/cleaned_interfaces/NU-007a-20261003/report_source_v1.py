"""Summarize NU-007a fresh pairs and the fixed archived retention gates.

Execute this script with the NU-007a frozen tree first on PYTHONPATH and
NU007_WORKSPACE pointing to the repository. Does not alter shared sources.
"""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

from experiments.cleaned_interface.nu007a import (
    ROOT, BASE, DEFAULT_OUTPUT, CORE, ROLES, TIERS, verify, read, write, digest,
    case_drift, decide, identity, pair_report,
)


def report(output):
    manifest = verify(output)
    precheck = read(output/'precheck.json')
    complete = read(output/'campaign_complete.json')
    assert complete['passed'] and complete['manifest_sha256'] == digest(output/'manifest.json')
    suites = ET.parse(output/'focused_tests.xml').getroot().findall('testsuite')
    focused = {k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','errors','failures','skipped')}
    assert focused['tests'] >= 23 and not any(focused[k] for k in ('errors','failures','skipped'))
    nodal_status = {r['id']:r['status'] for r in read(BASE/'CI-001/comparison.json')['rows']}
    nodal = dict(cases={}, status=nodal_status)
    candidate = dict(cases={}, status={})
    cases, pairs, historical = [], [], []
    keys = ('same_accepted_states','same_final_curve','same_decisions','same_units','same_tiers','same_status','audits_passed')
    tier_keys = [f'{role}_{tier}' for role in ROLES for tier in TIERS]
    for case in CORE:
        nodal['cases'][case] = case_drift(BASE/'CI-001/runs'/case, certificate=True)
        folder = output/'pair_1/device/runs'/case
        candidate['cases'][case] = case_drift(folder, certificate=True)
        candidate['status'][case] = read(folder/'result.json')['comparison_status']
        samples = {'host': [], 'device': []}
        old = read(BASE/'NU-006/runs'/case/'result.json')
        for repeat in range(1,4):
            roots = {arm: output/f'pair_{repeat}'/arm/'runs'/case for arm in samples}
            pair = pair_report(roots['host'], roots['device'])
            pairs.append(dict(case=case, repeat=repeat, **pair))
            for arm in samples:
                result = read(roots[arm]/'result.json')
                samples[arm].append(result)
                compare = identity(BASE/'NU-006/runs'/case, roots[arm])
                historical.append(dict(case=case, repeat=repeat, arm=arm,
                    same_accepted_steps=compare['same_accepted_steps'],
                    same_units=old['total_units']==result['total_units'],
                    same_tiers=all(old['geometry_work'][k]==result['geometry_work'][k] for k in tier_keys),
                    final_curve_relative=compare['final_curve_relative']))
        wall = {arm:float(np.median([r['total_seconds'] for r in values])) for arm,values in samples.items()}
        cert = {arm:float(np.median([r['geometry_work']['certificate_seconds'] for r in values])) for arm,values in samples.items()}
        no_external = all(not r['timing_environment'][k] for values in samples.values() for r in values
                          for k in ('external_work_before','external_work_after'))
        no_fallback = all(r['geometry_work']['prepare_fallbacks']==0 and
            r['geometry_work'].get('device_certificate_fallbacks',0)==0 for values in samples.values() for r in values)
        cases.append(dict(case=case, status=candidate['status'][case], wall_median=wall, certificate_median=cert,
            saving_fraction=1-wall['device']/wall['host'], no_external_work_at_boundaries=no_external,
            no_fallback=no_fallback, samples={arm:[dict(wall=r['total_seconds'], certificate=r['geometry_work']['certificate_seconds'])
                for r in values] for arm,values in samples.items()}))
        print('REPORT',case,'median wall',wall,'certificate',cert,flush=True)
    retention = decide(nodal, candidate)
    gates = dict(precheck=precheck['passed'], focused_tests=not any(focused[k] for k in ('errors','failures','skipped')),
        fresh_identity=all(p[k] for p in pairs for k in keys),
        archived_identity=all(p[k] for p in historical for k in ('same_accepted_steps','same_units','same_tiers')),
        nodal_retention=retention['qualifies'])
    seconds = {name: {arm:sum(r[name][arm] for r in cases) for arm in ('host','device')}
               for name in ('wall_median','certificate_median')}
    result = dict(experiment='NU-007a', adoption_ready=all(gates.values()), gates=gates, focused_tests=focused,
        precheck=precheck, retention=retention, seconds=seconds, cases=cases, fresh_pairs=pairs,
        historical_identity=historical,
        runtime=dict(repetitions=3, no_known_external_work_at_boundaries=all(r['no_external_work_at_boundaries'] for r in cases),
            per_case_within_20_percent=all(r['wall_median']['device']<=1.2*r['wall_median']['host'] for r in cases),
            aggregate_saving_fraction=1-seconds['wall_median']['device']/seconds['wall_median']['host'],
            limitation='External numerical work sampled at fit boundaries, not continuously. Six core cases only.'),
        manifest_sha256=digest(output/'manifest.json'), source_archive_sha256=manifest['archive_sha256'])
    verify(output)
    write(output/'qualification.json',result)
    print('ADOPTION READY',result['adoption_ready'],gates,flush=True)
    if not result['adoption_ready']:
        raise RuntimeError('Qualification failed: retain existing shared selection.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    report(parser.parse_args().output.resolve())
