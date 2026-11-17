% Mchi is a native raw 64-step history; do not call show_output (it masks it).
native_end_posix=posixtime(datetime('now','TimeZone','UTC'));
counts=[128 256 512 1024 2048]; counts=counts(counts<=pars.itenum);
if isempty(counts); counts=pars.itenum; end
snapshots=cell(size(counts));
for k=1:numel(counts); snapshots{k}=mchi1{counts(k)/64}; end
assert(isequal(mchi1{pars.itenum/64}(:),chi1{end}(:)));
mesh=grid3d{1}.l;
grid_x_primary_m=para.m_unit*mesh{1,1}(pars.nx);
grid_y_primary_m=para.m_unit*mesh{2,1}(pars.ny);
csi_pars=rmfield(pars,'XBP');
save(fullfile(getenv('CSI_OUT'),'final_contrast.mat'),'counts','snapshots','chi1', ...
    'time1','fre','para','csi_pars','grid_x_primary_m','grid_y_primary_m','-v7');
save(fullfile(getenv('CSI_OUT'),'full_history.mat'),'mchi1','chi1','time1','pars','rawdat','Einc','-v7');
summary=struct('case_name',str,'matlab',version,'threads',maxNumCompThreads, ...
    'native_end_posix',native_end_posix, ...
    'frequencies_GHz',fre,'Ninv',pars.Ninv,'iterations',pars.itenum, ...
    'source_count',para.NTX,'time_seconds',time1,'cell_size_m',para.m_unit, ...
    'source_radius_m',para.Tr,'receiver_radius_m',para.Rr,'snapshot_counts',counts);
fid=fopen(fullfile(getenv('CSI_OUT'),'matlab_summary.json'),'w');
fprintf(fid,'%s\n',jsonencode(summary,PrettyPrint=true));fclose(fid);
fprintf('CSI preparation outputs saved; native CC seconds %.9g; threads %d\n',time1,maxNumCompThreads);
