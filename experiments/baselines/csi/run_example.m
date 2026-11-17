% Run from the upstream checkout. clearvars in the driver is intentional.
maxNumCompThreads(8);
cd(getenv('CSI_UPSTREAM'));
set(groot, 'defaultFigureVisible', 'off');
fprintf('CSI wrapper: MATLAB %s, compute threads %d\n', version, maxNumCompThreads);
try
    eval(fileread(getenv('CSI_SCRIPT')));
    run(fullfile(getenv('CSI_REPO'), 'experiments/baselines/csi/save_outputs.m'));
catch failure
    % Keep completed methods when a later method fails. Do not save operators.
    save(fullfile(getenv('CSI_OUT'), 'partial_reconstruction.mat'), ...
        '-regexp', '^(mchi[123]|chi[123]|time[123]|xinv|yinv|fre|para|centre|xs|ys|regSize|rawdat)$', '-v7');
    fid = fopen(fullfile(getenv('CSI_OUT'), 'failure.txt'), 'w');
    fprintf(fid, '%s\n', getReport(failure, 'extended', 'hyperlinks', 'off'));
    fclose(fid);
    rethrow(failure);
end
