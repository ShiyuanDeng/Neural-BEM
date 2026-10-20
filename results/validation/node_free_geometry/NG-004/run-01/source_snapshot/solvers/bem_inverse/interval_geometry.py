"""NG-001 directed interval admissibility of finite dyadic Fourier curves.

Requires mpmath only when a verifier is constructed. Arc Taylor boxes and
monotone derivative projections cover the entire periodic parameter domain.
No polygon or point-only validity fallback is used. Failure is unresolved,
unless a declared admissibility violation is itself proved.
"""
import math
import hashlib
import time

import numpy as np


def _down(x):
    return float(np.nextafter(float(x.a), -np.inf))


def _up(x):
    return float(np.nextafter(float(x.b), np.inf))


class IntervalGeometry:
    def __init__(self, *, digits=30, max_seconds=5., max_cells=20000, max_depth=18):
        from mpmath.ctx_iv import MPIntervalContext
        self.iv = MPIntervalContext()
        self.iv.dps = digits
        self.max_seconds, self.max_cells, self.max_depth = max_seconds, max_cells, max_depth

    def _complex(self, z):
        return self.iv.mpc(float(z.real), float(z.imag))

    @staticmethod
    def curve_key(coefficients):
        a=np.asarray(coefficients,dtype='<c16')
        if a.ndim!=1 or len(a)%2!=1 or not np.isfinite(a).all():
            raise ValueError('Expected a finite odd-length coefficient vector.')
        while len(a)>1 and a[0]==0 and a[-1]==0:
            a=a[1:-1]
        return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

    def _jet(self,coefficients,derivatives,centre):
        """Directed Laurent Horner evaluation: one interval exponential."""
        iv=self.iv
        zero=iv.mpc(0)
        e=iv.exp(iv.mpc(0,iv.mpf(centre)))
        negative=iv.mpc(e.real,-e.imag)
        z,dz=coefficients.get(0,zero),zero
        for sign,phase in ((1,e),(-1,negative)):
            degree=max((sign*j for j in coefficients if sign*j>0),default=0)
            part,dpart=zero,zero
            for n in range(degree,0,-1):
                coefficient=coefficients.get(sign*n,zero)
                part=(part+coefficient)*phase
                dpart=(dpart+derivatives.get(sign*n,zero))*phase
            z+=part
            dz+=dpart
        return z,dz

    def _area_floor(self, coefficients):
        iv = self.iv
        K = len(coefficients)//2
        area, energy = iv.mpf(0), iv.mpf(0)
        for j,z in zip(range(-K, K+1), coefficients):
            a = self._complex(z)
            squared = a.real**2+a.imag**2
            area += j*squared
            energy += j*j*squared
        return area, iv.mpf(float(1e-12))*energy

    def increment(self, base, accepted, candidate):
        """Use exact interval differences, not rounded float subtraction."""
        started = time.perf_counter()
        old_key=self.curve_key(accepted)
        new_key=self.curve_key(candidate)
        if base['outcome'] != 'valid' or not base['arithmetic_verified']:
            return dict(outcome='unresolved', reason='base_unproved', seconds=time.perf_counter()-started)
        if base.get('curve_sha256')!=old_key:
            return dict(outcome='unresolved',reason='base_curve_mismatch',seconds=time.perf_counter()-started)
        K = max(len(accepted)//2, len(candidate)//2)
        def padded(a):
            return np.pad(a, (K-len(a)//2,)*2)
        old, new = padded(accepted), padded(candidate)
        amount = self.iv.mpf(0)
        for j,a,b in zip(range(-K, K+1),old,new):
            amount += abs(j)*abs(self._complex(b)-self._complex(a))
        lower = self.iv.mpf(base['lower_W'])-amount
        area, floor = self._area_floor(candidate)
        valid = _down(lower)>0 and _down(lower**2)>_up(floor) and _down(area)>0
        return dict(outcome='valid' if valid else 'unresolved', reason='direct_increment' if valid else 'increment_margin',
                    lower_W=max(0.,_down(lower)), increment_nu_upper=_up(amount),
                    curve_sha256=new_key,
                    arithmetic_verified=True, seconds=time.perf_counter()-started)

    def certify(self, coefficients):
        begun = time.perf_counter()
        key=self.curve_key(coefficients)
        iv = self.iv
        area, floor = self._area_floor(coefficients)
        if _up(area) <= 0:
            return dict(outcome='invalid', reason='nonpositive_area', arithmetic_verified=True,
                        seconds=time.perf_counter()-begun)
        if _down(area) <= 0:
            return dict(outcome='unresolved', reason='area_sign', arithmetic_verified=True,
                        seconds=time.perf_counter()-begun)
        K = len(coefficients)//2
        modes = np.arange(-K, K+1)
        threshold = 1e-13*max(1.,float(np.sum(np.abs(coefficients))))
        active = [(int(j),self._complex(z)) for j,z in zip(modes,coefficients) if abs(z)>threshold]
        active_coefficients=dict(active)
        active_derivatives={j:iv.mpc(0,j)*c for j,c in active}
        tails = [iv.mpf(0),iv.mpf(0)]
        for j,z in zip(modes,coefficients):
            if abs(z) <= threshold:
                magnitude = abs(self._complex(z))
                tails[0] += magnitude
                tails[1] += abs(int(j))*magnitude
        second = sum((j*j*abs(z) for j,z in active),iv.mpf(0))
        tau = _up(2*iv.pi)
        cache = {}
        examined = 0
        smallest = float('inf')

        def budget():
            if time.perf_counter()-begun > self.max_seconds:
                raise TimeoutError('seconds_budget')
            if examined > self.max_cells:
                raise TimeoutError('pair_cell_budget')

        def cell(lo,hi,depth=0):
            key=(lo,hi)
            if key in cache:
                return cache[key]
            budget()
            centre=(lo+hi)/2
            h=max(_up(iv.mpf(centre)-iv.mpf(lo)),_up(iv.mpf(hi)-iv.mpf(centre)))
            z,dz=self._jet(active_coefficients,active_derivatives,centre)
            radius=second*iv.mpf(h)**2/2+tails[0]
            delta=iv.mpf([-h,h])
            x=z.real+dz.real*delta+iv.mpf([-_up(radius),_up(radius)])
            y=z.imag+dz.imag*delta+iv.mpf([-_up(radius),_up(radius)])
            # An axis projection has exact unit norm, avoiding a normalized
            # floating tangent in the proof.
            components=(dz.real,dz.imag)
            projection=max(components,key=lambda t:abs((float(t.a)+float(t.b))/2))
            sign=1 if (float(projection.a)+float(projection.b))>=0 else -1
            cone=sign*projection-second*iv.mpf(h)-tails[1]
            result=dict(lo=lo,hi=hi,depth=depth,centre=centre,h=h,
                        box=(_down(x),_up(x),_down(y),_up(y)),cone=_down(cone),
                        phase=iv.exp(iv.mpc(0,centre)))
            cache[key]=result
            return result

        def split(c):
            if c['depth']>=self.max_depth:
                raise TimeoutError('depth_budget')
            mid=(c['lo']+c['hi'])/2
            return (cell(c['lo'],mid,c['depth']+1),cell(mid,c['hi'],c['depth']+1))

        try:
            pending=[cell(i*tau/16,(i+1)*tau/16) for i in range(16)]
            arcs=[]
            while pending:
                c=pending.pop()
                if c['cone']>0 and _down(iv.mpf(c['cone'])**2)>_up(floor):
                    arcs.append(c)
                    smallest=min(smallest,c['cone'])
                else:
                    pending.extend(split(c))
            arcs.sort(key=lambda c:c['lo'])
            pairs=[(a,b) for i,a in enumerate(arcs) for b in arcs[i+1:]]
            while pairs:
                budget()
                a,b=pairs.pop()
                examined+=1
                A,B=a['box'],b['box']
                gx=max(0.,_down(iv.mpf(A[0])-B[1]),_down(iv.mpf(B[0])-A[1]))
                gy=max(0.,_down(iv.mpf(A[2])-B[3]),_down(iv.mpf(B[2])-A[3]))
                gap=max(gx,gy)
                if gap>0:
                    denominator=min(2.,_up(abs(a['phase']-b['phase'])+iv.mpf(a['h'])+iv.mpf(b['h'])))
                    smallest=min(smallest,_down(iv.mpf(gap)/iv.mpf(denominator)))
                    continue
                lo,hi=min(a['lo'],b['lo']),max(a['hi'],b['hi'])
                # Exact periodicity permits a wrapped connected interval.
                # Subtract lower/upper enclosures of 2pi to cover it.
                if hi-lo > tau/2:
                    left,right=(a,b) if a['lo']<b['lo'] else (b,a)
                    lo=_down(iv.mpf(right['lo'])-2*iv.pi)
                    hi=left['hi']
                union=cell(lo,hi,max(a['depth'],b['depth']))
                if union['cone']>0:
                    smallest=min(smallest,union['cone'])
                    continue
                if a['hi']-a['lo'] >= b['hi']-b['lo']:
                    pairs.extend((child,b) for child in split(a))
                else:
                    pairs.extend((a,child) for child in split(b))
            return dict(outcome='valid',reason='arc_range_cover',lower_W=smallest,
                        curve_sha256=key,jet_evaluation='directed Laurent Horner',
                        arithmetic_verified=True,interval_digits=iv.dps,arcs=len(arcs),
                        pair_cells=examined,range_cells=len(cache),active_modes=len(active),
                        omitted_position_bound=_up(tails[0]),omitted_derivative_bound=_up(tails[1]),
                        seconds=time.perf_counter()-begun)
        except TimeoutError as exc:
            return dict(outcome='unresolved',reason=str(exc),arithmetic_verified=True,
                        pair_cells=examined,range_cells=len(cache),active_modes=len(active),
                        seconds=time.perf_counter()-begun)
