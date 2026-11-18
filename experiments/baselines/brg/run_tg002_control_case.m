function run_tg002_control_case
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
upstream=fullfile(getenv('HOME'),'neural_bem_external','inverse-obstacle-scattering2d');
case_name=getenv('BRG_TG002_CASE'); eta=str2double(getenv('BRG_ETA'));
curvature=getenv('BRG_CURVATURE'); assert(any(strcmp(curvature,{'shipped','default'})));
shape=getenv('BRG_SHAPE'); limited=false;
source_base=fullfile(root,'results','brg','tg002_shapes','2026-11-17');
base=getenv('BRG_TG002_OUTPUT_BASE'); assert(~isempty(base));
out=fullfile(base,case_name); local=fullfile(out,'local');
data_dir=fullfile(source_base,case_name,'local');
input=fullfile(source_base,'local',[shape '.mat']);
stop_file=getenv('BRG_TG002_STOP'); assert(~isempty(stop_file));
cd(upstream); startup; cd(out); warning('off'); pause('off');
set(groot,'defaultFigureVisible','off'); maxNumCompThreads(8);
% No elapsed-time stop. Only a user STOP ends early at a checkpoint.
input_data=load(input,'ks'); ks=input_data.ks(:).'; nk=numel(ks);
bc=struct('type','Transmission','invtype','o','q',sqrt(eta),'transa',[1;1],'transb',[1;1]);
optim=struct('optim_type','min(gn,sd)','filter_type','gauss-conv','maxit',50,'eps_res',1e-5,'eps_upd',1e-5);
if strcmp(curvature,'shipped'), optim.eps_curv=0.1; optim.n_curv_min=20; end
opts=struct('verbose',true,'nppw',70,'use_lscaled_modes',false);
truth=tg002_geometry(input,2048,false); L=truth.L;
truth_curve=struct('xs',truth.xs,'ys',truth.ys,'L',L); clear truth;
polytrue=polyshape(truth_curve.xs,truth_curve.ys); true_area=area(polytrue);
% This source is used only by BRG's analytic forward check.
[src_in,source_clearance,diagnostic_grid_size]=tg002_diagnostic_point(polytrue,truth_curve);
fprintf('BRG DIAGNOSTIC %s x=%.17g y=%.17g clearance=%.17g grid=%d\n',case_name,src_in(1),src_in(2),source_clearance,diagnostic_grid_size);
data_opts=struct('verbose',false,'test_analytic',true,'src_in',src_in);
settings=struct('case',case_name,'shape',shape,'eta',eta,'curvature',curvature, ...
    'data_status','provisional BRG forward; frozen BEM-side data pending', ...
    'data_nppw_exterior',100,'inverse_nppw_exterior',70,'data_nppw_interior',100/sqrt(eta), ...
    'inverse_nppw_interior',70/sqrt(eta),'ks',ks,'optim',optim,'opts',opts, ...
    'limited',limited,'src_in',src_in,'source_verified_inside',true, ...
    'source_boundary_clearance',source_clearance,'diagnostic_grid_size',diagnostic_grid_size,'compute_threads',maxNumCompThreads,'matlab',version);
write_json(fullfile(out,'settings.json'),settings); save(fullfile(out,'truth_curve.mat'),'truth_curve');
data_records=cell(1,nk); inverse_records=cell(1,nk);
for i=1:nk
    file=fullfile(data_dir,sprintf('data_%03d.mat',i));
    if isfile(file), loaded=load(file,'data_record'); data_records{i}=loaded.data_record; continue; end
    if isfile(stop_file), finish('coordinator_stop'); return; end
    assert(strcmp(curvature,'shipped'),'Control row must reuse all data; generation forbidden.');
    k=ks(i); nd=floor(10*k); nr=nd; if limited, nd=10; nr=200; end
    [tr,td]=meshgrid((0:nr-1)*2*pi/nr,(0:nd-1)*2*pi/nd);
    sensor=struct('tgt',10*[cos(tr(:))';sin(tr(:))'],'t_dir',td(:));
    n=max(300,ceil(100*L*k/2/pi)); n=n+mod(n,2);
    bc.transk=[sqrt(eta)*k k]; t=tic;
    [src,geometry_check]=tg002_geometry(input,n); [mats,err]=rla.get_fw_mats(k,src,bc,sensor,data_opts);
    fields=rla.compute_fields(k,src,mats,sensor,bc,data_opts);
    measurement=struct('kh',k,'tgt',sensor.tgt,'t_dir',sensor.t_dir,'uscat_tgt',fields.uscat_tgt,'err_est',err);
    data_record=struct('index',i,'k',k,'points',n,'directions',nd,'receivers',nr,'wall_seconds',toc(t),'err_est',err,'geometry_check',geometry_check);
    tmp=[file '.tmp']; save(tmp,'measurement','data_record','-v7'); movefile(tmp,file,'f');
    data_records{i}=data_record;
    write_json(fullfile(out,'data_summary.json'),data_records(~cellfun(@isempty,data_records)));
    fprintf('BRG DATA %s %d/%d k=%.2f n=%d seconds=%.3f err=%.6g\n',case_name,i,nk,k,n,data_record.wall_seconds,err);
    clear src mats fields measurement;
end
% Required also when all data frequencies were loaded for a resumed run.
write_json(fullfile(out,'data_summary.json'),data_records);
src_init=[];
for i=1:nk
    file=fullfile(out,sprintf('frequency_%03d.mat',i)); checkpoint=fullfile(local,sprintf('state_%03d.mat',i));
    if isfile(file)&&isfile(checkpoint)
        loaded=load(checkpoint,'src_info_out'); src_init=loaded.src_info_out;
        loaded=load(file,'record'); inverse_records{i}=loaded.record; continue;
    end
    if isfile(stop_file), finish('coordinator_stop'); return; end
    loaded=load(fullfile(data_dir,sprintf('data_%03d.mat',i)),'measurement');
    opts.ncoeff_boundary=floor(3*max(ks(i),sqrt(eta)*ks(i))); t=tic;
    [inv,src_info_out]=rla.rla_inverse_solver({loaded.measurement},bc,optim,opts,src_init,[],[]);
    seconds=toc(t); info=inv{1}; recovered=polyshape(src_info_out.xs,src_info_out.ys);
    area_error=area(subtract(polytrue,recovered))+area(subtract(recovered,polytrue));
    record=struct('index',i,'k',ks(i),'iterations',info.iter_count,'residual_history',info.res_all, ...
        'residual',info.res_opt,'exit_flag',info.exit_criterion,'wall_seconds',seconds, ...
        'area_error',area_error,'relative_area_error',area_error/true_area,'xs',src_info_out.xs,'ys',src_info_out.ys,'nodes',numel(src_info_out.xs));
    tmp=[checkpoint '.tmp']; save(tmp,'src_info_out','-v7'); movefile(tmp,checkpoint,'f');
    tmp=[file '.tmp']; save(tmp,'record','-v7'); movefile(tmp,file,'f');
    inverse_records{i}=record; src_init=src_info_out; finish('running');
    fprintf('BRG INVERSE %s %d/%d k=%.2f iter=%d residual=%.8g area=%.8g exit=%d n=%d seconds=%.3f\n',case_name,i,nk,ks(i),record.iterations,record.residual,record.relative_area_error,record.exit_flag,record.nodes,seconds);
    clear inv info loaded;
end
% Frozen protocol: residuals of the returned curve at its own resolution.
residual_file=fullfile(out,'final_residuals.json');
if ~isfile(residual_file)
    final_residuals=cell(1,nk); eval_opts=struct('verbose',false);
    for i=1:nk
        if isfile(stop_file), finish('coordinator_stop'); return; end
        loaded=load(fullfile(data_dir,sprintf('data_%03d.mat',i)),'measurement');
        k=ks(i); bc.transk=[sqrt(eta)*k k]; t=tic;
        mats=rla.get_fw_mats(k,src_init,bc,loaded.measurement,eval_opts);
        fields=rla.compute_fields(k,src_init,mats,loaded.measurement,bc,eval_opts);
        relative=norm(fields.uscat_tgt-loaded.measurement.uscat_tgt)/norm(loaded.measurement.uscat_tgt);
        final_residuals{i}=struct('index',i,'k',k,'relative_residual',relative,'wall_seconds',toc(t));
        clear mats fields;
    end
    write_json(residual_file,final_residuals);
end
finish('complete');
    function finish(status)
        records=inverse_records(~cellfun(@isempty,inverse_records)); compact=cell(size(records));
        for j=1:numel(records), compact{j}=rmfield(records{j},{'xs','ys'}); end
        summary=struct('case',case_name,'curvature',curvature,'status',status,'data_frequencies',sum(~cellfun(@isempty,data_records)), ...
            'inverse_frequencies',numel(records),'true_area',true_area,'frequencies',{compact});
        write_json(fullfile(out,'summary.json'),summary);
    end
end
function write_json(path,value)
tmp=[path '.tmp']; fid=fopen(tmp,'w'); assert(fid>=0,'Cannot write %s',tmp);
fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true)); fclose(fid); movefile(tmp,path,'f');
end
