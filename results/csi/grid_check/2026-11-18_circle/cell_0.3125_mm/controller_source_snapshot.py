"""Small, separate circle forward-grid check; never writes campaign inputs."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
from scipy.io import loadmat
from scipy.optimize import least_squares, minimize_scalar
from scipy.special import hankel1, h1vp, jv, jvp

from experiments.baselines.csi import campaign as base

ROOT = base.REPO / 'results/csi/grid_check/2026-11-18_circle'
ACT = base.REPO / 'docs/iterations/csi_adaptation/05_check_circle_grid_convergence'
REF = base.REPO / 'results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks'
GEOMETRY = base.REPO / 'results/csi/preparation/2026-11-17_geometry/geometry.mat'
OLD_TABLE = base.REPO / 'results/csi/preparation/2026-11-17_generate/synthetic_input.txt'
CELLS = [1.25, .625, .3125]


def folder(cell):
    return ROOT / f'cell_{cell:g}_mm'


def table_path(cell):
    if cell == .625:
        return OLD_TABLE
    candidates = [folder(cell), *sorted(ROOT.glob(f'cell_{cell:g}_mm_attempt_*'))]
    complete = [p for p in candidates if (p/'outcome.json').exists()
                and json.loads((p/'outcome.json').read_text())['returncode'] == 0
                and (p/'synthetic_input.txt').exists()]
    assert len(complete) <= 1, 'do not select between successful repetitions'
    return (complete[0] if complete else folder(cell)) / 'synthetic_input.txt'


def source_receivers():
    tx = np.deg2rad(10*np.arange(36)-2.5)
    rx = np.deg2rad(5*np.arange(72))
    return .72*np.exp(1j*tx), .76*np.exp(1j*rx)


def blocks(path):
    table = np.loadtxt(path)
    original = np.loadtxt(OLD_TABLE)
    assert table.shape == (14112, 7) and np.isfinite(table).all()
    assert np.array_equal(table[:, :3], original[:, :3])
    out = []
    for f in range(1, 9):
        b = table[table[:, 2] == f]
        key = (b[:, 0].astype(int)-1)*72+b[:, 1].astype(int)-1
        order = np.argsort(key, kind='stable')
        mask = np.zeros((36, 72), bool); mask.ravel()[key] = True
        values = ((b[:, 3]+1j*b[:, 4])-(b[:, 5]+1j*b[:, 6])).conj()[order]
        assert np.array_equal(np.sort(key), np.flatnonzero(mask))
        out.append((f, values, mask))
    return out


def exact_circle(radius, epsilon, centre, ghz, mask):
    """Formula copied from BEM-side exact_circle; physical metre units here."""
    k = 2*np.pi*ghz*1e9/299792458.
    k1 = k*np.sqrt(epsilon)
    n = np.arange(-int(k*radius+40), int(k*radius+40)+1)[:, None]
    t = -((k*jvp(n, k*radius)*jv(n, k1*radius)-k1*jv(n, k*radius)*jvp(n, k1*radius)) /
          (k*h1vp(n, k*radius)*jv(n, k1*radius)-k1*hankel1(n, k*radius)*jvp(n, k1*radius)))
    sources, receivers = source_receivers()
    zs, zr = sources-centre, receivers-centre
    incoming = .25j*hankel1(n, k*abs(zs)[None])*np.exp(-1j*n*np.angle(zs)[None])
    outgoing = hankel1(n, k*abs(zr)[None])*np.exp(1j*n*np.angle(zr)[None])
    return np.einsum('ns,nr->sr', t*incoming, outgoing)[mask]


def truth():
    b = loadmat(GEOMETRY, simplify_cells=True)['boundary']
    return float(np.mean(abs(b-b.mean()))), complex(b.mean())


def generate(cell):
    assert cell in (1.25, .3125)
    available = base.memory()['MemAvailable']
    # Coarse measured family 1.457 GiB and saved 0.625-mm generation 2.160
    # GiB give about 4.97 GiB at 664^2 nodes with fixed startup + grid-linear
    # allocation. The actual cap remains 6 GiB, with continuous reserve checks.
    expected = (2 if cell == 1.25 else 5)*base.GIB
    if available < base.RESERVE + expected + .25*base.GIB:
        print(json.dumps(dict(state='waiting for memory; no MATLAB started', cell_mm=cell,
                             available_gib=available/base.GIB, required_gib=(base.RESERVE+expected+.25*base.GIB)/base.GIB)))
        return
    out = folder(cell)
    if table_path(cell).exists():
        raise RuntimeError('a completed table already exists; never rerun it')
    attempt = 1
    while out.exists():
        attempt += 1
        out = ROOT / f'cell_{cell:g}_mm_attempt_{attempt:02d}'
    out.mkdir(parents=True, exist_ok=False)
    source = base.CODE / 'generate_synthetic.m'
    driver = source.read_text()
    substitutions = {
        'para.m_unit=.000625;': f'para.m_unit={cell*1e-3:.10g};\nN=round(2*.10375/para.m_unit); halfN=N/2; geometry.x_m=(-halfN:halfN-1)*para.m_unit; geometry.y_m=geometry.x_m;',
        'assert(isequal(pars.Ninv,[332 332 1]))': 'assert(isequal(pars.Ninv,[N N 1]))',
        '[-166 166;-166 166;0 1]': '[-halfN halfN;-halfN halfN;0 1]',
        "'forward_grid',[332 332]": "'forward_grid',[N N]",
    }
    for old, new in substitutions.items():
        assert driver.count(old) == 1, old
        driver = driver.replace(old, new)
    executed = out / 'executed_driver.m'; executed.write_text(driver)
    base.write(out / 'sources.json', dict(utc=base.now(), files=[dict(path=str(p.relative_to(base.REPO)), sha256=base.sha(p))
        for p in (Path(__file__), source, executed, GEOMETRY, REF/'truth_predictions.npz', REF/'forward_checks.json')]))
    job = base.launch(out, executed, dict(CSI_GEOMETRY=str(GEOMETRY), CSI_CASE=f'circle_grid_{cell:g}_mm_TM'))
    job['record'].update(cell_mm=cell, reserve_gib=14, stop_margin_gib=.25, family_limit_gib=6,
        predicted_family_gib=expected/base.GIB,
        command_python=['env','PYTHONPATH=solvers:.',os.sys.executable,'-B','-m','experiments.baselines.csi.circle_grid_check','--generate',str(cell)])
    base.write(out / 'launch.json', job['record'])
    while job['process'].poll() is None:
        mem = base.sample(job)
        if mem['MemAvailable'] < base.RESERVE + .25*base.GIB:
            base.terminate(job, '14 GiB reserve plus 0.25 GiB stop margin')
        elif job.get('family', 0) > 6*base.GIB:
            base.terminate(job, 'six-GiB family memory limit; fine grid skipped')
        elif time.monotonic()-job['start'] > 600:
            base.terminate(job, 'ten-minute forward-only limit')
        time.sleep(.2)
    rc = base.finish(job)
    state = 'completed' if rc == 0 else 'failed or stopped; evidence preserved'
    base.write(out / 'outcome.json', dict(state=state, returncode=rc, utc=base.now()))
    if (out / 'synthetic_input.txt').exists():
        blocks(out / 'synthetic_input.txt')
        base.write(out / 'data.json', dict(path=str(out/'synthetic_input.txt'), sha256=base.sha(out/'synthetic_input.txt'),
                                        bytes=(out/'synthetic_input.txt').stat().st_size, cell_mm=cell))
    print(json.dumps(dict(state=state, returncode=rc, peak_family_gib=job['peak_family']/base.GIB,
                         minimum_available_gib=job['min_available']/base.GIB)), flush=True)


def analyze():
    ROOT.mkdir(parents=True, exist_ok=True)
    reference = np.load(REF / 'truth_predictions.npz')
    expected = json.loads((REF/'forward_checks.json').read_text())['mismatch']['circle__c4']['per_frequency'][:8]
    radius, centre = truth()
    rows = []
    for cell in CELLS:
        path = table_path(cell)
        if not path.exists():
            continue
        values = []
        for (f, data, mask), e in zip(blocks(path), expected):
            ref = reference[f'circle__c4_truth_band_{f}GHz']
            exact = exact_circle(radius, 4., centre, f, mask)
            series_agreement = np.linalg.norm(ref-exact)/np.linalg.norm(exact)
            assert series_agreement < 1e-10
            err = np.linalg.norm(data-exact)
            relative = err/np.linalg.norm(data)
            if cell == .625:
                assert abs(relative-e['relative_mismatch']) < 1e-10
            values.append(dict(frequency_GHz=f, relative_L2_over_table=relative,
                               relative_L2_over_exact=err/np.linalg.norm(exact),
                               copied_exact_vs_reference=series_agreement))
        rows.append(dict(cell_mm=cell, path=str(path), sha256=base.sha(path), per_frequency=values))
    orders = []
    for coarse, fine in zip(rows, rows[1:]):
        orders.append(dict(coarse_mm=coarse['cell_mm'], fine_mm=fine['cell_mm'], per_frequency=[
            np.log(a['relative_L2_over_table']/b['relative_L2_over_table'])/np.log(coarse['cell_mm']/fine['cell_mm'])
            for a,b in zip(coarse['per_frequency'], fine['per_frequency'])]))
    result = dict(utc=base.now(), rows=rows, observed_orders=orders,
                  boundary='binary staircase on dual cells, then native mean_material_node four-cell average to primary Ez',
                  reference_sha256=base.sha(REF/'truth_predictions.npz'), report_sha256=base.sha(REF/'forward_checks.json'),
                  command=['env','PYTHONPATH=solvers:.',os.sys.executable,'-B','-m','experiments.baselines.csi.circle_grid_check','--analyze'])
    base.write(ROOT/'grid_errors.json', result)
    for row in rows:
        print(f"{row['cell_mm']:g} mm: " + ', '.join(f"{100*v['relative_L2_over_table']:.5f}" for v in row['per_frequency']))
    for order in orders:
        print('Observed order', order['coarse_mm'], 'to', order['fine_mm'], ':', ', '.join(f'{v:.3f}' for v in order['per_frequency']))


def fit():
    radius, centre = truth(); results = []
    for cell in CELLS:
        path = table_path(cell)
        if not path.exists():
            continue
        data_blocks = blocks(path); independent = []
        for f, data, mask in data_blocks:
            norm = np.linalg.norm(data)
            fun = lambda eps: np.linalg.norm(exact_circle(radius, eps, centre, f, mask)-data)**2/norm**2
            opt = minimize_scalar(fun, bounds=(3.8,4.2), method='bounded', options=dict(xatol=1e-11))
            assert opt.success
            independent.append(dict(frequency_GHz=f, epsilon=float(opt.x), relative_L2=float(np.sqrt(opt.fun))))
        # Each frequency has equal relative-L2 weight, as in the diagnostic rows.
        def residual(x):
            r, eps, dx, dy = x
            arrays=[]
            for f, data, mask in data_blocks:
                value=(exact_circle(r*1e-3, eps, centre+(dx+1j*dy)*1e-3, f, mask)-data)/np.linalg.norm(data)
                arrays.extend([value.real,value.imag])
            return np.concatenate(arrays)
        opt = least_squares(residual, [radius*1000,4.,0.,0.], bounds=([49.,3.8,-1.,-1.],[51.,4.2,1.,1.]),
                            xtol=1e-11,ftol=1e-11,gtol=1e-11,max_nfev=50)
        assert opt.success, opt.message
        r,eps,dx,dy=opt.x
        errors=[float(np.linalg.norm(exact_circle(r*1e-3,eps,centre+(dx+1j*dy)*1e-3,f,mask)-data)/np.linalg.norm(data)) for f,data,mask in data_blocks]
        results.append(dict(cell_mm=cell,sha256=base.sha(path),per_frequency_contrast=independent,
                            common=dict(radius_mm=r,epsilon=eps,centre_shift_mm=[dx,dy],centre_shift_norm_mm=float(np.hypot(dx,dy)),
                                        relative_L2_per_frequency=errors,nfev=opt.nfev,weighting='equal relative-L2 weight per frequency')))
        base.write(ROOT/'exact_circle_fits.json',dict(utc=base.now(),results=results,
            command=['env','PYTHONPATH=solvers:.',os.sys.executable,'-B','-m','experiments.baselines.csi.circle_grid_check','--fit']))
        print(cell,'mm independent epsilon',[round(v['epsilon'],6) for v in independent],flush=True)
        print(cell,'mm common',json.dumps(results[-1]['common']),flush=True)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--generate',type=float,choices=[1.25,.3125])
    parser.add_argument('--analyze',action='store_true')
    parser.add_argument('--fit',action='store_true')
    args=parser.parse_args()
    if args.generate is not None:generate(args.generate)
    if args.analyze:analyze()
    if args.fit:fit()


if __name__=='__main__':main()
