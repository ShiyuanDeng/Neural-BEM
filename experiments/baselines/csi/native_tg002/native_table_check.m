function native_table_check(input_dir, output_dir)
[Emea,Phi,~,chi,vJ,eInc,~,pars,info] = native_configuration(input_dir);
indices = info.mask_indices;
[receiver_id,source_id] = ind2sub(size(Emea{1}),indices);
expected = info.frozen_geometry;
pair_match = isequal([source_id receiver_id], expected(:,1:2));
source_error = max(vecnorm(info.source_xy_m(source_id,:) - expected(:,3:4),2,2));
rx_error = max(vecnorm(info.receiver_xy_m(receiver_id,:) - expected(:,5:6),2,2));
roundtrip = info.native_scale * conj(Emea{1}(indices));
delta = roundtrip - info.observed_native;
relative_error = norm(delta) / norm(info.observed_native);
writematrix([source_id receiver_id real(info.observed_native) imag(info.observed_native) ...
    real(roundtrip) imag(roundtrip) abs(delta)],fullfile(output_dir,'pairs.csv'));

% Repeat only the data objective lines of the pinned CSI.m at iteration zero.
etaS = 1 / norm(Emea{1},'fro')^2;
raw_residual = Emea{1} - Phi{1} * vJ{1};
masked = zeros(size(Emea{1}));
masked(indices) = raw_residual(indices);
cost = etaS * norm(masked,'fro')^2;
pair_cost = sum(abs(raw_residual(indices)).^2) / sum(abs(Emea{1}(indices)).^2);
% CSI.m regularizes etaD with eps + (norm(chi .* incident,'fro')^2)^2.
state_denom = norm(chi{1} .* eInc{1},'fro')^4;

% Native back-propagation uses ALL receiver rows in the weight denominator.
pre_phi = Phi{1} / pars.omega{1};
back = pre_phi' * Emea{1};
forward_back = pre_phi * back;
kappa = sum(abs(back).^2,1) ./ sum(abs(forward_back).^2,1);
xbp_error = norm(pars.XBP - back .* kappa,'fro') / norm(pars.XBP,'fro');
record = struct('pair_indices_exact',pair_match,'source_position_max_error_m',source_error, ...
    'receiver_position_max_error_m',rx_error,'roundtrip_relative_error',relative_error, ...
    'mask_count',numel(indices),'nonzero_Emea',nnz(Emea{1}), ...
    'normalizer_entries',nnz(Emea{1}),'normalizer_inverse_energy',etaS, ...
    'residual_entries',nnz(masked),'start_data_cost',cost,'explicit_24_pair_cost',pair_cost, ...
    'full_backprop_rows_per_source',size(forward_back,1),'backprop_kappa',kappa, ...
    'backprop_relative_error',xbp_error,'scaled_start_etaD_eps_over_denom',eps/state_denom, ...
    'unscaled_start_etaD_eps_over_denom',eps/(state_denom*info.native_scale^4), ...
    'initial_old_gradient_norm_squared',0, 'machine_epsilon',eps);
record.passed = pair_match && isequal(indices,find(info.frozen_mask)) ...
    && max(source_error,rx_error)<1e-14 && relative_error<1e-10 && numel(indices)==24 ...
    && nnz(Emea{1})==24 && nnz(masked)==24 && abs(cost-pair_cost)<1e-12 && xbp_error<1e-12;
fid = fopen(fullfile(output_dir,'metrics.json'),'w');
fprintf(fid,'%s\n',jsonencode(record,PrettyPrint=true));
fclose(fid);
end
