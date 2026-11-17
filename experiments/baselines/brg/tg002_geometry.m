function [src,check]=tg002_geometry(input,n,resample)
% Frozen Cartesian Fourier geometry; no solver or upstream code change.
if nargin<3, resample=true; end
fit=load(input,'coefficients','modes'); modes=double(fit.modes(:).');
t=(0:n-1)'*2*pi/n; basis=exp(1i*t*modes); c=fit.coefficients(:);
z=basis*c; dz=basis*(1i*modes(:).*c); ddz=basis*(-modes(:).^2.*c);
src=struct('xs',real(z).','ys',imag(z).','dxs',real(dz).','dys',imag(dz).', ...
 'ds',abs(dz).','H',(imag(conj(dz).*ddz)./abs(dz).^3).', ...
 'h',2*pi/n,'paramL',2*pi,'L',sum(abs(dz))*2*pi/n);
src.Der_param=specdiffmat_ds(n,ones(n,1));src.Der=specdiffmat_ds(n,src.ds);
check=struct('resampled',resample,'max_point_error',0,'relative_length_change',0);
if resample
 old_length=src.L;[src,ier,tts]=rla.update_geom(src,0,0);
 assert(ier==0,'Frozen TG-002 geometry failed public geometry check.');
 exact=exp(1i*tts(:)*modes)*c;
 check.max_point_error=max(abs(src.xs(:)+1i*src.ys(:)-exact));
 check.relative_length_change=abs(src.L-old_length)/old_length;
end
end
