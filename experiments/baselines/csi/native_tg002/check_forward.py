"""Compare the two native circle FDFD grids to sealed and analytic scattered fields."""
import numpy as np
from scipy.io import savemat

from bem_inverse.io import curve_from
from bem_inverse import mie_grid, mie_localize
from experiments.benchmark import campaign, scenes

from .check_table import launch_check
from .inputs import arguments, digest, native_observation, read, write_json


def prepare_reference(folder, inputs):
    obs, row, _ = native_observation('circle__c4', 'clean')
    path = campaign.ROOT / row['truth']
    seal = read(campaign.INPUTS/'manifest.json')['inputs'][str(path.relative_to(campaign.INPUTS))]
    assert digest(path) == seal
    curve = curve_from(read(path))
    assert curve.band == 1 and abs(curve.coefficients[0]) < 1e-14
    center = curve.coefficients[1]
    radius = abs(curve.coefficients[2])
    cut = int(np.ceil(obs.wavenumber * np.sqrt(row['contrast']) * radius + 30))
    acq = obs.acquisition
    products = mie_grid.products_recurrence(obs.wavenumber,[center],acq.sources,acq.receivers,cut)
    radial = mie_localize.radial_coefficients(obs.wavenumber,row['contrast'],[radius],np.arange(-cut,cut+1))
    exact = (products[0] @ radial[0]) * acq.strength
    savemat(folder/'reference.mat', dict(center_m=center*scenes.LENGTH, radius_m=radius*scenes.LENGTH,
            ratio=row['contrast'], exact_native=exact[:,None]))
    write_json(folder/'reference.json', dict(truth_path=row['truth'], truth_sha256=seal,
               reference_mat_sha256=digest(folder/'reference.mat'), order_cutoff=cut,
               reference='mie_grid.products_recurrence and mie_localize.radial_coefficients',
               sealed_vs_series_relative=float(np.linalg.norm(obs.scattered-exact)/np.linalg.norm(exact))))


if __name__ == '__main__':
    args = arguments(__doc__, forward=True)
    for name in ['equivalence_upstream', 'table_circle__c4__clean','table_kite__c4__clean']:
        if read(args.run_dir/'checks'/name/'check.json').get('passed') is not True:
            raise SystemExit(f'prerequisite has not passed: {name}')
    launch_check(args.run_dir,args.case,'clean','forward','native_forward_check',prepare_reference)
