"""Recover coordinates from Cairo vector paths, never from raster images."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import hashlib
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.io import savemat
from scipy.interpolate import CubicSpline
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "results/brg/paper_sources/local"
OUT = ROOT / "results/brg/paper_examples/2026-11-17/shapes"
FIG = ROOT / "docs/iterations/brg_adaptation/02_rebuild_paper_examples/figures"
NUM = r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?"


def paths(name):
    return list(ET.parse(SOURCE / (name + ".svg")).getroot().iter("{http://www.w3.org/2000/svg}path"))


def points(path):
    return np.array(re.findall(NUM, path.get("d")), float).reshape(-1, 2)


def panel(ps, ids, axes):
    # All selected paths and tick paths have the SAME affine transform,
    # so mapping their native coordinates cancels the PDF/SVG transform.
    transform = ps[ids[0]].get("transform")
    assert all(ps[i].get("transform") == transform for i in [*ids, *axes])
    assert all(set(re.findall(r"[A-Za-z]", ps[i].get("d"))) <= {"M", "L"} for i in ids)
    assert all('fill:none' in ps[i].get('style','') and 'stroke-dasharray' not in ps[i].get('style','') for i in ids)
    chunks = [points(ps[i]) for i in ids]
    for left, right in zip(chunks[:-1], chunks[1:]):
        assert np.max(abs(left[-1] - right[0])) < 1e-6
    xy = np.concatenate([chunks[0], *[p[1:] for p in chunks[1:]]])
    assert np.max(abs(xy[-1] - xy[0])) < 1e-6
    bottom, top = points(ps[axes[0]]), points(ps[axes[1]])
    xmin, xmax = bottom[:, 0]; ymax, ymin = bottom[0, 1], top[0, 1]
    xy[:, 0] = (xy[:, 0] - (xmin+xmax)/2) * np.pi/(xmax-xmin)
    xy[:, 1] = ((ymin+ymax)/2 - xy[:, 1]) * np.pi/(ymax-ymin)
    zero_tick=[points(ps[axes[0]+3])[0,0],points(ps[axes[0]+13])[0,1]]
    zero_error=[(zero_tick[0]-(xmin+xmax)/2)*np.pi/(xmax-xmin),
                ((ymin+ymax)/2-zero_tick[1])*np.pi/(ymax-ymin)]
    assert max(abs(np.array(zero_error))) < 1e-4
    return xy, dict(path_indices=list(ids), axis_path_indices=axes,
                    transform=transform, x_ticks=[xmin, (xmin+xmax)/2, xmax],
                    y_ticks=[ymin, (ymin+ymax)/2, ymax],
                    observed_zero_tick=zero_tick, zero_tick_residual=zero_error,
                    tick_labels=["-pi/2", "0", "pi/2"], points=len(xy)-1)


def fit_curve(xy, band):
    z = xy[:-1, 0] + 1j*xy[:-1, 1]
    if np.sum(xy[:-1, 0]*xy[1:, 1]-xy[1:, 0]*xy[:-1, 1]) < 0:
        z = z[::-1]
    distance = np.abs(np.diff(np.r_[z, z[0]]))
    t = np.r_[0, np.cumsum(distance[:-1])] / distance.sum()*2*np.pi
    modes = np.arange(-band, band+1)
    # Alternating least squares and tangential projection gives a smooth
    # Cartesian Fourier parameterization without assuming equal PDF steps.
    for iteration in range(1800 if band == 35 else 150):
        basis = np.exp(1j*np.outer(t, modes))
        coef = np.linalg.lstsq(basis, z, rcond=1e-12)[0]
        predicted = basis @ coef
        deriv = basis @ (1j*modes*coef)
        step = np.real((z-predicted)*np.conj(deriv))/np.maximum(abs(deriv)**2, 1e-16)
        step = np.clip(step, -.002, .002)
        if max(abs(step)) < 1e-10:
            break
        t += .8*step
    basis = np.exp(1j*np.outer(t, modes))
    coef = np.linalg.lstsq(basis, z, rcond=1e-12)[0]
    residual = abs(basis@coef-z)
    dense_t = np.arange(16000)*2*np.pi/16000
    dense = np.exp(1j*np.outer(dense_t,modes))@coef
    return modes, coef, dense, dict(band=band, iterations=iteration+1,
        point_fit_rms=float(np.sqrt(np.mean(residual**2))), point_fit_max=float(max(residual)),
        minimum_parameter_step=float(min(np.diff(np.sort(t)))))


def recover_shape(name, source, ids1, axes1, ids2, axes2, band):
    ps = paths(source)
    first, meta1 = panel(ps, ids1, axes1)
    second, meta2 = panel(ps, ids2, axes2)
    # Sampling differences can occur when Cairo simplifies almost-collinear
    # points. Compare periodic cubic interpolants in normalized arc length.
    def sampled(xy):
        s = np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        return CubicSpline(s/s[-1], xy, bc_type="periodic")(np.arange(16000)/16000)
    a,b = sampled(first),sampled(second)
    cross = np.r_[cKDTree(a).query(b)[0],cKDTree(b).query(a)[0]]
    modes, coef, dense, fit = fit_curve(first, band)
    # Distance from fitted curve to the vector polyline (segment distance,
    # not nearest vertices); chunking keeps memory bounded.
    vertices=first[:-1]; edges=np.diff(first,axis=0); d2=np.sum(edges**2,axis=1)
    errs=[]
    for chunk in np.array_split(np.c_[dense.real,dense.imag],32):
        diff=chunk[:,None,:]-vertices
        proj=np.clip(np.sum(diff*edges,axis=2)/d2,0,1)
        errs.extend(np.sqrt(np.min(np.sum((diff-proj[:,:,None]*edges)**2,axis=2),axis=1)))
    fit.update(fitted_curve_to_vector_polyline_max=float(max(errs)),
               fitted_curve_to_vector_polyline_rms=float(np.sqrt(np.mean(np.square(errs)))))
    metadata=dict(label="recovered from the paper's figure files", source=source+".pdf",
        source_sha256=hashlib.sha256((SOURCE/(source+'.pdf')).read_bytes()).hexdigest(),
        panels=[meta1,meta2], cross_panel_max=float(max(cross)),
        cross_panel_rms=float(np.sqrt(np.mean(cross**2))), fit=fit,
        caveat="Accuracy is against vector centerlines, not the absent original analytic coefficients.")
    OUT.mkdir(parents=True,exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(OUT/(name+'_vector_panels.npz'),panel1=first,panel2=second)
    savemat(OUT/(name+'_fourier.mat'),{'modes':modes[:,None],'coefficients':coef[:,None]})
    (OUT/(name+'_recovery.json')).write_text(json.dumps(metadata,indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(6,6));ax.plot(*first.T,'k-',lw=1,label='Paper true curve, panel 1')
    ax.plot(*second.T,'--',lw=.8,label='Paper true curve, panel 2')
    ax.plot(dense.real,dense.imag,':',lw=1,label=f'Cartesian Fourier fit, band {band}')
    ax.set(aspect='equal',xlabel='x',ylabel='y',title=name.capitalize()+': recovered from paper vector paths')
    ax.legend(fontsize=8);fig.tight_layout();fig.savefig(FIG/(name+'_vector_recovery.png'),dpi=160);plt.close(fig)
    print(name,json.dumps(metadata),flush=True)


def figure1():
    ps=paths('contrast_obstacle'); records={}
    for label,ids,axis,yticks in [('eta_033',range(343,380),281,(293,292)),('eta_10',range(473,510),383,(395,394))]:
        # Filled round marker centers are midpoint of their vector bounds.
        centers=[]
        for i in ids:
            p=ps[i]; assert 'stroke:none' in p.get('style','')
            xy=points(p);centers.append((xy.max(0)+xy.min(0))/2)
        centers=np.array(centers)
        transform=np.array(re.findall(NUM,ps[axis].get('transform')),float)
        scale_x,_,_,scale_y,offset_x,offset_y=transform
        xx=(centers[:,0]-offset_x)/scale_x
        yy=(centers[:,1]-offset_y)/scale_y
        bounds=points(ps[axis])[:,0]
        k=(xx-bounds[0])*10/(bounds[1]-bounds[0])
        # Verify y=10^0 and y=10^-1 for left; right uses 10^0,10^-2.
        y0=points(ps[yticks[0]])[0,1];y1=points(ps[yticks[1]])[0,1]
        exponent=-(yy-y0)/(y1-y0)*(1 if label=='eta_033' else 2)
        assert np.max(abs(k-np.arange(1,10.01,.25)))<.001
        records[label]=dict(k=k.tolist(),relative_area_error=(10**exponent).tolist(),
            marker_path_indices=list(ids),axis_path=axis,y_tick_paths=list(yticks))
    (OUT/'figure1_errors.json').write_text(json.dumps(records,indent=2)+'\n')


if __name__=='__main__':
    recover_shape('star','limited_data_reconstruction',range(155,163),[115,116],range(224,232),[184,185],35)
    recover_shape('cavity','cavity_reconstruction',range(144,152),[108,109],range(205,213),[173,174],100)
    figure1()
