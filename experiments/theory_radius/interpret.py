"""Reporting supplement separating radius probes from numerical-floor effects.

Added during TR-001 execution without changing its sealed numerical sources.
The checks use the per-probe resolution flag already recorded by that source.
"""
from .common import *


def run():
    folder = OUTPUT/'TR-001'
    rows_ = [read(p) for p in sorted((folder/'rows').glob('*.json'))]
    qualified = [r for r in rows_ if r['qualification']['passed'] and r.get('complete')]
    probes = [p for r in qualified for p in r['radius_checks'] if 'tcc' in p]
    resolved = [p for p in probes if p['resolved_against_origin_floor']]
    unresolved = [p for p in probes if not p['resolved_against_origin_floor']]
    out = dict(source_sha256=digest(Path(__file__)), qualified_rows=len(qualified),
        resolved_radius_probes=len(resolved), unresolved_radius_probes=len(unresolved),
        resolved_tcc_exceeds_half=sum(p['tcc']>.5 for p in resolved),
        unresolved_tcc_exceeds_half=sum(p['tcc']>.5 for p in unresolved),
        maximum_resolved_tcc=max((p['tcc'] for p in resolved),default=None),
        weakest_sigma_unresolved=sum(not e['sigma_resolved'] for r in qualified for e in r['estimates']),
        stage2=[], inputs={str(p.relative_to(folder)):digest(p) for p in sorted((folder/'rows').glob('*.json'))})
    lines=['# Numerical interpretation of TR-001', '',
        'This reporting supplement uses only saved measurements. It was added during the '
        'run after tiny circle-band probes exposed the need to separate numerical-floor effects; '
        'the sealed solver, probes, radii, gates and source archive were unchanged.', '',
        f'Of {len(probes)} radius probes, {len(resolved)} exceed 100 times the measured '
        f'origin field-refinement floor and {len(unresolved)} do not. TCC ratios above 1/2: '
        f'**{out["resolved_tcc_exceeds_half"]} resolved**, '
        f'**{out["unresolved_tcc_exceeds_half"]} unresolved**. The latter cannot be interpreted '
        'as violations of a local theorem. This is still a sampled check, with an origin-based '
        'resolution diagnostic, not a uniform bound.', '',
        'Smallest singular values are separately flagged unresolved when they do not exceed '
        '10 times the measured Jacobian refinement error. Raw diagnostic tables preserve '
        'these numbers, but they must not be treated as positive lower stability bounds.', '',
        'Stage-2 configuration: M5, 0.5 and 0.75 GHz:', '',
        '| Case | Catalog | Paired rho (mm) | Full rho (mm) | Full/paired |',
        '|---|---|---:|---:|---:|']
    for row in qualified:
        if row['M']!=5:
            continue
        p=next(e for e in row['estimates'] if e['frequencies']==2 and e['paired'])
        f=next(e for e in row['estimates'] if e['frequencies']==2 and not e['paired'])
        record=dict(case=row['case'],catalog=row['catalog'],paired=p,full=f,
                    full_over_paired=f['rho_sample_mm']/p['rho_sample_mm'])
        out['stage2'].append(record)
        lines.append(f'| {row["case"]} | {row["catalog"]} | {p["rho_sample_mm"]:.6g} | {f["rho_sample_mm"]:.6g} | {record["full_over_paired"]:.4g} |')
    lines += ['', 'These truth-centred neighborhoods address local conditioning. They do not '
              'establish recovery from a distant circle, nonuniqueness of paired data, or a '
              'safe online band-release rule. TR-002 checks whether archived endpoints are '
              'even inside such neighborhoods.', '']
    write(folder/'assessment.json',out)
    (folder/'ASSESSMENT.md').write_text('\n'.join(lines)+'\n')
    print({k:v for k,v in out.items() if k not in ('inputs','stage2')})


if __name__=='__main__':
    run()
