function run_shipped_cavity
% Shipped driver settings; only orchestration/storage differ. Not table B.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
upstream=fullfile(getenv('HOME'),'neural_bem_external','inverse-obstacle-scattering2d');
out=fullfile(root,'results','brg','examples','shipped_cavity_full');
local=fullfile(out,'local');
figdir=fullfile(root,'docs','iterations','brg_adaptation','01_run_published_examples','figures','shipped_cavity_full');
if ~exist(figdir,'dir'), mkdir(figdir); end
cd(upstream); startup; cd(out);
set(groot,'defaultFigureVisible','off'); pause('off'); warning('off');
maxNumCompThreads(8);
timer=tic; limit=str2double(getenv('BRG_REMAINING_SECONDS'));
assert(isfinite(limit) && limit>0,'Launch through run_full.py for the wall limit.');
label='BRG shipped cavity example; not a table B result';
kh=1:0.25:30; nk=numel(kh); charlie_flag=10.2; nppw=30;
bc=struct('type','Transmission','invtype','o','q',1.5, ...
    'transa',complex([1;1]),'transb',complex([1;1]));
optim_opts=struct('optim_type','sd','filter_type','gauss-conv','maxit',100, ...
    'eps_upd',1e-3,'eps_curv',1e-1,'n_curv_min',20);
opts=struct('verbose',true,'store_src_info',true,'use_lscaled_modes',true, ...
    'test_analytic',true,'src_in',[0.85;0]);
truth=geometries.charlie_cavity(charlie_flag,300); L=truth.L;
settings=struct('label',label,'kh',kh,'charlie_flag',charlie_flag,'bc',bc, ...
    'optim_opts',optim_opts,'opts',opts,'data_nppw',nppw,'data_minimum_points',500, ...
    'receiver_radius',10,'angular_counts','ceil(10*k)','initial_radius',1, ...
    'initial_points',500,'compute_threads',maxNumCompThreads,'matlab',version);
write_json(fullfile(out,'settings.json'),settings);
truth_curve=struct('xs',truth.xs,'ys',truth.ys,'L',truth.L);
save(fullfile(out,'truth_curve.mat'),'truth_curve');
copyfile(fullfile(upstream,'tests','driver_charlie_transmission.m'),fullfile(out,'upstream_driver.m'));
data_records=cell(1,nk); inverse_records=cell(1,nk);
fprintf('%s\nMATLAB %s, compute threads %d\n',label,version,maxNumCompThreads);
% Preserve the shipped order: generate the entire data set, then invert.
for ik=1:nk
    file=fullfile(local,sprintf('data_%03d.mat',ik));
    if isfile(file)
        loaded=load(file,'data_record'); data_records{ik}=loaded.data_record;
        continue
    end
    if toc(timer)>=limit, finish('budget_exhausted'); return; end
    t=tic; k=kh(ik); count=ceil(10*k);
    tr=0:2*pi/count:2*pi-2*pi/count;
    td=0:2*pi/count:2*pi-2*pi/count;
    [tr,td]=meshgrid(tr,td); tr=tr(:); td=td(:);
    sensor_info=struct('tgt',10*[cos(tr)';sin(tr)'],'t_dir',td);
    n=max(ceil(nppw*L*abs(k)/2/pi),500);
    src_info=geometries.charlie_cavity(charlie_flag,n);
    bc.transk=[k*bc.q k];
    [mats,erra]=rla.get_fw_mats(k,src_info,bc,sensor_info,opts);
    fields=rla.compute_fields(k,src_info,mats,sensor_info,bc,opts);
    measurement=struct('kh',k,'uscat_tgt',fields.uscat_tgt, ...
        'tgt',sensor_info.tgt,'t_dir',sensor_info.t_dir,'err_est',erra);
    data_record=struct('index',ik,'k',k,'points',n,'directions',count, ...
        'receivers',count,'err_est',erra,'wall_seconds',toc(t));
    temporary=[file '.tmp']; save(temporary,'measurement','data_record','-v7'); movefile(temporary,file,'f');
    data_records{ik}=data_record;
    write_json(fullfile(out,'data_summary.json'),data_records(~cellfun(@isempty,data_records)));
    fprintf('BRG DATA %d/%d k=%.2f n=%d seconds=%.3f err=%.5g\n',ik,nk,k,n,data_record.wall_seconds,erra);
    clear mats fields measurement src_info;
end
src_init=geometries.ellipse(1,1,500);
for ik=1:nk
    compact_file=fullfile(out,sprintf('frequency_%03d.mat',ik));
    checkpoint=fullfile(local,sprintf('state_%03d.mat',ik));
    if isfile(compact_file) && isfile(checkpoint)
        loaded=load(checkpoint,'src_info_out'); src_init=loaded.src_info_out;
        loaded=load(compact_file,'record'); inverse_records{ik}=loaded.record;
        continue
    end
    if toc(timer)>=limit, finish('budget_exhausted'); return; end
    loaded=load(fullfile(local,sprintf('data_%03d.mat',ik)),'measurement');
    t=tic;
    [inv_data_all,src_info_out]=rla.rla_inverse_solver({loaded.measurement},bc, ...
        optim_opts,opts,src_init,[],[]);
    seconds=toc(t); inverse=inv_data_all{1};
    record=struct('label',label,'index',ik,'k',kh(ik),'iterations',inverse.iter_count, ...
        'residual_history',inverse.res_all,'residual',inverse.res_opt, ...
        'exit_flag',inverse.exit_criterion,'wall_seconds',seconds, ...
        'xs',src_info_out.xs,'ys',src_info_out.ys);
    % Save the exact continuation state first, then the compact durable result.
    temporary=[checkpoint '.tmp']; save(temporary,'src_info_out','-v7'); movefile(temporary,checkpoint,'f');
    temporary=[compact_file '.tmp']; save(temporary,'record','-v7'); movefile(temporary,compact_file,'f');
    inverse_records{ik}=record; src_init=src_info_out;
    finish('running');
    fprintf('BRG INVERSE %d/%d k=%.2f iter=%d residual=%.8g exit=%d seconds=%.3f\n', ...
        ik,nk,kh(ik),record.iterations,record.residual,record.exit_flag,seconds);
    clear inverse inv_data_all loaded;
end
finish('complete');

    function finish(status)
        keep=~cellfun(@isempty,inverse_records); records=inverse_records(keep);
        compact=cell(size(records));
        for j=1:numel(records), compact{j}=rmfield(records{j},{'xs','ys'}); end
        summary=struct('label',label,'status',status,'data_frequencies',sum(~cellfun(@isempty,data_records)), ...
            'inverse_frequencies',numel(records),'total_frequencies',nk,'frequencies',{compact});
        if ~isempty(records)
            last=records{end}; polytrue=polyshape(truth.xs,truth.ys); polythis=polyshape(last.xs,last.ys);
            summary.last_k=last.k;
            summary.driver_area_error=area(subtract(polytrue,polythis))+area(subtract(polythis,polytrue));
            summary.true_area=area(polytrue);
            summary.relative_area_error=summary.driver_area_error/summary.true_area;
            f=figure('Visible','off'); plot(truth.xs,truth.ys,'k-',last.xs,last.ys,'r-','LineWidth',1.5);
            axis equal; grid on; legend('True cavity','BRG recovered','Location','best');
            title(sprintf('BRG shipped example (not Table B), k=%.2f, area error %.4g',last.k,summary.driver_area_error));
            xlabel('x'); ylabel('y');
            exportgraphics(f,fullfile(figdir,'cavity_comparison.png'),Resolution=150); close(f);
        end
        write_json(fullfile(out,'summary.json'),summary);
    end
end

function write_json(path,value)
temporary=[path '.tmp']; fid=fopen(temporary,'w');
assert(fid>=0,'Cannot write %s',temporary);
fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true)); fclose(fid); movefile(temporary,path,'f');
end
