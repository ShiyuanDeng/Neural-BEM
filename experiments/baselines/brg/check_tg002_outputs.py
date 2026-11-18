"""Check saved BRG records without repeating scoring or solver calls."""
import argparse
import collections
import datetime
import json
from pathlib import Path
import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[3]


def check_case(folder, data_folder=None):
    data_folder = data_folder or folder/'local'
    attempts = [json.loads(p.read_text()) for p in sorted(folder.glob('attempt_*.json'))]
    receipt = attempts[-1]
    metrics = json.loads((folder/'metrics.json').read_text())
    summary = json.loads((folder/'summary.json').read_text())
    records = sorted(folder.glob('frequency_*.mat'))
    residuals = json.loads((folder/'final_residuals.json').read_text()) if (folder/'final_residuals.json').exists() else []
    issues, flags = [], collections.Counter()
    for path in records:
        r = loadmat(path, simplify_cells=True)['record']
        for key in ['xs','ys','residual_history','residual','wall_seconds','k']:
            if not np.isfinite(np.asarray(r[key])).all():
                issues.append(f'{path.name}: nonfinite {key}')
        flags[str(r['exit_flag'])] += 1
    if not np.isfinite([r['relative_residual'] for r in residuals]).all():
        issues.append('nonfinite final residual')
    counts = dict(compact_frequency_records=len(records), data_files=len(list(data_folder.glob('data_*.mat'))),
                  exact_state_files=len(list((folder/'local').glob('state_*.mat'))),
                  final_curve_residuals=len(residuals), summary_frequencies=len(summary['frequencies']))
    if metrics['status']=='complete' and any(n!=37 for n in counts.values()):
        issues.append('complete status with missing outputs')
    if receipt['case_wall_seconds']>3600:
        issues.append('case over one-hour cap')
    if receipt.get('returncode') or receipt.get('scoring_failure'):
        issues.append('failed receipt')
    manifest=json.loads((folder/'bulk_manifest.json').read_text())
    for item in manifest['files']:
        p=ROOT/item['path']
        if not p.exists() or p.stat().st_size!=item['bytes']:
            issues.append('manifest size mismatch: '+item['path'])
    compact=sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
    if compact>5_000_000:
        issues.append('compact files over 5 MB')
    log=(ROOT/receipt['log']).read_text(errors='replace')
    errors=[line for line in log.splitlines() if any(t in line for t in ['Error using','Error in ','NaN','Segmentation','Fatal'])]
    result=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        check='saved outputs only; no solver or scoring rerun',case=folder.name,status=metrics['status'],counts=counts,
        curves_and_histories_finite=not any('nonfinite' in i for i in issues),exit_flag_counts=dict(flags),
        case_wall_seconds=receipt['case_wall_seconds'],returncode=receipt.get('returncode'),
        manifest_sizes_match=not any('manifest' in i for i in issues),compact_bytes=compact,log_error_lines=errors,issues=issues)
    (folder/'saved_output_check.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--data-base',type=Path)
    args=parser.parse_args()
    state=json.loads((args.base/'campaign.json').read_text())
    for case in state['cases']:
        folder=args.base/case
        if case in state['active'] or (folder/'saved_output_check.json').exists() or not (folder/'bulk_manifest.json').exists():
            continue
        if not (folder/'metrics.json').exists():
            print(case, 'missing score; inspect receipt before post-processing')
            continue
        result=check_case(folder, args.data_base/case/'local' if args.data_base else None)
        print(case, result['status'], 'issues:', result['issues'])
    print('LIVE',state['updated'],state['status'],'active',[(c,len(list((args.base/c).glob('frequency_*.mat')))) for c in state['active']], 'pending',len(state['pending']))


if __name__=='__main__':
    main()
