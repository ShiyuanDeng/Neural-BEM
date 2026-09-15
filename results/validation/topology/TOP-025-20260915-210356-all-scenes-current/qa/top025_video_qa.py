"""Decode representative video frames; no numerical recomputation."""
import json
from pathlib import Path
import subprocess
from PIL import Image,ImageOps,ImageDraw
root=Path('/home/drdeng/Neural_SDF_BEM_AD')
bundle=Path((root/'experiments/top025/output_path.txt').read_text().strip())
manifest=json.loads((bundle/'video_manifest.json').read_text());folder=bundle/'qa';folder.mkdir(exist_ok=True)
records=[]
for name,result in manifest['outputs'].items():
    duration=float(result['probe']['duration'])
    for label,time in [('progress',min(8,duration/2)),('final',duration-1)]:
        output=folder/f'{name}_{label}_decoded.png'
        subprocess.run(['ffmpeg','-y','-loglevel','error','-ss',str(time),'-i',str(bundle/'videos'/f'{name}.mp4'),'-frames:v','1',str(output)],check=True)
        records.append(dict(video=name,time_seconds=time,frame=str(output.relative_to(bundle))))
for label in ('progress','final'):
    names=[name for name in manifest['outputs'] if name!='all_scenes']
    montage=Image.new('RGB',(1500,4*410),'#e2e8f0')
    for n,name in enumerate(names):
        frame=Image.open(folder/f'{name}_{label}_decoded.png').convert('RGB');frame.thumbnail((500,380))
        x=(n%3)*500+(500-frame.width)//2;y=(n//3)*410+20
        montage.paste(frame,(x,y));ImageDraw.Draw(montage).text(((n%3)*500+12,(n//3)*410+3),name,fill='#0f172a')
    montage.save(folder/f'encoded_{label}_contact_sheet.png')
(folder/'decoded_frames.json').write_text(json.dumps(dict(new_physical_solves=0,frames=records),indent=2)+'\n')
print(json.dumps(dict(videos_decoded=len(manifest['outputs']),frames=len(records),contact_sheets=2)))
