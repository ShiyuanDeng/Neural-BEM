function [Emea,Phi,A,chi,vJ,eIncInv,eTot,pars,info] = native_configuration(input_dir, cell_m)
% The finer grid is used only by the circle forward check.
if nargin < 2, cell_m = 0.00125; end
assert(ismember(cell_m,[0.00125 0.000625]));
metadata = jsondecode(fileread(fullfile(input_dir,'inputs.json')));
table = readmatrix(fullfile(input_dir,'table.csv'));
assert(isequal(size(table),[24 7]));
[Emea,Phi,A,chi,vJ,eIncInv,eTot,pars,info] = native_ring_tm(table,cell_m,metadata.ring_radius_m,24);
assert(abs(pars.omega{1}/cell_m - metadata.k_background_per_m) < 1e-12);
readings = readmatrix(fullfile(input_dir,'readings.csv'));
info.frozen_mask = logical(readmatrix(fullfile(input_dir,'mask.csv')));
info.frozen_geometry = readmatrix(fullfile(input_dir,'geometry.csv'));
info.native_scale = metadata.native_units_per_csi_unit;
info.conjugate_to_native = true;
info.observed_native = complex(readings(:,2), readings(:,3));
end
