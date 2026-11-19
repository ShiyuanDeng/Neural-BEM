function native_equivalence_check(input_dir, output_dir)
% Deterministic two-receiver fixture, used only to exercise the upstream reader.
rows = readmatrix(fullfile(input_dir,'table.csv'));
metadata = jsondecode(fileread(fullfile(input_dir,'inputs.json')));
second = rows([2:end 1],:);
second(:,1) = rows(:,1);
radius = metadata.ring_radius_m;
distance = radius * hypot(cosd(second(:,1))-cosd(second(:,2)), ...
    sind(second(:,1))-sind(second(:,2)));
inc = conj(0.25j*besselh(0,1,metadata.k_background_per_m*distance));
total = inc + 0.5*complex(rows(:,4)-rows(:,6),rows(:,5)-rows(:,7));
second(:,4:7) = [real(total) imag(total) real(inc) imag(inc)];
table = repelem(rows,2,1);
table(2:2:end,:) = second;
writematrix(table,fullfile(output_dir,'equivalence_table.csv'));

[E,P,A,chi,vJ,incident,eTot,p,info] = native_ring_tm(table,0.00125,radius,24);
upstream = fullfile(getenv('HOME'),'neural_bem_external','CC-CSI');
original_dir = pwd;
restore_dir = onCleanup(@() cd(original_dir));
cd(upstream);
assert(~exist(['Phi' num2str(table(1,3)) 'GHz.mat'],'file'));
para = struct('pt',PT.TM,'NTX',24,'Tr',radius,'Rr',radius,'m_unit',0.00125);
[Eu,~,Pu,Au,cu,ju,iu,tu,grid,pu] = Pre_InvFresnel_Conf(table,table(1,3), ...
    [-1.2 1.2;-1.2 1.2],[0 0 0],103.75,103.75,para);
Pu{1} = Pu{1} * pu.omega{1};
rel = @(a,b) norm(a-b,'fro') / norm(b,'fro');
errors = struct('Phi',rel(P{1},Pu{1}),'A',rel(A{1},Au{1}),'incident',rel(incident{1},iu{1}), ...
    'vJ',rel(vJ{1},ju{1}),'chi',rel(chi{1},cu{1}),'Emea',rel(E{1},Eu{1}), ...
    'eTot',rel(eTot{1},tu{1}),'XBP',rel(p.XBP,pu.XBP));
gx = reshape(grid{1}.l{1,1}(pu.nx),[],1)*para.m_unit;
gy = reshape(grid{1}.l{2,1}(pu.ny),[],1)*para.m_unit;
errors.x_m = rel(info.x_m,gx);
errors.y_m = rel(info.y_m,gy);
mask_exact = isequal(p.rmea,pu.rmea) && isequal(p.rd,pu.rd) && isequal(p.rchi,pu.rchi);
threshold = 1e-12;
passed = mask_exact && all(structfun(@(v) isfinite(v) && v<=threshold,errors));
metrics = struct('passed',passed,'relative_tolerance',threshold,'relative_errors',errors, ...
    'mask_exact',mask_exact,'receiver_rows',numel(pu.Runiq),'pairs',numel(pu.rmea{1}), ...
    'upstream_reference','ReadFreData and Pre_InvFresnel_Conf; final Inv_Fresnel_I Phi scaling');
fid = fopen(fullfile(output_dir,'metrics.json'),'w');
fprintf(fid,'%s\n',jsonencode(metrics,PrettyPrint=true));
fclose(fid);
end
