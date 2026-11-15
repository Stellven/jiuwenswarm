"""Pinned public ARC sampling and transparent generative correctness adaptation.

ARC-Challenge belongs to AI2 (CC BY-SA 4.0). This module does not implement the
lm-evaluation-harness log-likelihood ARC score. It prepares a bounded, zero-shot
letter-generation regression sample and a llama-bench-inspired pg512/tg128 case.
No model launch or generated code execution occurs here.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

REVISION = '210d026faf9955653af8916fad021475a3f00453'
REPOSITORY = 'allenai/ai2_arc'
LICENSE = 'CC-BY-SA-4.0'
PAGE_SIZE = 100
SELECTION_VERSION = 'sha256(seed-colon-id)-v1'
EXTRACTION_VERSION = 'single-letter-optional-punctuation-v1'
CHAT_PREFIX = '<｜begin▁of▁sentence｜><｜User｜>'
CHAT_SUFFIX = '<｜Assistant｜></think>'
TOKENIZER_REL = 'tokenizer'
PACK = Path('/home/user2/strata-baseline/Strata-data/packs/deepseek-v4.1-flash-ist-das-2.00bpw')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def _write_once(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Refuse to change pinned input: '+str(path))
        return
    with path.open('xb') as stream:
        stream.write(data)


def _download(url, limit=2*1024*1024):
    request = urllib.request.Request(url, headers={'User-Agent': 'SparkFactoryBenchmark/1.0 (public data; no authentication)'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit+1)
        headers = dict(response.headers)
        revision = response.headers.get('x-revision')
    if len(data)>limit:
        raise ValueError('Public dataset response exceeds bound')
    return data, headers, revision


def fetch_split(cache, split, revision=REVISION):
    """Retain exact response bytes, checking every page's immutable dataset revision."""
    if split not in {'test','train'}:
        raise ValueError('Only explicit test/train ARC splits supported')
    cache = Path(cache)
    rows, total, offset, page_receipts = [], None, 0, []
    while total is None or offset<total:
        path = cache/(split+f'-{offset:04d}.json')
        receipt_path = path.with_suffix('.receipt.json')
        query = urllib.parse.urlencode(dict(dataset=REPOSITORY, config='ARC-Challenge', split=split, offset=offset, length=PAGE_SIZE))
        url = 'https://datasets-server.huggingface.co/rows?'+query
        if path.exists() and receipt_path.exists():
            data=path.read_bytes(); receipt=json.loads(receipt_path.read_text())
            if receipt['sha256']!=digest(data) or receipt['revision']!=revision or receipt['url']!=url:
                raise ValueError('Cached ARC source identity differs')
        else:
            data, headers, found_revision = _download(url)
            if found_revision!=revision:
                raise ValueError('Public ARC server revision changed; use a new explicitly pinned dataset version')
            receipt=dict(url=url,revision=found_revision,sha256=digest(data),bytes=len(data),
                         source='Hugging Face official dataset viewer API',content_type=headers.get('Content-Type'))
            _write_once(path,data);_write_once(receipt_path,canonical(receipt)+b'\n')
        document=json.loads(data)
        if document.get('partial') is not False:
            raise ValueError('Partial dataset response cannot define a benchmark')
        found_total=document['num_rows_total']
        if type(found_total) is not int or not 1<=found_total<=10000:
            raise ValueError('Unexpected ARC split size')
        if total is not None and total!=found_total:
            raise ValueError('Dataset size changed during preparation')
        total=found_total; page=document['rows']
        expected=min(PAGE_SIZE,total-offset)
        if len(page)!=expected or any(item['row_idx']!=offset+i for i,item in enumerate(page)):
            raise ValueError('ARC page coverage/index differs')
        for item in page:
            if item.get('truncated_cells'):
                raise ValueError('Truncated dataset text cannot define a benchmark')
            rows.append(item['row'])
        page_receipts.append(receipt)
        offset+=len(page)
    if len({r['id'] for r in rows})!=len(rows):
        raise ValueError('Duplicate ARC question IDs')
    return rows,dict(split=split,total_rows=total,revision=revision,canonical_rows_sha256=digest(canonical(rows)),pages=page_receipts)


def select_rows(rows, count, seed=42):
    if type(count) is not int or count<1 or count>len(rows):
        raise ValueError('Invalid deterministic sample count')
    if len({row['id'] for row in rows})!=len(rows):
        raise ValueError('Duplicate question IDs')
    return sorted(rows,key=lambda row:(digest((str(seed)+':'+row['id']).encode()),row['id']))[:count]


def normalize_question(row):
    labels=row['choices']['label'];texts=row['choices']['text']
    if not isinstance(row.get('id'),str) or not isinstance(row.get('question'),str):
        raise ValueError('Invalid ARC question identity or stem')
    if not 2<=len(labels)<=5 or len(labels)!=len(texts) or len(set(labels))!=len(labels):
        raise ValueError('Invalid ARC choices')
    if not all(isinstance(v,str) and v for v in labels+texts):
        raise ValueError('ARC choices must be nonempty text')
    if row.get('answerKey') not in labels:
        raise ValueError('ARC answer does not identify an offered choice')
    allowed=list('ABCDE'[:len(labels)])
    expected=allowed[labels.index(row['answerKey'])]
    return allowed,expected,[(letter,text) for letter,text in zip(allowed,texts)]


def quality_prompt(row):
    """Ground truth is deliberately not interpolated into the prompt."""
    allowed,expected,choices=normalize_question(row)
    text=('Answer the multiple-choice science question. Reply with only the letter of the best answer '
          '('+', '.join(allowed)+'). Do not include an explanation.\n\n'+row['question']+'\n'
          +'\n'.join(letter+'. '+choice for letter,choice in choices)+'\n\nAnswer: ')
    return CHAT_PREFIX+text+CHAT_SUFFIX


def extract_answer(text, allowed_letters='ABCDE'):
    if not isinstance(text,str):
        raise ValueError('Decoded answer must be text')
    allowed=set(allowed_letters)
    if not allowed or not allowed<=set('ABCDE'):
        raise ValueError('Invalid offered answer letters')
    match=re.fullmatch(r'\s*([A-Ea-e])[.)]?\s*',text)
    if not match:
        return None
    letter=match[1].upper()
    return letter if letter in allowed else None


def decode_answer(ids, tokenizer, allowed_letters='ABCDE', eos_id=1):
    """Stop at the known EOS ID; do not strip arbitrary markup or mine explanations."""
    ids=list(ids)
    if any(type(value) is not int or value<0 for value in ids):
        raise ValueError('Invalid generated token IDs')
    if eos_id in ids:
        ids=ids[:ids.index(eos_id)]
    bos=tokenizer.special_ids.get('bos')
    if ids and bos is not None and ids[0]==bos:
        ids=ids[1:]
    text=tokenizer.decode(ids)
    return dict(text=text,answer=extract_answer(text,allowed_letters))


class DecodeOnlyTokenizer:
    """The reference byte decoder without its encoding-only regex dependency.

    Encoding and prompt preparation continue to use Strata's reference tokenizer.
    Scoring only needs token bytes; special tokens of type 3/4 are UTF-8 literals.
    """
    def __init__(self, vocab, token_types, special_ids=None):
        if (not vocab or set(vocab.values()) != set(range(len(vocab)))
                or len(token_types) != len(vocab)):
            raise ValueError('Malformed decoder vocabulary/type table')
        self.tokens = [None]*len(vocab)
        for token, index in vocab.items(): self.tokens[index] = token
        self.token_types = token_types
        self.special_ids = special_ids or {}
        direct = list(range(33,127))+list(range(161,173))+list(range(174,256))
        missing = [v for v in range(256) if v not in direct]
        self.byte_map = {chr(v):v for v in direct}
        self.byte_map.update({chr(256+i):v for i,v in enumerate(missing)})
        self.cache = {}

    def token_bytes(self, token):
        if type(token) is not int or not 0 <= token < len(self.tokens):
            raise ValueError('Generated token outside decoder vocabulary')
        if token not in self.cache:
            text = self.tokens[token]
            self.cache[token] = (text.encode('utf-8') if self.token_types[token] in (3,4)
                else bytes(self.byte_map[ch] for ch in text))
        return self.cache[token]

    def decode(self, ids):
        return b''.join(self.token_bytes(v) for v in ids).decode('utf-8',errors='replace')


def load_decoder(root, files):
    """Validate frozen tokenizer inputs before dependency-free host scoring."""
    for path, expected in files.items():
        if digest(Path(path).read_bytes()) != expected:
            raise ValueError('Frozen tokenizer input changed: '+path)
    directory = PACK/TOKENIZER_REL
    for name in ('vocab.json','token_type.json','tokenizer.json'):
        if str(directory/name) not in files:
            raise ValueError('Pinned decoder table missing: '+name)
    return DecodeOnlyTokenizer(json.loads((directory/'vocab.json').read_text()),
        json.loads((directory/'token_type.json').read_text()),
        json.loads((directory/'tokenizer.json').read_text()).get('special_ids'))


def load_tokenizer(root):
    root=Path(root)
    module=root/'sources/strata-deepseek/tools/strata_tokenizer.py'
    spec=importlib.util.spec_from_file_location('spark_benchmark_strata_tokenizer',module)
    imported=importlib.util.module_from_spec(spec);spec.loader.exec_module(imported)
    directory=PACK/TOKENIZER_REL
    vocab=json.loads((directory/'vocab.json').read_text());config=json.loads((directory/'tokenizer.json').read_text())
    tokens=[None]*len(vocab)
    for token,index in vocab.items():tokens[index]=token
    tokenizer=imported.Tokenizer(tokens,(directory/'merges.txt').read_text().split('\n'),
        json.loads((directory/'token_type.json').read_text()),config['pre'],config.get('special_ids'))
    reference=json.loads((root/'notes/port-smoke-workload.json').read_text())
    if tokenizer.encode(reference['prompt'],parse_special=True)!=reference['ids']:
        raise ValueError('Tokenizer does not reproduce prior trusted IDs')
    return tokenizer


def make_quality_case(row, tokenizer, split):
    allowed,expected,_=normalize_question(row);prompt=quality_prompt(row)
    ids=tokenizer.encode(prompt,parse_special=True)
    if tokenizer.decode(ids)!=prompt:
        raise ValueError('Tokenizer round trip differs')
    return dict(id=row['id'],kind='quality',split=split,prompt=prompt,ids=ids,max_new_tokens=8,
                allowed_letters=allowed,expected_letter=expected,original_answer_key=row['answerKey'])


def make_speed_cases(tokenizer, source):
    """A complete natural-text chat prompt at exactly 512 tokens, repeated four times."""
    prefix=(CHAT_PREFIX+'Write a detailed explanation of at least 500 words about how GPU memory, system RAM, '
        'and storage cooperate to run a large language model. Explain the tradeoffs in several long paragraphs. '
        'Use the following technical background as context.\n\n')
    suffix='\n\nNow write the detailed explanation in at least 500 words.\n'+CHAT_SUFFIX
    words=source.split();best=None
    for count in range(1,len(words)+1):
        body=' '.join(words[:count]);prompt=prefix+body+suffix;ids=tokenizer.encode(prompt,parse_special=True)
        if len(ids)<=512:best=(body,prompt,ids)
        if len(ids)==512:break
        if len(ids)>520:break
    if best is None:raise ValueError('Speed chat framing exceeds 512 tokens')
    body,prompt,ids=best
    if len(ids)!=512:
        for padding in range(1,65):
            candidate=prefix+body+' detail'*padding+suffix
            candidate_ids=tokenizer.encode(candidate,parse_special=True)
            if len(candidate_ids)==512:
                prompt,ids=candidate,candidate_ids;break
        else:raise ValueError('Could not form exact512-token chat prompt')
    if tokenizer.decode(ids)!=prompt or not prompt.startswith(CHAT_PREFIX) or not prompt.endswith(CHAT_SUFFIX):
        raise ValueError('Speed prompt framing or round trip invalid')
    return [dict(id='pg512-tg128-'+str(i),kind='speed',phase='warmup' if i==0 else 'measured',
        prompt=prompt,ids=list(ids),max_new_tokens=128) for i in range(4)]


def prepare(root, output):
    root=Path(root).resolve();output=Path(output).resolve()
    if output.suffix!='.json':output=output/'dataset.json'
    cache=output.parent/'public-source'
    test,test_provenance=fetch_split(cache,'test');train,train_provenance=fetch_split(cache,'train')
    card_url=f'https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/README.md'
    card=cache/'README.md'
    if not card.exists():
        body,_,_=_download(card_url);_write_once(card,body)
    if b'cc-by-sa-4.0' not in card.read_bytes().lower():raise ValueError('Pinned dataset card license missing')
    tokenizer=load_tokenizer(root)
    selected=select_rows(test,64);pilot=select_rows(train,2)
    if set(r['id'] for r in selected)&set(r['id'] for r in pilot):raise ValueError('Pilot/test IDs overlap')
    source=root/'sources/strata-deepseek/docs/HOW_IT_WORKS.md'
    license_path=root/'sources/strata-deepseek/LICENSE'
    tokenizer_paths=[root/'sources/strata-deepseek/tools/strata_tokenizer.py',
        *[PACK/'tokenizer'/name for name in ['tokenizer.json','vocab.json','merges.txt','token_type.json']]]
    value=dict(schema_version=1,benchmark_id='arc-challenge64-generation-pg512-tg128-v1',
        quality=[make_quality_case(row,tokenizer,'test') for row in selected],
        pilot=[make_quality_case(row,tokenizer,'train') for row in pilot],
        speed=make_speed_cases(tokenizer,source.read_text()),
        provenance=dict(dataset_repository=REPOSITORY,dataset_revision=REVISION,license=LICENSE,
            attribution='AI2 Reasoning Challenge (ARC), Peter Clark et al., 2018; allenai/ai2_arc.',
            dataset_card_url=card_url,dataset_card_sha256=digest(card.read_bytes()),
            splits=[test_provenance,train_provenance],selection=dict(version=SELECTION_VERSION,seed=42,
                test_count=64,test_ids=[row['id'] for row in selected],pilot_train_ids=[row['id'] for row in pilot]),
            extraction_version=EXTRACTION_VERSION,
            speed_source=dict(path=str(source),sha256=digest(source.read_bytes()),license='MIT',
                license_sha256=digest(license_path.read_bytes()),
                upstream='https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/docs/HOW_IT_WORKS.md'),
            tokenizer=dict(files={str(path):digest(path.read_bytes()) for path in tokenizer_paths},
                pre=tokenizer.pre if hasattr(tokenizer,'pre') else 'deepseek3',special_ids=tokenizer.special_ids,
                trusted_prompt_ids_reproduced=True)),
        methodology=dict(quality='Zero-shot short letter generation on a deterministic64-question ARC-Challenge test sample.',
            official_arc_score=False,official_lm_eval_loglikelihood=False,
            speed='Combined pg512/tg128 adaptation inspired by llama-bench; real text and native Strata sampling.',
            official_llama_bench=False,speed_repetitions=4,speed_warmups=1,speed_measured=3,
            limitations=['Not the complete ARC-Challenge benchmark or official lm-eval score.',
                'No statistical/general-quality guarantee from this small regression sample.',
                'Strata native timings include its sampling path; literal llama-bench timings exclude sampling.']))
    _write_once(output,json.dumps(value,ensure_ascii=False,indent=2).encode()+b'\n')
    _write_once(output.parent/'ARC-LICENSE-ATTRIBUTION.txt',
        ('ARC-Challenge is by AI2, licensed CC BY-SA4.0.\n'
         'Dataset: https://huggingface.co/datasets/allenai/ai2_arc\n'
         'License: https://creativecommons.org/licenses/by-sa/4.0/\n'
         'Citation: Clark et al. (2018), Think you have Solved Question Answering? Try ARC, the AI2 Reasoning Challenge.\n'
         'This artifact adapts labels to A-E and samples64 test questions; source response files and IDs are retained.\n').encode())
    _write_once(output.parent/'STRATA-MIT-LICENSE.txt',license_path.read_bytes())
    return value
