% Own input driver using the shipped FDFD matrix and receiver kernel.
% No upstream inverse function or forward builder is edited.
maxNumCompThreads(8);cd(getenv('CSI_UPSTREAM'));restoredefaultpath;add_path;
geometry_path=getenv('CSI_GEOMETRY');
if isempty(geometry_path);geometry_path=fullfile(getenv('CSI_REPO'),'results/csi/preparation/2026-11-17_geometry/geometry.mat');end
geometry=load(geometry_path);
raw=load('dielTM_dec8f.txt');
para.pt=PT.TM;para.NTX=36;para.Tr=.72;para.Rr=.76;para.m_unit=0.0003125;
N=round(2*.10375/para.m_unit); halfN=N/2; geometry.x_m=(-halfN:halfN-1)*para.m_unit; geometry.y_m=geometry.x_m;
para.showconfg=false;para.disflag=false;
invdom=[-.10375 .10375 -.10375 .10375 0 0];regSize=[-1.2 1.2;-1.2 1.2];
fre=1:8;reports={};timer=tic;
for f=fre
    indices=find(raw(:,3)==f);table=raw(indices,:);
    tx=deg2rad(10*(table(:,1)-1)-2.5);rx=deg2rad(5*(table(:,2)-1));
    distance=hypot(para.Rr*cos(rx)-para.Tr*cos(tx),para.Rr*sin(rx)-para.Tr*sin(tx));
    k=2*pi*f*1e9/PhysC.c0;
    % Physical unit outgoing scalar Green source, independent of cell size.
    inc=1j/4*besselh(0,1,-k*distance);
    table(:,4)=real(inc);table(:,5)=imag(inc);table(:,6)=real(inc);table(:,7)=imag(inc);
    angles=table;angles(:,1)=10*(angles(:,1)-1)-2.5;angles(:,2)=5*(angles(:,2)-1);
    begin=tic;
    [dat,Phi,A,Einc,grid,pars]=ReadFreData(f,angles,invdom,regSize,para);
    assert(isequal(pars.Ninv,[N N 1]));assert(norm(dat,'fro')==0);
    gx=grid.l{1,1}(pars.nx)*para.m_unit;gy=grid.l{2,1}(pars.ny)*para.m_unit;
    assert(max(abs(gx(:)-geometry.x_m(:)))<1e-12);
    assert(max(abs(gy(:)-geometry.y_m(:)))<1e-12);
    % Native material assignment samples cells at dual nodes, then averages
    % four neighbouring cell values onto each primary Ez node.
    dualx=geometry.x_m(:)+para.m_unit/2;
    [dx,dy]=ndgrid(dualx,dualx);
    boundary=geometry.boundary(:);
    eps_nodes=1+3*inpolygon(dx,dy,real(boundary),imag(boundary));
    options.returnAandb=true;
    [~,forward_grid,~,true_matrix,~]=FDFDpars( ...
        'OSC',para.m_unit,PhysC.c0/(f*1e9)/para.m_unit, ...
        'DOM',{'vacuum','none',1},[-halfN halfN;-halfN halfN;0 1],1,BC.p,[5 5 0], ...
        'OBJ',eps_nodes,'SRCJ',PointSrc(Axis.z,[0 0 .5]),options,PT.TM);
    assert(max(abs(forward_grid.l{1,2}(:)*para.m_unit-dualx))<1e-12);
    eps_cell=mean_material_node(forward_grid,GT.prim,{eps_nodes,eps_nodes,eps_nodes});
    eps_ez=eps_cell{3};chi=eps_ez(:)-1;
    material=true_matrix/pars.omega^2;
    mass_check=norm(material-(A-spdiags(chi,0,numel(chi),numel(chi))),'fro')/norm(material,'fro');
    assert(mass_check<1e-12);
    if f==1
        save(fullfile(getenv('CSI_OUT'),'forward_material.mat'),'eps_nodes','eps_ez','dualx','-v7');
    end
    rhs=chi.*Einc;
    esc=material\rhs;
    residual=norm(material*esc-rhs,'fro')/norm(rhs,'fro');
    assert(isfinite(residual) && residual<1e-9);
    active=find(chi~=0);
    currents=chi(active).*(Einc(active,:)+esc(active,:));
    full_data=(Phi(:,active)*pars.omega)*currents;
    nr=size(table,1)/para.NTX;
    select=pars.Rindex+(0:para.NTX-1)*size(full_data,1);
    scattered=full_data(select);
    total=inc+scattered(:);
    table(:,4)=real(total);table(:,5)=imag(total);
    raw(indices,:)=table;
    reports{end+1}=struct('frequency_GHz',f,'seconds',toc(begin),'solve_residual',residual, ...
        'native_material_matrix_relative_check',mass_check, ...
        'Ninv',pars.Ninv,'omega_normalized',pars.omega,'expected_source_calibration',1/pars.omega^2, ...
        'measured_entries',numel(scattered),'scattered_norm',norm(scattered,'fro'));
    fprintf('Generated %d GHz, relative native FDFD residual %.3g\n',f,residual);
    clear Phi A Einc material true_matrix rhs esc currents full_data
end
out=getenv('CSI_OUT');
fid=fopen(fullfile(out,'synthetic_input.txt'),'w');
fprintf(fid,'%.16e %.16e %.16e %.16e %.16e %.16e %.16e\n',raw.');fclose(fid);
case_name=getenv('CSI_CASE');if isempty(case_name);case_name='tg002_circle_c4_TM';end
summary=struct('case_name',case_name,'threads',maxNumCompThreads,'forward_grid',[N N], ...
    'inverse_grid',[166 166],'frequencies_GHz',fre,'seconds',toc(timer),'frequencies',{reports}, ...
    'source_model','unit scalar Green source; raw incident and total fields pass unchanged through ReadFreData calibration');
fid=fopen(fullfile(out,'forward_summary.json'),'w');fprintf(fid,'%s\n',jsonencode(summary,PrettyPrint=true));fclose(fid);
fprintf('Synthetic input generation complete.\n');
