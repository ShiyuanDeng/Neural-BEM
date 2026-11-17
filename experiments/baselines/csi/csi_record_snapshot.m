function csi_record_snapshot(iteration, raw_contrast, native_elapsed)
% Output only: persist the raw value just placed in native Mchi.
persistent counts snapshots native_elapsed_seconds metadata
if isempty(counts)
    counts=[];snapshots={};native_elapsed_seconds=[];
    metadata=load(fullfile(getenv('CSI_OUT'),'snapshot_metadata.mat'));
end
if ~ismember(iteration,[256 512 1024 2048]);return;end
write_timer=tic;
counts(end+1)=iteration;snapshots{end+1}=raw_contrast;
native_elapsed_seconds(end+1)=native_elapsed;
payload=metadata;payload.counts=counts;payload.snapshots=snapshots;
payload.native_elapsed_seconds=native_elapsed_seconds;
out=getenv('CSI_OUT');temporary=fullfile(out,'snapshot_atomic.mat');
save(temporary,'-struct','payload','-v7');
movefile(temporary,fullfile(out,'final_contrast.mat'),'f');
fid=fopen(fullfile(out,'checkpoint_writes.csv'),'a');
fprintf(fid,'%d,%.9f,%.9f\n',iteration,native_elapsed,toc(write_timer));fclose(fid);
end
