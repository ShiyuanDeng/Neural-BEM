"""AC-001 bounded scalar accuracy/timing study; no inverse campaign or truth data.

Run with PYTHONPATH=solvers:. python -m experiments.benchmark.analytic_radial_validation.
The archived DCT construction lives here only as an independent control.
"""
from pathlib import Path
import hashlib
import json
import platform
from time import perf_counter

import mpmath as mp
import numpy as np
from numpy.polynomial.chebyshev import chebval
from scipy.fft import dct
import scipy

from bem_inverse.modal_operator import radial_coefficients, radial_functions


OUTPUT = Path('results/validation/cleaned_interfaces/AC-001/scalars.json')


def sampled_coefficients(ko, ki, upper, tolerance=1e-15, fixed_count=None):
    """Preserved pre-AC-001 DCT algorithm (or an oversampled reference)."""
    alpha = max(abs(ko), abs(ki))*np.sqrt(upper)/2
    count = fixed_count or 16*int(np.ceil(max(64, 2*(alpha+6*alpha**(1/3)+24))/16))
    for _ in range(4):
        x = np.cos(np.pi*(np.arange(count)+.5)/count)
        values = radial_functions(upper*(x+1)/2, ko, ki)
        c = dct(values, type=2, axis=1)/count
        c[:, 0] /= 2
        if fixed_count:
            return c
        size = np.sum(np.abs(c), axis=1)
        later = np.maximum.accumulate(np.abs(c)[:, ::-1], axis=1)[:, ::-1]
        small = later <= tolerance*size[:, None]
        if np.all(small[:, count//2]):
            degree = int(max(np.argmax(row) for row in small))+2
            return c[:, :degree+1]
        count *= 2
    raise ValueError('Archived DCT radial series unresolved.')


def exact_values(ko, ki, points):
    with mp.workdps(80):
        ko, ki = mp.mpc(ko), mp.mpc(ki)

        def split(k, r):
            constant = mp.j/4-(mp.euler+mp.log(k/2))/(2*mp.pi)
            if not r:
                return (-1/(4*mp.pi), constant, k*k/(16*mp.pi),
                        -k*k/4*(constant+1/(2*mp.pi)))
            z = k*mp.sqrt(r)
            p = -mp.besselj(0, z)/(4*mp.pi)
            q = mp.j/4*mp.hankel1(0, z)-p*mp.log(r)
            dp = k*mp.besselj(1, z)/(8*mp.pi*mp.sqrt(r))
            dq = -mp.j*k*mp.hankel1(1, z)/(8*mp.sqrt(r))-dp*mp.log(r)-p/r
            return p, q, dp, dq

        rows = []
        for point in points:
            r = mp.mpf(float(point))
            po, qo, dpo, dqo = split(ko, r)
            pi, qi, dpi, dqi = split(ki, r)
            rows.append([complex(v) for v in (po-pi, qo-qi, dpo-dpi,
                dqo-dqi+((po-pi)/r if r else dpo-dpi),
                ko*ko*po-ki*ki*pi, ko*ko*qo-ki*ki*qi)])
        return np.array(rows).T


def median_seconds(function, args):
    function(*args)
    durations = []
    for _ in range(15):
        start = perf_counter()
        function(*args)
        durations.append(perf_counter()-start)
    return float(np.median(durations))


def main():
    rows = []
    for k, upper in ((.05, .01), (.6, 4.), (6.417188604442469, 12.), (6.417188604442469, 64.)):
        for contrast in (.5, 4., 13.3):
            for damping in (0., .25):
                ko = k*(1+1j*damping)
                args = (ko, ko*np.sqrt(contrast), upper)
                c, info = radial_coefficients(*args)
                reference = sampled_coefficients(*args, fixed_count=4096)
                scale = np.sum(np.abs(reference), axis=1)
                padded = np.pad(c, ((0, 0), (0, reference.shape[1]-c.shape[1])))
                coefficient_error = np.sum(np.abs(padded-reference), axis=1)/scale
                points = upper*np.array([0., 1e-12, .001, .17, .63, 1.])
                exact = exact_values(*args[:2], points)
                values = chebval(2*points/upper-1, c.T)
                value_error = np.max(np.abs(values-exact), axis=1)/scale
                old_values = chebval(2*points/upper-1, sampled_coefficients(*args).T)
                analytic_seconds = median_seconds(radial_coefficients, args)
                dct_seconds = median_seconds(sampled_coefficients, args)
                rows.append(dict(k=k, upper=upper, contrast=contrast, damping=damping,
                    diagnostics=info, coefficient_relative_l1=coefficient_error.tolist(),
                    value_error_over_coefficient_l1=value_error.tolist(),
                    origin_absolute_error=np.abs(values[:, 0]-exact[:, 0]).tolist(),
                    archived_dct_origin_absolute_error=np.abs(old_values[:, 0]-exact[:, 0]).tolist(),
                    archived_dct_value_error_over_coefficient_l1=(
                        np.max(np.abs(old_values-exact), axis=1)/scale).tolist(),
                    analytic_seconds=analytic_seconds, archived_dct_seconds=dct_seconds,
                    analytic_over_dct=analytic_seconds/dct_seconds,
                    passed=bool(max(np.max(coefficient_error), np.max(value_error)) <= 1e-11)))
    sources = ('solvers/bem_inverse/modal_operator.py', __file__)
    report = dict(study='AC-001', scope='scalar coefficients only; no inverse recovery claim',
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        mpmath=mp.__version__,
        sha256={str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in sources},
        scalar_names=['P_o-P_i', 'Q_o-Q_i', 'P_o_prime-P_i_prime',
                      'Q_o_prime-Q_i_prime+(P_o-P_i)/R', 'k2_P_difference', 'k2_Q_difference'],
        rows=rows, passed=all(row['passed'] for row in rows),
        maximum_coefficient_error=max(max(row['coefficient_relative_l1']) for row in rows),
        maximum_value_error=max(max(row['value_error_over_coefficient_l1']) for row in rows),
        median_analytic_over_dct=float(np.median([row['analytic_over_dct'] for row in rows])))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('passed', 'maximum_coefficient_error',
          'maximum_value_error', 'median_analytic_over_dct')}, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
