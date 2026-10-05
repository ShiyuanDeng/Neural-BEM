"""AC-002 exclusive forward timing; runs only a bounded TG-002 forward probe."""
from collections import defaultdict
from contextlib import contextmanager, ExitStack
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter
from unittest.mock import patch

import numpy as np
import torch

from bem_inverse import modal_muller as service_module
from bem_inverse import modal_geometry, modal_cuda, modal_operator
from bem_inverse.modal_muller import ModalMuller, token
from bem_inverse.physics import Execution
from .campaign import problem
from .scenes import truth_fixture


class Timers:
    def __init__(self, device):
        self.device = device
        self.seconds = defaultdict(float)
        self.stack = []

    @contextmanager
    def region(self, name, sync=False):
        started = perf_counter()
        frame = [0.]
        self.stack.append(frame)
        try:
            if sync:
                torch.cuda.synchronize()
            yield
            if sync:
                torch.cuda.synchronize()
        finally:
            elapsed = perf_counter()-started
            self.stack.pop()
            self.seconds[name] += elapsed-frame[0]
            if self.stack:
                self.stack[-1][0] += elapsed

    def wrapped(self, function, name, sync=False):
        def measured(*args, **kwargs):
            with self.region(name, sync):
                return function(*args, **kwargs)
        return measured

    @contextmanager
    def installed(self):
        original_stage = ModalMuller._stage

        @contextmanager
        def stage(service, kind):
            with self.region(kind):
                with original_stage(service, kind):
                    yield

        gpu = self.device == 'cuda'
        module = modal_cuda if gpu else modal_geometry
        arrays = module.DeviceChebyshevArrays if gpu else module.ChebyshevArrays
        coefficient_module = modal_cuda if gpu else modal_operator
        with ExitStack() as patches:
            patches.enter_context(patch.object(ModalMuller, '_stage', stage))
            for owner, attribute, name, sync in (
                (module, 'log_modulus', 'log_chebyshev_and_certificate', gpu),
                (arrays, '__init__', 'radial_chebyshev_setup', gpu),
                (arrays, 'ensure', 'radial_chebyshev_extension', gpu),
                (arrays, 'combine', 'radial_coefficient_contraction', gpu),
                (coefficient_module, 'radial_coefficients', 'scalar_analytic_coefficients', False),
            ):
                patches.enter_context(patch.object(owner, attribute,
                    self.wrapped(getattr(owner, attribute), name, sync)))
            yield


def main():
    assert torch.cuda.is_available(), 'CUDA access is required for this paired profile.'
    case = problem('c_shape__c13.3')
    curve, observation = truth_fixture('c_shape'), case.real[-1]
    rows = []
    for device in ('cpu', 'cuda'):
        execution = Execution(device=device, frequency_threads=1)
        warmup = ModalMuller(execution)
        reference = warmup.evaluate(curve, observation, case.contrast, token(96)).prediction
        for repetition in range(3):
            service = ModalMuller(execution)
            for cache in ('fresh', 'reused'):
                timers = Timers(device)
                if device == 'cuda':
                    torch.cuda.synchronize()
                with timers.installed():
                    start = perf_counter()
                    prediction = service.evaluate(curve, observation, case.contrast, token(96))
                    if device == 'cuda':
                        torch.cuda.synchronize()
                    total = perf_counter()-start
                np.testing.assert_allclose(prediction.prediction, reference, rtol=1e-11, atol=1e-15)
                seconds = dict(timers.seconds)
                seconds['overhead'] = total-sum(seconds.values())
                assert min(seconds.values()) >= -1e-9
                assert abs(sum(seconds.values())-total) < 1e-9
                rows.append(dict(device=device, cache=cache, repetition=repetition,
                    total_seconds=total, exclusive_seconds=seconds,
                    field_relative_difference=float(np.linalg.norm(prediction.prediction-reference)
                                                    /np.linalg.norm(reference)),
                    radial_degree=prediction.diagnostics['radial_degree'],
                    log_degree=prediction.diagnostics['log_degree']))
    summaries = []
    for device in ('cpu', 'cuda'):
        for cache in ('fresh', 'reused'):
            selected = [r for r in rows if r['device'] == device and r['cache'] == cache]
            total = sum(r['total_seconds'] for r in selected)
            names = set().union(*(r['exclusive_seconds'] for r in selected))
            durations = {name: sum(r['exclusive_seconds'].get(name, 0.) for r in selected)
                         for name in sorted(names)}
            summaries.append(dict(device=device, cache=cache, mean_seconds=total/len(selected),
                mean_stage_seconds={name: value/len(selected) for name, value in durations.items()},
                percent={name: 100*value/total for name, value in durations.items()}))
    paths = [Path(__file__), *(Path(module.__file__) for module in
              (service_module, modal_operator, modal_geometry, modal_cuda))]
    report = dict(study='AC-002', scene='TG-002 c_shape', contrast=case.contrast,
        frequency_hz=observation.frequency_hz, trace_cutoff=96, coefficient_window=160,
        threads=1, repetitions=3, python=platform.python_version(), numpy=np.__version__,
        torch=torch.__version__, gpu=torch.cuda.get_device_name(0),
        source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        timing_scope='Exclusive instrumented wall time; CUDA boundary synchronization; initialization excluded',
        rows=rows, summaries=summaries, passed=True)
    output = Path('results/validation/cleaned_interfaces/AC-002/profile.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
