from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time
import numpy as np
from experiments.shape_continuation import atlas_strategy_tests as st
from experiments.shape_continuation.atlas_survey import band_coordinates


def cell(job):
    case, frequency = job
    old = st.sc.read(st.ad.BASE / "SC-025-band-policies/runs/ladder" / case / "result.json")
    curve = st.curve_from(old["final_curve"])
    obs = st.catalog_only(case)[st.ac.CATALOG_HZ.index(frequency)]
    jac = []
    for n in (512, 1024):
        state = st.solve(curve, obs.wavenumber, st.ac.contrast(), obs.acquisition, n)
        jac.append(st.shape_jacobian(state, st.normal_basis(state.curve,48)/st.sc.LENGTH))
    norms = np.linalg.norm(jac[1],axis=0)
    errors = np.linalg.norm(jac[0]-jac[1],axis=0)/np.maximum(norms,1e-300)
    worst = int(errors.argmax())
    return dict(case=case, frequency_hz=frequency,
        band_max_relative={str(m):float(errors[band_coordinates(m,48)].max()) for m in (9,11,13,15,17,19,48)},
        worst_column=worst, worst_column_norm=float(norms[worst]),
        worst_column_norm_relative=float(norms[worst]/norms.max()),
        whole_matrix_relative=float(np.linalg.norm(jac[0]-jac[1])/np.linalg.norm(jac[1])))


if __name__ == "__main__":
    start = time.perf_counter()
    with ProcessPoolExecutor(6) as pool:
        rows = list(pool.map(cell, [(c,f) for c in st.CASES for f in (1.5e9,2.5e9)]))
    output = dict(rows=rows, seconds=time.perf_counter()-start, work_units=48,
                  max_active_M19_error=max(r["band_max_relative"]["19"] for r in rows))
    st.sc.write(Path(__file__).with_name("diagnostic.json"),output)
    print(json.dumps(output))
