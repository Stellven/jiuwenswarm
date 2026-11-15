"""CPU token-state reference; no tensor attention kernels or performance claims."""
import math

IDENTITY = ('model', 'tokenizer', 'adapter', 'position', 'dtype', 'tenant')

def identity(value):
    if set(value) != set(IDENTITY) or any(not isinstance(value[k], str) or not value[k] for k in IDENTITY):
        raise ValueError('identity requires nonempty model/tokenizer/adapter/position/dtype/tenant fingerprints')
    return tuple(value[k] for k in IDENTITY)

def integer(v, name, minimum=0, maximum=10000000):
    if type(v) is not int or not minimum <= v <= maximum:
        raise ValueError(name + ' outside bounded integer range')
    return v

def tokens(value):
    if not isinstance(value, list) or len(value) > 100000 or any(type(t) is not int or t < 0 for t in value):
        raise ValueError('tokens must be a bounded list of nonnegative integer token IDs')
    return value

class PagePool:
    def __init__(self, capacity, block_tokens):
        self.capacity = integer(capacity, 'capacity', 1, 10000)
        self.block_tokens = integer(block_tokens, 'block_tokens', 1, 4096)
        self.pages = {}; self.owners = {}; self.next_id = 0

    def _page(self, data):
        if len(self.pages) >= self.capacity: raise ValueError('page capacity exhausted; release an owner first')
        pid = self.next_id; self.next_id += 1
        self.pages[pid] = {'tokens': list(data), 'refs': 1}
        return pid

    def create(self, owner, data):
        if owner in self.owners: raise ValueError('duplicate owner')
        data = tokens(data)
        if math.ceil(len(data)/self.block_tokens) > self.capacity-len(self.pages): raise ValueError('capacity exhausted')
        self.owners[owner] = [self._page(data[i:i+self.block_tokens]) for i in range(0,len(data),self.block_tokens)]

    def share(self, source, target):
        if target in self.owners: raise ValueError('duplicate owner')
        ids = list(self.owners[source]); self.owners[target] = ids
        for pid in ids: self.pages[pid]['refs'] += 1

    def append(self, owner, token):
        tokens([token]); ids = self.owners[owner]
        if not ids or len(self.pages[ids[-1]]['tokens']) == self.block_tokens:
            ids.append(self._page([token])); return
        old = self.pages[ids[-1]]
        if old['refs'] > 1:
            new_id = self._page(old['tokens'])  # allocate first: failure leaves state untouched
            old['refs'] -= 1; ids[-1] = new_id
        self.pages[ids[-1]]['tokens'].append(token)

    def release(self, owner):
        for pid in self.owners.pop(owner):
            self.pages[pid]['refs'] -= 1
            if not self.pages[pid]['refs']: del self.pages[pid]

    def evict(self, pid):
        if pid in self.pages and self.pages[pid]['refs']: raise ValueError('cannot evict referenced/in-flight page')
        self.pages.pop(pid, None)

    def read(self, owner):
        return [t for p in self.owners[owner] for t in self.pages[p]['tokens']]

    def snapshot(self):
        return {'pages': {str(k):v for k,v in self.pages.items()}, 'owners':self.owners,
                'used_pages':len(self.pages), 'capacity':self.capacity,
                'allocated_token_slots':len(self.pages)*self.block_tokens}

def replay(spec):
    if not isinstance(spec, dict): raise ValueError('spec must be object')
    ops = spec['operations']
    if not isinstance(ops,list) or len(ops)>2000: raise ValueError('too many operations')
    pool = PagePool(spec['capacity'],spec['block_tokens']); trace=[]
    for op in ops:
        kind=op['op']
        if kind=='create': pool.create(op['owner'],op['tokens'])
        elif kind=='share': pool.share(op['source'],op['target'])
        elif kind=='append': pool.append(op['owner'],op['token'])
        elif kind=='release': pool.release(op['owner'])
        elif kind=='evict': pool.evict(op['page'])
        else: raise ValueError('unknown operation')
        trace.append({'op':kind,'used_pages':len(pool.pages)})
    return dict(pool.snapshot(), sequences={o:pool.read(o) for o in pool.owners},trace=trace, scope='CPU token-state reference')

def prefix(spec):
    """Longest exact token prefix within a fully fingerprinted cache namespace."""
    key=identity(spec['identity']); query=tokens(spec['tokens']); best=0; hit=None
    entries=spec['entries']
    if not isinstance(entries,list) or len(entries)>1000: raise ValueError('too many entries')
    invalidated=spec.get('invalidated_models',[])
    for i,e in enumerate(entries):
        ekey=identity(e['identity']); data=tokens(e['tokens'])
        if ekey != key or e['identity']['model'] in invalidated: continue
        n=0
        for a,b in zip(query,data):
            if a != b: break
            n+=1
        if n>best: best=n; hit=i
    return {'matched_tokens':best,'entry':hit,'remaining_tokens':query[best:],
            'exact_prefix_only':True,'invalidation':'model fingerprint denylist; changed identity is always a miss'}

def estimate(spec):
    """Logical KV storage; compressed MLA and materialized MHA are separate layouts."""
    layers=integer(spec['layers'],'layers',1,1024); count=integer(spec['tokens'],'tokens'); batch=integer(spec.get('batch',1),'batch',1,10000)
    layout=spec['layout']; bits=integer(spec['bits'],'bits',1,32)
    if layout=='mha':
        width=2*integer(spec['kv_heads'],'kv_heads',1,1024)*integer(spec['head_dim'],'head_dim',1,8192)
        formula='layers * tokens * batch * 2 * kv_heads * head_dim'
    elif layout=='mla':
        width=integer(spec['latent_dim'],'latent_dim',1,32768)+integer(spec['rope_dim'],'rope_dim',1,8192)
        formula='layers * tokens * batch * (latent_dim + rope_dim)'
    else: raise ValueError('layout must be mha or mla; dimensions must describe actual backend storage')
    elements=layers*count*batch*width
    payload=(elements*bits+7)//8
    group=integer(spec.get('group_size',64),'group_size',1,100000)
    scale=integer(spec.get('scale_bytes',2),'scale_bytes',0,16)
    metadata=((elements+group-1)//group)*scale if bits<16 else 0
    logical=payload+metadata
    return {'layout':layout,'elements':elements,'formula':formula,'payload_bytes':payload,'scale_bytes':metadata,
            'logical_bytes':logical,'approximate_quantization':bits<16,
            'admission_authorized':False,'model_support':'unknown; explicit dimensions are not a backend support claim',
            'excluded':['page rounding','allocator alignment','workspace','weights','activation buffers','quantization error'],
            'unified_memory_rule':'count GB10 shared DRAM once; subtract weights, OS, workspace and safety headroom before runtime admission'}
