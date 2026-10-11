"""Opt-in paths for complex-radius research and its real graph control.

The real control uses the affine stationary equation F(q,t)=A(q)-t*B(q).
Its sampled denominator guards establish numerical resolution, not certified
absence of a zero between samples. It never reconnects after a refusal.
"""
from time import perf_counter

import numpy as np

from .complex_radius import ComplexDomainError, record_state


def lollipop_path(tf, radius, base=1., height=.05, points=256):
    """A counterclockwise circle attached to a real base by an upper stem.

    The stem is retraced exactly after the loop; returning to the same data
    parameter does not imply restoration of the lifted stationary root.
    """
    if (not all(np.isfinite(x) and np.isreal(x) for x in (tf, radius, base, height))
            or not 0 < radius < height or points < 8 or int(points) != points):
        raise ValueError('Finite real parameters, 0 < radius < height and integer points >= 8 required')
    tf, radius, base, height = map(float, (tf, radius, base, height))
    attachment = np.array([base, base+1j*height, tf+1j*height], complex)
    circle = tf+1j*radius*np.exp(1j*np.linspace(0, 2*np.pi, int(points)+1))
    circle[0] = circle[-1] = tf+1j*radius
    return np.concatenate((attachment, circle, attachment[::-1]))


def _graph_state(model, q):
    A, B, _ = model.ab(q)
    values = [complex(v) for v in (A[0], A[1], B[0], B[1])]
    if any(not np.isfinite(v) or abs(v.imag) > 1e-10*max(1., abs(v.real)) for v in values):
        raise ComplexDomainError('REAL_GRAPH_JETS: nonfinite or nonreal affine jets')
    a, ap, b, bp = (v.real for v in values)
    if b == 0:
        raise ComplexDomainError('B_ZERO: radius graph denominator vanishes')
    t = a/b
    if not np.isfinite(t):
        raise ComplexDomainError('B_RATIO: nonfinite radius graph parameter')
    row = record_state(model, q, t)
    row.update(B=b, Bq=bp, Tq=(ap-t*bp)/b)
    return row


def _guard_segment(left, middle, right, max_dt, t_bounds):
    rows = (left, middle, right)
    if any(not t_bounds[0] <= row['t'].real <= t_bounds[1] for row in rows):
        raise ComplexDomainError('T_DOMAIN_BOUNDARY: radius graph left the real parameter window')
    if any(np.sign(row['B']) != np.sign(left['B']) for row in rows[1:]):
        raise ComplexDomainError('B_SIGN: sampled graph denominator changes sign')
    if abs(right['t']-left['t']) > max_dt:
        raise ComplexDomainError('T_RESOLUTION: full graph step exceeds parameter increment')
    for first, second in ((left, middle), (middle, right)):
        h = abs(second['q']-first['q'])
        if h*max(abs(first['Bq']), abs(second['Bq'])) > .1*min(abs(first['B']), abs(second['B'])):
            raise ComplexDomainError('B_RESOLUTION: sampled derivative resolves denominator too poorly')
        if abs(second['t']-first['t']) > max_dt/2:
            raise ComplexDomainError('T_RESOLUTION: half graph step exceeds parameter increment')
        if h*max(abs(first['Tq']), abs(second['Tq'])) > max_dt:
            raise ComplexDomainError('T_RESOLUTION: sampled tangent requires a smaller graph step')


def radius_graph(model, q0=1.3, *, direction=1, q_bounds=(.5, 2.),
                 t_bounds=(-2., 3.), max_dq=1e-5, max_dt=.002,
                 min_dq=1e-10, steps=20000):
    """Continue the real stationary graph t=A/B from one prescribed radius.

    Both midpoints and endpoints of accepted steps are retained. Rejected
    trials are halved and preserved. Denominator signs and derivative guards
    use point samples only; they are not interval bounds. The result includes
    t=1 brackets from adjacent accepted states, without correcting any root.
    """
    if (direction not in (-1, 1) or not np.isfinite(q0) or not np.isreal(q0)
            or not q_bounds[0] < q_bounds[1] or not q_bounds[0] <= q0 <= q_bounds[1]
            or not t_bounds[0] < t_bounds[1] or not 0 < min_dq <= max_dq
            or not max_dt > 0 or steps < 1 or int(steps) != steps):
        raise ValueError('Valid real chart, direction +/-1, positive steps and step bounds required')
    started = perf_counter()
    first = _graph_state(model, float(q0))
    if not t_bounds[0] <= first['t'].real <= t_bounds[1]:
        raise ComplexDomainError('Initial graph state lies outside the real parameter window')
    states, rejected, brackets = [first], [], []
    q_boundary = q_bounds[1] if direction > 0 else q_bounds[0]
    cap, attempts, accepted = max_dq, 0, 0
    status, last_reason = 'STEP_BUDGET', None
    for _ in range(int(steps)):
        current = states[-1]
        q = current['q'].real
        remaining = abs(q_boundary-q)
        if remaining == 0:
            status = 'Q_DOMAIN_BOUNDARY'
            break
        step = min(cap, remaining)
        while True:
            dq = direction*step
            if q+dq == q or step < min_dq:
                if last_reason and last_reason.startswith('T_DOMAIN_BOUNDARY:'):
                    status = 'T_DOMAIN_BOUNDARY'
                elif last_reason and last_reason.startswith('B_'):
                    status = 'B_DENOMINATOR_REFUSAL'
                else:
                    status = 'MINIMUM_STEP'
                break
            attempts += 1
            try:
                middle = _graph_state(model, q+dq/2)
                right_q = q_boundary if step == remaining else q+dq
                right = _graph_state(model, right_q)
                _guard_segment(current, middle, right, max_dt, t_bounds)
                for row in (middle, right):
                    left = states[-1]
                    states.append(row)
                    if (left['t'].real-1)*(row['t'].real-1) <= 0:
                        brackets.append(dict(left_index=len(states)-2, right_index=len(states)-1,
                            q_left=left['q'].real, q_right=row['q'].real,
                            t_left=left['t'].real, t_right=row['t'].real))
                accepted += 1
                cap = min(max_dq, step*1.5)
                last_reason = None
                break
            except (ComplexDomainError, FloatingPointError, ZeroDivisionError) as exc:
                last_reason = str(exc)
                rejected.append(dict(q=current['q'], t=current['t'], dq=dq, reason=last_reason))
                step /= 2
        if status != 'STEP_BUDGET':
            break
        if states[-1]['q'].real == q_boundary:
            status = 'Q_DOMAIN_BOUNDARY'
            break
    return dict(status=status, states=states, rejected=rejected, attempts=attempts,
                accepted_steps=len(states)-1, graph_steps=accepted, seconds=perf_counter()-started,
                last_reason=last_reason, t1_brackets=brackets)
