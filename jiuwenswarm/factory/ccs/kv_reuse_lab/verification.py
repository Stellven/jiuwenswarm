"""Package-attached executable checks, independent from factory trusted units."""
import reference as r

def verify():
    key=dict(model='model@1',tokenizer='tok@1',adapter='none',position='rope@1',dtype='fp16',tenant='alice')
    spec=dict(identity=key,tokens=[1,2,9],entries=[dict(identity=key,tokens=[1,2,3])])
    assert r.prefix(spec)['matched_tokens']==2
    for field in key:
        changed=dict(key); changed[field]+='changed'
        assert r.prefix(dict(spec,identity=changed))['matched_tokens']==0
    assert r.prefix(dict(spec,invalidated_models=['model@1']))['matched_tokens']==0
    p=r.PagePool(4,4); p.create('a',[1,2]); p.share('a','b'); p.append('b',3)
    assert p.read('a')==[1,2] and p.read('b')==[1,2,3]
    assert sorted(v['refs'] for v in p.pages.values())==[1,1]
    try: p.evict(p.owners['a'][0])
    except ValueError: pass
    else: raise AssertionError('evicted referenced page')
    p.release('a'); p.release('b'); assert p.pages=={}
    q=r.PagePool(1,4); q.create('a',[1]);q.share('a','b')
    try:q.append('b',2)
    except ValueError:pass
    else:raise AssertionError('unbounded allocation')
    assert q.read('a')==q.read('b')==[1] and q.pages[0]['refs']==2
    q.release('b');q.append('a',2);assert q.read('a')==[1,2]
    e=r.estimate(dict(layout='mla',layers=2,tokens=3,bits=16,latent_dim=4,rope_dim=2))
    assert e['logical_bytes']==72 and not e['approximate_quantization']
    m=r.estimate(dict(layout='mha',layers=2,tokens=3,bits=16,kv_heads=4,head_dim=2))
    assert m['logical_bytes']==192
    quant=r.estimate(dict(layout='mla',layers=2,tokens=3,bits=4,latent_dim=4,rope_dim=2,group_size=8,scale_bytes=2))
    assert quant['payload_bytes']==18 and quant['scale_bytes']==10 and quant['logical_bytes']==28
    assert quant['approximate_quantization'] and not quant['admission_authorized']
    large=r.estimate(dict(layout='mha',layers=1023,tokens=9999999,batch=9999,bits=3,kv_heads=1023,head_dim=8191,group_size=63,scale_bytes=2))
    # Independent integer quotient/remainder reference, beyond binary64 exact range.
    elements=1023*9999999*9999*2*1023*8191
    whole,rem=divmod(elements*3,8)
    assert large['payload_bytes']==whole+bool(rem)==642844572747743796780
    whole,rem=divmod(elements,63)
    assert large['scale_bytes']==(whole+bool(rem))*2
    assert large['logical_bytes']==large['payload_bytes']+large['scale_bytes']
    return {'passed':True,'checks':['identity-isolation-all-fields','prefix-invalidation','COW-no-mutation','release-refcounts','no-inflight-eviction','allocation-failure-atomicity','MLA-storage-formula','MHA-storage-formula','quantized-size-and-scale-overhead','large-integer-ceiling-no-underestimate'],'scope':'CPU reference only','factory_qualification':False}
