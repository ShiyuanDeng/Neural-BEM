// Isolated Algoim surface quadrature for analytic ellipses and exported SIRENs.
#include <cmath>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include "algoim/quadrature_general.hpp"

struct Layer { int inputs, outputs; double omega; std::vector<double> weights, bias; };
struct Field {
    bool neural = false;
    double ax = .05, ay = .035, ox = .5, oy = .5, scale = .2;
    std::vector<Layer> layers;

    template<class T> T operator()(const algoim::uvector<T,2>& x) const {
        using std::sin;
        if (!neural) return ((x(0)-ox)/ax)*((x(0)-ox)/ax) + ((x(1)-oy)/ay)*((x(1)-oy)/ay) - 1.;
        std::vector<T> values{(x(0)-ox)/scale, (x(1)-oy)/scale};
        for (const auto& l: layers) {
            std::vector<T> next(l.outputs);
            for (int j=0; j<l.outputs; ++j) {
                T z(l.bias[j]);
                for (int i=0;i<l.inputs;++i) z += l.weights[j*l.inputs+i]*values[i];
                next[j] = l.omega ? sin(l.omega*z) : z;
            }
            values=std::move(next);
        }
        return scale*values[0];
    }
    template<class T> algoim::uvector<T,2> grad(const algoim::uvector<T,2>& x) const {
        using std::sin; using std::cos;
        if (!neural) return algoim::uvector<T,2>(2.*(x(0)-ox)/(ax*ax), 2.*(x(1)-oy)/(ay*ay));
        std::vector<T> values{(x(0)-ox)/scale, (x(1)-oy)/scale};
        std::vector<T> dx{T(1./scale),T(0.)},dy{T(0.),T(1./scale)};
        for (const auto& l: layers) {
            std::vector<T> next(l.outputs),nx(l.outputs),ny(l.outputs);
            for (int j=0;j<l.outputs;++j) {
                T z(l.bias[j]), zx(0.),zy(0.);
                for (int i=0;i<l.inputs;++i) {
                    const double w=l.weights[j*l.inputs+i]; z+=w*values[i]; zx+=w*dx[i]; zy+=w*dy[i];
                }
                const T multiplier = l.omega ? l.omega*cos(l.omega*z) : T(1.);
                next[j]=l.omega?sin(l.omega*z):z; nx[j]=multiplier*zx;ny[j]=multiplier*zy;
            }
            values=std::move(next);dx=std::move(nx);dy=std::move(ny);
        }
        return algoim::uvector<T,2>(scale*dx[0],scale*dy[0]);
    }
};

int main(int argc,char**argv) {
    if (argc!=8) {std::cerr<<"field_file_or_ellipse cells order delta parameter output lower_upper_margin\n";return 2;}
    Field phi;
    std::string name=argv[1]; const int cells=std::stoi(argv[2]),order=std::stoi(argv[3]);
    const double delta=std::stod(argv[4]); const int parameter=std::stoi(argv[5]);
    const double extent=std::stod(argv[7]);
    if(cells<1 || order<1 || order>10 || extent<=0) return 2;
    if(name!="ellipse") {
        phi.neural=true;std::ifstream in(name);int count;
        in>>phi.ox>>phi.oy>>phi.scale>>count;
        if(!in || count<1) return 3;
        for(int k=0;k<count;++k) {
            Layer l;in>>l.inputs>>l.outputs>>l.omega;
            l.weights.resize(l.inputs*l.outputs);l.bias.resize(l.outputs);
            for(double&v:l.weights)in>>v;for(double&v:l.bias)in>>v;
            if(!in)return 3;phi.layers.push_back(std::move(l));
        }
        if(parameter<0)phi.layers.back().bias[0]+=delta;
        else phi.layers.back().weights.at(parameter)+=delta;
    } else phi.ax+=delta;
    std::ofstream out(argv[6]);out<<std::setprecision(17);
    double sum=0.;size_t count=0;
    for(int i=0;i<cells;++i)for(int j=0;j<cells;++j) {
        const double h=2*extent/cells;
        algoim::uvector<double,2> lo{phi.ox-extent+i*h,phi.oy-extent+j*h};
        algoim::uvector<double,2> hi{lo(0)+h,lo(1)+h};
        auto q=algoim::quadGen<2>(phi,algoim::HyperRectangle<double,2>(lo,hi),2,-1,order);
        for(const auto& n:q.nodes){out<<n.x(0)<<' '<<n.x(1)<<' '<<n.w<<'\n';sum+=n.w;++count;}
    }
    std::cout<<std::setprecision(17)<<sum<<' '<<count<<'\n';
}
