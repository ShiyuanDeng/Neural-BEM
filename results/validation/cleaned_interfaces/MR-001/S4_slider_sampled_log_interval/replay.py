"""Replay S3's failed aphex trial through CPU and CUDA A1 geometry."""
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import torch

from bem_inverse.a1_geometry import ModalGeometry
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.modal_cuda import DeviceModalGeometry

root = Path('results/validation/cleaned_interfaces/MR-001')
source = root / 'S3_slider_no_log_cap/runs/aphex_twin__c0.5/stage_3_damped.json'
failure = json.loads(source.read_text())['physics_failures'][0]
coefficients = failure['candidate_coefficients']
curve = FourierCurve(np.array(coefficients['real']) + 1j*np.array(coefficients['imag']))
assert torch.cuda.is_available(), 'The requested CUDA replay needs a visible GPU.'
started = perf_counter()
cpu = ModalGeometry(curve, 128)
gpu = DeviceModalGeometry(curve, 128, device='cuda')
for geometry in (cpu, gpu):
    interval = geometry.log_interval
    assert interval['interval_source'] == 'sampled_unverified'
    assert interval['certificate']['lower'] <= 0
    assert interval['lower'] == interval['sampled_minimum']/2 > 0
    assert interval['series_bound'] <= 1e-16
gpu_log = gpu.log.cpu().numpy()
assert np.isfinite(cpu.log).all() and np.isfinite(gpu_log).all()
relative_difference = float(np.linalg.norm(cpu.log-gpu_log)/np.linalg.norm(cpu.log))
assert relative_difference < 1e-8, relative_difference
receipt = dict(source=str(source), old_failure=failure['message'],
               cpu=cpu.log_interval, cuda=gpu.log_interval,
               relative_log_difference=relative_difference, seconds=perf_counter()-started)
destination = root / 'S4_slider_sampled_log_interval/replay.json'
destination.write_text(json.dumps(receipt, indent=2)+'\n')
print('Saved failed trial now returns finite CPU/CUDA logarithms with sampled intervals.', flush=True)
print('CPU/CUDA relative difference:', relative_difference, flush=True)
