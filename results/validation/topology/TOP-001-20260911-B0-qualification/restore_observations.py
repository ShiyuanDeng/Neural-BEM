"""Restore ignored NPZ inputs exactly from the portable, tracked observations."""
import json
from pathlib import Path
import numpy as np

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    for chart in ('radial','cartesian'):
        path = root / chart / 'split'
        payload = json.loads((path/'observations.json').read_text())
        manifest = json.loads((path/'manifest.json').read_text())
        arrays = dict(observed=np.array(payload['observed_real'])+1j*np.array(payload['observed_imag']),
            source_points=np.array(payload['problem']['source_points']),
            receiver_points=np.array(payload['problem']['receiver_points']),
            frequencies_hz=np.array(manifest['frequencies_hz']))
        target=path/'observations.npz'
        if target.exists():
            with np.load(target) as old:
                for key, value in arrays.items():
                    np.testing.assert_array_equal(old[key], value)
            print(f'{chart}: existing input arrays verified')
        else:
            np.savez_compressed(target, **arrays)
            print(f'{chart}: restored arrays (NPZ container bytes may differ)')
