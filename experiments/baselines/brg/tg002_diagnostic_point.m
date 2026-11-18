function [src_in,clearance,grid_size]=tg002_diagnostic_point(polytrue,truth_curve)
% Wrapper diagnostic source only; never an incident wave or inverse setting.
% Choose the deepest sampled interior point, retaining the 0.01 clearance test.
grid_size=201;
[xx,yy]=meshgrid(linspace(min(truth_curve.xs),max(truth_curve.xs),grid_size), ...
                 linspace(min(truth_curve.ys),max(truth_curve.ys),grid_size));
[cx,cy]=centroid(polytrue);
candidates=[xx(:) yy(:);cx cy;0 0];
inside=isinterior(polytrue,candidates(:,1),candidates(:,2));
vertices=[truth_curve.xs(:) truth_curve.ys(:)];edges=circshift(vertices,-1)-vertices;
edge_norm2=sum(edges.^2,2);
distances=zeros(size(inside));
for j=find(inside).'
    delta=candidates(j,:)-vertices;
    fraction=max(0,min(1,sum(delta.*edges,2)./edge_norm2));
    distances(j)=min(sqrt(sum((delta-fraction.*edges).^2,2)));
end
[clearance,index]=max(distances);
assert(any(inside)&&clearance>0.01, ...
    'Best interior diagnostic clearance %.17g is not above 0.01.',clearance);
src_in=candidates(index,:).';
end
