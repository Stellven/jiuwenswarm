"""Read bounded GGUF headers; unknown quantization remains an explicit gap."""
import hashlib
import math
from pathlib import Path
import struct

# Storage definitions only, from the source-pinned ggml headers in LAYOUT-SOURCES.json.
# A known layout does not establish a supported or measured GPU kernel.
LAYOUTS = {
    0: ('fp32', 1, 4), 1: ('fp16', 1, 2),
    8: ('q8_0', 32, 34), 13: ('q5_k', 256, 176), 17: ('iq2_xs', 256, 74),
    16: ('iq2_xxs', 256, 66), 19: ('iq1_s', 256, 50),
    21: ('iq3_s', 256, 110), 29: ('iq1_m', 256, 56),
    24: ('int8', 1, 1), 25: ('int16', 1, 2), 26: ('int32', 1, 4),
    27: ('int64', 1, 8), 28: ('fp64', 1, 8), 30: ('bf16', 1, 2),
}


def inspect_gguf(path, expected_header_sha256=None):
    path=Path(path)
    limit=64*1024*1024
    with path.open('rb') as stream:
        def read(n):
            if n<0 or stream.tell()+n>limit: raise ValueError('GGUF header exceeds 64 MiB')
            data=stream.read(n)
            if len(data)!=n: raise ValueError('Truncated GGUF header')
            return data
        def unpack(fmt): return struct.unpack('<'+fmt,read(struct.calcsize('<'+fmt)))[0]
        def text():
            n=unpack('Q')
            return read(n).decode('utf-8')
        formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
        def value(kind,depth=0):
            if depth>2: raise ValueError('Nested GGUF metadata exceeds limit')
            if kind==8:return text()
            if kind==9:
                element=unpack('I');count=unpack('Q')
                if count>1000000:raise ValueError('GGUF array exceeds limit')
                # Retain metadata counts, not the entire tokenizer vocabulary.
                for _ in range(count):value(element,depth+1)
                return {'element_type':element,'count':count}
            if kind not in formats: raise ValueError('Unsupported GGUF metadata type')
            return unpack(formats[kind])
        if read(4)!=b'GGUF' or unpack('I') not in (2,3):raise ValueError('Supported GGUF v2/v3 required')
        count=unpack('Q');kv_count=unpack('Q')
        if count>100000 or kv_count>100000:raise ValueError('GGUF inventory exceeds limit')
        metadata={}
        for _ in range(kv_count):
            key=text()
            if key in metadata: raise ValueError('Duplicate GGUF metadata key')
            metadata[key]=value(unpack('I'))
        tensors=[];names=set()
        for _ in range(count):
            name=text();dims=unpack('I')
            if name in names: raise ValueError('Duplicate GGUF tensor name')
            names.add(name)
            if not 1<=dims<=4:raise ValueError('Invalid GGUF tensor dimensions')
            shape=[unpack('Q') for _ in range(dims)]
            if any(v==0 for v in shape):raise ValueError('Empty tensor')
            kind=unpack('I');offset=unpack('Q')
            tensors.append(dict(name=name,gguf_shape=shape,ggml_type=kind,relative_offset=offset,
                numerical_path=LAYOUTS.get(kind,('unsupported_type_'+str(kind),))[0]))
        alignment=metadata.get('general.alignment',32)
        if type(alignment) is not int or alignment<=0 or alignment>65536 or alignment & (alignment-1):raise ValueError('Invalid alignment')
        base=(stream.tell()+alignment-1)//alignment*alignment
        read(base-stream.tell());stream.seek(0);header_hash=hashlib.sha256(stream.read(base)).hexdigest()
    if expected_header_sha256 is not None and header_hash!=expected_header_sha256:
        raise ValueError('Header identity differs')
    size=path.stat().st_size
    ordered=sorted(tensors,key=lambda t:t['relative_offset'])
    for index,tensor in enumerate(ordered):
        tensor['offset']=base+tensor['relative_offset']
        offset=tensor['offset']
        end=base+ordered[index+1]['relative_offset'] if index+1<len(ordered) else size
        if tensor['relative_offset']%alignment or offset>=size or end<=offset:
            raise ValueError('Invalid or overlapping tensor offset')
        tensor['storage_extent_bytes']=end-offset
        tensor['kernel_qualified']=False
        layout=LAYOUTS.get(tensor['ggml_type'])
        if layout:
            _,block,block_bytes=layout
            if tensor['gguf_shape'][0]%block:
                raise ValueError('Packed row is not block aligned')
            tensor.update(block_elements=block,block_bytes=block_bytes,
                          bytes=math.prod(tensor['gguf_shape'])//block*block_bytes,
                          storage_layout_known=True)
            if offset+tensor['bytes']>end:
                raise ValueError('Tensor extends beyond file or overlaps next tensor')
        else:
            tensor['storage_layout_known']=False
    return dict(kind='actual_gguf_header',header_sha256=header_hash,file_bytes=size,metadata=metadata,tensors=tensors,
        full_weights_digest_verified=False, kernel_qualification='not_established',
        scope='One GGUF file header; not complete model/routing/activation coverage',
        gaps=sorted({'Unqualified kernel path: '+t['numerical_path'] for t in tensors}))
