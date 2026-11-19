function [Emea,Phi,A,chi,vJ,eIncInv,eTot,pars,info] = native_configuration(input_dir, cell_m)
% Make the single-frequency CSI inputs for the native ring. Only the
% forward refinement check supplies a cell size other than the inverse one.
if nargin < 2, cell_m = 0.00125; end
assert(ismember(cell_m, [0.00125 0.000625]));
metadata = jsondecode(fileread(fullfile(input_dir, 'inputs.json')));
table = readmatrix(fullfile(input_dir, 'table.csv'));
readings = readmatrix(fullfile(input_dir, 'readings.csv'));
geometry = readmatrix(fullfile(input_dir, 'geometry.csv'));
mask = logical(readmatrix(fullfile(input_dir, 'mask.csv')));
assert(isequal(size(table), [24,7]) && isequal(size(mask), [24,24]));
assert(all(table(:,3) == table(1,3)));
freq = table(1,3);
cell_count = round(0.2075 / cell_m);

% Use the shipped single-frequency reader and back-propagation unmodified.
% It accepts physical angles in degrees and infers one reading per source.
upstream = fullfile(getenv('HOME'), 'neural_bem_external', 'CC-CSI');
original_dir = pwd;
restore_dir = onCleanup(@() cd(original_dir));
cd(upstream);
add_path;
assert(strcmp(which('CSI'), fullfile(upstream, 'functions', 'CSI.m')));
assert(~exist(['Phi' num2str(freq) 'GHz.mat'], 'file'), 'Unexpected upstream operator cache');
para = struct('pt',PT.TM,'NTX',24,'Tr',metadata.ring_radius_m, ...
    'Rr',metadata.ring_radius_m,'m_unit',cell_m);
[Emea,~,Phi,A,chi,vJ,eIncInv,eTot,grids,pars] = Pre_InvFresnel_Conf( ...
    table, freq, [-1.2 1.2; -1.2 1.2], [0 0 0], 103.75, 103.75, para);
% Inv_Fresnel_I applies this final factor AFTER native back-propagation.
Phi{1} = Phi{1} * pars.omega{1};
pars.bgchi = 1;
pars.disflag = false;
pars.recflag = false;
pars.terflag = false;
pars.itenum = 2048;
assert(isequal(pars.Ninv, [cell_count cell_count 1]));
assert(abs(pars.omega{1}/cell_m - metadata.k_background_per_m) < 1e-12);
grid = grids{1};
info.x_m = reshape(grid.l{1,1}(pars.nx) * cell_m, [], 1);
info.y_m = reshape(grid.l{2,1}(pars.ny) * cell_m, [], 1);
info.cell_m = cell_m;
info.mask_indices = pars.rmea{1}(:);
info.frozen_mask = mask;
info.source_xy_m = para.Tr * [cosd(table(:,1)) sind(table(:,1))];
info.receiver_xy_m = para.Rr * [cosd(pars.Runiq) sind(pars.Runiq)];
info.frozen_geometry = geometry;
info.native_scale = metadata.native_units_per_csi_unit;
info.conjugate_to_native = true;
info.observed_native = complex(readings(:,2), readings(:,3));
info.A = A{1};
info.Phi = Phi{1};
info.incident = eIncInv{1};
end
