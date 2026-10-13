"""Summarize the returned MA-007 batch from saved receipts only.

No fitting, field assembly, new scoring, probes, or tests are performed.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from bem_inverse.io import digest, write
from . import campaign as c
from .ma007_retention import read


IDS = ('G', 'F0', 'M0', 'K0', 'U0', 'F1', 'M1', 'K1', 'U1', 'G_E0',
       'O1', 'O2', 'O3', 'O4', 'O5', 'O6', 'O7', 'O8')
DEFAULT = c.ROOT / 'results/validation/modal_atlas/MA-007/research18-001'


def report(folder):
    state = read(folder / 'state.json')
    root = folder / f"workspace_{state['workspace']}" / 'runs'
    results, rows, paths = {}, [], {}
    for name in IDS:
        run = root / name
        result = read(run / 'result.json')
        index = read(run / 'recording/index.json')
        results[name] = result
        definitions = {d['operation']['label']: d['operation']['stage']
                       for d in result['decisions'] if 'stage' in d['operation']}
        qualification = [e for e in index['events'] if e['kind'] == 'qualification']
        stages = []
        for stage in result['stages']:
            definition = definitions[stage['stage']]
            stages.append(dict(
                stage=stage['stage'], F_GHz=max(definition['frequencies_hz']) / 1e9,
                catalog='damped' if any(definition['damping']) else 'real',
                M=stage['M'], K=stage['K_geometry'],
                entered_Ku=stage['resolution_selection']['actual_cutoff'],
                accepted_steps=stage['accepted_steps'], stop=stage['stop'],
                outcome=stage['outcome'], work_units=stage['work']['work_units'],
                compute_seconds=stage['work']['seconds']))
        paths[name] = stages
        moving = [s for s in stages if s['accepted_steps']]
        row = dict(
            configuration=name, recovered=result['recovered'], outcome=result['outcome'],
            F_cap_GHz=result['assigned_caps'][0], M_cap=result['assigned_caps'][1],
            K_cap=result['assigned_caps'][2], Ku_cap=result['assigned_caps'][3],
            peak_entered_M=max(s['M'] for s in stages),
            peak_entered_K=max(s['K'] for s in stages),
            peak_M_with_committed_moves=max((s['M'] for s in moving), default=0),
            peak_K_with_committed_moves=max((s['K'] for s in moving), default=0),
            largest_F_with_committed_moves_GHz=max((s['F_GHz'] for s in moving), default=0),
            last_service_Ku=result['physics']['independent_accuracy']['actual_cutoff'],
            peak_accepted_move_qualification_Ku=max(
                (e['row']['cutoff'] for e in qualification if e['kind_detail'] == 'accepted_move'),
                default=0),
            cap_binding_events=sum(e['kind_detail'] == 'cap_binding' for e in qualification),
            accepted_steps=sum(s['accepted_steps'] for s in stages),
            rms_mm=result['metrics']['rms_mm'],
            hausdorff_upper_mm=result['metrics']['hausdorff_upper_mm'],
            max_full_catalog_residual=max(result['relative_residual']),
            fit_units=result['fit_and_localization_units'],
            fit_compute_seconds=result['fit_and_localization_seconds'],
            audited_fit_return_seconds=result['audited_output_seconds'],
            audit_compute_seconds=result['audit_seconds'],
            recording_serialization_seconds=result['recording']['serialization_seconds'],
            recording_raw_array_bytes=result['recording']['raw_array_bytes'],
            recorder_offline_reciprocal_seconds=result['recording']['offline_refusal_reciprocal_seconds'],
            online_monitor_field_events=sum(e['kind'] == 'field' and
                e.get('calculation_role') == 'online_controller_monitor' for e in index['events']),
            result_path=str((run / 'result.json').relative_to(c.ROOT)),
            result_sha256=digest(run / 'result.json'))
        rows.append(row)

    recovered = [r for r in rows if r['recovered']]
    minimum = min(r['fit_units'] for r in recovered)
    near = [r for r in recovered if r['fit_units'] <= 1.05 * minimum]
    winner = min(near, key=lambda r: (r['configuration'] == 'O8', r['last_service_Ku'],
                                    r['peak_entered_K'], r['peak_entered_M'], r['configuration']))
    fastest = min(recovered, key=lambda r: r['audited_fit_return_seconds'])

    def coefficients(name):
        value = results[name]['final_curve']
        return np.asarray(value['real']) + 1j * np.asarray(value['imag'])

    residual_split = {}
    frequencies = sorted({f for d in results['G']['decisions'] if 'stage' in d['operation']
                          for f in d['operation']['stage']['frequencies_hz']})
    for name in ('F0', 'F1'):
        rr = np.asarray(results[name]['relative_residual'])
        inside = np.asarray(frequencies) <= results[name]['assigned_caps'][0] * 1e9
        residual_split[name] = dict(included_max=float(max(rr[inside])),
            omitted_max=float(max(rr[~inside])),
            worst_frequency_GHz=frequencies[int(np.argmax(rr))] / 1e9)
    comparisons = dict(
        G_M1_final_coefficients_bitwise_equal=np.array_equal(coefficients('G'), coefficients('M1')),
        G_U1_final_coefficients_bitwise_equal=np.array_equal(coefficients('G'), coefficients('U1')),
        F_residual_split=residual_split,
        K32_work_increase_over_K64=results['K0']['fit_and_localization_units'] /
            results['K1']['fit_and_localization_units'] - 1,
        historical_exit_work_increase_over_progress_exit=results['G_E0']['fit_and_localization_units'] /
            results['G']['fit_and_localization_units'] - 1,
        O2_work_reduction_vs_G=1-results['O2']['fit_and_localization_units'] /
            results['G']['fit_and_localization_units'],
        O2_output_time_increase_vs_G=results['O2']['audited_output_seconds'] /
            results['G']['audited_output_seconds'] - 1)
    summary = dict(
        experiment='MA-007', scope='18 returned research fits on hook__c13.3; saved-data analysis only',
        nominal_batch_complete=True, full_study_complete=False, returned=len(rows),
        recovered=len(recovered), recovered_configurations=[r['configuration'] for r in recovered],
        provisional_work_winner=winner['configuration'], fastest_observed_output=fastest['configuration'],
        independent_confirmations=0, C_star=state['C_star'],
        comparisons=comparisons, configurations=rows,
        peak_cutoff_note='Accepted-move qualification includes speculative O8 branches. '
            'last_service_Ku excludes audit witnesses; entered_Ku precedes within-stage promotions.',
        timing_note='Fit compute and audited fit return are distinct. Serialization overlaps computation. '
            'Audited fit return excludes later scoring, recorder completion, receipt processing, and push.',
        raw_retention='Raw arrays remain on this machine; committed receipts carry local paths and hashes.',
        unestablished=['scientific no-gain upper bounds', 'joint reduced-cap combination',
            'research five-role offline atlases/local probes', 'independent winner confirmations',
            'benchmark-wide generalization'])
    write(folder / 'summary.json', summary)
    write(folder / 'actual_paths.json', paths)
    with (folder / 'results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ['# MA-007: all 18 returned research fits', '',
             f"{len(rows)}/18 returned; {len(recovered)}/18 recovered. Saved receipts only.", '',
             '| ID | Recovered | RMS mm | Max full-catalog residual % | Fit units | Fit compute s | Audited fit return s | Outcome |',
             '|---|---|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['configuration']} | {'yes' if r['recovered'] else 'no'} | "
            f"{r['rms_mm']:.6f} | {100*r['max_full_catalog_residual']:.6f} | {r['fit_units']} | "
            f"{r['fit_compute_seconds']:.2f} | {r['audited_fit_return_seconds']:.2f} | {r['outcome']} |")
    lines += ['', summary['timing_note'], '', summary['raw_retention'], '',
              'Three-question interpretation: [report](../../../../../docs/iterations/modal_atlas/iteration_07/06_research18_results.md).']
    (folder / 'results.md').write_text('\n'.join(lines) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=DEFAULT)
    value = report(parser.parse_args().folder.resolve())
    print(f"{value['returned']}/18 returned, {value['recovered']}/18 recovered; "
          f"work: {value['provisional_work_winner']}; observed output time: {value['fastest_observed_output']}")


if __name__ == '__main__':
    main()
