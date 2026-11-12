"""Engine effective configuration vocabulary shared by probes and lab ingestion."""
ENV_KEYS = {
    'LLAMA_EXPERT_FILL': 'fill', 'LLAMA_EXPERT_FILL_RANDOM': 'random',
    'LLAMA_EXPERT_FILL_THREADS': 'threads', 'LLAMA_EXPERT_FILL_CHUNK_KIB': 'chunk_kib',
    'LLAMA_EXPERT_FILL_MIN_TOKENS': 'min_tokens', 'LLAMA_EXPERT_FILL_MAX_TOKENS': 'max_tokens',
    'LLAMA_EXPERT_FILL_DIAG': 'diag', 'LLAMA_EXPERT_FILL_DIAG_CSV': 'diag_csv',
    'LLAMA_EXPERT_FILL_POPULATE': 'populate', 'LLAMA_EXPERT_PREGATE': 'pregate',
    'LLAMA_EXPERT_PREGATE_K': 'k', 'LLAMA_EXPERT_PREGATE_ORDER': 'order',
    'LLAMA_EXPERT_PREGATE_MAX_INFLIGHT': 'max_inflight',
    'LLAMA_EXPERT_PREGATE_LOOKAHEAD': 'lookahead',
    'LLAMA_EXPERT_PREFETCH': 'prefetch', 'LLAMA_EXPERT_PREFETCH_NEXT': 'prefetch_next',
}

# Defaults from the component's ExpertConfig (patch 08).
DEFAULTS = dict(fill='0', random='0', threads='8', chunk_kib='1024', min_tokens='0',
                max_tokens='0', diag='0', diag_csv='(unset)', populate='0', pregate='0',
                k='8', order='after', max_inflight='4', lookahead='1', prefetch='0', prefetch_next='0')


def parse_effective(stderr):
    import re
    lines = re.findall(r'^expert_config: effective (.*)$', stderr, re.MULTILINE)
    effective = dict(re.findall(r'(\w+)=(.*?)(?= \w+=|$)', lines[0])) if lines else {}
    return lines, effective
