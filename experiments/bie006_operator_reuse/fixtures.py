"""Chronological selection of saved geometry only; no truth/objective access."""
from pathlib import Path
import json
import numpy as np
from ordered_boundary import fourier_curve

TRAJECTORY=Path('results/validation/topology/TOP-012-20260912-acquisition-route-a/suite/runs/H/central-ellipse-star/trajectory.json')
ACQUISITION=Path('results/validation/topology/TOP-018-20260915-resolution-qualified-pair/inputs/far-two-stars/observations.json')
AMPLITUDES=[1e-5,1e-4,1e-3,5e-3]
FREQUENCIES=[500_000_000,1_250_000_000]


def coefficients(record):
    v=np.asarray(record['parameters'],float);cut=2*(record['maximum_mode']+1)
    return v[:cut].reshape(-1,2),np.vstack((np.zeros(2),v[cut:].reshape(-1,2)))


def producer(c,s):
    return fourier_curve(c,s,component_id='saved_single',period=2*np.pi,parameter_origin=0.)


def frozen_inputs():
    original=json.loads(TRAJECTORY.read_text())
    # Copy only geometry and event labels. Never use losses or truth to select.
    trajectory=[dict(index=i,cycle=r.get('cycle'),label=r.get('label'),state=r.get('state'))
                for i,r in enumerate(original)]
    base=trajectory[1];record=base['state'][0];assert len(base['state'])==1
    assert record['chart']=='cartesian' and record['maximum_mode']==3
    c,s=coefficients(record);params=np.arange(4096)*2*np.pi/4096
    base_points=producer(c,s).evaluate(params).points
    radius=np.linalg.norm(base_points-c[0],axis=1)
    assert np.ptp(radius)>1e-4, 'The frozen base must be noncircular.'
    directions=[]
    for index in [2,3,4]:
        row=trajectory[index];assert row['cycle']==base['cycle']
        assert len(row['state'])==1
        r=row['state'][0]
        assert (r['chart'],r['component_id'],r['maximum_mode'])==(
            record['chart'],record['component_id'],record['maximum_mode'])
        cc,ss=coefficients(r);dc,ds=cc-c,ss-s
        displacement=producer(dc,ds).evaluate(params).points
        length=float(np.linalg.norm(displacement,axis=1).max())
        assert length>1e-12
        directions.append(dict(id=f'to_row_{index}',target_row=index,cosine=dc/length,
                               sine=ds/length,original_max_displacement_m=length,
                               rms_over_max=float(np.sqrt(np.mean(displacement**2)*2)/length)))
    nearby=[]
    for row in trajectory[2:]:
        state=row['state']
        if row['cycle']!=base['cycle'] or not state or len(state)!=1:break
        r=state[0]
        if (r['chart'],r['component_id'],r['maximum_mode'])!=(
            record['chart'],record['component_id'],record['maximum_mode']):break
        cc,ss=coefficients(r)
        displacement=producer(cc,ss).evaluate(params).points-base_points
        nearby.append(dict(row=row['index'],label=row['label'],
                           maximum_displacement_m=float(np.linalg.norm(displacement,axis=1).max())))
    saved=json.loads(ACQUISITION.read_text())
    acq={k:saved[k] for k in ('source_points','receiver_points','exterior','interior','eps0','mu0')}
    assert all(v==1e-6 for v in saved['source_strengths_real'])
    assert not any(saved['source_strengths_imag'])
    acq['source_strength']=1e-6
    assert np.array(acq['source_points']).shape==np.array(acq['receiver_points']).shape==(24,2)
    return dict(base_row=base,cosine=c,sine=s,directions=directions,acquisition=acq,
                nearby_saved_states=nearby,scene_length_m=.1,amplitudes_m=AMPLITUDES,
                frequencies_hz=FREQUENCIES,normalization_samples=4096,
                provenance=[str(TRAJECTORY),str(ACQUISITION)])
