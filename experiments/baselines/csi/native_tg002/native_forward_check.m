function native_forward_check(input_dir,output_dir)
truth = load(fullfile(output_dir,'reference.mat'));
cells = [0.00125 0.000625];
for i = 1:numel(cells)
    [~,~,~,~,~,~,~,~,config] = native_configuration(input_dir,cells(i));
    x_m = config.x_m;
    y_m = config.y_m;
    % As in generate_synthetic.m, sample material on dual centres and use
    % MaxwellFDFD's own four-cell average to form the primary-Ez image.
    [x,y] = ndgrid(config.grid.l{1,2}*cells(i),config.grid.l{2,2}*cells(i));
    dual = 1 + (truth.ratio-1) * (hypot(x-real(truth.center_m),y-imag(truth.center_m)) <= truth.radius_m);
    eps_cell = mean_material_node(config.grid,GT.prim,{dual,dual,dual});
    chi_image = eps_cell{3}-1;
    [predicted_native,solve_residual] = native_predict(chi_image,config);
    observed_native = config.observed_native;
    exact_native = truth.exact_native;
    tag = sprintf('%gmm',cells(i)*1000);
    save(fullfile(output_dir,['truth_' tag '.mat']), 'chi_image','predicted_native', ...
        'observed_native','exact_native','x_m','y_m','-v7');
    values = [real(observed_native),imag(observed_native),real(exact_native),imag(exact_native), ...
        real(predicted_native),imag(predicted_native),abs(predicted_native-observed_native)];
    writematrix([(1:24)' values],fullfile(output_dir,['pairs_' tag '.csv']));
    difference = predicted_native - observed_native;
    gain = (predicted_native'*observed_native)/(predicted_native'*predicted_native);
    grids(i) = struct('cell_m',cells(i),'grid_shape',size(chi_image), ...
        'relative_to_sealed',norm(difference)/norm(observed_native), ...
        'relative_to_series',norm(predicted_native-exact_native)/norm(exact_native), ...
        'sealed_vs_series',norm(observed_native-exact_native)/norm(exact_native), ...
        'solve_residual',solve_residual,'gain_diagnostic_only_real',real(gain), ...
        'gain_diagnostic_only_imag',imag(gain)); %#ok<AGROW>
    clear config
end
metrics = struct('passed',grids(1).relative_to_sealed<=0.01 && grids(1).relative_to_series<=0.01 ...
    && all([grids.solve_residual]<1e-9) && all([grids.sealed_vs_series]<1e-10), ...
    'coarse_relative_error',grids(1).relative_to_sealed,'fine_relative_error',grids(2).relative_to_sealed, ...
    'threshold',0.01,'grids',grids,'applied_gain',1,'applied_phase_rad',0, ...
    'native_units_per_csi_unit',1e-6,'reference','sealed circle and independent TM disk series');
fid = fopen(fullfile(output_dir,'metrics.json'),'w');
fprintf(fid,'%s\n',jsonencode(metrics,PrettyPrint=true));
fclose(fid);
end
