#!/usr/bin/env python3
"""Prepare fixed prompts using metadata only; never opens model tensor data."""
import hashlib
import json
from pathlib import Path
import sys

home = Path.home()
strata = home / 'strata-baseline/Strata'
sys.path[:0] = [str(strata), str(strata / 'tools')]
from strata_tokenizer import Tokenizer
from serve.frontend import ChatTemplate
from serve.dsml import pick_template
from gguf_reader import GGUFFile

model = home / 'software-factory-spark-20261113/deepseek-v41-upstream-20261119/converted/DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00001-of-00006.gguf'
metadata = GGUFFile(model).metadata
tok = Tokenizer.from_gguf(model)
root = Path(__file__).resolve().parent
out = root / 'prompts'
out.mkdir(exist_ok=True)
llama_template = out / 'llama-embedded-template.jinja'
llama_template.write_text(metadata['tokenizer.chat_template'])
strata_template = home / 'strata-baseline/Strata-data/packs/deepseek-v4.1-flash-ist-das-2.00bpw/tokenizer/chat_template.jinja'
pack_template = strata_template
strata_template, swapped = pick_template(pack_template)
templates = [ChatTemplate(llama_template), ChatTemplate(strata_template)]
words = ('river stone market lantern copper winter garden signal harbor needle orbit velvet canyon ember ledger quartz meadow anchor violet thunder cedar marble piston ribbon cobalt falcon glacier hollow ivory juniper kernel lattice mirror nectar oasis pepper quarry raven saddle tundra umber vessel willow yellow zephyr').split()
prefix = 'Read this field notebook and explain its recurring themes in a detailed paragraph. Continue for at least one hundred words.\n\n'
records = []
for target in (512, 2048):
    body = ''
    for i in range(target * 2):
        candidate = body + (' ' if body else '') + words[i % len(words)]
        prompt = prefix + candidate
        rendered = templates[0].render([{'role':'user','content':prompt}], enable_thinking=False)
        n = len(tok.encode(rendered, parse_special=True))
        if n > target:
            break
        body = candidate
    prompt = prefix + body
    rendered = templates[0].render([{'role':'user','content':prompt}], enable_thinking=False)
    while len(tok.encode(rendered, parse_special=True)) < target:
        prompt += ' a'
        rendered = templates[0].render([{'role':'user','content':prompt}], enable_thinking=False)
    ids = tok.encode(rendered, parse_special=True)
    assert len(ids) == target, len(ids)
    alternate = templates[1].render([{'role':'user','content':prompt}], enable_thinking=False)
    record = {'target_tokens_including_template':target, 'actual_metadata_token_count':len(ids), 'templates_render_identically':alternate == rendered, 'strata_token_count':len(tok.encode(alternate, parse_special=True)), 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(), 'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest(), 'strata_rendered_sha256':hashlib.sha256(alternate.encode()).hexdigest(), 'token_ids_sha256':hashlib.sha256(json.dumps(ids, separators=(',',':')).encode()).hexdigest()}
    (out/f'{target}.txt').write_text(prompt)
    (out/f'{target}.rendered.txt').write_text(rendered)
    (out/f'{target}.strata-rendered.txt').write_text(alternate)
    (out/f'{target}.tokens.json').write_text(json.dumps(ids))
    records.append(record)
manifest = {'model_metadata_only':str(model), 'template_parameters':{'enable_thinking':False}, 'templates':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (llama_template,strata_template)}, 'prompts':records, 'server_token_counts_pending':True}
(out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
