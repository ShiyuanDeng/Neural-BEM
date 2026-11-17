% Explicit old-query-grid check; no inversion, no upstream changes.
maxNumCompThreads(8);
rng(17);
checks = struct([]);
for N = [17 112]
    for complex_case = [false true]
        V = rand(N);
        if complex_case; V = V + 1j*rand(N); end
        Vq = interp2(V, 1);
        X = rand(size(Vq));
        if complex_case; X = X + 1j*rand(size(X)); end
        for refined_case = [false true]
            if refined_case; X = Vq; end
            % The old negative-refinement rule explicitly queries grid nodes.
            old = interp2(X, 1:2:size(X,2), (1:2:size(X,1))', 'linear');
            sampled = X(1:2:end, 1:2:end);
            difference = max(abs(old(:)-sampled(:)));
            bound = 64*eps*max(1,max(abs(sampled(:))));
            assert(difference <= bound);
            checks(end+1) = struct('N',N,'complex',complex_case, ...
                'refined_original',refined_case,'max_abs_difference',difference, ...
                'rounding_bound',bound,'isequal',isequal(old,sampled));
        end
    end
end
record = struct('checks',checks,'threads',maxNumCompThreads,'matlab',version);
fid = fopen(fullfile(getenv('CSI_CHECK_OUT'),'explicit_interpolation.json'),'w');
fprintf(fid,'%s\n',jsonencode(record,PrettyPrint=true));
fclose(fid);
fprintf('Explicit interpolation versus node sampling: %d checks passed.\n',numel(checks));
