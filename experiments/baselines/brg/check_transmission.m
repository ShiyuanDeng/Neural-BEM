function check_transmission(stage,out)
% Diagnostic only: exact true boundary isolates frequency plumbing from fitting.
ks = [1 1.25 1.5];
bc = struct('type','Transmission','invtype','o','q',1.5, ...
    'transa',[1;1],'transb',[1;1]);
opts = struct('verbose',false,'store_src_info',true,'use_lscaled_modes',true);
optim = struct('optim_type','sd','filter_type','gauss-conv','maxit',1, ...
    'eps_upd',1e-3,'eps_curv',1e-1,'n_curv_min',20);
truth = geometries.charlie_cavity(10.2,500);
data = cell(1,3); records = struct([]);
for i=1:numel(ks)
    k=ks(i); count=ceil(10*k);
    angles=(0:count-1)*2*pi/count;
    [tr,td]=meshgrid(angles,angles);
    sensor=struct('tgt',10*[cos(tr(:))';sin(tr(:))'],'t_dir',td(:));
    bc.transk=[bc.q*k k];
    t=tic;
    mats=rla.get_fw_mats(k,truth,bc,sensor,opts);
    fields=rla.compute_fields(k,truth,mats,sensor,bc,opts);
    data{i}=sensor; data{i}.kh=k; data{i}.uscat_tgt=fields.uscat_tgt;
    records(i).k=k; records(i).data_seconds=toc(t);
end
save(fullfile(out,'low_frequency_data.mat'),'data','truth','bc','opts','optim');
for i=1:numel(ks)
    k=ks(i);
    bc.transk=[45 30]; % exactly the stale endpoint left by the shipped driver
    t=tic;
    [inv,curve]=rla.rla_inverse_solver(data(i),bc,optim,opts,truth,[],[]);
    records(i).inverse_seconds=toc(t);
    records(i).relative_residual=inv{1}.res_opt;
    records(i).iterations=inv{1}.iter_count;
    records(i).exit_criterion=inv{1}.exit_criterion;
    save(fullfile(out,sprintf('frequency_%03d.mat',i)),'inv','curve','k','bc');
    fprintf('BRG frequency check k=%.2f relative_residual=%.12g elapsed=%.3f\n', ...
        k,records(i).relative_residual,records(i).inverse_seconds);
end
save(fullfile(out,'check.mat'),'records','stage');
fid=fopen(fullfile(out,'check.json'),'w');
fprintf(fid,'%s\n',jsonencode(records,PrettyPrint=true)); fclose(fid);
assert(all([records.relative_residual]<1e-8),'BRG:staleWavenumbers', ...
    'True-shape residual must vanish at each frequency; stale transk violates the known material.');
end
