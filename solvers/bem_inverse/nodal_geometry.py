"""Fit-local exact-curve nodal geometry, shared by real and damped assembly."""
from collections import OrderedDict
from threading import RLock
from time import perf_counter
import numpy as np
from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.geometry import adapt_periodic_curve


class GeometryCache:
    def __init__(self, capacity=4, byte_limit=256*1024**2):
        self.capacity, self.byte_limit = capacity, byte_limit
        self._lock = RLock()
        self._entries = OrderedDict()
        self._stats = dict(builds=0, hits=0, evictions=0, bypasses=0, build_seconds=0.,
                           retained_device_bytes=0, peak_device_bytes=0,
                           retained_host_bytes=0, peak_host_bytes=0)

    def get(self, shape, nodes, selected, *, enabled):
        if not enabled:
            return shape.nodes(nodes), None, None
        device = 'cuda' if selected != 'cpu' and CA.available() else 'cpu'
        key = (shape.coefficients.dtype.str, shape.coefficients.shape,
               shape.coefficients.tobytes(), int(nodes), device)
        with self._lock:
            if key in self._entries:
                self._stats['hits'] += 1
                self._entries.move_to_end(key)
                return self._entries[key][0]
            started = perf_counter()
            curve = shape.nodes(nodes)
            adapter = adapt_periodic_curve(curve)
            prepared = None
            device_bytes = 0
            if device == 'cuda':
                import torch
                with CA._device_work:
                    prepared = CA.prepare_geometry(adapter, device)
                    torch.cuda.synchronize()
                device_bytes = sum(v.numel()*v.element_size() for v in prepared.values()
                                   if isinstance(v, torch.Tensor))
            # Conservative host accounting includes adapter arrays even when aliased.
            host_bytes = sum(v.nbytes for obj in (curve, adapter) for v in vars(obj).values()
                             if isinstance(v, np.ndarray)) + len(key[2])
            self._stats['builds'] += 1
            self._stats['build_seconds'] += perf_counter()-started
            for kind, size in (('device', device_bytes), ('host', host_bytes)):
                self._stats['peak_'+kind+'_bytes'] = max(self._stats['peak_'+kind+'_bytes'],
                    self._stats['retained_'+kind+'_bytes']+size)
            value = (curve, adapter, prepared)
            if max(device_bytes, host_bytes) > self.byte_limit:
                self._stats['bypasses'] += 1
                return value
            while self._entries and (len(self._entries) >= self.capacity or
                    self._stats['retained_device_bytes']+device_bytes > self.byte_limit or
                    self._stats['retained_host_bytes']+host_bytes > self.byte_limit):
                _, (_, old_device, old_host) = self._entries.popitem(last=False)
                self._stats['retained_device_bytes'] -= old_device
                self._stats['retained_host_bytes'] -= old_host
                self._stats['evictions'] += 1
            self._entries[key] = (value, device_bytes, host_bytes)
            self._stats['retained_device_bytes'] += device_bytes
            self._stats['retained_host_bytes'] += host_bytes
            return value

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._stats['retained_device_bytes'] = self._stats['retained_host_bytes'] = 0

    def receipt(self):
        with self._lock:
            return dict(self._stats, entries=len(self._entries), capacity=self.capacity,
                        byte_limit_each=self.byte_limit, key='exact coefficient bytes, shape, dtype, nodes, device')
