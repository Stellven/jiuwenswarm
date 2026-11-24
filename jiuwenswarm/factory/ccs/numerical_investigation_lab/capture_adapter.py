"""Pinned DS4_SERVE_DUMP adapter. Planning and offline import never launch engines."""
import base64
import copy
import hashlib
import json
import math
import os
import stat
from pathlib import Path
import re
import struct
import sys

SOURCE_MAIN_SHA256 = 'fb3ff96a416b8efe077c5eecffd1bdbdf957ebc36cd8ae7f8ff86e50a4aa3973'
MAX_BYTES = 256 * 1024 * 1024
MARKER = 'STRATA_NUMERICAL_CAPTURE '


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_profile(profile):
    require(type(profile) is dict, 'profile object required')
    args = profile.get('args')
    require(type(args) is list and 1 <= len(args) <= 256 and all(type(v) is str and v and '\0' not in v and '\n' not in v for v in args), 'invalid argv')
    def flag(name):
        require(args.count(name) == 1 and args.index(name)+1 < len(args), 'one explicit ' + name + ' required')
        return args[args.index(name)+1]
    for key, value in {'--dspark':'none', '--experts':'6', '--mmap-experts':'on', '--cpu-threads':'8', '--reserve-mib':'16384', '--vram-experts':'1.0', '--dspark-conf':'0.65'}.items():
        require(flag(key) == value, 'fixed no-drafting/full-six profile changed: '+key)
    require(flag('--prefill-chunk') in ('256','512','1024'), 'bounded prefill chunk required')
    require(args.count('--no-expert-cache') == 1 and not any('skip' in a.lower() for a in args if a.startswith('--')), 'static full target required')
    require('--parallel' not in args or flag('--parallel') == '1', 'dump requires single conversation')
    require(('environment' in profile) != ('env' in profile), 'one environment mapping required')
    env = profile.get('environment', profile.get('env'))
    allowed = {'DS4_ASYNC_T','DS4_UMA_HEADROOM_GIB','DS4_STORE_GB','DS4_COPY_ALL','DS4_AHEAD','DS4_ENGRAM_THREADS','DS4_ENGRAM_CACHE_MB','STRATA_DS4_REUSE','DS4_EXPERT_BUDGET_BYTES'}
    require(type(env) is dict and not set(env)-allowed and all(type(v) is str and '\0' not in v and '\n' not in v for v in env.values()), 'unapproved environment override')
    for key,value in {'STRATA_DS4_REUSE':'0','DS4_UMA_HEADROOM_GIB':'16','DS4_COPY_ALL':'0','DS4_STORE_GB':'0'}.items():
        require(env.get(key) == value, 'fixed environment changed: '+key)
    if 'DS4_EXPERT_BUDGET_BYTES' in env:
        value=env['DS4_EXPERT_BUDGET_BYTES']
        require(re.fullmatch('[1-9][0-9]{0,11}',value) and 2**30 <= int(value) <= 128*2**30, 'invalid fixed budget')
    return 'environment' if 'environment' in profile else 'env'


def validate_context(spec, arm, profile):
    from components import validate_spec
    validate_spec(spec)
    require(arm in ('baseline','candidate'), 'arm must be baseline/candidate')
    require(spec['step'] == 49, 'initial native adapter supports only zero-based step49')
    validate_profile(profile)
    require(spec[arm+'_identity']['profile'] in (digest(profile), 'sha256:'+digest(profile)), 'profile identity must bind exact supplied profile SHA256')


def capture_plan(profile, spec, arm, dump_prefix):
    validate_context(spec,arm,profile)
    require(type(dump_prefix) is str and len(dump_prefix) <= 256 and Path(dump_prefix).is_absolute() and not any(c in dump_prefix for c in ('\n','\0')), 'absolute bounded dump prefix required')
    observed=copy.deepcopy(profile)
    observed['environment' if 'environment' in profile else 'env']['DS4_SERVE_DUMP']=dump_prefix
    request='GEN 50 temperature=0 top_p=1 top_k=1 min_p=0 seed=42 spec=0 '+','.join(map(str,spec['prompt_ids']))
    return dict(profile=observed, request=request, quit_request='QUIT', dump_path=dump_prefix+'.1.f32',
        source_main_sha256=SOURCE_MAIN_SHA256, step=49, expected_rows=50,
        vocabulary_size=spec['vocabulary_size'], executed=False,
        limitations=['DS4_SERVE_DUMP captures every row; observer can synchronize and change timing.',
                    'No teacher forcing: import requires generated tokens0..48 equal the frozen teacher history.',
                    'Source-file pin is not proof of binary/model/tokenizer identity; retain image/build witnesses.',
                    'Observer-off/on comparison is required; this capture cannot establish performance.'])


def witness(raw, vocabulary_size, step=49):
    require(sys.byteorder == 'little', 'native dump adapter requires little-endian host')
    require(type(vocabulary_size) is int and 2 <= vocabulary_size <= 262144 and step == 49, 'unsupported dimensions')
    width=vocabulary_size*4
    require(len(raw) <= MAX_BYTES and len(raw) == 50*width, 'dump truncated, oversized or wrong row count')
    row=raw[step*width:(step+1)*width]
    values=struct.unpack('<'+'f'*vocabulary_size,row)
    require(all(math.isfinite(x) for x in values), 'nonfinite selected logits')
    return dict(format='strata-native-logit-row/1', row_index=step, vocabulary_size=vocabulary_size,
        rows=50, raw_size=len(raw), raw_sha256=sha(raw), row_sha256=sha(row),
        row_f32_base64=base64.b64encode(row).decode(), source_main_sha256=SOURCE_MAIN_SHA256)


def read_contained(root, relative, limit):
    require(type(relative) is str and relative and not Path(relative).is_absolute(), 'relative evidence path required')
    root=Path(root).resolve(strict=True)
    require(root.is_dir(), 'evidence root must be a directory')
    path=(root/relative).resolve(strict=True)
    require(path.is_relative_to(root), 'evidence escapes root')
    flags=os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path,flags),'rb') as stream:
        before=os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'evidence must be a regular file')
        require(before.st_size <= limit, 'evidence file exceeds bound')
        # A raced ancestor replacement must not redirect the opened descriptor.
        opened=Path('/proc/self/fd/'+str(stream.fileno())).resolve(strict=True)
        require(opened.is_relative_to(root), 'opened evidence escapes root')
        raw=stream.read(limit+1)
        after=os.fstat(stream.fileno())
        require(len(raw) <= limit, 'evidence file exceeds bound')
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and
                len(raw)==before.st_size, 'evidence changed during read')
        return raw


def import_capture(spec, arm, evidence_root, dump_path, transcript_path, stdin_path, profile, source_main_sha256):
    validate_context(spec,arm,profile)
    require(source_main_sha256 == SOURCE_MAIN_SHA256, 'unsupported native source identity')
    raw=read_contained(evidence_root,dump_path,MAX_BYTES)
    transcript=read_contained(evidence_root,transcript_path,4*1024*1024)
    stdin=read_contained(evidence_root,stdin_path,1024*1024)
    expected=capture_plan(profile,spec,arm,'/tmp/identity-only')['request']+'\nQUIT\n'
    wire = stdin.decode('utf-8')
    # The recorder sends a line ending in byte10 before the native request.
    gate = 'FACTORY_EXEC' + chr(10)
    if wire.startswith(gate):
        wire = wire[len(gate):]
    require(wire == expected, 'native stdin does not match frozen request and prompt')
    text=transcript.decode('utf-8')
    tokens=[]; done=[]
    for line in text.splitlines():
        if line.startswith('ERR'):
            raise ValueError('native transcript contains error')
        if line.startswith('T '):
            require(re.fullmatch(r'T [0-9]+',line), 'malformed native token')
            tokens.append(int(line[2:]))
        if line.startswith('DONE '):
            done.append(line.split())
    require(len(done)==1 and len(tokens)==50, 'exactly one completed50-token native request required')
    d=done[0]
    require(len(d)==11 and d[1]=='50' and d[2]==str(len(spec['prompt_ids'])) and d[5]=='length' and d[6:8]==['0','0'], 'wrong completion, prompt or draft count')
    require(tokens[:49]==spec['teacher_ids'][:49], 'native output does not match common teacher history')
    require(all(0<=x<spec['vocabulary_size'] for x in tokens), 'native token outside vocabulary')
    if raw.startswith(b'{'):
        def unique(pairs):
            out={}
            for key,value in pairs:
                require(key not in out, 'duplicate wrapper witness key')
                out[key]=value
            return out
        def reject(value):
            raise ValueError('nonfinite wrapper witness constant')
        record=json.loads(raw,object_pairs_hook=unique,parse_constant=reject)
        require(set(record)=={'format','row_index','vocabulary_size','rows','raw_size','raw_sha256','row_sha256','row_f32_base64','source_main_sha256'}, 'wrapper witness schema mismatch')
        require(record['format']=='strata-native-logit-row/1' and record['row_index']==49 and record['vocabulary_size']==spec['vocabulary_size'] and record['rows']==50 and record['raw_size']==50*spec['vocabulary_size']*4 and record['source_main_sha256']==SOURCE_MAIN_SHA256, 'wrapper dimensions/source mismatch')
        require(re.fullmatch('[0-9a-f]{64}',record['raw_sha256']) is not None, 'raw digest missing')
        row=base64.b64decode(record['row_f32_base64'],validate=True)
        require(len(row)==4*spec['vocabulary_size'] and sha(row)==record['row_sha256'], 'wrapper row hash/length mismatch')
        raw_verified=False
    else:
        record=witness(raw,spec['vocabulary_size'])
        row=base64.b64decode(record['row_f32_base64'])
        raw_verified=True
    logits=list(struct.unpack('<'+'f'*spec['vocabulary_size'],row))
    require(all(math.isfinite(v) for v in logits), 'nonfinite selected logits')
    capture=dict(identity=spec[arm+'_identity'], spec_sha256=digest(spec), history_ids=spec['history_ids'],
        step=49, vocabulary_ids=list(range(spec['vocabulary_size'])), logits=logits, complete=True,
        capture_id='sha256:'+digest(dict(dump_sha256=sha(raw),transcript_sha256=sha(transcript),stdin_sha256=sha(stdin),spec_sha256=digest(spec))))
    return dict(capture=capture, provenance=dict(raw_size=record['raw_size'],raw_sha256=record['raw_sha256'],
        row_sha256=sha(row),transcript_sha256=sha(transcript),stdin_sha256=sha(stdin),artifact_sha256=sha(raw),
        source_main_sha256=SOURCE_MAIN_SHA256,profile_sha256=digest(profile),full_raw_hash_recomputed=raw_verified,
        identity_authenticated=False, observer_parity_verified=False,
        scope='Native capture import with caller-supplied build/model/tokenizer identity; no provenance authentication or performance claim.'))
