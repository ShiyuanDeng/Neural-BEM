"""Regenerate atlas CSV summaries and descriptive frequency scaling fits."""
import csv
import json
from pathlib import Path
import numpy as np
from .run_jacobian_spectrum import write_json


def summarize(directory):
    directory=Path(directory)
    rows=json.loads((directory/'spectra.json').read_text())
    keys=['shape','epsr','frequency_ghz','acquisition','kR','kiR','rank','structural_nullity',
          'field_refinement','mie_relative','refinement_relative_to_sigma1']
    with (directory/'cutoffs.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=keys);writer.writeheader()
        writer.writerows({k:r[k] for k in keys} for r in rows)
    fits=[]
    for shape in dict.fromkeys(r['shape'] for r in rows):
        rs=[r for r in rows if r['shape']==shape and r['acquisition']=='multistatic']
        y=np.array([r['rank'] for r in rs])
        for x_name in ('kR','kiR'):
            x=np.array([r[x_name] for r in rs]);a=np.column_stack((np.ones_like(x),x))
            b=np.linalg.lstsq(a,y,rcond=None)[0];prediction=a@b
            fits.append(dict(shape=shape,predictor=x_name,intercept=float(b[0]),slope=float(b[1]),
                             pooled_rmse=float(np.sqrt(np.mean((prediction-y)**2))),
                             r_squared=float(1-np.sum((prediction-y)**2)/np.sum((y-y.mean())**2)),
                             meaning='Descriptive affine fit pooled over contrast; not a physical cutoff law.'))
    write_json(directory/'scaling_fits.json',fits)

if __name__=='__main__':
    import sys
    summarize(sys.argv[1])
