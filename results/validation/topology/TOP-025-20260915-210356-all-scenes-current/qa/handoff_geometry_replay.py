"""Read-only geometry replay of completed handoff failures; zero BIE calls."""
import sys,json
from pathlib import Path
root=Path('/home/drdeng/Neural_SDF_BEM_AD');sys.path.insert(0,str(root))
from experiments.top025 import run as r
from solvers.sdf_inverse import radial_topology as rt
bundle=Path((root/'experiments/top025/output_path.txt').read_text().strip());spec=r.read(bundle/'scene_spec.json')
control=r.p.benchmark.controller_config(spec,'H');solve=r.p.driver.baseline.iteration01_solve_config()
records=[];ledger=r.m.Ledger(cap=0,seconds=60)
with ledger.instrument():
    for name in ('far-ellipse-star','empty-ellipse-star'):
        source=bundle/'runs'/name/'topology/terminal.json';state=r.p.driver.deserialize_state(r.read(source)['final_state'])
        padded=r.p.MultiRadialFourierState(tuple(r.p.zero_padded_component(c,9) for c in state.components))
        tests=[]
        for nodes in (64,128,256,512):
            try:
                rt.adapt_multicomponent_boundary(padded.boundary(r.p.driver.baseline._geometry_config(nodes)),config=solve.assembly)
                tests.append(dict(nodes=nodes,admissible=True))
            except (rt.OrderedSDFGeometryError,rt.MultiComponentKressGeometryError) as exc:
                tests.append(dict(nodes=nodes,admissible=False,error_type=type(exc).__name__,detail=str(exc)))
        records.append(dict(scene=name,source=str(source.relative_to(bundle)),source_sha256=r.p.digest(source),
            state_sha256=r.m.state_hash(state),minimum_component_radius_m=control.minimum_component_radius_m,
            component_radius_floor_m=[r.p.component_radius_floor(c) for c in padded.components],tests=tests))
assert ledger.total==0
out=bundle/'qa/handoff_geometry.json';r.write(out,dict(new_physical_solves=0,records=records))
print(json.dumps(r.read(out),indent=2))
