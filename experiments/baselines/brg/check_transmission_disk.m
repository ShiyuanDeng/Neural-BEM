function check_transmission_disk(stage,out)
% Compare the real RLA boundary with the direct single-frequency reference.
frozen=load(fullfile(fileparts(out),'low_frequency_stale','low_frequency_data.mat'));
data=frozen.data; bc=frozen.bc; opts=frozen.opts; optim=frozen.optim;
start=geometries.ellipse(1,1,500);
start.lambda=ones(500,1);
opts.ncoeff_boundary_mult=2*start.L/2/pi;
records=struct([]);
for i=1:numel(data)
    k=data{i}.kh;
    bc.transk=[bc.q*k k];
    t=tic;
    [reference,ref_curve]=rla.inverse_solver(k,start,bc,data{i},optim,opts);
    records(i).reference_seconds=toc(t);
    bc.transk=[45 30];
    t=tic;
    [inv,curve]=rla.rla_inverse_solver(data(i),bc,optim,opts,start,[],[]);
    records(i).rla_seconds=toc(t);
    records(i).k=k;
    records(i).reference_residual=reference.res_opt;
    records(i).rla_residual=inv{1}.res_opt;
    records(i).residual_difference=abs(inv{1}.res_opt-reference.res_opt);
    if numel(curve.xs)==numel(ref_curve.xs)
        records(i).curve_difference=norm([curve.xs-ref_curve.xs curve.ys-ref_curve.ys])/norm([ref_curve.xs ref_curve.ys]);
    else
        records(i).curve_difference=Inf;
    end
    save(fullfile(out,sprintf('frequency_%03d.mat',i)),'reference','ref_curve','inv','curve','k','bc','opts','optim');
    fprintf('BRG disk check k=%.2f reference=%.12g RLA=%.12g difference=%.12g curve_difference=%.12g\n', ...
        k,reference.res_opt,inv{1}.res_opt,records(i).residual_difference,records(i).curve_difference);
end
save(fullfile(out,'check.mat'),'records','stage');
fid=fopen(fullfile(out,'check.json'),'w'); fprintf(fid,'%s\n',jsonencode(records,PrettyPrint=true)); fclose(fid);
assert(all([records.residual_difference]<1e-10) && all([records.curve_difference]<1e-10), ...
    'BRG:staleWavenumbers','RLA must reproduce the correctly parameterized direct frequency solve.');
end
