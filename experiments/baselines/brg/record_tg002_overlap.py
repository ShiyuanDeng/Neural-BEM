"""Annotate completed control receipts using saved fit-process intervals only."""
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'results/brg/tg002_no_curvature/2026-11-18'
B1 = ROOT / 'results/bem/baseline_data/brg_tg002/2026-11-18'


def epoch(value):
    return datetime.datetime.fromisoformat(value).timestamp()


def overlap_counts(intervals, start, end, own):
    selected = [r for r in intervals if r['receipt'] != own
                and r['start'] < end and r['end'] > start]
    events = []
    for row in selected:
        events.extend([(max(start, row['start']), 1), (min(end, row['end']), -1)])
    count = peak = 0
    for _, change in sorted(events):
        count += change
        peak = max(peak, count)
    return dict(peak_other_fits=peak, distinct_overlapping_fits=len(selected),
                overlapping_receipts=sorted(r['receipt'] for r in selected))


def main():
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    intervals = []
    for base in [ROOT / 'results/brg/tg002_shapes/2026-11-17', BASE]:
        for path in sorted(base.glob('*/attempt_*.json')):
            row = json.loads(path.read_text())
            if not row.get('matlab_pid'):
                continue
            end = epoch(row['ended']) if row.get('ended') else now
            start = end-row['wall_seconds'] if row.get('ended') and 'wall_seconds' in row else epoch(row['started'])+row.get('data_hash_check_seconds', 0)
            intervals.append(dict(receipt=str(path.relative_to(ROOT)), group='BRG',
                                  start=start, end=end))
    for path in sorted(B1.glob('*/*/attempt_*/manifest.json')):
        row = json.loads(path.read_text())
        end_path = path.parent/'worker_end.json'
        end = epoch(json.loads(end_path.read_text())['end']['utc']) if end_path.exists() else now
        intervals.append(dict(receipt=str(path.relative_to(ROOT)), group='B1',
                              start=epoch(row['start']['utc']), end=end))
    active = json.loads((BASE/'campaign.json').read_text())['active']
    changed = []
    for path in sorted(BASE.glob('*/attempt_01.json')):
        row = json.loads(path.read_text())
        if path.parent.name in active or not row.get('case_ended'):
            continue
        own = str(path.relative_to(ROOT))
        window = next(r for r in intervals if r['receipt'] == own)
        result = overlap_counts(intervals, window['start'], window['end'], own)
        result['peak_other_brg_fits'] = overlap_counts([r for r in intervals if r['group']=='BRG'], window['start'], window['end'], own)['peak_other_fits']
        result['peak_b1_fits'] = overlap_counts([r for r in intervals if r['group']=='B1'], window['start'], window['end'], own)['peak_other_fits']
        result['method'] = 'Saved BRG MATLAB-process and B1 worker intervals; peak concurrent count excludes this case. BRG interval includes final residual evaluation. B1 source files are read only.'
        result['scope'] = 'BRG and B1 fits; CSI held throughout activity 05. Counts exclude data preparation, scoring and non-fit host tasks. Timings are shared-machine timings.'
        result['other_matlab_count_at_start'] = len(row.get('other_matlab_at_start', []))
        result['other_matlab_count_at_end'] = len(row.get('other_matlab_at_end', []))
        if row.get('fit_overlap') != result:
            row['fit_overlap'] = result
            path.write_text(json.dumps(row, indent=2)+'\n')
            changed.append(path.parent.name)
    print('Overlap receipts updated:', ', '.join(changed) or 'none')


if __name__ == '__main__':
    main()
