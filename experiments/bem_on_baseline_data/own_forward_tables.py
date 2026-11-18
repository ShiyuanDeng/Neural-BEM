"""Activity 09: nodal reference tables and the four checks, without solver edits."""
from csi_runtime import ROOT, provenance, peak_memory_gib
import argparse
import gc
import hashlib
import json
import time
import traceback
from dataclasses import asdict
from pathlib import Path

import numpy as np
from bem_inverse import Execution, PointSourceAcquisition
from bem_inverse.problem import Observation
from bem_inverse.forward_solvers.nodal_kress import NodalKress, forward_solve
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings
from experiments.benchmark import scenes
import csi_data as D
import csi_forward_check as C

OUTPUT = ROOT/'results/bem/baseline_data/fresnel_own_forward/2026-11-18'
SHAPES = ('circle', 'star', 'kite', 'hook')
NODES = (1024, 2048)
TOLERANCE = 1e-6
FROZEN = D.SIMULATED


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=float)+'\n')


def receipt(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def prepare(shape):
    case = shape+'__c4'
    folder = OUTPUT/'data'/shape
    if folder.exists():
        raise RuntimeError(f'Refusing a second generation in {folder}; keep the first attempt.')
    folder.mkdir(parents=True)
    checks = OUTPUT/'adapter_checks'
    checks.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    record = dict(shape=shape, contrast=4., provenance=provenance(), nodes=NODES,
                  tolerance=TOLERANCE, forward='nodal_kress CPU reference',
                  layout='full 36 by 72 prediction, then frozen CSI mask in C order',
                  written_resolution=2048, per_frequency=[], status='running')
    manifest = folder/'manifest.json'
    write(manifest, record)
    try:
        source = ROOT/FROZEN.format(shape=shape)
        frozen_digest = D.verify_sha256(source)
        mask, entries, _ = D.read_table(source)
        assert np.all(mask.sum(axis=1) == 49)
        raw = np.loadtxt(source)
        assert raw.shape == (8820, 7)
        assert [e.frequency_hz/1e9 for e in entries] == [.5, 1., 1.5, 2., 2.5]
        record['frozen_csi'] = dict(path=str(source.relative_to(ROOT)), sha256=frozen_digest)
        full = PointSourceAcquisition(D.source_positions_m()/D.LENGTH_M,
                                      D.receiver_positions_m()/D.LENGTH_M, paired=False)
        truth = scenes.truth_fixture(shape)
        execution = Execution(device='cpu', acceleration='reference', frequency_threads=1)
        record['execution'] = asdict(execution)
        context = NodalKress(execution)
        generated, arrays = [], {}
        table = raw.copy()
        for entry in entries:
            ghz = entry.frequency_hz/1e9
            obs = Observation(entry.k_m*D.LENGTH_M, full, np.ones(full.data_shape), entry.frequency_hz)
            fields, timings = [], []
            for nodes in NODES:
                tick = time.perf_counter()
                state = forward_solve(truth, obs, 4., nodes, context=context)
                fields.append(np.asarray(state.prediction)[mask].copy())
                timings.append(time.perf_counter()-tick)
                del state
                gc.collect()
            coarse, fine = fields
            generated.append(fine)
            row = dict(frequency_ghz=ghz, doubling_relative=C.relative(coarse, fine),
                       csi_difference_relative=C.relative(fine, entry.data), seconds=timings)
            if shape == 'circle':
                masked_obs = Observation(obs.wavenumber, D.acquisition(mask), fine, obs.frequency_hz)
                exact = C.exact_circle(truth, 4., masked_obs)
                row['exact_series_relative'] = C.relative(fine, exact)
            record['per_frequency'].append(row)
            arrays[f'{ghz:g}GHz_N1024'] = coarse
            arrays[f'{ghz:g}GHz_N2048'] = fine
            # Keep CSI's incident field and calibration; reverse its reader exactly.
            total = entry.incident + D.to_file_order(entry, fine)*entry.factors[entry.sources]
            table[entry.file_rows, 3] = total.real
            table[entry.file_rows, 4] = -total.imag
            write(manifest, record)
            print(shape, json.dumps(row), flush=True)
        path = folder/'synthetic_input.txt'
        np.savetxt(path, table, fmt=['%d', '%d', '%.17g', '%.17e', '%.17e', '%.17e', '%.17e'])
        digest = receipt(path)['sha256']
        Path(str(path)+'.sha256').write_text(f'{digest}  {path.name}\n')
        np.savez_compressed(folder/'fields.npz', **arrays)
        read, _, _ = D.observations(path)
        loaded = np.loadtxt(path)
        same_layout = bool(np.array_equal(loaded[:, :3], raw[:, :3]))
        same_incident = bool(np.array_equal(loaded[:, 5:], raw[:, 5:]))
        for row, obs, fine in zip(record['per_frequency'], read, generated):
            row['reader_relative'] = C.relative(obs.scattered, fine)
        record['table_layout'] = dict(rows=len(loaded), columns=7, sources=36,
            receivers=72, measured_per_source=49, source_receiver_frequency_columns_equal=same_layout,
            incident_columns_equal=same_incident)
        # Use the unchanged check with its case path pointed at the new table.
        C.CASES[case] = dict(path=path, truth=lambda: scenes.truth_fixture(shape), contrast=4.,
                            truth_note=f'frozen TG-002 truth_fixture("{shape}"), permittivity 4')
        modal = ModalMuller(Execution(device='cpu', frequency_threads=1), ModalSettings(table_mode=True))
        checked = C.check_case(case, modal, checks, layout=False)
        record['checks'] = dict(
            doubling_pass=all(r['doubling_relative'] <= TOLERANCE for r in record['per_frequency']),
            circle_exact_pass=all(r.get('exact_series_relative', 0) <= TOLERANCE for r in record['per_frequency']),
            reader_pass=all(r['reader_relative'] < 1e-13 for r in record['per_frequency']),
            layout_pass=same_layout and same_incident and checked['summary']['adapter_checks_pass'],
            modal_truth_pass=checked['summary']['worst_truth_mismatch_on_rule_frequencies'] <= TOLERANCE,
            modal_truth_worst=checked['summary']['worst_truth_mismatch_on_rule_frequencies'])
        record['status'] = 'passed' if all(v for k, v in record['checks'].items() if k.endswith('_pass')) else 'failed'
        record['bulk_files'] = [receipt(path), receipt(folder/'fields.npz'),
                               receipt(checks/f'{case}_truth_predictions.npz')]
        record['seconds'] = time.perf_counter()-started
        record['peak_memory_gib'] = peak_memory_gib()
        write(manifest, record)
        print(shape, record['status'], json.dumps(record['checks']), flush=True)
        if record['status'] != 'passed':
            raise RuntimeError('A required check failed. Stop before fitting and report.')
    except BaseException:
        record['status'] = 'failed'
        record['failure'] = traceback.format_exc()
        record['seconds'] = time.perf_counter()-started
        record['peak_memory_gib'] = peak_memory_gib()
        record['bulk_files'] = [receipt(p) for p in folder.iterdir() if p.is_file() and p != manifest]
        write(manifest, record)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shape', required=True, choices=SHAPES)
    prepare(parser.parse_args().shape)
