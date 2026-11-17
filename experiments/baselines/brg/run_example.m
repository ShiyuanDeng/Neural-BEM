function run_example(stage)
% Wrapper only: upstream numerical settings are preserved.
root = fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
upstream = fullfile(getenv('HOME'),'neural_bem_external','inverse-obstacle-scattering2d');
out = fullfile(root,'results','brg','examples',stage);
figdir = fullfile(root,'docs','iterations','brg_adaptation', ...
    '01_run_published_examples','figures',stage);
if ~exist(figdir,'dir'), mkdir(figdir); end
cd(upstream); startup;
cd(out);
set(groot,'defaultFigureVisible','off');
pause('off');
initial_threads = maxNumCompThreads;
maxNumCompThreads(8);
meta = struct('matlab',version,'initial_threads',initial_threads, ...
    'compute_threads',maxNumCompThreads,'stage',stage);
fprintf('BRG MATLAB %s; initial threads %d; requested/current threads %d\n', ...
    version, initial_threads, maxNumCompThreads);
save(fullfile(out,'metadata.mat'),'meta');
started = tic;
try
    switch stage
        case 'suite'
            rng(20261117);
            A = randn(2500)+1i*randn(2500); B = randn(2500,16)+1i*randn(2500,16);
            timings = zeros(2,3);
            thread_order = [1 8 8 1 1 8];
            counts = [0 0];
            for threads = thread_order
                maxNumCompThreads(threads);
                j = 1+(threads==8); counts(j)=counts(j)+1;
                t = tic; X = A\B; timings(j,counts(j))=toc(t);
            end
            maxNumCompThreads(8);
            speedup = median(timings(1,:))/median(timings(2,:));
            relative_residual = norm(A*X-B,'fro')/norm(B,'fro');
            save(fullfile(out,'thread_check.mat'),'timings','thread_order','speedup','relative_residual');
            fprintf('Dense solve median 1-thread %.6f s; 8-thread %.6f s; speedup %.3f; residual %.3g\n', ...
                median(timings(1,:)),median(timings(2,:)),speedup,relative_residual);
            clear A B X;
            evalin('base',fileread(fullfile(upstream,'tests','test_all.m')));
            assert(evalin('base','all(ipass==1)'), 'BRG:testFailure','Upstream test_all failed');
        case 'transmission'
            script = fullfile(upstream,'tests','test_frechet_ders_trans.m');
            source = fileread(script);
            source = strrep(source,'run ../inverse-obstacle-scattering2d/startup.m', ...
                '% startup supplied by BRG wrapper');
            evalin('base',source);
            evalin('base',sprintf('save(''%s'',''-v7.3'')',fullfile(out,'frechet_workspace.mat')));
            evalin('base','clear');
            evalin('base',fileread(fullfile(upstream,'tests','test_transmission_multi.m')));
            assert(evalin('base','ipass==1'), 'BRG:testFailure','Transmission multi test failed');
        case 'data'
            source = fileread(fullfile(upstream,'examples','data_generation_scripts','starn_transmission_tensor_data.m'));
            source = strrep(source,'''../data/star''', ['''' out '/star''']);
            evalin('base',source);
            assert(evalin('base','numel(u_meas)==17'), 'BRG:incomplete','Expected 17 frequencies');
        case {'low_frequency_unpatched','low_frequency_fixed'}
            check_transmission(stage,out);
        otherwise
            error('BRG:stage','Unknown stage: %s',stage);
    end
    meta.success = true;
catch err
    meta.success = false;
    meta.error = getReport(err,'extended','hyperlinks','off');
    save_outputs(out,figdir,meta,toc(started));
    rethrow(err);
end
save_outputs(out,figdir,meta,toc(started));
end

function save_outputs(out,figdir,meta,wall)
meta.compute_seconds = wall;
save(fullfile(out,'metadata.mat'),'meta');
fid=fopen(fullfile(out,'metadata.json'),'w');
fprintf(fid,'%s\n',jsonencode(meta,PrettyPrint=true)); fclose(fid);
evalin('base',sprintf('save(''%s'',''-v7.3'')',fullfile(out,'workspace.mat')));
figures=findall(groot,'Type','figure');
for i=1:numel(figures)
    exportgraphics(figures(i),fullfile(figdir,sprintf('figure_%02d.png',i)));
    savefig(figures(i),fullfile(figdir,sprintf('figure_%02d.fig',i)));
end
fprintf('BRG %s success=%d compute_seconds=%.6f\n',meta.stage,meta.success,wall);
end
