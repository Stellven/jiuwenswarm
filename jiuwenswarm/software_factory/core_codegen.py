"""Discover, structurally lower and assemble real STRATA production kernels.

Arithmetic is supplied by cuda_lowering's source-bound functions. CodeGen only
assembles those produced functions, execution contracts, CLI and isolated tests.
The cooperative CUDA runtime is an explicit CPU reference target, not native NPU
validation or complete language-model inference.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from .cuda_lowering import (CPU_RUNTIME, balanced, discover_operations, lower_operation,
                            sha256 as _hash, strip_comments)


CATEGORY_ALIASES = {'router':'routing','swiglu':'activation','moe_combine':'aggregation','rms_norm':'normalization'}


def _choose(discovery, demand):
    candidates=[item for item in discovery if item['supported'] and
                demand in {item['id'],item['name'],item['operation'],item['category']}]
    if not candidates:
        rejected=[item for item in discovery if demand in {item['id'],item['name']}]
        if rejected:raise ValueError(rejected[0].get('reason','Unsupported source operation'))
        raise ValueError('No executable discovered capability matches demand: '+str(demand))
    # Prefer a direct source kernel with fewer unsupported dependencies and explicit
    # source precision; no source file or function-name whitelist is involved.
    candidates.sort(key=lambda item:(-int('double' in strip_comments(item['body'])), len(item['body']),item['id']))
    return candidates[0]


def _reference(repository):
    """Optional independent upstream host reference, used in tests only."""
    for path in sorted((repository/'src').rglob('*parity.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        match=re.search(r'void\s+reference\s*\([^)]*const float\*[^)]*int\*[^)]*float\*[^)]*\)\s*\{',text,re.S)
        if match and 'RENORM_CLAMP' in text and 'stable_sort' in text:
            opening=text.index('{',match.start());closing=balanced(text,opening)
            clamp=re.search(r'constexpr double RENORM_CLAMP\s*=\s*([0-9.eE+-]+)',text)
            if clamp:
                source=text[match.start():closing+1]
                return {'path':path.relative_to(repository).as_posix(),'source_path':str(path),'source_sha256':_hash(path.read_bytes()),
                    'function':'reference','source_code':source,'function_sha256':_hash(source),'clamp':clamp[1]}
    return None


def _inventory(repository, records, discovery, demands):
    kernels={}
    for record in records:
        key=record['operation']
        if key in kernels:key=record['name']
        if key in kernels:key=record['id']
        kernels[key]=record
    selected=list(kernels)
    operations={record['operation'] for record in records}
    if operations=={'router','swiglu','moe_combine'}:mode='combined'
    elif len(records)==1:mode=records[0]['operation']
    else:mode='operations'
    formats={'combined':'whitespace: N K D; N logits; N*D gate; N*D up; D shared',
             'router':'whitespace: N K; N logits',
             'swiglu':'whitespace: N; N gate; N up',
             'moe_combine':'whitespace: K D; K weights; K*D parts; D shared',
             'rms_norm':'whitespace: rows cols epsilon; rows*cols values; cols weights',
             'elementwise':'whitespace: N; scalar float parameters in signature order; N values for each pointer in signature order',
             'operations':'use --operation <discovered function name>; each capability declares its own tensor contract'}
    return {'schema':'strata.core.ir.v1','source_dir':str(repository),
        'commit_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip(),
        'selected':selected,'kernels':kernels,'reference':_reference(repository),'demands':list(demands),
        'discovery':[{key:value for key,value in item.items() if key not in {'body','source_code','parameters_text','constants'}} for item in discovery],
        'cli':{'mode':mode,'format':formats[mode],'argv':['strata_engine','--input','PATH'],
               'operations':[{'source_id':r['id'],'name':r['name'],'operation':r['operation'],'category':r['category'],'format':formats[r['operation']]} for r in records]},
        'scope':'Source-lowered production computational kernels; CPU cooperative CUDA reference execution. No model loader or full token-generation claim',
        'native_device_validated':False,'full_inference_validated':False}


def extract_core(repository, output_dir, selected=None, demands=None):
    repository=Path(repository).resolve(strict=True);output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    discovery=discover_operations(repository)
    # A caller may supply task-derived capability demands or exact discovered IDs.
    # The compatibility default expresses a task goal in capability categories;
    # its producers are selected from live discovery, never fixed source names.
    requested=list(selected if selected is not None else demands if demands is not None else ['routing','activation','aggregation'])
    if not requested:raise ValueError('At least one executable operation demand is required')
    chosen=[]
    for demand in requested:
        descriptor=_choose(discovery,demand)
        if descriptor['id'] not in {item['id'] for item in chosen}:chosen.append(descriptor)
    records=[lower_operation(repository,item) for item in chosen]
    inventory=_inventory(repository,records,discovery,requested)
    for key,record in inventory['kernels'].items():
        (output_dir/(re.sub(r'[^\w.-]','_',key)+'.cu.txt')).write_text(record['source_code']+'\n')
    (output_dir/'core_ir.json').write_text(json.dumps(inventory,indent=2)+'\n')
    return inventory


def merge_core(inventories):
    if not inventories:raise ValueError('No lowered operation inventories supplied')
    first=inventories[0];repository=Path(first['source_dir']).resolve(strict=True)
    records=[];demands=[]
    for inventory in inventories:
        validate_core(inventory)
        if inventory['source_dir']!=first['source_dir'] or inventory['commit_sha']!=first['commit_sha']:
            raise ValueError('Cannot compose operations from different source revisions')
        for item in inventory['kernels'].values():
            if item['id'] not in {record['id'] for record in records}:records.append(item)
        demands+=inventory.get('demands',[])
    return _inventory(repository,records,discover_operations(repository),demands)


def validate_core(inventory):
    if inventory.get('schema')!='strata.core.ir.v1' or not inventory.get('kernels'):raise ValueError('Invalid core IR')
    repository=Path(inventory['source_dir']).resolve(strict=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip()
    if inventory.get('commit_sha')!=commit:raise ValueError('Repository commit changed after extraction')
    if list(inventory['kernels'])!=inventory.get('selected'):raise ValueError('Selected operation records disagree')
    for record in inventory['kernels'].values():
        actual=lower_operation(repository,record)
        for key in ['id','path','name','function','source_path','source_sha256','function_sha256','source_code','body','line','end_line','signature','parameters_text','parameters','params','tensor_extents','constants','operation','category','features','lowering_kind','supported','build_guards','semantic_ir']:
            if actual[key]!=record[key]:raise ValueError('Actual source/slice changed: '+key)
    if inventory.get('reference')!=_reference(repository):raise ValueError('Actual upstream reference source changed')
    return {'valid':True,'selected':inventory['selected'],'source_functions':len(inventory['kernels'])}


def _invocation(record,args,blocks):
    symbol=record['semantic_ir']['symbol']
    params=record['parameters'];bound=[]
    substitution={p['name']:arg for p,arg in zip(params,args)}
    for p,arg in zip(params,args):
        if p['pointer']:
            extent=record['tensor_extents'][p['name']]
            extent=re.sub(r'\b[A-Za-z_]\w*\b',lambda m:'('+substitution[m[0]]+')' if m[0] in substitution else m[0],extent)
            bound.append('cuda_cpu::view('+arg+',size_t('+extent+'))')
        else:bound.append(arg)
    return 'cuda_cpu::launch('+blocks+', [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return '+symbol+'('+', '.join(bound)+',block,thread);});'


def _bindings_body(record):
    """Generate tensor-contract launch bindings; these contain no kernel math."""
    op=record['operation'];p=record['parameters'];name=record['semantic_ir']['symbol']
    if op=='router':
        return '''Routing route(const std::vector<float>& logits,int k) {
 const int n=int(logits.size());if(n<1||n>512||k<1||k>n)throw std::invalid_argument("invalid routing shape");
 for(float v:logits)if(!std::isfinite(v))throw std::invalid_argument("non-finite router input");
 Routing result;result.ids.resize(k);result.weights.resize(k);
 '''+_invocation(record,['logits.data()','1','n','k','result.ids.data()','result.weights.data()'],'1')+'''
 for(int id:result.ids)if(id<0||id>=n)throw std::runtime_error("source kernel produced invalid expert index");
 for(float value:result.weights)if(!std::isfinite(value))throw std::runtime_error("source kernel produced non-finite weight");
 return result;
}
'''
    if op=='swiglu':
        return '''void swiglu(const float* gate,const float* up,float* output,int n) {
 if(!gate||!up||!output||n<1)throw std::invalid_argument("invalid activation shape");
 '''+_invocation(record,['gate','up','output','n'],'unsigned((n+31)/32)')+'\n}\n'
    if op=='moe_combine':
        return '''void moe_combine(const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared) {
 if(!parts||!weights||!output||d<1||k<1||(has_shared&&!shared))throw std::invalid_argument("invalid aggregation shape");
 '''+_invocation(record,['parts','weights','shared','output','d','k','has_shared'],'unsigned((d+31)/32)')+'\n}\n'
    if op=='rms_norm':
        return '''void rms_norm(float* values,const float* weights,int64_t rows,int64_t cols,float epsilon) {
 if(!values||rows<1||cols<1||rows>1000000||cols>65536||!std::isfinite(epsilon)||epsilon<0)throw std::invalid_argument("invalid normalization contract");
 '''+_invocation(record,['values','weights','rows','cols','epsilon'],'unsigned(rows)')+'\n}\n'
    # Any supported scalar kernel is bound by its discovered pointer/scalar
    # signature. New arithmetic and names require no generator change.
    signature=', '.join(item['type']+' '+item['name'] for item in p)
    dimension=next(item['name'] for item in p if not item['pointer'] and item['base'] not in {'float','double'})
    args=[item['name'] for item in p]
    return 'void '+record['name']+'('+signature+') {\n if('+dimension+'<1||'+dimension+'>16777216)throw std::invalid_argument("invalid elementwise extent");\n '+_invocation(record,args,'unsigned(('+dimension+'+31)/32)')+'\n}\n'


def _binding_name(record):
    return 'invoke_'+_hash(record['id'])[:16]


def _bindings(record, independent=False):
    body=_bindings_body(record)
    if independent:
        name={'router':'route','swiglu':'swiglu','moe_combine':'moe_combine','rms_norm':'rms_norm'}.get(record['operation'],record['name'])
        body=body.replace(name+'(',_binding_name(record)+'(',1)
    return body


def _source(inventory):
    source='#include "strata_core.h"\n#include "cuda_cpu_runtime.h"\n#include <cmath>\n#include <stdexcept>\nusing std::exp;using std::expf;using std::fmax;using std::fmaxf;using std::fmin;using std::fminf;\n'
    for record in inventory['kernels'].values():source+=record['semantic_ir']['lowered_cpp']+'\n'
    source+='namespace strata_core {\n'
    emitted=set()
    for record in inventory['kernels'].values():
        source+=_bindings(record, independent=True)
        # Stable convenience APIs expose one selected producer per operation.
        # Each selected producer also has its own callable API and CLI dispatch.
        alias=('elementwise',record['name']) if record['operation']=='elementwise' else record['operation']
        if alias not in emitted:
            source+=_bindings(record);emitted.add(alias)
    source+='const char* backend(){return "CPU";}\n}\n'
    return source


def _header(inventory):
    declarations={'router':'Routing route(const std::vector<float>&,int);',
      'swiglu':'void swiglu(const float*,const float*,float*,int);',
      'moe_combine':'void moe_combine(const float*,const float*,const float*,float*,int,int,int);',
      'rms_norm':'void rms_norm(float*,const float*,int64_t,int64_t,float);'}
    result='#pragma once\n#include <vector>\n#include <cstdint>\n#include <cstddef>\nnamespace strata_core {\nstruct Routing{std::vector<int> ids;std::vector<float> weights;};\n'
    seen=set()
    for record in inventory['kernels'].values():
        op=record['operation']
        if op=='elementwise':
            result+='void '+_binding_name(record)+'('+', '.join(p['type']+' '+p['name'] for p in record['parameters'])+');\n'
        else:result+=declarations[op].replace({'router':'route','swiglu':'swiglu','moe_combine':'moe_combine','rms_norm':'rms_norm'}[op]+'(',_binding_name(record)+'(',1)+'\n'
        if op=='elementwise' and ('elementwise',record['name']) not in seen:
            result+='void '+record['name']+'('+', '.join(p['type']+' '+p['name'] for p in record['parameters'])+');\n';seen.add(('elementwise',record['name']))
        elif op!='elementwise' and op not in seen:result+=declarations[op]+'\n';seen.add(op)
    return result+'const char* backend();\n}\n'


def _handler_body(record):
    op=record['operation']
    if op=='router':return '''int n,k;if(!(input>>n>>k)||n<1||n>512||k<1||k>n)throw std::runtime_error("invalid N/K shape");std::vector<float> x(n);read(input,x);auto value=strata_core::route(x,k);emit(value);'''
    if op=='swiglu':return '''int n;if(!(input>>n)||n<1||n>16777216)throw std::runtime_error("invalid N");std::vector<float> gate(n),up(n),output(n);read(input,gate);read(input,up);strata_core::swiglu(gate.data(),up.data(),output.data(),n);emit(output);'''
    if op=='moe_combine':return '''int k,d;if(!(input>>k>>d)||k<1||k>512||d<1||d>65536)throw std::runtime_error("invalid K/D");std::vector<float> weights(k),parts(size_t(k)*d),shared(d),output(d);read(input,weights);read(input,parts);read(input,shared);strata_core::moe_combine(parts.data(),weights.data(),shared.data(),output.data(),d,k,1);emit(output);'''
    if op=='rms_norm':return '''int64_t rows,cols;float eps;if(!(input>>rows>>cols>>eps)||rows<1||rows>100000||cols<1||cols>65536||rows*cols>16777216)throw std::runtime_error("invalid normalization shape");std::vector<float> values(size_t(rows*cols)),weights(cols);read(input,values);read(input,weights);strata_core::rms_norm(values.data(),weights.data(),rows,cols,eps);emit(values);'''
    params=record['parameters'];pointers=[p for p in params if p['pointer']]
    scalars=[p for p in params if not p['pointer'] and p['base'] in {'float','double'}]
    const_inputs=any(p['const'] for p in pointers)
    result='int n;if(!(input>>n)||n<1||n>16777216)throw std::runtime_error("invalid elementwise N");\n'
    for i,p in enumerate(scalars):result+=p['type']+' scalar_'+str(i)+';if(!(input>>scalar_'+str(i)+')||!std::isfinite(scalar_'+str(i)+'))throw std::runtime_error("invalid scalar input");\n'
    for i,p in enumerate(pointers):
        result+='std::vector<float> tensor_'+str(i)+'(n);\n'
        if p['const'] or not const_inputs:result+='read(input,tensor_'+str(i)+');\n'
    args=[]
    for p in params:
        if p['pointer']:args.append('tensor_'+str(pointers.index(p))+'.data()')
        elif p['base'] in {'float','double'}:args.append('scalar_'+str(scalars.index(p)))
        else:args.append('n')
    result+='strata_core::'+record['name']+'('+','.join(args)+');\n'
    output=next(i for i,p in enumerate(pointers) if not p['const'])
    return result+'emit(tensor_'+str(output)+');'


def _handler(record):
    source=_handler_body(record)
    name={'router':'route','swiglu':'swiglu','moe_combine':'moe_combine','rms_norm':'rms_norm'}.get(record['operation'],record['name'])
    return source.replace('strata_core::'+name+'(', 'strata_core::'+_binding_name(record)+'(')


CLI_COMMON=r'''#include "strata_core.h"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static void read(std::istream& input,std::vector<float>& values){for(auto& v:values)if(!(input>>v)||!std::isfinite(v))throw std::runtime_error("missing/non-finite input value");}
static void array(const std::vector<float>& values){for(size_t i=0;i<values.size();++i){if(!std::isfinite(values[i]))throw std::runtime_error("non-finite computed output");std::cout<<(i?",":"")<<values[i];}}
static void emit(const std::vector<float>& values){std::cout<<"{\"backend\":\""<<strata_core::backend()<<"\",\"output\":[";array(values);std::cout<<"]}";}
static void emit(const strata_core::Routing& routing){std::cout<<"{\"backend\":\""<<strata_core::backend()<<"\",\"ids\":[";for(size_t i=0;i<routing.ids.size();++i)std::cout<<(i?",":"")<<routing.ids[i];std::cout<<"],\"weights\":[";array(routing.weights);std::cout<<"]}";}
'''


def _main(inventory):
    mode=inventory['cli']['mode']
    source=CLI_COMMON+'''int main(int argc,char** argv){try{
 std::string path,operation="'''+mode+'''";
 for(int i=1;i<argc;++i){std::string key=argv[i];if((key=="--input"||key=="--operation")&&i+1<argc){if(key=="--input")path=argv[++i];else operation=argv[++i];}else throw std::runtime_error("usage: strata_engine --input PATH [--operation FUNCTION]");}
 if(path.empty())throw std::runtime_error("--input is required");std::ifstream input(path);if(!input)throw std::runtime_error("cannot open input");std::cout<<std::setprecision(9);
'''
    if mode=='combined':
        source+='''if(operation=="combined"){
 int n,k,d;if(!(input>>n>>k>>d)||n<1||n>512||k<1||k>n||d<1||d>65536)throw std::runtime_error("invalid combined tensor shapes");
 std::vector<float> logits(n),gate(size_t(n)*d),up(gate.size()),activated(gate.size()),shared(d),parts(size_t(k)*d),output(d);
 read(input,logits);read(input,gate);read(input,up);read(input,shared);auto routing=strata_core::route(logits,k);
 strata_core::swiglu(gate.data(),up.data(),activated.data(),int(activated.size()));
 for(int e=0;e<k;++e)for(int j=0;j<d;++j)parts[size_t(e)*d+j]=activated[size_t(routing.ids[e])*d+j];
 strata_core::moe_combine(parts.data(),routing.weights.data(),shared.data(),output.data(),d,k,1);
 std::cout<<"{\\"backend\\":\\""<<strata_core::backend()<<"\\",\\"ids\\":[";for(int i=0;i<k;++i)std::cout<<(i?",":"")<<routing.ids[i];
 std::cout<<"],\\"weights\\":[";array(routing.weights);std::cout<<"],\\"output\\":[";array(output);std::cout<<"]}";
 }else '''
    for index,record in enumerate(inventory['kernels'].values()):
        terms=[record['name'],record['id'],record['operation'],record['category']]
        source+='if('+ '||'.join('operation=='+json.dumps(value) for value in terms)+'){'+_handler(record)+'}else '
    source+='''throw std::runtime_error("requested operation is not in this compiled capability set");
 std::string extra;if(input>>extra)throw std::runtime_error("unexpected trailing input");std::cout<<"\\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<"\\n";return 2;}}
'''
    return source


def _tests(inventory):
    """Execute independent references for EACH selected source identity.

    Category totals are not coverage evidence. Arbitrary scalar kernels have no
    invented built-in oracle; they emit an explicit unverified record even when
    another selected source has passed its own comparison.
    """
    records=list(inventory['kernels'].values())
    test=r'''#include "strata_core.h"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
struct OperationCheck {
 std::string source_id,name,operation,status="unverified",error;
 long long outputs_compared=0;double max_abs_error=0;
};
static void compare(OperationCheck& check,float actual,float expected){
 check.outputs_compared++;
 if(!std::isfinite(actual)||!std::isfinite(expected))throw std::runtime_error("non-finite numerical comparison");
 const double error=std::abs(double(actual)-double(expected));
 check.max_abs_error=std::max(check.max_abs_error,error);
 if(error>1e-5)throw std::runtime_error("independent numerical reference mismatch");
}
static void quote(const std::string& value){
 std::cout<<'"';for(unsigned char c:value){
  if(c=='"'||c=='\\')std::cout<<'\\'<<c;
  else if(c=='\n')std::cout<<"\\n";else if(c=='\r')std::cout<<"\\r";else if(c=='\t')std::cout<<"\\t";
  else if(c<32)std::cout<<"\\u00"<<"0123456789abcdef"[c>>4]<<"0123456789abcdef"[c&15];
  else std::cout<<c;
 }std::cout<<'"';
}
'''
    has_router=any(record['operation']=='router' for record in records)
    if has_router and inventory.get('reference'):
        test+='namespace upstream {constexpr double RENORM_CLAMP='+inventory['reference']['clamp']+';\n'+inventory['reference']['source_code']+'\n}\n'
    bodies={
      'router':r'''for(int trial=0;trial<20;++trial){
 int n=trial%2?512:37,k=trial%3?10:1;
 std::vector<float> values(n),weights(k);std::vector<int> ids(k);for(auto& v:values)v=normal(rng);
 auto actual=@CALL@(values,k);upstream::reference(values.data(),n,k,ids.data(),weights.data());
 for(int i=0;i<k;++i){
  check.outputs_compared++;if(actual.ids[i]!=ids[i])throw std::runtime_error("upstream host router expert selection mismatch");
  compare(check,actual.weights[i],weights[i]);
 }
}
std::vector<float> tied(512,0.f);tied[511]=1e-10f;auto tied_result=@CALL@(tied,10);
for(int i=0;i<10;++i){check.outputs_compared++;if(tied_result.ids[i]!=i)throw std::runtime_error("production rounded tie order mismatch");}
''',
      'swiglu':r'''const int n=51;std::vector<float> x(n),u(n),actual(n);
for(auto& v:x)v=normal(rng);for(auto& v:u)v=normal(rng);
@CALL@(x.data(),u.data(),actual.data(),n);
for(int i=0;i<n;++i){const float expected=float(double(x[i])/(1.+std::exp(-double(x[i]))))*u[i];compare(check,actual[i],expected);}
''',
      'moe_combine':r'''const int d=17,k=3;std::vector<float> parts(d*k),weights={.2f,.3f,.5f},shared(d),actual(d);
for(auto& v:parts)v=normal(rng);for(auto& v:shared)v=normal(rng);
@CALL@(parts.data(),weights.data(),shared.data(),actual.data(),d,k,1);
for(int j=0;j<d;++j){double expected=0;for(int e=0;e<k;++e)expected+=double(weights[e])*parts[e*d+j];expected+=shared[j];compare(check,actual[j],float(expected));}
''',
      'rms_norm':r'''const int rows=3,cols=33;const float eps=1e-5f;
std::vector<float> original(rows*cols),actual,weights(cols);for(auto& v:original)v=normal(rng);for(auto& v:weights)v=normal(rng);
actual=original;@CALL@(actual.data(),weights.data(),rows,cols,eps);
for(int row=0;row<rows;++row){
 float partial[32]={};for(int lane=0;lane<32;++lane)for(int c=lane;c<cols;c+=32)partial[lane]+=original[row*cols+c]*original[row*cols+c];
 for(int offset=16;offset>0;offset>>=1){float previous[32];std::copy(partial,partial+32,previous);for(int lane=0;lane<32;++lane)partial[lane]+=previous[lane+offset<32?lane+offset:lane];}
 const float inv=1.f/std::sqrt(partial[0]/float(cols)+eps);
 for(int c=0;c<cols;++c){const float expected=(original[row*cols+c]*weights[c])*inv;compare(check,actual[row*cols+c],expected);}
}
'''}
    test+='int main(){std::vector<OperationCheck> checks;bool failed=false;\n'
    for record in records:
        test+='checks.push_back({'+','.join(json.dumps(record[key]) for key in ['id','name','operation'])+'});\n{auto& check=checks.back();try{\n'
        op=record['operation']
        if op in bodies and (op!='router' or inventory.get('reference')):
            test+='std::mt19937 rng(20261114);std::normal_distribution<float> normal;\n'
            test+=bodies[op].replace('@CALL@','strata_core::'+_binding_name(record))
            test+='if(check.outputs_compared>0)check.status="passed";\n'
        else:
            test+='check.status="unverified";check.error="No built-in independent semantic oracle for this selected source; external oracle required";\n'
        test+='}catch(const std::exception& error){check.status="failed";check.error=error.what();failed=true;}}\n'
    test+=r'''long long compared=0;double maximum=0;bool complete=true;
for(const auto& check:checks){compared+=check.outputs_compared;maximum=std::max(maximum,check.max_abs_error);complete=complete&&check.status=="passed";}
std::cout<<std::setprecision(17)<<"{\"check\":\"source_lowered_strata_core\",\"outputs_compared\":"<<compared<<",\"max_abs_error\":"<<maximum<<",\"coverage_complete\":"<<(complete?"true":"false")<<",\"operation_checks\":[";
for(size_t i=0;i<checks.size();++i){const auto& check=checks[i];if(i)std::cout<<',';
 std::cout<<"{\"source_id\":";quote(check.source_id);std::cout<<",\"name\":";quote(check.name);
 std::cout<<",\"operation\":";quote(check.operation);std::cout<<",\"status\":";quote(check.status);
 std::cout<<",\"outputs_compared\":"<<check.outputs_compared<<",\"max_abs_error\":"<<check.max_abs_error;
 if(!check.error.empty()){std::cout<<",\"error\":";quote(check.error);}std::cout<<'}';
}
std::cout<<"],\"native_device_validated\":false,\"full_inference_validated\":false}\n";
return failed?1:0;}
'''
    return test

CMAKE = '''cmake_minimum_required(VERSION 3.24)
project(strata_source_lowered_core LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(STRATA_CORE_BACKEND CPU CACHE STRING "CPU cooperative reference or optional real Ascend activation")
set_property(CACHE STRATA_CORE_BACKEND PROPERTY STRINGS CPU ASCEND)
add_library(strata_core src/strata_core.cpp)
target_include_directories(strata_core PUBLIC include)
if(STRATA_CORE_BACKEND STREQUAL "ASCEND")
 list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
 find_package(AscendCL REQUIRED)
 @ASCEND_GUARD@
 find_package(Threads REQUIRED)
 target_sources(strata_core PRIVATE src/ascend_backend.cpp)
 target_compile_definitions(strata_core PRIVATE STRATA_CORE_ASCEND=1)
 target_link_libraries(strata_core PRIVATE AscendCL::ascendcl AscendCL::opapi Threads::Threads)
elseif(NOT STRATA_CORE_BACKEND STREQUAL "CPU")
 message(FATAL_ERROR "Unknown backend; no fallback permitted")
endif()
add_executable(strata_engine src/main.cpp)
target_link_libraries(strata_engine PRIVATE strata_core)
add_executable(strata_core_test tests/numerical.cpp)
target_link_libraries(strata_core_test PRIVATE strata_core)
enable_testing()
add_test(NAME source_lowered_core_numerical COMMAND strata_core_test)
'''


FIND_ASCEND = 'set(AscendCL_ROOT "$ENV{ASCEND_HOME_PATH}" CACHE PATH "Real CANN toolkit root")\nfind_path(AscendCL_INCLUDE_DIR acl/acl.h HINTS "${AscendCL_ROOT}" PATH_SUFFIXES include)\nfind_path(AscendCL_OP_INCLUDE_DIR aclnnop/aclnn_silu.h HINTS "${AscendCL_ROOT}" PATH_SUFFIXES include)\nfind_library(AscendCL_LIBRARY ascendcl HINTS "${AscendCL_ROOT}" PATH_SUFFIXES lib64)\nfind_library(AscendCL_OPAPI_LIBRARY opapi HINTS "${AscendCL_ROOT}" PATH_SUFFIXES lib64)\ninclude(FindPackageHandleStandardArgs)\nfind_package_handle_standard_args(AscendCL REQUIRED_VARS AscendCL_INCLUDE_DIR AscendCL_OP_INCLUDE_DIR AscendCL_LIBRARY AscendCL_OPAPI_LIBRARY)\nif(AscendCL_FOUND)\n  add_library(AscendCL::ascendcl UNKNOWN IMPORTED)\n  set_target_properties(AscendCL::ascendcl PROPERTIES IMPORTED_LOCATION "${AscendCL_LIBRARY}" INTERFACE_INCLUDE_DIRECTORIES "${AscendCL_INCLUDE_DIR};${AscendCL_OP_INCLUDE_DIR}")\n  add_library(AscendCL::opapi UNKNOWN IMPORTED)\n  set_target_properties(AscendCL::opapi PROPERTIES IMPORTED_LOCATION "${AscendCL_OPAPI_LIBRARY}")\nendif()\n'

ASCEND_SOURCE = '#include <acl/acl.h>\n#include <aclnn/acl_meta.h>\n#include <aclnnop/aclnn_silu.h>\n#include <aclnnop/aclnn_mul.h>\n#include <mutex>\n#include <stdexcept>\n#include <string>\nnamespace strata_core {\nnamespace {\nvoid check(int code,const char* op) { if(code)throw std::runtime_error(std::string(op)+" failed: "+std::to_string(code)); }\nstruct Storage {\n void* ptr=nullptr;size_t bytes;\n explicit Storage(size_t size):bytes(size){check(aclrtMalloc(&ptr,size,ACL_MEM_MALLOC_NORMAL_ONLY),"aclrtMalloc");}\n ~Storage(){if(ptr)aclrtFree(ptr);}\n};\nstruct Tensor {\n aclTensor* ptr=nullptr;\n Tensor(Storage& buffer,int64_t size){int64_t shape[]={size},stride[]={1};ptr=aclCreateTensor(shape,1,ACL_FLOAT,stride,0,ACL_FORMAT_ND,shape,1,buffer.ptr);if(!ptr)throw std::runtime_error("aclCreateTensor failed");}\n ~Tensor(){if(ptr)aclDestroyTensor(ptr);}\n};\nstruct Session {\n aclrtStream stream=nullptr;\n Session(){check(aclInit(nullptr),"aclInit");check(aclrtSetDevice(0),"aclrtSetDevice");check(aclrtCreateStream(&stream),"aclrtCreateStream");}\n ~Session(){if(stream)aclrtDestroyStream(stream);}\n};\n}\nvoid ascend_swiglu(const float* gate,const float* up,float* output,int n) {\n static std::mutex mutex;const std::lock_guard<std::mutex> guard(mutex);static Session session;\n const size_t size=size_t(n)*sizeof(float);Storage g(size),u(size),s(size),y(size);Tensor gt(g,n),ut(u,n),st(s,n),yt(y,n);\n check(aclrtMemcpy(g.ptr,size,gate,size,ACL_MEMCPY_HOST_TO_DEVICE),"gate upload");\n check(aclrtMemcpy(u.ptr,size,up,size,ACL_MEMCPY_HOST_TO_DEVICE),"up upload");\n uint64_t bytes=0;aclOpExecutor* executor=nullptr;\n check(aclnnSiluGetWorkspaceSize(gt.ptr,st.ptr,&bytes,&executor),"aclnnSiluGetWorkspaceSize");\n if(bytes){Storage workspace(bytes);check(aclnnSilu(workspace.ptr,bytes,executor,session.stream),"aclnnSilu");check(aclrtSynchronizeStream(session.stream),"Silu sync");}\n else{check(aclnnSilu(nullptr,0,executor,session.stream),"aclnnSilu");check(aclrtSynchronizeStream(session.stream),"Silu sync");}\n check(aclnnMulGetWorkspaceSize(st.ptr,ut.ptr,yt.ptr,&bytes,&executor),"aclnnMulGetWorkspaceSize");\n if(bytes){Storage workspace(bytes);check(aclnnMul(workspace.ptr,bytes,executor,session.stream),"aclnnMul");check(aclrtSynchronizeStream(session.stream),"Mul sync");}\n else{check(aclnnMul(nullptr,0,executor,session.stream),"aclnnMul");check(aclrtSynchronizeStream(session.stream),"Mul sync");}\n check(aclrtMemcpy(output,size,y.ptr,size,ACL_MEMCPY_DEVICE_TO_HOST),"result download");\n}\n}\n'

def _validation_input(inventory):
    mode=inventory['cli']['mode']
    if mode=='combined':return '4 2 3\n1 5 -2 3\n-3 0 2 1 -1 0.25 7 -0.1 4 0.5 2.5 -4\n0.5 -1 2 3 0.5 -2 0.75 4 1 -0.5 2 1.25\n0.2 -0.3 0.4\n'
    record=next(iter(inventory['kernels'].values()));op=record['operation']
    if op=='router':return '4 2\n1 5 -2 3\n'
    if op=='swiglu':return '4\n-1 0 1 2\n0.5 1 -1 2\n'
    if op=='moe_combine':return '2 3\n0.25 0.75\n1 2 3 4 5 6\n0.1 0.2 0.3\n'
    if op=='rms_norm':return '2 3 0.00001\n1 2 3 -1 0 1\n0.5 1 2\n'
    pointers=[p for p in record['parameters'] if p['pointer']]
    scalars=[p for p in record['parameters'] if not p['pointer'] and p['base'] in {'float','double'}]
    lines=['4']+['1.25' for _ in scalars]
    const_inputs=any(p['const'] for p in pointers)
    lines+=['1 2 3 4' for p in pointers if p['const'] or not const_inputs]
    return '\n'.join(lines)+'\n'


def _native_activation(record):
    """Prove the narrow source expression supported by the optional CANN port.

    CPU lowering has no expression whitelist. This check protects a DIFFERENT
    hand-ported native implementation from silently accepting changed arithmetic.
    """
    if record['operation']!='swiglu':return False
    body=re.sub(r'\s+','',strip_comments(record['body']))
    params=record['parameters'];gate,up,out,extent=[p['name'] for p in params]
    pattern=(r'constint(\w+)=blockIdx\.x\*blockDim\.x\+threadIdx\.x;'
             r'if\(\1>='+re.escape(extent)+r'\)return;constdouble(\w+)=\(double\)'+re.escape(gate)+r'\[\1\];'
             +re.escape(out)+r'\[\1\]=\(float\)\(\2/\(1\.0\+exp\(-\2\)\)\)\*'+re.escape(up)+r'\[\1\];')
    return bool(re.fullmatch(pattern,body))


def generate_project(inventory,destination):
    validate_core(inventory)
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    source=_source(inventory)
    activation=next((record for record in inventory['kernels'].values() if _native_activation(record)),None)
    if activation:
        source=source.replace('namespace strata_core {\n','namespace strata_core {\n#ifdef STRATA_CORE_ASCEND\nvoid ascend_swiglu(const float*,const float*,float*,int);\n#endif\n',1)
        launch=_invocation(activation,['gate','up','output','n'],'unsigned((n+31)/32)')
        source=source.replace(launch,'#ifdef STRATA_CORE_ASCEND\n ascend_swiglu(gate,up,output,n);\n#else\n '+launch+'\n#endif')
        source=source.replace('const char* backend(){return "CPU";}', 'const char* backend(){\n#ifdef STRATA_CORE_ASCEND\n return "Ascend activation; CPU cooperative router/aggregation";\n#else\n return "CPU";\n#endif\n}')
    guard='' if activation else 'message(FATAL_ERROR "Selected source expressions have no native implementation; CPU cooperative execution is not Ascend")'
    files={'include/strata_core.h':_header(inventory),'include/cuda_cpu_runtime.h':CPU_RUNTIME,
        'src/strata_core.cpp':source,'src/main.cpp':_main(inventory),'tests/numerical.cpp':_tests(inventory),
        'tests/cli-input.txt':_validation_input(inventory),'CMakeLists.txt':CMAKE.replace('@ASCEND_GUARD@',guard),
        'cmake/FindAscendCL.cmake':FIND_ASCEND}
    if activation:files['src/ascend_backend.cpp']=ASCEND_SOURCE
    task_oracle=inventory.get('task_oracle')
    oracle_metadata=None
    if task_oracle is not None:
        # Package the exact stdlib runner used by the factory, so an extracted
        # delivery executes real task cases without importing this application.
        import ast
        import sys
        from .oracle_validation import normalize_oracle
        normalized_oracle=normalize_oracle(task_oracle)
        runner_source=Path(__file__).with_name('oracle_validation.py').read_text()
        for node in ast.walk(ast.parse(runner_source)):
            if isinstance(node,ast.ImportFrom):
                if node.level or (node.module and node.module.split('.')[0] not in sys.stdlib_module_names):
                    raise ValueError('Task oracle runner must be self-contained standard-library source before packaging')
            elif isinstance(node,ast.Import):
                if any(alias.name.split('.')[0] not in sys.stdlib_module_names for alias in node.names):
                    raise ValueError('Task oracle runner has a non-standard-library dependency')
        files['tests/task-oracle.json']=json.dumps(normalized_oracle,indent=2,allow_nan=False)+'\n'
        files['tests/verify_task_oracle.py']=runner_source
        files['CMakeLists.txt']+='\nfind_package(Python3 3.9 COMPONENTS Interpreter REQUIRED)\nadd_test(NAME task_oracle_acceptance\n COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_task_oracle.py"\n --binary $<TARGET_FILE:strata_engine>\n --project "${CMAKE_CURRENT_SOURCE_DIR}/project.json"\n --oracle "${CMAKE_CURRENT_SOURCE_DIR}/tests/task-oracle.json")\n'
        oracle_metadata={'oracle':'tests/task-oracle.json','runner':'tests/verify_task_oracle.py',
            'cases':len(normalized_oracle['cases']),'scope':'Isolated CPU task acceptance; no native device or model correctness claim'}
    operation_metadata=[]
    for record in inventory['kernels'].values():
        relative='tests/operations/'+_hash(record['id'])[:16]+'-input.txt'
        single={'cli':{'mode':record['operation']},'kernels':{'operation':record}}
        files[relative]=_validation_input(single)
        has_reference=record['operation'] in {'swiglu','moe_combine','rms_norm'} or (record['operation']=='router' and bool(inventory.get('reference')))
        operation_metadata.append({'source_id':record['id'],'id':record['id'],'name':record['name'],
            'operation':record['operation'],'category':record['category'],'binding':_binding_name(record),
            'validation_input':relative,'validation_argv':['--input',relative,'--operation',record['id']],
            'operation_literal':record['id'],'builtin_reference_available':has_reference})
    for key,record in inventory['kernels'].items():files['reference/'+re.sub(r'[^\w.-]','_',key)+'.cu.txt']=record['source_code']+'\n'
    if inventory.get('reference'):files['reference/router_reference.cpp.txt']=inventory['reference']['source_code']+'\n'
    license_path=Path(inventory['source_dir'])/'LICENSE'
    if not license_path.is_file():raise ValueError('Source license is absent')
    files['LICENSE']=license_path.read_text()
    files['README.md']='''# Source-lowered STRATA computational core

This independent C++20 project compiles arithmetic and control flow extracted from real production CUDA function bodies. A bounded cooperative CPU runtime executes thread indices, shared memory, block barriers and full-warp shuffles. Unknown helpers, atomics, vectors, templates and divergent collectives fail explicitly. This is CPU reference execution, not validated CUDA/Ascend execution or complete model inference.

    cmake -S . -B build -DSTRATA_CORE_BACKEND=CPU
    cmake --build build --parallel 2
    ctest --test-dir build --output-on-failure
    ./build/strata_engine --input tests/cli-input.txt

An application supplies its own numeric file using this selected contract:

'''+inventory['cli']['format']+'''

For multiple independently selected capabilities, pass --operation SOURCE_ID. Function names are accepted only as convenience aliases; source IDs identify exact producers. The bundled tests/cli-input.txt is an isolated arithmetic validation input, not model weights or production inference. Each selected known production source is called through its unique binding and receives an operation_checks result from its independent reference in tests/numerical.cpp. Aggregate comparison counts do not prove coverage of other sources. Arbitrary discovered scalar arithmetic requires a task-provided semantic oracle; zero reference comparisons must not be treated as correctness validation.

Optional STRATA_CORE_BACKEND=ASCEND requires real CANN headers, libraries and a device. Only a structurally proven SiLU-times-up activation has an explicit native aclnnSilu/aclnnMul implementation; remaining operations are CPU. Changed activation mathematics without a corresponding native implementation fails configuration. There is no silent backend fallback. All native/full-model validation flags remain false until actual target evidence exists.

Source casts, expression ordering and collective structure are retained. CPU exp/rsqrt implementations may differ from device math intrinsics; CPU checks do not establish GPU bit equality. The independent upstream router host reference uses double probabilities whereas production selection rounds them to float; tests separately cover the production tie case.
'''
    provenance={'schema':'strata.source.provenance.v2','commit_sha':inventory['commit_sha'],'demands':inventory.get('demands',[]),
        'operations':[{'id':record['id'],'function_sha256':record['function_sha256'],'source_sha256':record['source_sha256'],
          'operation':record['operation'],'category':record['category'],'lowering_kind':record['lowering_kind'],
          'features':record['features']} for record in inventory['kernels'].values()]}
    files['reference/provenance.json']=json.dumps(provenance,indent=2)+'\n'
    for relative,code in files.items():
        path=destination/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(code)
    generated=[{'path':name,'sha256':_hash(code),'bytes':len(code.encode())} for name,code in files.items()]
    diff={'schema':'strata.code.diff.v1','files':[{'source_path':record['path'],'generated_path':'src/strata_core.cpp','source_code':record['source_code'],'generated_code':record['semantic_ir']['lowered_cpp']} for record in inventory['kernels'].values()],
          'selected':inventory['selected'],'transforms':['Discovered signatures and executable tensor contracts','Production kernel body retained; CUDA execution primitives lowered to C++20 cooperative CPU runtime','Source casts, local types, loop/control/selection operations retained'], 'generated_files':generated}
    (destination/'code_diff.json').write_text(json.dumps(diff,indent=2)+'\n')
    generated.append({'path':'code_diff.json','sha256':_hash((destination/'code_diff.json').read_bytes()),'bytes':(destination/'code_diff.json').stat().st_size})
    cli=dict(inventory['cli']);cli['validation_input']='tests/cli-input.txt'
    if cli['mode']=='operations':cli['validation_operation']=next(iter(inventory['kernels'].values()))['name']
    cli['validation_case']={'kind':'isolated_external_numeric_input','semantic_oracle_available':all(item['builtin_reference_available'] for item in operation_metadata) if cli['mode']=='combined' else operation_metadata[0]['builtin_reference_available']}
    cli['operations']=[dict(item) for item in operation_metadata]
    metadata={'schema':'strata.core.project.v1','project_dir':str(destination),'source_commit':inventory['commit_sha'],
        'selected':inventory['selected'],'operations':operation_metadata,'generated_files':generated,'code_diff':'code_diff.json','cli':cli,
        'targets':['strata_engine','strata_core_test'],'runtime':'cpu_cooperative_cuda_reference','scope':inventory['scope'],
        'native_activation_generated':bool(activation),'native_device_validated':False,'full_inference_validated':False}
    if oracle_metadata is not None:metadata['task_oracle']=oracle_metadata
    (destination/'project.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def main():
    parser=argparse.ArgumentParser(description='Assemble actual source-lowered STRATA functions into a standalone C++20 project')
    parser.add_argument('--inventory',required=True);parser.add_argument('--output',required=True)
    options=parser.parse_args();result=generate_project(json.loads(Path(options.inventory).read_text()),options.output)
    print(json.dumps(result,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
