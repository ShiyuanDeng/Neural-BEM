% Check checkpoint writes on a saved fixture, without running an inversion.
maxNumCompThreads(8);
repo=getenv('CSI_REPO');out=getenv('CSI_OUT');
addpath(fullfile(repo,'experiments/baselines/csi'));
addpath(fullfile(repo,'experiments/baselines/csi/recorded'));
assert(nargin('CC_CSI_Brent_recorded')==9);
assert(nargin('csi_record_snapshot')==3);
fixture=load(fullfile(repo,'results/csi/preparation/2026-11-17_probe/final_contrast.mat'));
grid_x_primary_m=fixture.grid_x_primary_m;grid_y_primary_m=fixture.grid_y_primary_m;
Ninv=[166 166 1];frequencies_GHz=1:8;reference_frequency_GHz=8;
save(fullfile(out,'snapshot_metadata.mat'),'grid_x_primary_m','grid_y_primary_m','Ninv','frequencies_GHz','reference_frequency_GHz');
fid=fopen(fullfile(out,'checkpoint_writes.csv'),'w');fprintf(fid,'iterations,native_elapsed_seconds,write_seconds\n');fclose(fid);
value=fixture.snapshots{1};
csi_record_snapshot(256,value,1);csi_record_snapshot(512,value,2);
saved=load(fullfile(out,'final_contrast.mat'));
assert(isequal(saved.counts,[256 512]));
assert(isequal(saved.snapshots{1},value) && isequal(saved.snapshots{2},value));
assert(isequal(saved.native_elapsed_seconds,[1 2]));
movefile(fullfile(out,'final_contrast.mat'),fullfile(out,'recording_fixture.mat'));
result=struct('passed',true,'fixture_only',true,'inversion_run',false, ...
    'description','Two atomic writes preserve exact complex native values and metadata; synthetic iteration labels are callback test inputs only.', ...
    'matlab',version,'threads',maxNumCompThreads);
fid=fopen(fullfile(out,'check.json'),'w');fprintf(fid,'%s\n',jsonencode(result,PrettyPrint=true));fclose(fid);
fprintf('Output-only recording check passed; no inversion was run.\n');
