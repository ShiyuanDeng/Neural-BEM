"""Count terminal rejection codes from saved MATLAB logs; never run a solver."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE = ROOT / 'results/brg/tg002_shapes/2026-11-17'


def parse_log(text):
    rows = []
    filters = {}
    final = None
    selected = None
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith('Starting inverse interation'):
            filters, final, selected = {}, None, None
        match = re.search(r'Post (gn|sd) filter:.*filter iteration count:\s*(\d+)\s+ier:\s*(-?\d+)', line)
        if match:
            filters[match[1]] = {'levels': int(match[2]), 'ier': int(match[3])}
        match = re.search(r'optimization method used = (gn|sd)', line)
        if match:
            selected = match[1]
        match = re.search(r'iter number:\s*(\d+).*ier:\s*(-?\d+)', line)
        if match:
            final = dict(iteration=int(match[1]), iteration_ier=int(match[2]),
                         selected_method=selected, filters=filters.copy(), line=number)
            filters = {}
        match = re.search(r'BRG INVERSE (\S+) (\d+)/(\d+).*exit=(-?\d+)', line)
        if match:
            row = dict(case=match[1], index=int(match[2]), exit_flag=int(match[4]), terminal=final)
            rows.append(row)
            filters, final, selected = {}, None, None
    return rows


def summarize_case(folder):
    rows = {}
    logs = []
    for path in sorted((folder/'local').glob('matlab_*.log')):
        data = path.read_bytes()
        logs.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(data).hexdigest()))
        for row in parse_log(data.decode(errors='replace')):
            row['log'] = str(path.relative_to(ROOT))
            rows[row['index']] = row
    selected, iteration, any_filter, both = (collections.Counter() for _ in range(4))
    for row in rows.values():
        terminal = row['terminal']
        if terminal is None:
            continue
        iteration[str(terminal['iteration_ier'])] += 1
        # Only rejected terminal updates count as frequency-ending rejections.
        if row['exit_flag'] != -1:
            continue
        filters = terminal['filters']
        chosen = filters.get(terminal['selected_method'])
        if chosen is not None:
            selected[str(chosen['ier'])] += 1
        codes = [f['ier'] for f in filters.values()]
        for code in set(codes):
            any_filter[str(code)] += 1
        if len(codes) == 2 and codes[0] == codes[1]:
            both[str(codes[0])] += 1
    result = dict(case=folder.name, source='existing MATLAB logs only',
                  completed_frequencies=len(rows),
                  selected_terminal_filter_ier_counts=dict(selected),
                  any_terminal_filter_ier_counts=dict(any_filter),
                  both_terminal_filter_ier_counts=dict(both),
                  final_iteration_ier_counts=dict(iteration),
                  explanation='Geometry ier 2 is curvature rejection, ier 1 self-intersection. '
                  'The public update routine replaces rejected/no-decrease steps by iteration ier -5; '
                  'filter and iteration counts overlap and must not be added.',
                  logs=logs, frequencies=[rows[i] for i in sorted(rows)])
    (folder/'rejection_counts.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=DEFAULT_BASE)
    args = parser.parse_args()
    state = json.loads((args.base/'campaign.json').read_text())
    for case in state['cases']:
        folder = args.base/case
        if case in state.get('active', []) or not (folder/'metrics.json').exists() or (folder/'rejection_counts.json').exists():
            continue
        result = summarize_case(folder)
        counts = result['selected_terminal_filter_ier_counts']
        print(case, result['completed_frequencies'], 'selected filter ier2/ier1',
              counts.get('2', 0), counts.get('1', 0),
              'iteration ier-5', result['final_iteration_ier_counts'].get('-5', 0))


if __name__ == '__main__':
    main()
