"""Validate final gallery provenance and links, seal artifacts, and package review."""
import csv,hashlib,json,re,zipfile
from pathlib import Path
root=Path('/home/drdeng/Neural_SDF_BEM_AD');bundle=Path((root/'experiments/top025/output_path.txt').read_text().strip())
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
score=read(bundle/'scorecard.json');manifest=read(bundle/'manifest.json');videos=read(bundle/'video_manifest.json')
assert len(score['rows'])==12 and len(videos['outputs'])==13 and score['all_scenes_attempted']
assert read(bundle/'verification.json')['status']=='PASS'
for name,digest in manifest['source_sha256'].items():
    assert sha(root/name)==digest,name
    assert sha(bundle/'measured_sources'/name)==digest,name
for name,digest in manifest['input_sha256'].items():assert sha(bundle/name)==digest,name
for name,digest in manifest['historical_input_sha256'].items():assert sha(root/name)==digest,name
for name,digest in read(bundle/'pre_dispatch_validation.json')['test_sha256'].items():
    assert sha(root/name)==digest,name
    assert sha(bundle/'measured_sources'/name)==digest,name
for row in score['rows']:
    data=videos['scenes'][row['scene']]
    assert data['catalog'][data['timeline'][-1][0]]['state_sha256']==row['state_sha256']
    assert set(range(len(data['catalog']))) <= {i for i,_ in data['timeline']}
    for name,digest in data['sources_sha256'].items():assert sha(bundle/name)==digest,name
    for frame in data['catalog']:
        path=bundle/frame['source'];selector=frame['selector']
        if selector.startswith('line '):state=json.loads(path.read_text().splitlines()[int(selector.split()[1])-1])['state']
        else:
            value=read(path);state=value if selector=='root' else value[selector]
        assert state==frame['state'],(row['scene'],selector)
for name,video in videos['outputs'].items():
    assert sha(bundle/'videos'/f'{name}.mp4')==video['sha256'],name
    assert int(video['probe']['nb_frames'])==video['frames']
qa=read(bundle/'qa/decoded_frames.json');assert len(qa['frames'])==26
for record in qa['frames']:assert (bundle/record['frame']).is_file()
for record in read(bundle/'qa/handoff_geometry.json')['records']:
    assert sha(bundle/record['source'])==record['source_sha256']
    assert [t['admissible'] for t in record['tests']]==[True,True,False,False]
for path in [bundle/'preview_video_provenance.json',*(bundle/'qa').glob('*preview_provenance.json')]:
    if path.exists():
        data=read(path)
        assert sha(bundle/data['archived_preview_video'])==data['output']['sha256']
paths=[bundle/'README.md',root/'docs/iterations/topology/iteration_18/01_results.md',root/'docs/iterations/topology/iteration_17/03_plan.md']
links=0
for path in paths:
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
        target=target.strip('<>').split('#')[0]
        if not target or '://' in target:continue
        assert (path.parent/target).exists(),(path,target)
        links+=1
with (root/'results/catalog.csv').open(newline='') as f:catalog=list(csv.DictReader(f))
entries=[row for row in catalog if row['run_id']==bundle.name]
assert len(entries)==12 and len({row['scene_target'] for row in entries})==12
report=dict(status='PASS',scene_count=12,video_count=13,source_files=len(manifest['source_sha256']),
    source_and_input_files_unchanged=True,video_sources_and_final_state_matches=True,
    all_accepted_records_covered=True,decoded_video_frame_count=26,relative_links_checked=links,
    catalog_rows_added=12,new_physical_solves=0)
(bundle/'delivery_verification.json').write_text(json.dumps(report,indent=2)+'\n')
files={str(p.relative_to(bundle)):sha(p) for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'}
(bundle/'artifact_manifest.json').write_text(json.dumps(files,sort_keys=True,indent=2)+'\n')
for name,digest in read(bundle/'artifact_manifest.json').items():assert sha(bundle/name)==digest,name
archive=bundle.with_name(bundle.name+'-review.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(bundle.rglob('*')):
        if p.is_file():z.write(p,arcname=bundle.name+'/'+str(p.relative_to(bundle)))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({**report,'artifact_files_sealed':len(files),'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive)},indent=2))
