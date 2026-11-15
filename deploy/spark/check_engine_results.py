"""Independent integrity/metric checks for recorded Strata engine cells.

This verifies functional evidence, not a scored A/B performance improvement or
semantic model accuracy. It never launches Docker, reads weights, or edits data.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


class InvalidEvidence(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidEvidence(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise InvalidEvidence('Missing or invalid JSON: ' + str(path)) from exc


def verify_cell(directory, verify_inputs=False):
    directory = Path(directory)
    result = load(directory / 'engine-result.json')
    root = directory / 'engine'
    report = load(root / 'report.json')
    cfg = result['configuration']
    require(result['status'] == 'success', 'Cell did not succeed')
    require(report['reason'] == 'completed' and report['quiescent'], 'Collector not completed/quiescent')
    require(report['container_exit_code'] == 0 and not report['container_oom_killed'], 'Container failed or OOM killed')
    require(result['container_removed'], 'Container removal was not recorded')
    require(result['collector'] == report, 'Embedded collector report differs from retained report')
    require(all(result['input_identity_after'].values()), 'Producer recorded changed input')
    for name, expected in report['artifacts'].items():
        path = root / name
        require(path.is_file() and sha(path) == expected, 'Artifact hash mismatch: ' + name)
    if verify_inputs:
        for name, expected in cfg['pins'].items():
            path = Path(name)
            require(path.is_file(), 'Pinned input is missing: ' + name)
            require(path.stat().st_size <= 64 * 2**20, 'Verifier refuses to hash a weight-sized input')
            require(sha(path) == expected, 'Pinned input hash mismatch: ' + name)
    before, final = load(root / 'inspect-created.json'), load(root / 'inspect-final.json')
    require(before['Id'] == final['Id'] == report['container_id'], 'Container identity differs')
    require(before['Image'] == final['Image'] == cfg['image'], 'Immutable image differs')
    host = before['HostConfig']
    require(host['Memory'] == 104*2**30 and host['MemorySwap'] == host['Memory'], 'Memory/swap boundary differs')
    require(host['NanoCpus'] == 8_000_000_000, 'CPU boundary differs')
    require(host['ReadonlyRootfs'] and host['NetworkMode'] == 'none' and not host['Privileged'], 'Isolation boundary differs')
    require(all(not m['RW'] for m in before['Mounts'] if m['Type'] == 'bind'), 'Writable bind mount')
    require(not final['State']['Running'] and final['State']['Pid'] == 0, 'Final container still running')
    require(final['State']['ExitCode'] == 0 and not final['State']['OOMKilled'], 'Final inspect failed')
    args = cfg['args']
    require('--experts' in args and args[args.index('--experts')+1] == '6', 'Target is not full-six-expert mode')
    stderr = (root/'stderr.log').read_text()
    require('experts per word: 6 (full quality)' in stderr, 'Effective full-quality engagement missing')
    environment = {e.split('=',1)[0]: e.split('=',1)[1] for e in before['Config']['Env'] if '=' in e}
    for key, value in cfg['environment'].items():
        require(environment.get(key) == value, 'Effective environment differs: ' + key)
    require(not any(('SKIP' in key and value not in ('0','')) for key,value in environment.items() if key.startswith(('DS4_','STRATA_DS4_'))), 'Skipping configuration present')
    raw = (root/'stdout.log').read_bytes()
    require(not any(line.startswith(b'ERR') for line in raw.splitlines()), 'Native ERR response')
    ids, rows = [], []
    for line in raw.decode().splitlines():
        if line.startswith('T '):
            ids.append(int(line.split()[1]))
        elif line.startswith('DONE '):
            parts = line.split()
            require(len(parts) == 11, 'Invalid DONE framing')
            count, prompt = int(parts[1]), int(parts[2])
            prompt_ms, decode_ms = float(parts[3]), float(parts[4])
            require(count == len(ids) and 0 < count <= 128, 'DONE/token count or cap differs')
            require(prompt > 0 and math.isfinite(prompt_ms) and prompt_ms > 0 and math.isfinite(decode_ms) and decode_ms > 0, 'Invalid native timing')
            require(parts[5] in ('length','stop') and int(parts[8]) == 0, 'Incomplete request or prefix reuse')
            accepted, offered = int(parts[6]), int(parts[7])
            require(0 <= accepted <= offered, 'Invalid draft counters')
            index = len(rows)
            require(index < len(result['requests']), 'Unexpected native request')
            declared = result['requests'][index]
            require(declared['ids'] == ids and declared['generated_tokens'] == count and declared['prompt_tokens'] == prompt, 'Declared tokens differ from raw stream')
            tps = count * 1000.0 / decode_ms
            require(math.isclose(declared['native_decode_tps'], tps, rel_tol=1e-12), 'Declared decode rate differs from native timing')
            require(math.isclose(declared['native_prefill_tps'], prompt*1000.0/prompt_ms, rel_tol=1e-12), 'Declared prefill rate differs')
            rows.append(dict(generated_tokens=count, prompt_tokens=prompt, decode_ms=decode_ms, decode_tps=tps,
                             accepted_drafts=accepted, offered_drafts=offered,
                             canonical_ids_sha256=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()))
            ids = []
    require(not ids and len(rows) == len(cfg['requests']) == len(result['requests']), 'Missing/extra request completion')
    events=[]
    try:
        events = [json.loads(line) for line in (root/'pipe-events.jsonl').read_text().splitlines()]
        samples = [json.loads(line) for line in (root/'samples.jsonl').read_text().splitlines()]
    except ValueError as exc:
        raise InvalidEvidence('Truncated or invalid telemetry JSONL') from exc
    offsets = dict(stdin=0, stdout=0, stderr=0)
    for index, event in enumerate(events):
        require(event['sequence'] == index, 'Pipe event sequence gap')
        stream = event['stream']
        require(event['offset'] == offsets[stream] and not event.get('truncated',False), 'Pipe offsets/truncation differ')
        offsets[stream] += event['retained_bytes']
    for stream, name in [('stdout','stdout.log'),('stderr','stderr.log'),('stdin','stdin-wire.log')]:
        require(offsets[stream] == (root/name).stat().st_size, 'Pipe event byte coverage differs: ' + stream)
    require(bool(samples), 'No memory telemetry')
    require(all(s['host_kib']['MemAvailable']*1024 >= 8*2**30 for s in samples), 'Host memory guard violated')
    require(all(not s['memory_events'].get(k,0) for s in samples for k in ('oom','oom_kill','oom_group_kill')), 'OOM event present')
    return dict(directory=str(directory),status='functional_evidence_verified',requests=rows,
                total_generated_tokens=sum(r['generated_tokens'] for r in rows),input_hashes_rechecked=verify_inputs,
                semantic_accuracy='not_tested',scored_ab_improvement='not_established',
                host_reboot_or_power_loss_durability='not_tested')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directories', nargs='+', type=Path)
    p.add_argument('--verify-inputs',action='store_true')
    p.add_argument('--output',type=Path)
    a=p.parse_args();results=[]
    for directory in a.directories:
        try:results.append(verify_cell(directory,a.verify_inputs))
        except (InvalidEvidence,KeyError,OSError,ValueError) as exc:
            results.append(dict(directory=str(directory),status='invalid',error=str(exc)))
    data=dict(results=results,all_verified=all(r['status']=='functional_evidence_verified' for r in results))
    if a.output:a.output.write_text(json.dumps(data,indent=2))
    print(json.dumps(dict(all_verified=data['all_verified'],cells=len(results),tokens=sum(r.get('total_generated_tokens',0) for r in results),invalid=[r for r in results if r['status']=='invalid'])))
    return 0 if data['all_verified'] else 1

if __name__=='__main__':raise SystemExit(main())
