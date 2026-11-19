function [predicted, solve_residual] = native_predict(chi_image, config)
% Predict from the final complex primary-node susceptibility in CSI units.
n = numel(config.x_m);
assert(isequal(size(chi_image),[n n]) || (isvector(chi_image) && numel(chi_image)==n*n));
chi = chi_image(:);
system = config.A - spdiags(chi, 0, numel(chi), numel(chi));
rhs = chi .* config.incident;
scattered = system \ rhs;
if nargout > 1
    solve_residual = norm(system*scattered - rhs,'fro') / max(norm(rhs,'fro'),realmin);
end
currents = chi .* (config.incident + scattered);
readings = config.Phi * currents;
predicted = config.native_scale * conj(readings(config.mask_indices));
end
