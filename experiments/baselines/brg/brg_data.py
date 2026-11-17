"""BRG observations and experiment-only truth; never imported by the inverse."""
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from bem_inverse import FourierCurve, Observation, PlaneWaveAcquisition

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'results/brg/paper_examples/2026-11-17'
REFERENCE_LENGTH_M=1.
C0=299792458.
LADDER=(1.,1.25,1.5,1.75,2.,2.5,3.,3.5,4.,5.,6.,7.,8.,10.,12.,15.)


def observation(case,k,mask=None):
    index=round((k-1)*4)+1
    assert k==1+(index-1)/4
    path=BASE/case/'local'/f'data_{index:03d}.mat'
    saved=loadmat(path,simplify_cells=True)
    measurement,record=saved['measurement'],saved['data_record']
    nd,nr=int(record['directions']),int(record['receivers'])
    angles=np.asarray(measurement['t_dir']).reshape(-1)
    tgt=np.asarray(measurement['tgt'])
    receivers=tgt[:,::nd].T
    assert np.array_equal(tgt,np.repeat(receivers.T,nd,axis=1))
    assert np.array_equal(angles,np.tile(angles[:nd],nr))
    table=np.asarray(measurement['uscat_tgt']).reshape(nr,nd).T
    assert np.array_equal(table.T.reshape(-1),np.asarray(measurement['uscat_tgt']).reshape(-1))
    directions=np.c_[np.cos(angles[:nd]),np.sin(angles[:nd])]
    acq=PlaneWaveAcquisition(directions,receivers,mask)
    data=table if mask is None else table[mask]
    return Observation(float(k),acq,data,C0*k/(2*np.pi*REFERENCE_LENGTH_M)),path,record


def true_curve(shape):
    if shape=='glider':
        c=np.zeros(19,complex);c[10]=.9
        for mode,value in [(3,.18),(4,.018),(6,.09),(8,.09)]:
            c[9+1+mode]+=value/2;c[9+1-mode]+=value/2
        return FourierCurve(c)
    saved=loadmat(BASE/'shapes'/f'{shape}_fourier.mat',simplify_cells=True)
    c=np.asarray(saved['coefficients']).reshape(-1)
    assert np.array_equal(np.asarray(saved['modes']).reshape(-1),np.arange(-len(c)//2+1,len(c)//2+1))
    return FourierCurve(c)
