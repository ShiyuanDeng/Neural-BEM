import sys,shutil
from pathlib import Path
root=Path('/home/drdeng/Neural_SDF_BEM_AD');sys.path.insert(0,str(root))
from experiments.top025 import render as v
b=Path((root/'experiments/top025/output_path.txt').read_text().strip());spec=v.read(b/'scene_spec.json')
for name in ('merge','central-ellipse-star'):
    scene=next(x for x in spec['scenes'] if x['id']==name);result=v.read(b/'runs'/name/'result.json');schedule=result['continuation']['schedule'];score=schedule['final'];g=score['geometry']
    row=dict(recovered=result['fresh_recovery_pass'],schedule_complete=schedule['schedule_complete'],boundary_mm=g['maximum_matched_hausdorff_m']*1000,iou=g['union_iou'],count=g['component_count'],truth_count=g['truth_component_count'],prediction_errors=score['training_errors']+score['evaluation_errors'])
    data=v.collect(b,name);output=v.render_scene(b,scene,row,data);archive='qa/'+name+'_preview.mp4';shutil.copyfile(b/'videos'/f'{name}.mp4',b/archive)
    v.write(b/'qa'/f'{name}_preview_provenance.json',dict(scene=name,new_physical_solves=0,data=data,output=output,archived_preview_video=archive))
    print(name,output['probe'],flush=True)
