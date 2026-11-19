function [Emea,Phi,A,chi,vJ,eInc,eTot,pars,info] = native_ring_tm(table, cell_m, radius, source_count)
% Owned TM-only version of ReadFreData, Pre_InvFresnel_Conf and the final
% frequency scaling in Inv_Fresnel_I. Input rows are blocked by source.
upstream = fullfile(getenv('HOME'), 'neural_bem_external', 'CC-CSI');
original_dir = pwd;
restore_dir = onCleanup(@() cd(original_dir));
cd(upstream);
add_path;
assert(strcmp(which('CSI'), fullfile(upstream, 'functions', 'CSI.m')));
freq = table(1,3);
assert(all(table(:,3) == freq));
half = round(0.10375/cell_m);
wavelength_cells = PhysC.c0 / (freq*1e9) / cell_m;
[osc,grid,~,matrix,~] = FDFDpars('OSC',cell_m,wavelength_cells, ...
    'DOM',{'vacuum','none',1},[-half half; -half half; 0 1],1,BC.p,[5 5 0], ...
    'SRCJ',PointSrc(Axis.z,[0 0 .5]),struct('returnAandb',true),PT.TM);
omega = osc.in_omega0();
A = {matrix / omega / omega};
pars.Ninv = grid.N;
assert(isequal(grid.N, [2*half 2*half 1]));
[x,y] = ndgrid(grid.l{1,1},grid.l{2,1});
x = x(:); y = y(:);
nr = size(table,1)/source_count;
source_angles = reshape(table(:,1),nr,source_count);
assert(all(source_angles == source_angles(1,:), 'all'));
receiver_angles = unique(table(:,2));
receiver_angles = receiver_angles(:); % including the one-reading-per-source case
[~,row] = ismember(table(:,2),receiver_angles);
source = repelem((1:source_count)',nr);
mask_indices = sub2ind([numel(receiver_angles),source_count],row,source);
assert(numel(unique(mask_indices)) == numel(mask_indices));

t = deg2rad(source_angles(1,:));
r = deg2rad(receiver_angles);
tx = radius*cos(t); ty = radius*sin(t);
rx = radius*cos(r); ry = radius*sin(r);
d = sqrt((rx/cell_m - x.').^2 + (ry/cell_m - y.').^2);
% Preserve the native TM normalization used before back-propagation.
pre_phi = (omega/4 * besselh(0,1,-omega*d) * omega^2 / (-1j*omega)) / omega;
inc = complex(table(:,6),table(:,7));
total = complex(table(:,4),table(:,5));
Emea = {zeros(numel(r),source_count)};
Emea{1}(mask_indices) = total-inc;
incident = zeros(numel(x),source_count);
k = omega/cell_m;
calibration_index = floor(nr/2)+1;
for s = 1:source_count
    idx = (s-1)*nr + calibration_index;
    distance = sqrt((x*cell_m - tx(s)).^2 + (y*cell_m - ty(s)).^2);
    reference_distance = sqrt((rx(row(idx))-tx(s))^2 + (ry(row(idx))-ty(s))^2);
    field = omega/4 * besselh(0,1,-k*distance) * omega^2 / (-1j*omega);
    reference = omega/4 * besselh(0,1,-k*reference_distance) * omega^2 / (-1j*omega);
    incident(:,s) = (inc(idx)/reference) * field;
end
eInc = {incident};

% Same five-cell border and full-receiver back-propagation as upstream.
border = true(grid.N(1:2));
border(6:end-5,6:end-5) = false;
pars.rd = find(border);
pars.rchi = pars.rd;
back = pre_phi' * Emea{1};
propagated = pre_phi * back;
weights = sum(abs(back).^2,1) ./ sum(abs(propagated).^2,1);
pars.XBP = back * diag(weights);
vJ = {pars.XBP / omega};
vJ{1}(pars.rd,:) = 0;
eTot = {incident + (A{1} \ vJ{1})};
pars.omega = {omega};
chi = {OrthgPro(get_chiMF(vJ,eTot,grid.N,source_count,pars.omega,PT.TM),1)};
chi{1}(pars.rchi) = 0;
Phi = {pre_phi * omega};
pars.rmea = {mask_indices};
pars.ptype = PT.TM;
pars.Nsrc = source_count;
pars.bgchi = 1;
pars.disflag = false;
pars.recflag = false;
pars.terflag = false;
pars.itenum = 2048;
info.x_m = grid.l{1,1}(:)*cell_m;
info.y_m = grid.l{2,1}(:)*cell_m;
info.cell_m = cell_m;
info.mask_indices = mask_indices;
info.source_xy_m = [tx(:) ty(:)];
info.receiver_xy_m = [rx(:) ry(:)];
info.A = A{1};
info.Phi = Phi{1};
info.incident = incident;
info.grid = grid;
end
