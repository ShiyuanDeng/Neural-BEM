"""Work charging, ordered dispatch, quotas and elapsed-time accounting."""
from contextlib import contextmanager
from threading import RLock
from time import perf_counter
from .errors import StageQuota, TrialSolveCap, TrialWallLimit

class Ledger:
    """Work units, stage quotas and hard limits with the SPD reservation rule.

    A reservation raises before a batch whose declared maximum would cross
    the stage quota (a normal stage end) or the total cap/wall (a hard stop).
    """

    def __init__(self, cap=8012, seconds=7200.0, clock=perf_counter, endpoint_reserve=12,
                 strict_dispatch=False):
        self.cap, self.seconds, self.clock = int(cap), float(seconds), clock
        self.endpoint_reserve = int(endpoint_reserve)
        self.started = clock()
        self.units = 0
        self.stage = None
        self.stage_start = 0
        self.stage_quota = None
        self.endpoint = False
        self.solves = {}
        self.failed = {}
        self.reciprocal = {}
        self.strict_dispatch = strict_dispatch
        self._lock = RLock()

    @contextmanager
    def calls(self, calls_for, function, items, kind, category):
        """Opt-in accounting at dispatch; default retains historical SPD receipts."""
        items = tuple(items)
        if not self.strict_dispatch:
            with calls_for(function, items) as calls:
                def consume(call):
                    self.reserve(1)
                    self.charge(kind, category)
                    return call()
                yield [lambda call=call: consume(call) for call in calls]
            return
        self.reserve(len(items))  # complete batch, before a pool starts any work
        def dispatched(item):
            with self._lock:
                self.reserve(1)
                self.charge(kind, category)
            try:
                return function(item)
            except Exception:
                with self._lock:
                    self.fail(category)
                raise
        with calls_for(dispatched, items) as calls:
            yield calls

    def begin_stage(self, label, quota):
        if self.clock() - self.started >= self.seconds:
            raise TrialWallLimit("hard wall limit at stage boundary")
        if self.units >= self.cap:
            raise TrialSolveCap("hard work cap at stage boundary")
        self.stage, self.stage_start, self.stage_quota = label, self.units, quota

    @classmethod
    def restore(cls, snapshot, *, seconds, endpoint_reserve=12, strict_dispatch=False):
        """Restore consumed fitting work/time without granting a new stage quota."""
        ledger = cls(cap=snapshot['cap'], seconds=seconds, endpoint_reserve=endpoint_reserve,
                     strict_dispatch=strict_dispatch)
        ledger.units = snapshot['work_units']
        ledger.stage = snapshot['stage']
        ledger.stage_start = ledger.units-snapshot['stage_units']
        ledger.stage_quota = snapshot['stage_quota']
        ledger.solves = dict(snapshot['solves'])
        ledger.reciprocal = dict(snapshot['reciprocal_batches'])
        ledger.failed = dict(snapshot['failed'])
        ledger.started -= snapshot['seconds']
        return ledger

    def reserve(self, maximum):
        overhead = self.endpoint_reserve if self.stage is not None and not self.endpoint else 0
        spent = self.units - self.stage_start
        if self.clock() - self.started >= self.seconds:
            raise TrialWallLimit("hard wall limit")
        if self.units >= self.cap and maximum + overhead > 0:
            raise TrialSolveCap("total work cap reached")
        if (self.stage_quota is not None and spent + maximum + overhead > self.stage_quota
                and self.stage_quota - spent <= self.cap - self.units
                and self.units + overhead <= self.cap):
            raise StageQuota("next complete batch and endpoint reserve exceed the stage quota")
        if self.units + maximum + overhead > self.cap:
            raise TrialSolveCap("next complete batch and endpoint reserve exceed the total cap")

    @contextmanager
    def endpoint_scope(self):
        previous, self.endpoint = self.endpoint, True
        try:
            yield
        finally:
            self.endpoint = previous

    def charge(self, kind, category):
        store = self.solves if kind == "solve" else self.reciprocal
        key = f"{self.stage}:{category}"
        store[key] = store.get(key, 0) + 1
        self.units += 1

    def replay(self, kind, category, count):
        """Charge ``count`` calls exactly as ``calls`` would, for results reused without dispatch.

        Reservations and charges follow the same order, so quotas, caps and receipts are
        unchanged; only the solver work is skipped.
        """
        if self.strict_dispatch:
            self.reserve(count)
        for _ in range(count):
            with self._lock:
                self.reserve(1)
                self.charge(kind, category)

    def fail(self, category):
        key = f"{self.stage}:{category}"
        self.failed[key] = self.failed.get(key, 0) + 1

    def snapshot(self):
        return dict(work_units=self.units, stage=self.stage, stage_units=self.units - self.stage_start,
                    stage_quota=self.stage_quota, cap=self.cap, solves=dict(self.solves),
                    reciprocal_batches=dict(self.reciprocal), failed=dict(self.failed),
                    seconds=self.clock() - self.started)


Ledger.__module__ = "bem_inverse.continuation.lm_backend"
