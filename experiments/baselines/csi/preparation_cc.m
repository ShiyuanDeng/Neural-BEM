% Owned copy/instrumentation of the shipped driver. Numerical functions unchanged.
maxNumCompThreads(8);
set(groot,'defaultFigureVisible','off');
cd(getenv('CSI_UPSTREAM'));
try
    eval(fileread(getenv('CSI_SCRIPT')));
    run(fullfile(getenv('CSI_REPO'),'experiments/baselines/csi/save_preparation_cc.m'));
catch failure
    fid=fopen(fullfile(getenv('CSI_OUT'),'failure.txt'),'w');
    fprintf(fid,'%s\n',getReport(failure,'extended','hyperlinks','off')); fclose(fid);
    rethrow(failure);
end
