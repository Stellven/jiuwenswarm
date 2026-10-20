"""Build-time wheel-only dependency closure from the committed uv lock."""
import sys
import tomllib


def frozen_requirements(lock,roots):
    packages={}
    for p in lock['package']:packages.setdefault(p['name'],[]).append(p)
    selected={};pending=[{'name':x} for x in roots]
    while pending:
        dep=pending.pop();choices=[p for p in packages.get(dep['name'],[]) if 'version' not in dep or p['version']==dep['version']]
        if len(choices)!=1:raise ValueError('ambiguous locked side dependency: '+dep['name'])
        p=choices[0]
        if p['name'] in selected:
            if selected[p['name']]['version']!=p['version']:raise ValueError('conflicting locked dependency')
            continue
        if set(p.get('source',{}))!={'registry'}:raise ValueError('non-registry dependency cannot enter the side image')
        wheels=p.get('wheels',[])
        if not wheels or any(not w.get('hash','').startswith('sha256:') for w in wheels):raise ValueError('locked wheel hashes required')
        selected[p['name']]=p;pending.extend(p.get('dependencies',[]))
    lines=[]
    for name,p in sorted(selected.items()):
        lines.append(name+'=='+p['version']+' '+' '.join('--hash='+w['hash'] for w in p['wheels']))
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    with open(sys.argv[1],'rb') as stream:lock=tomllib.load(stream)
    with open(sys.argv[2],'w',encoding='utf8',newline='\n') as stream:stream.write(frozen_requirements(lock,sys.argv[3:]))
