% Metadata for the output-only checkpoint callback. No solver input changes.
out=getenv('CSI_OUT');
grid_x_primary_m=para.m_unit*grid3d{1}.l{1,1}(pars.nx);
grid_y_primary_m=para.m_unit*grid3d{1}.l{2,1}(pars.ny);
Ninv=pars.Ninv;frequencies_GHz=fre;reference_frequency_GHz=fre(end);
save(fullfile(out,'snapshot_metadata.mat'),'grid_x_primary_m','grid_y_primary_m', ...
    'Ninv','frequencies_GHz','reference_frequency_GHz','-v7');
fid=fopen(fullfile(out,'checkpoint_writes.csv'),'w');
fprintf(fid,'iterations,native_elapsed_seconds,write_seconds\n');fclose(fid);
addpath(fullfile(getenv('CSI_REPO'),'experiments/baselines/csi'));
addpath(fullfile(getenv('CSI_REPO'),'experiments/baselines/csi/recorded'));
