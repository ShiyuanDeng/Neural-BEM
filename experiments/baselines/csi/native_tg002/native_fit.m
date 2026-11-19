function native_fit(mode,input_dir,out_dir,iterations)
% Output-only wrapper around pinned, unchanged classical CSI.
maxNumCompThreads(8);set(groot,'defaultFigureVisible','off');
addpath(genpath(fullfile(getenv('HOME'),'neural_bem_external','CC-CSI')));
addpath(genpath(fullfile(getenv('HOME'),'neural_bem_external','maxwellfdfd')));
addpath(fileparts(mfilename('fullpath')));
try
    [Emea,Phi,A,chi,vJ,eIncInv,eTot,pars,info]=native_configuration(input_dir);
    x_m=info.x_m;y_m=info.y_m;
    observed_native=info.observed_native(:);
    assert(numel(observed_native)==24 && numel(info.mask_indices)==24);
    if strcmp(mode,'self_test')
        fixture=load(fullfile(out_dir,'truth_input.mat'));
        chi_image=fixture.chi_image;
        assert(isequal(size(chi_image),[numel(x_m),numel(y_m)]));
        assert(max(abs(x_m(:)-fixture.x_m(:)))<1e-12);
        assert(max(abs(y_m(:)-fixture.y_m(:)))<1e-12);
    else
        assert(strcmp(mode,'fit') && iterations==2048);
        pars.itenum=iterations;pars.disflag=false;pars.terflag=false;pars.recflag=false;
        started=tic;
        [snapshots,native_seconds,chi,~,~]=CSI(Emea,Phi,A,chi,vJ,eIncInv,eTot,pars,[]);
        wrapper_seconds=toc(started);
        chi_image=reshape(chi{end},pars.Ninv);
        counts=[64:64:iterations iterations];
        save(fullfile(out_dir,'snapshots.mat'),'snapshots','counts','native_seconds','wrapper_seconds','x_m','y_m','-v7');
        % Save before the independent prediction, preserving a failed prediction's image.
        save(fullfile(out_dir,'final_image.mat'),'chi_image','x_m','y_m','native_seconds','-v7');
    end
    predicted_native=native_predict(chi_image,info);predicted_native=predicted_native(:);
    assert(numel(predicted_native)==24 && all(isfinite(predicted_native)));
    save(fullfile(out_dir,'prediction.mat'),'chi_image','x_m','y_m','predicted_native','observed_native','-v7');
catch failure
    fid=fopen(fullfile(out_dir,'failure.txt'),'w');
    fprintf(fid,'%s\n',getReport(failure,'extended','hyperlinks','off'));fclose(fid);
    rethrow(failure);
end
end
