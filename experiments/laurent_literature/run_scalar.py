"""Reproduce JWY2021 index counts and manufactured-density ellipse convergence."""
import argparse
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

from .scalar import (ellipse_coefficients, ellipse_log_density, kernel_matrix,
                     literature_mask, convolution_diagonal)
from .evidence import Evidence

PUBLISHED_EXAMPLE3 = {
    16: (.263, .257, .269), 32: (.0586, .0592, .0633),
    64: (.00532, .00536, .00542), 128: (7.73e-5, 7.73e-5, 8.73e-5),
    256: (2.99e-8, 2.99e-8, 7.09e-8), 512: (1.74e-14, 2.52e-14, 4.25e-12)}
PUBLISHED_CC = {64:(15.48,10.41),128:(16.74,10.84),256:(17.78,11.15),
                512:(18.72,11.42),1024:(19.50,11.59)}
PUBLISHED_CR = {64:(.0651,.0431),128:(.0347,.0228),256:(.0183,.0119),
                512:(.0095,.0062),1024:(.0049,.0031)}


def density_coefficients(example, cutoff, samples=1048576):
    modes = np.arange(-cutoff, cutoff+1)
    if example == 3:
        return ellipse_log_density(modes)
    t = 2*np.pi*np.arange(samples)/samples
    r = np.abs(2*np.cos(t)+1j*np.sin(t)-2)
    if example == 1:
        rho = r*np.log(np.maximum(r, 1e-300))
    elif example == 2:
        rho = r*t
    else:
        raise ValueError(example)
    return np.fft.fft(rho)[modes%samples]*np.sqrt(2*np.pi)/samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--stage', choices=['pilot','campaign'], default='pilot')
    args = parser.parse_args()
    ns = [16,32,64,128] if args.stage == 'pilot' else [16,32,64,128,256,512,1024]
    examples = [3] if args.stage == 'pilot' else [1,2,3]
    record = Evidence(args.output, dict(stage=args.stage, ns=ns, examples=examples,
        wave=3., axes=[2.,1.], grids=[256,512], mu=[1.1,1.2,1.4],
        source='doi:10.1007/s11075-021-01082-0, Sections 2,3,6',
        purpose='Truncation/convergence reproduction; dense reference assembly, no fast-assembly claim',
        example3_wavenumber='3, inherited from preceding examples; not restated in Example 3',
        density_samples=[524288,1048576],density_tail_cutoff=131071,
        scalar_reference_relative_gate=1e-10, example3_final_error_gate=1e-10))
    count_rows, rows = [], []
    for n, cc in PUBLISHED_CC.items():
        for j, mu in enumerate([1.2,1.4]):
            mask = literature_mask(n-1, mu)
            count = int(mask.sum())
            count_rows.append(dict(n=n, mu=mu, retained=count, size=2*n-1,
                cr=count/mask.size, cc=count/(2*n-1), published_cr=PUBLISHED_CR[n][j],
                published_cc=cc[j], cc_matches_rounding=round(count/(2*n-1),2)==cc[j],
                published_identity_discrepancy=PUBLISHED_CR[n][j]*(2*n-1)-cc[j]))
    record.csv('counts.csv', count_rows)
    # Large enough to include every input mode which can couple to the largest
    # scored output window under the independently refined coefficient support.
    ref_k = max(ns)-1+256
    record.reserve(assemblies=2)
    p, s = ellipse_coefficients(2.,1.,3.,256)
    a_coarse = kernel_matrix(p,s,ref_k)
    p, s = ellipse_coefficients(2.,1.,3.,512)
    a_ref = kernel_matrix(p,s,ref_k)
    refinement = float(np.linalg.norm(a_ref-a_coarse)/np.linalg.norm(a_ref))
    if refinement > 1e-10:
        record.finish(reference_qualified=False, refinement=refinement)
        raise RuntimeError('Scalar operator reference not qualified')
    del a_coarse
    # Tail retained well beyond every solve window, independently of RHS size.
    tail_k = 131071
    true = {e:density_coefficients(e,tail_k) for e in examples}
    coarse = {e:density_coefficients(e,tail_k,524288) for e in examples}
    f_ref = {e:a_ref @ true[e][tail_k-ref_k:tail_k+ref_k+1] for e in examples}
    density_refinement = {str(e):float(np.linalg.norm(true[e]-coarse[e])) for e in examples}
    density_tail_extension = {str(e):float(np.linalg.norm(np.r_[v[:tail_k-65535],v[tail_k+65536:]]))
                              for e,v in true.items()}
    for n in ns:
        k = n-1
        sel = slice(ref_k-k, ref_k+k+1)
        a = a_ref[sel,sel].copy()
        a0 = np.diag(convolution_diagonal(k))
        rem = a-a0
        scale = np.sqrt(1+np.arange(-k,k+1,dtype=float)**2)
        for mu in [None,1.1,1.2,1.4]:
            mask = np.ones_like(a, bool) if mu is None else literature_mask(k,mu)
            compressed = a0+mask*rem
            record.reserve(factorizations=1)
            started = perf_counter()
            if mu is None:
                factors = lu_factor(scale[:,None]*compressed)
                solve = lambda f: lu_solve(factors,scale*f)
                factor_slots = int(a.size)
            else:
                factors = splu(csc_matrix(scale[:,None]*compressed))
                solve = lambda f: factors.solve(scale*f)
                factor_slots = int(factors.L.nnz+factors.U.nnz)
            factor_seconds = perf_counter()-started
            for e in examples:
                f = f_ref[e][sel]
                solution = solve(f)
                exact = true[e][tail_k-k:tail_k+k+1]
                tail = np.r_[true[e][:tail_k-k],true[e][tail_k+k+1:]]
                err = float(np.hypot(np.linalg.norm(solution-exact),np.linalg.norm(tail)))
                density_error = float(np.linalg.norm(solution-exact))
                published = (PUBLISHED_EXAMPLE3[n][[None,1.1,1.2].index(mu)]
                             if e==3 and n in PUBLISHED_EXAMPLE3 and mu in [None,1.1,1.2] else None)
                rows.append(dict(example=e,n=n,cutoff=k,arm='CFG' if mu is None else f'FFG_mu{mu}',
                    error_l2=err, resolved_density_error=density_error, tail_l2=float(np.linalg.norm(tail)),
                    published_error=published, same_as_printed_table=(abs(err-published)/published < .05) if published else None,
                    relative_full_residual=float(np.linalg.norm(a@solution-f)/np.linalg.norm(f)),
                    retained=int(mask.sum()), total=int(mask.size), retained_fraction=float(mask.mean()),
                    factor_slots=factor_slots, factor_seconds=factor_seconds))
            record.csv('convergence.csv',rows)
        print(f'completed scalar n={n}',flush=True)
        record.check()
    np.savez_compressed(record.out/'density_reference.npz', **{f'example{e}':v for e,v in true.items()})
    summary=record.finish(reference_qualified=True, operator_refinement=refinement,
        density_coefficient_refinement=density_refinement, comparisons=len(rows),
        density_tail_extension_65535_to_131071=density_tail_extension,
        final_example3={r['arm']:r['error_l2'] for r in rows if r['example']==3 and r['n']==max(ns)},
        final_example3_gate_pass={r['arm']:r['error_l2']<=1e-10 for r in rows
                                 if r['example']==3 and r['n']==max(ns)},
        published_counts_all_match=all(r['cc_matches_rounding'] for r in count_rows))
    print(summary,flush=True)


if __name__=='__main__':
    main()
