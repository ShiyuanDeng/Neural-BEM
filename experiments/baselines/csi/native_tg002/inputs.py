"""Freeze the native paired observations and the seven-column CC-CSI table."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.constants import c as C0
from scipy.special import hankel1

from experiments.benchmark import campaign, scenes
from experiments.comparison import bem, noise, runs
from bem_inverse.io import digest, read

REPO = campaign.ROOT
EXTERNAL = Path.home() / 'neural_bem_external'


def arguments(description, *, forward=False):
    parser = argparse.ArgumentParser(description=description)
    choices = ['circle__c4'] if forward else ['circle__c4', 'kite__c4']
    parser.add_argument('--case', required=True, choices=choices)
    if not forward:
        parser.add_argument('--data', required=True, choices=['clean', 'n1d0'])
    parser.add_argument('--run-dir', required=True, type=Path)
    return parser.parse_args()


def write_json(path, value):
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def pins():
    sources = read(REPO / 'external/sources.json')['sources']
    states = {}
    for name in ['cc-csi', 'maxwellfdfd']:
        pin = sources[name]
        repo = EXTERNAL / pin['checkout']
        git = ['git', '-C', str(repo)]
        head = subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip()
        if head != pin['commit']:
            raise ValueError(f'{repo} is not at its pinned commit')
        states[name] = dict(commit=head, dirty_status=subprocess.check_output(
            git + ['status', '--porcelain'], text=True).splitlines())
        if name == 'cc-csi':
            rel = 'functions/CSI.m'
            current = digest(repo / rel)
            pinned = hashlib.sha256(subprocess.check_output(git + ['show', f'{head}:{rel}'])).hexdigest()
            if current != pinned:
                raise ValueError('CSI.m differs from its pinned bytes')
            states[name]['CSI_m_sha256'] = current
    return states


def native_observation(case, data):
    row = campaign.row(case)
    run = runs.parse(f'bem/default_{data}_uc_sf0.5')
    (obs,), _ = bem.observations(run, row, runs.RESULTS)
    return obs, row, run


def freeze(case, data, run_dir):
    obs, row, run = native_observation(case, data)
    sealed = REPO / row['data']
    manifest = read(campaign.INPUTS / 'manifest.json')
    source_hash = digest(sealed)
    if not manifest['inputs_sealed'] or source_hash != manifest['inputs'][str(sealed.relative_to(campaign.INPUTS))]:
        raise ValueError('observations differ from the TG-002 seal')
    source = dict(path=row['data'], sha256=source_hash)
    noise_source = None
    if run.noise:
        p = noise.path(*run.noise, case)
        noise_source = dict(path=str(p.relative_to(REPO)), sha256=digest(p))
    src = obs.acquisition.sources * scenes.LENGTH
    rec = obs.acquisition.receivers * scenes.LENGTH
    strength = complex(obs.acquisition.strength)
    if strength != 1e-6 or src.shape != (24, 2) or rec.shape != (24, 2):
        raise ValueError('unexpected native acquisition')
    k = float(obs.wavenumber) / scenes.LENGTH
    f_equiv = k * C0 / (2 * np.pi * 1e9)
    ids = np.arange(1, 25)
    native = obs.scattered
    inc = strength * 0.25j * hankel1(0, k * np.linalg.norm(rec - src, axis=1))
    inc_csi = np.conj(inc / strength)
    total_csi = inc_csi + np.conj(native / strength)
    angles = lambda xy: np.mod(np.degrees(np.arctan2(xy[:, 1], xy[:, 0])), 360)
    table = np.column_stack((angles(src), angles(rec), np.full(24, f_equiv),
                             total_csi.real, total_csi.imag, inc_csi.real, inc_csi.imag))
    # ReadFreData orders receiver rows by unique ascending angle, columns by source block.
    _, rec_idx = np.unique(table[:, 1], return_inverse=True)
    mask = np.zeros((24, 24), dtype=int)
    mask[rec_idx, ids - 1] = 1
    states = pins()
    out = run_dir / 'inputs' / f'{case}__{data}'
    out.mkdir(parents=True, exist_ok=False)
    np.savetxt(out/'readings.csv', np.column_stack((ids, native.real, native.imag)),
               delimiter=',', fmt=['%d', '%.17g', '%.17g'])
    np.savetxt(out/'geometry.csv', np.column_stack((ids, ids, src, rec)), delimiter=',', fmt='%.17g')
    np.savetxt(out/'table.csv', table, delimiter=',', fmt='%.17g')
    np.savetxt(out/'mask.csv', mask, delimiter=',', fmt='%d')
    hashes = {p.name: digest(p) for p in sorted(out.glob('*.csv'))}
    record = dict(case=case, data=data, sealed=source, noise=noise_source, sha256=hashes,
                  native_readings_sha256=hashlib.sha256(native.astype('<c16').tobytes()).hexdigest(),
                  native_readings_encoding='24 little-endian complex128 in sealed pair order',
                  upstream=states, frequency_hz=obs.frequency_hz, k_background_per_m=k,
                  vacuum_equivalent_GHz=f_equiv, exterior_relative_permittivity=6,
                  image_ratio='1 + real(chi); chi is susceptibility relative to the exterior',
                  source_strength=strength.real, native_units_per_csi_unit=strength.real,
                  to_csi='conj(native / source_strength)', to_native='source_strength * conj(csi)',
                  geometry_columns=['source_id','receiver_id','source_x_m','source_y_m','receiver_x_m','receiver_y_m'],
                  geometry_origin='ring centre', ring_radius_m=.30, offset_rad=.20,
                  readings_columns=['pair_id','native_scattered_real','native_scattered_imag'],
                  table_columns=['source_deg','receiver_deg','equivalent_GHz','total_real','total_imag',
                                 'incident_real','incident_imag'],
                  mask_axes=['receiver angle ascending','source in sealed order'])
    write_json(out / 'inputs.json', record)
    print(f'{case} {data}: {len(native)} readings; SHA-256 {record["native_readings_sha256"]}')


if __name__ == '__main__':
    args = arguments(__doc__)
    freeze(args.case, args.data, args.run_dir)
