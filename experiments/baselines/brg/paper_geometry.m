function src=paper_geometry(shape,n,resample)
% Geometry only: exact glider or a frozen Cartesian fit to vector paths.
if nargin<3, resample=true; end
if strcmp(shape,'glider')
    coefs=[0.9 0 0 0.18 0.018 0 0.09 0 0.09 zeros(1,8)];
    src=geometries.starn(coefs,8,n);
else
    root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
    fit=load(fullfile(root,'results','brg','paper_examples','2026-11-17','shapes',[shape '_fourier.mat']));
    t=(0:n-1)'*2*pi/n; modes=double(fit.modes(:).');
    basis=exp(1i*t*modes);
    z=basis*fit.coefficients(:); dz=basis*(1i*modes(:).*fit.coefficients(:));
    ddz=basis*(-modes(:).^2.*fit.coefficients(:));
    src=struct('xs',real(z).','ys',imag(z).','dxs',real(dz).','dys',imag(dz).', ...
        'ds',abs(dz).','H',(imag(conj(dz).*ddz)./abs(dz).^3).', ...
        'h',2*pi/n,'paramL',2*pi,'L',sum(abs(dz))*2*pi/n);
    src.Der_param=specdiffmat_ds(n,ones(n,1));
    src.Der=specdiffmat_ds(n,src.ds);
end
if resample
    [src,ier]=rla.update_geom(src,0,0);
    assert(ier==0,'Recovered true curve failed public geometry check.');
end
end
