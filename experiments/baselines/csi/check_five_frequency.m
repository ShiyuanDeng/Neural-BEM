% Small native-array checks only. No FDFD solve, data generation or fit.
maxNumCompThreads(1);
repo=getenv('CSI_REPO');up=getenv('CSI_UPSTREAM');out=getenv('CSI_OUT');
addpath(fullfile(up,'functions'));addpath(genpath(fullfile(up,'MaxwellFDFD')));
% Use the native path setup for PT and PhysC, without executing any driver.
old=pwd;cd(up);add_path;cd(old);
frequencies=[0.5 1 1.5 2 2.5];Nfre=length(frequencies);assert(Nfre==5);
reader=fileread(fullfile(up,'functions','ReadFreData.m'));
config=fileread(fullfile(up,'functions','Pre_InvFresnel_Conf.m'));
solver=fileread(fullfile(up,'functions','CC_CSI_Brent.m'));
driver=fileread(fullfile(up,'Inv_Fresnel_I.m'));
% Execute the unmodified reader prefix through angle conversion. It includes
% native equality row selection, complex subtraction and TM reshaping.
a=strfind(reader,'pars_LSM        = [];');b=strfind(reader,'%% Create Ms and A');
prefix=reader(a(1):b(1)-1);
para=struct('m_unit',1.25e-3,'NTX',36,'pt',PT.TM,'Tr',.72,'Rr',.76,'showconfg',false);
fixture=zeros(8820,7);
for pair=1:1764
    rows=(pair-1)*5+(1:5);fixture(rows,1)=10*floor((pair-1)/49)-2.5;
    fixture(rows,2)=5*mod(pair-1,49);fixture(rows,3)=frequencies;
    fixture(rows,4)=pair+frequencies;fixture(rows,5)=-frequencies;
    fixture(rows,6)=pair;fixture(rows,7)=0;
end
for fi=1:Nfre
    fre=frequencies(fi);rawdat=fixture;eval(prefix);
    assert(isequal(size(dat),[49 36]));
    assert(max(abs(dat(:)-(fre-1j*fre)))<1e-12);
    assert(isequal(size(Finc),[49 36]));
end
% Native array allocation uses length(fre), not the last frequency value.
a=strfind(config,'Nfre            = length(fre);');b=strfind(config,'para.disflag    = false;');
fre=frequencies;eval(config(a(1):b(1)-1));
blocks={A,dat,Emea,Einc,err,grid3d,omega,Phi,rmea,XBP,pars_LSM};
assert(all(cellfun(@numel,blocks)==5));
% Execute the exact native initial-field loop with tiny sentinel operators.
NTX=36;pars=struct('rd',[]);XBP=repmat(1:180,2,1);
omega=num2cell(2*pi*frequencies);A=repmat({eye(2)},1,5);Einc=repmat({ones(2,36)},1,5);
a=strfind(config,'vJ          ');b=strfind(config,'chiinv{1}');
assert(~isempty(a));eval(config(a(1):b(1)-1));
for fi=1:5
    block=(fi-1)*36+(1:36);
    assert(isequal(vJ{fi},XBP(:,block)/omega{fi}));
    assert(isequal(eTotInv{fi},Einc{fi}+vJ{fi}));
end
% Execute native first-frequency scaling, without its inverse solve.
chiinv{1}=[2-3j;4-5j];
a=strfind(config,'chiinv          = cellfun');b=strfind(config,'pars.rmea');
eval(config(a(1):b(1)-1));
for fi=1:5
    expected=[2;4]+1j*[-3;-5]*.5/frequencies(fi);
    assert(max(abs(chiinv{fi}-expected))<1e-12);
end
% Exercise the actual native TM multifrequency contrast initializer.
ref=[2-3j;4-5j];v2=repmat({ones(2,36)},1,5);
v1=cellfun(@(w) repmat(real(ref)+1j*imag(ref)*omega{1}/w,1,36),omega,'UniformOutput',false);
initialized=get_chiMF(v1,v2,[2 1 1],36,omega,PT.TM);
assert(max(abs(initialized-ref))<1e-12);
assert(contains(solver,'Nfre        = length(eIncInv);'));
assert(contains(solver,'omega{1} / x * imag(vnuChiCom)'));
assert(contains(solver,'Mchi{end}'));
assert(contains(solver,'mchi{end}'));
assert(contains(driver,'rf                  = 1 : length(fre);'));
metadata=fileread(fullfile(repo,'experiments/baselines/csi/init_campaign_record.m'));
assert(contains(metadata,'reference_frequency_GHz=fre(end)'));
assert(frequencies(end)==2.5);
result=struct('passed',true,'inversion_run',false,'forward_run',false, ...
    'frequencies_GHz',frequencies,'frequency_count',5,'selected_rows_per_frequency',1764, ...
    'initial_field_blocks',5,'sources_per_block',36,'conductivity_reference_GHz',.5, ...
    'image_reference_GHz',2.5,'numerical_upstream_edits',false,'matlab',version);
fid=fopen(fullfile(out,'native_check.json'),'w');fprintf(fid,'%s\n',jsonencode(result,PrettyPrint=true));fclose(fid);
fprintf('Half-integer native checks passed; no forward or inverse solve ran.\n');
