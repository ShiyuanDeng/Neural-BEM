"""MA-001 part B tables from analyze.py output."""
import argparse
import json

import numpy as np


def brightness(row):
    front = row['frontier_0.001']
    c = np.log10(np.array(row['column_norm'][:front + 1]))
    a = np.log10(np.array(row['available'][:front + 1]))
    k = np.log10(np.array(row['kappa'][:front + 1]))
    return dict(var_log_column=float(np.var(c)), var_log_available=float(np.var(a)), var_log_kappa=float(np.var(k)),
                corr_column_available=float(np.corrcoef(c, a)[0, 1]), corr_column_kappa=float(np.corrcoef(c, -k)[0, 1]),
                median_kappa=float(10 ** np.median(k)), max_kappa=float(10 ** k.max()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--states', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = json.load(open(args.analysis))
    endpoints = json.load(open(args.states))['endpoints']
    lines = ['# MA-001 part B tables', '',
             '## Qualification', '',
             '| State | modal vs nodal (512/1024) | 512 vs 1024 | nodal vs production | truncation bound |',
             '|---|---:|---:|---:|---|']
    for name, r in result.items():
        q = r['qualification']
        lines.append(f"| {name} | {q['modal_vs_nodal_512']:.1e} / {q['modal_vs_nodal_1024']:.1e} | "
                     f"{q['grid_512_vs_1024']:.1e} | {q['nodal_vs_production']:.1e} | "
                     f"{'holds' if q['truncation_bound_holds'] else 'VIOLATED'} |")
    lines += ['', '## Frontier and trace band at 0.25 / 1.25 / 2.5 GHz', '',
              'Frontier: highest p with column norm >= tau x strongest column. `K_U+K_V(eps)`: combined '
              'trace support at relative coefficient level eps. Trace K(1e-6): projected band giving every trace '
              'to 1e-6. J K(1e-6): projected band giving column p to 1e-6 of the strongest column.', '',
              '| State | GHz | kL/2pi | K_U+K_V (1e-1 / 1e-2) | frontier (1e-2 / 1e-3 / 1e-4) | trace K (1e-3 / 1e-6) | J K(1e-6) at p=0/10/20 | endpoint M |',
              '|---|---:|---:|---|---|---|---|---:|']
    for name, r in result.items():
        m = endpoints.get(name.replace('end/', ''), {}).get('update_modes', '')
        for f, ghz in ((0, 0.25), (8, 1.25), (18, 2.5)):
            row = r['per_frequency'][f]
            need = row['J_needed_K_1e-06']
            lines.append(f"| {name} | {ghz} | {row['kL_2pi']:.2f} | {row['K_U_0.1'] + row['K_V_0.1']} / "
                         f"{row['K_U_0.01'] + row['K_V_0.01']} | {row['frontier_0.01']} / {row['frontier_0.001']} / "
                         f"{row['frontier_0.0001']} | {row['trace_K_0.001']} / {row['trace_K_1e-06']} | "
                         f"{need[0]} / {need[10]} / {need[20]} | {m} |")
    lines += ['', '## Brightness decomposition, p <= frontier(1e-3), all 19 frequencies pooled per state', '',
              '`log ||J_p|| = log A_p - log kappa_p`. A_p: the norm of summed pair magnitudes; kappa_p: cancellation.', '',
              '| State | var log column | var log A | var log kappa | corr(log column, log A) | corr(log column, -log kappa) | median kappa | max kappa |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    summary = {}
    for name, r in result.items():
        rows = [brightness(row) for row in r['per_frequency']]
        s = {key: float(np.median([x[key] for x in rows])) for key in rows[0]}
        s['max_kappa'] = float(max(x['max_kappa'] for x in rows))
        summary[name] = s
        lines.append(f"| {name} | {s['var_log_column']:.3f} | {s['var_log_available']:.3f} | {s['var_log_kappa']:.3f} | "
                     f"{s['corr_column_available']:.3f} | {s['corr_column_kappa']:.3f} | {s['median_kappa']:.2f} | {s['max_kappa']:.1f} |")
    lines += ['', 'Brightness entries are medians over the 19 frequencies (max kappa: maximum).', '']
    open(args.output, 'w').write('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
