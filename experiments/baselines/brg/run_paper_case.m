function run_paper_case
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
upstream=fullfile(getenv('HOME'),'neural_bem_external','inverse-obstacle-scattering2d');
case_name=getenv('BRG_PAPER_CASE'); curvature=getenv('BRG_CURVATURE');
shape=getenv('BRG_SHAPE'); eta=str2double(getenv('BRG_ETA')); limited=str2double(getenv('BRG_LIMITED'));
base=fullfile(root,'results','brg','paper_examples','2026-11-17',case_name);
out=fullfile(base,curvature); local=fullfile(out,'local'); data_dir=fullfile(base,'local');
cd(upstream); startup; cd(out); warning('off'); pause('off');
set(groot,'defaultFigureVisible','off'); maxNumCompThreads(8);
timer=tic; limit=str2double(getenv('BRG_REMAINING_SECONDS'));
assert(isfinite(limit)&&limit>0,'Launch through run_paper.py');
ks=1:0.25:30; nk=numel(ks);
bc=struct('type','Transmission','invtype','o','q',sqrt(eta),'transa',[1;1],'transb',[1;1]);
optim=struct('optim_type','min(gn,sd)','filter_type','gauss-conv','maxit',50,'eps_res',1e-5,'eps_upd',1e-5);
if strcmp(curvature,'shipped'), optim.eps_curv=0.1; optim.n_curv_min=20; end
opts=struct('verbose',true,'nppw',70,'use_lscaled_modes',false);
truth=paper_geometry(shape,2048,false); L=truth.L;
truth_curve=struct('xs',truth.xs,'ys',truth.ys,'L',L); clear truth;
polytrue=polyshape(truth_curve.xs,truth_curve.ys); true_area=area(polytrue);
% This source is diagnostic only; choose it from the actual true polygon.
[cx,cy]=centroid(polytrue); candidates=[cx cy; 0 0]; used_interior_grid=false;
if ~any(isinterior(polytrue,candidates(:,1),candidates(:,2)))
    [xx,yy]=meshgrid(linspace(min(truth_curve.xs),max(truth_curve.xs),41),linspace(min(truth_curve.ys),max(truth_curve.ys),41));
    candidates=[xx(:) yy(:)]; used_interior_grid=true;
end
inside=isinterior(polytrue,candidates(:,1),candidates(:,2));
% Exclude boundary points: polygon membership alone can include an edge.
vertices=[truth_curve.xs(:) truth_curve.ys(:)]; edges=circshift(vertices,-1)-vertices;
clearance=zeros(size(inside));
for j=find(inside).'
    delta=candidates(j,:)-vertices;
    fraction=max(0,min(1,sum(delta.*edges,2)./sum(edges.^2,2)));
    clearance(j)=min(sqrt(sum((delta-fraction.*edges).^2,2)));
end
inside=inside & clearance>0.01;
assert(any(inside),'No strictly interior diagnostic point with 0.01 clearance.');
source_index=find(inside,1);
if used_interior_grid, [~,source_index]=max(clearance); end
src_in=candidates(source_index,:).';
data_opts=struct('verbose',false,'test_analytic',true,'src_in',src_in);
settings=struct('case',case_name,'shape',shape,'eta',eta,'curvature',curvature, ...
    'data_nppw_exterior',100,'inverse_nppw_exterior',70,'data_nppw_interior',100/sqrt(eta), ...
    'inverse_nppw_interior',70/sqrt(eta),'ks',ks,'optim',optim,'opts',opts, ...
    'limited',limited,'src_in',src_in,'source_verified_inside',true, ...
    'source_boundary_clearance',clearance(source_index),'compute_threads',maxNumCompThreads,'matlab',version);
write_json(fullfile(out,'settings.json'),settings); save(fullfile(out,'truth_curve.mat'),'truth_curve');
data_records=cell(1,nk); inverse_records=cell(1,nk);
for i=1:nk
    file=fullfile(data_dir,sprintf('data_%03d.mat',i));
    if isfile(file), loaded=load(file,'data_record'); data_records{i}=loaded.data_record; continue; end
    if toc(timer)>=limit, finish('budget_exhausted'); return; end
    k=ks(i); nd=floor(10*k); nr=nd; if limited, nd=10; nr=200; end
    [tr,td]=meshgrid((0:nr-1)*2*pi/nr,(0:nd-1)*2*pi/nd);
    sensor=struct('tgt',10*[cos(tr(:))';sin(tr(:))'],'t_dir',td(:));
    n=max(300,ceil(100*L*k/2/pi)); n=n+mod(n,2);
    bc.transk=[sqrt(eta)*k k]; t=tic;
    src=paper_geometry(shape,n); [mats,err]=rla.get_fw_mats(k,src,bc,sensor,data_opts);
    fields=rla.compute_fields(k,src,mats,sensor,bc,data_opts);
    measurement=struct('kh',k,'tgt',sensor.tgt,'t_dir',sensor.t_dir,'uscat_tgt',fields.uscat_tgt,'err_est',err);
    data_record=struct('index',i,'k',k,'points',n,'directions',nd,'receivers',nr,'wall_seconds',toc(t),'err_est',err);
    tmp=[file '.tmp']; save(tmp,'measurement','data_record','-v7'); movefile(tmp,file,'f');
    data_records{i}=data_record;
    write_json(fullfile(out,'data_summary.json'),data_records(~cellfun(@isempty,data_records)));
    fprintf('BRG DATA %s %d/%d k=%.2f n=%d seconds=%.3f err=%.6g\n',case_name,i,nk,k,n,data_record.wall_seconds,err);
    clear src mats fields measurement;
end
% Required also when all data frequencies were loaded for a resumed run.
write_json(fullfile(out,'data_summary.json'),data_records);
if eta>1 && ~isfile(fullfile(base,'accuracy_k30.json'))
    if toc(timer)>=limit, finish('budget_exhausted'); return; end
    coarse=load(fullfile(data_dir,'data_117.mat')); k=30;
    refinement_factor=2;
    if strcmp(shape,'cavity'), refinement_factor=1.25; end
    n=ceil(refinement_factor*coarse.data_record.points); n=n+mod(n,2);
    bc.transk=[sqrt(eta)*k k]; t=tic;
    src=paper_geometry(shape,n); mats=rla.get_fw_mats(k,src,bc,coarse.measurement,data_opts);
    fields=rla.compute_fields(k,src,mats,coarse.measurement,bc,data_opts);
    accuracy=struct('k',30,'coarse_points',coarse.data_record.points,'fine_points',n, ...
        'requested_refinement_factor',refinement_factor, ...
        'relative_field_difference',norm(fields.uscat_tgt-coarse.measurement.uscat_tgt)/norm(fields.uscat_tgt),'wall_seconds',toc(t));
    write_json(fullfile(base,'accuracy_k30.json'),accuracy);
    fine_field=fields.uscat_tgt; save(fullfile(data_dir,'accuracy_k30_fine.mat'),'fine_field','accuracy','-v7');
    fprintf('BRG ACCURACY %s k=30 relative_difference=%.8g seconds=%.3f\n',case_name,accuracy.relative_field_difference,accuracy.wall_seconds);
    clear src mats fields coarse fine_field;
end
src_init=[];
for i=1:nk
    file=fullfile(out,sprintf('frequency_%03d.mat',i)); checkpoint=fullfile(local,sprintf('state_%03d.mat',i));
    if isfile(file)&&isfile(checkpoint)
        loaded=load(checkpoint,'src_info_out'); src_init=loaded.src_info_out;
        loaded=load(file,'record'); inverse_records{i}=loaded.record; continue;
    end
    if toc(timer)>=limit, finish('budget_exhausted'); return; end
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
