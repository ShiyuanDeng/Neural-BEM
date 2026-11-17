% Called after the unmodified driver; save without altering solver outputs.
csi_out = getenv('CSI_OUT');
csi_pars = pars;
csi_pars = rmfield(csi_pars, 'XBP'); % large initial sources saved per frequency below
csi_methods = 2 + exist('mchi3', 'var');
csi_mesh = grid3d{1}.l;
grid_x_primary_m = para.m_unit * csi_mesh{1,1}(pars.nx);
grid_y_primary_m = para.m_unit * csi_mesh{2,1}(pars.ny);
grid_x_dual_m = para.m_unit * csi_mesh{1,2}(pars.nx);
grid_y_dual_m = para.m_unit * csi_mesh{2,2}(pars.ny);
save(fullfile(csi_out, 'reconstruction.mat'), '-regexp', ...
    '^(mchi[123]|chi[123]|time[123]|xinv|yinv|fre|para|centre|xs|ys|regSize|rawdat|csi_pars|normlz_factor|grid_.*)$', '-v7');
% Compact raw contrasts suffice for later scoring. Full workspaces stay local.
save(fullfile(csi_out, 'final_contrast.mat'), '-regexp', ...
    '^(chi[123]|xinv|yinv|fre|para|centre|xs|ys|csi_pars|normlz_factor|grid_.*)$', '-v7');
for csi_f = 1:numel(fre)
    evidence = struct('Emea', Emea{csi_f}, 'Einc', Einc{csi_f}, ...
        'chi_initial', chiinv{csi_f}, ...
        'vJ_initial', vJ{csi_f}, 'eTot_initial', eTotInv{csi_f});
    for csi_method = 1:csi_methods
        evidence.(['vJ' num2str(csi_method)]) = eval(sprintf('vJ%d{csi_f}', csi_method));
        evidence.(['eTot' num2str(csi_method)]) = eval(sprintf('eTot%d{csi_f}', csi_method));
    end
    save(fullfile(csi_out, sprintf('frequency_%gGHz.mat', fre(csi_f))), ...
        '-struct', 'evidence', '-v7');
end
csi_figs = findall(groot, 'Type', 'figure');
for csi_i = 1:numel(csi_figs)
    csi_name = sprintf('%s_figure_%02d', getenv('CSI_STEP'), csi_figs(csi_i).Number);
    savefig(csi_figs(csi_i), fullfile(csi_out, [csi_name '.fig']));
    exportgraphics(csi_figs(csi_i), fullfile(getenv('CSI_FIGURES'), [csi_name '.png']), 'Resolution', 140);
end
csi_times = [time1 time2];
if csi_methods == 3; csi_times(3) = time3; end
summary = struct('case_name', str, 'matlab', version, 'threads', maxNumCompThreads, ...
    'completed_posix_seconds', posixtime(datetime('now', 'TimeZone', 'UTC')), ...
    'frequencies_GHz', fre, 'Ninv', pars.Ninv, 'iterations', pars.itenum, ...
    'source_count', para.NTX, 'time_seconds', csi_times, ...
    'cell_size_m', para.m_unit, 'source_radius_m', para.Tr, 'receiver_radius_m', para.Rr);
fid = fopen(fullfile(csi_out, 'matlab_summary.json'), 'w');
fprintf(fid, '%s\n', jsonencode(summary, PrettyPrint=true));
fclose(fid);
fprintf('CSI wrapper: outputs saved; compute threads %d\n', maxNumCompThreads);
