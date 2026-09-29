"""MA-001R: compare a fresh MA-001 Part B analysis with the archived one.

Usage: python compare.py <fresh noncircular_analysis.json> <output summary.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
old = json.load(open(ROOT / 'results/validation/modal_atlas/MA-001/noncircular_analysis.json'))
new = json.load(open(sys.argv[1]))
assert sorted(old) == sorted(new)
integer_keys, continuous = set(), {}
qualification = {}
for s in sorted(old):
    qualification[s] = dict(archived=old[s]['qualification'], current=new[s]['qualification'])
    for fo, fn in zip(old[s]['per_frequency'], new[s]['per_frequency']):
        for key, a in fo.items():
            b = fn[key]
            if key in ('kappa', 'available', 'column_norm'):
                a, b = np.array(a), np.array(b)
                keep = a >= 1e-6 * a.max()
                r = np.abs(a - b) / a
                row = continuous.setdefault(key, {'columns_above_1e-6': 0.0, 'all_columns': 0.0})
                row['columns_above_1e-6'] = max(row['columns_above_1e-6'], float(r[keep].max()))
                row['all_columns'] = max(row['all_columns'], float(r.max()))
            elif key not in ('k', 'kL_2pi'):
                integer_keys.add(key)
                assert a == b, (s, key)
summary = dict(states=len(old), frequencies=len(old[s]['per_frequency']),
               identical_integer_quantities=sorted(integer_keys),
               maximum_relative_difference=continuous, qualification=qualification)
Path(sys.argv[2]).write_text(json.dumps(summary, indent=1))
print(json.dumps(continuous, indent=1))
