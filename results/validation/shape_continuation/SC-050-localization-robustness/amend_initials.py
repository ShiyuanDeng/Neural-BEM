"""One-time acquisition-only correction before any SC-050 transfer fit."""
from pathlib import Path
import importlib.util
import tarfile
import numpy as np

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('sc050_initial_amend',HERE/'run.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.verify()
assert not any((HERE/'runs'/scene).exists() for scene in m.TRANSFER)
assert not (HERE/'initial_domain_amendment.json').exists()
manifest=m.sc.read(HERE/'manifest.json')
(HERE/'pre_amendment/manifest_before_initial_correction.json').write_bytes((HERE/'manifest.json').read_bytes())
rows=[]
catalog,_=m.fitting_data('development_c')
for scene,d in m.SCENES.items():
    old=np.array(d['start']+[.065]);new=old.copy()
    before=m.circle_exterior_clearance(old,catalog)
    path=HERE/'inputs'/scene/'initial.json'
    prior_hash=m.sc.digest(path)
    if before<=0:
        offset=old[:2]-[.5,.5]
        new[:2]=[.5,.5]+.20*offset/np.linalg.norm(offset)
        saved=HERE/'pre_amendment/initial_inputs'/scene/'initial.json'
        saved.parent.mkdir(parents=True);saved.write_bytes(path.read_bytes())
        curve=m.FourierCurve.circle(new[2]/m.sc.LENGTH,(complex(*new[:2])-m.sc.CENTER)/m.sc.LENGTH)
        m.write(path,m.ast.curve_record(curve))
    after=m.circle_exterior_clearance(new,catalog)
    assert after>0
    rows.append(dict(scene=scene,old_parameters_m=old,new_parameters_m=new,old_clearance_m=before,
        new_clearance_m=after,old_sha256=prior_hash,new_sha256=m.sc.digest(path)))
    manifest['inputs'][str(path.relative_to(m.sc.ROOT))]=m.sc.digest(path)
    print(scene,new[:2].tolist(),'clearance mm',1000*after,flush=True)
m.write(HERE/'initial_domain_amendment.json',dict(rule='If inadmissible, contract center offset from fixed scene origin to 0.20 m; retain direction and 65 mm radius.',
    before_any_transfer=True,selection_sha256=m.sc.digest(HERE/'selection.json'),rows=rows))
paths=m.source_paths()+[HERE/'amendment_01.md',HERE/'amendment_02.md',Path(__file__).resolve()]
archive='source_amendment_02.tar.gz'
with tarfile.open(HERE/archive,'w:gz') as t:
    for p in paths:t.add(p,arcname=str(p.relative_to(m.sc.ROOT)),recursive=False)
manifest['amendments'].append(dict(reason='Acquisition-only feasible-start correction before all transfer fitting; no numerical driver change',
    sources={str(p.relative_to(m.sc.ROOT)):m.sc.digest(p) for p in paths},archive=archive,archive_sha256=m.sc.digest(HERE/archive),
    input_amendment_sha256=m.sc.digest(HERE/'initial_domain_amendment.json')))
m.write(HERE/'manifest.json',manifest);m.verify()
