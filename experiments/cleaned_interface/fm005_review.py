"""FM-005 post-run review: promotion, pre-stop identity and per-stage rejection tables.

``fm005.report`` reads ``resolution_promoted``, which the runner records only on
resumed fits; promotion is derived here from the stage resolutions instead.
Reads sealed artifacts only and writes ``review.json``.
"""
from bem_inverse.io import read, write
from . import fm005 as h


def key(state):
    return state['stage'], state['iteration'], state['loss'], state['curve']


def review(output=h.OUTPUT):
    h.verify(output)
    summary = read(output/'summary.json')
    rows = []
    for row in summary['rows']:
        case, start = row['case'], row['start']
        folder = output/'runs'/case/f'{start:04d}'
        result = read(folder/'result.json')
        before = read(h.fm004_accepted(case, start))['states']
        after = read(folder/'accepted.json')['states']
        stages = [dict(stage=s['stage'], outcome=s['outcome'], nodes=s.get('nodes'), accepted_steps=s['accepted_steps'],
                       initial_loss=s['initial_loss'], final_loss=s['final_loss'], stage_units=s['work']['stage_units'],
                       stage_quota=s['work']['stage_quota'],
                       rejected_unresolved=sum(e['action'] == 'reject_inaccurate_candidate'
                                               for e in s.get('resolution_events') or []))
                  for s in result.get('stages', [])]
        original = folder/'original_resolution_audit.json'
        rows.append(dict(case=case, start=start, block=row['block'], recovered=row['recovered'],
            promoted=row['promotion_stage'] is not None, promotion_stage=row['promotion_stage'],
            fm004_accepted_states=len(before), fm005_accepted_states=len(after),
            identical_through_fm004_stop=all(key(a) == key(b) for a, b in zip(before, after)) and len(after) >= len(before),
            unit_differences=sum(a['units'] != b['units'] for a, b in zip(before, after)),
            original_resolution_audit_passed=read(original)['passed'] if original.exists() else None,
            quota_limited_stages=sum(s['outcome'] == 'STAGE_QUOTA_REACHED' for s in stages),
            rejected_at_ceiling=sum(s['rejected_unresolved'] for s in stages if s['nodes'] == h.NODES),
            stages=stages))
    record = dict(experiment='FM-005', summary_sha256=h.digest(output/'summary.json'), rows=rows,
                  all_prefixes_identical=all(r['identical_through_fm004_stop'] for r in rows))
    write(output/'review.json', record)
    return record


if __name__ == '__main__':
    record = review()
    for r in record['rows']:
        print(r['start'], r['recovered'], r['promotion_stage'], r['identical_through_fm004_stop'],
              r['fm004_accepted_states'], r['fm005_accepted_states'], r['unit_differences'], r['quota_limited_stages'],
              r['rejected_at_ceiling'], r['original_resolution_audit_passed'])
    print('all prefixes identical', record['all_prefixes_identical'])
