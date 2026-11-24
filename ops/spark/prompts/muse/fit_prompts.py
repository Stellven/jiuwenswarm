import json, subprocess, sys, hashlib, random
from jinja2 import Environment
W = '/tmp/wt-stock-tools'
MODEL = sys.argv[1]
import re
tpl_src = re.sub(r'\{%-?\s*(end)?generation\s*-?%\}', '',open(f'{W}/muse-embedded.jinja').read())
env = Environment(trim_blocks=True, lstrip_blocks=True)
def raise_exception(m): raise RuntimeError(m)
env.globals['raise_exception'] = raise_exception
tpl = env.from_string(tpl_src)
KW = dict(reasoning_effort='low', current_date='2026-11-30')
def render(text):
    return tpl.render(messages=[{'role': 'user', 'content': text}], add_generation_prompt=True, **KW)
def count(rendered):
    out = subprocess.run([f'{W}/build-cpu/bin/llama-tokenize', '-m', MODEL, '--stdin', '--ids', '--log-disable'],
                         input=rendered.encode(), capture_output=True).stdout.decode()
    return len(json.loads(out.strip().splitlines()[-1]))
src = open(f'{W}/src-2048.txt').read()
head, _, body = src.partition('\n\n')
words = body.split()
while len(words) < 4000: words += body.split()
res = {}
for target in (512, 2048):
    lo, hi = 1, len(words)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count(render(head + '\n\n' + ' '.join(words[:mid]))) <= target: lo = mid
        else: hi = mid - 1
    text = head + '\n\n' + ' '.join(words[:lo])
    n = count(render(text))
    res[target] = n
    open(f'/tmp/muse-{target}.txt', 'w').write(text)
    open(f'/tmp/muse-{target}.rendered.txt', 'w').write(render(text))
print('counts', res)
# calibration: different topics, disjoint from lab prompts
rng = random.Random(7)
topics = ['Explain how a refrigerator moves heat out of its cabinet.', 'Write a short story about a lighthouse keeper who finds a map.',
 'Summarise the causes of the 1929 stock market crash.', 'Write a Python function that merges overlapping intervals and explain it.',
 'Compare the climates of Norway and New Zealand.', 'Describe how vaccines train the immune system.',
 'Translate into French: The train to the coast leaves at seven, so pack tonight.', 'Give a step by step proof that the square root of 2 is irrational.',
 'Draft a polite email asking a landlord to fix a leaking tap.', 'Explain the rules of chess castling to a beginner.',
 'What are the trade-offs between SQL and document databases?', 'Write a haiku sequence about autumn in a city.',
 'Explain how photosynthesis stores energy in sugar.', 'Plan a three day budget trip to Lisbon.',
 'Describe how a compiler turns source code into machine code.', 'Explain supply and demand with a coffee shop example.']
with open('/tmp/muse-calibration.jsonl', 'w') as f:
    for i, t in enumerate(topics):
        f.write(json.dumps(dict(id=f'cal{i:02d}', prompt=t, n_predict=256)) + '\n')
