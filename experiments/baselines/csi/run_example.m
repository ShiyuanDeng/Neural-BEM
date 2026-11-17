% Run from the upstream checkout. clearvars in the driver is intentional.
maxNumCompThreads(8);
cd(getenv('CSI_UPSTREAM'));
set(groot, 'defaultFigureVisible', 'off');
fprintf('CSI wrapper: MATLAB %s, compute threads %d\n', version, maxNumCompThreads);
try
    eval(fileread(getenv('CSI_SCRIPT')));
    run(fullfile(getenv('CSI_REPO'), 'experiments/baselines/csi/save_outputs.m'));
catch failure
    fid = fopen(fullfile(getenv('CSI_OUT'), 'failure.txt'), 'w');
    fprintf(fid, '%s\n', getReport(failure, 'extended', 'hyperlinks', 'off'));
    fclose(fid);
    rethrow(failure);
end
