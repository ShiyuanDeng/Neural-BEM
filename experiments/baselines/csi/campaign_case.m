% Execute an owned driver copy, with the numerical method unchanged.
maxNumCompThreads(8);set(groot,'defaultFigureVisible','off');
cd(getenv('CSI_UPSTREAM'));
try
    eval(fileread(getenv('CSI_SCRIPT')));
    native_end_posix=posixtime(datetime('now','TimeZone','UTC'));
    compact=load(fullfile(getenv('CSI_OUT'),'final_contrast.mat'));
    assert(isequal(compact.snapshots{end}(:),chi1{end}(:)));
    save(fullfile(getenv('CSI_OUT'),'full_history.mat'),'mchi1','chi1','time1','pars','rawdat','Einc','-v7');
    summary=struct('case_name',str,'matlab',version,'threads',maxNumCompThreads, ...
        'native_end_posix',native_end_posix,'frequencies_GHz',fre,'Ninv',pars.Ninv, ...
        'iterations',pars.itenum,'source_count',para.NTX,'time_seconds',time1, ...
        'cell_size_m',para.m_unit,'source_radius_m',para.Tr,'receiver_radius_m',para.Rr);
    fid=fopen(fullfile(getenv('CSI_OUT'),'matlab_summary.json'),'w');
    fprintf(fid,'%s\n',jsonencode(summary,PrettyPrint=true));fclose(fid);
catch failure
    fid=fopen(fullfile(getenv('CSI_OUT'),'failure.txt'),'w');
    fprintf(fid,'%s\n',getReport(failure,'extended','hyperlinks','off'));fclose(fid);
    rethrow(failure);
end
