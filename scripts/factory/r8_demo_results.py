"""Publish the two-arm demo slice from the closed final benchmark."""
import json
from pathlib import Path
from statistics import median

from jiuwenswarm.factory.ccs.paired_accuracy import paired

RUN = 'r8-final-bench'


def read(path):
    return json.loads(path.read_bytes())


def save(path, text):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def timed_rows(lab, arm, lid, census):
    receipt = read(lab / f'{lid}.load.json')
    speed = read(lab / f'{lid}.speed.json')
    clock = read(lab / f'{lid}.ttft.json')
    clocks = {row['source_pointer']: (i, row) for i, row in enumerate(clock['rows'])}
    leg, pack, obs = receipt['load'], receipt['pack'], receipt['observed']
    identity = speed['rows'][0]
    device = {k: v for k, v in obs['device_mib'].items() if k != 'host_compute'}
    prefix = f'{RUN}/{arm}'
    base = dict(schema='engine-bench/1', run=RUN, comparison_group=RUN, date=receipt['utc'][:10],
                arm=arm, label='measured',
                engine=dict(name='R8', binary='llama-server', commit=identity['engine_source_commit'],
                            sha256=identity['llama_server_sha256'], image=identity['image_id']),
                pack=dict(name=leg['pack'], bytes=pack['bytes'], manifest_sha256=pack['manifest_sha256'],
                          first_shard=pack['first_shard'], census=census),
                settings=dict(b=leg['batch'], ub=leg['ubatch'], ctx=leg['ctx'], np=leg['np'],
                              moe_cache_mib=leg['moe_cache_mib'], cpu_moe=True,
                              fitt=int(receipt['argv'][receipt['argv'].index('-fitt') + 1])),
                memory=dict(device=device, budget=110000, fit_margin=110000-sum(device.values()),
                            peak_rss=receipt['peak_process_rss_bytes']/2**20,
                            min_available=receipt['min_available_bytes']/2**20,
                            peak_cgroup_mib=receipt['peak_memory_bytes']/2**20))
    yield dict(base, id=f'{prefix}/load', kind='load', metrics={'load_s': receipt['ready_s']},
               source=dict(path=str(lab / f'{lid}.load.json'), record='/ready_s'))
    for index, raw in enumerate(speed['rows']):
        if raw['request'] not in ('p512', 'p2048'):
            continue
        pointer = f'/rows/{index}'
        clock_index, ttft = clocks[pointer]
        quiet = raw['quiet']
        request = dict(name=raw['request'], prompt_tokens=raw['prompt_tokens'], state=raw['state'],
                       repeat=raw['repeat'], generated_tokens=raw['generated_tokens'], n_predict=raw['n_predict'])
        yield dict(base, id=f"{prefix}/{raw['request']}/{raw['state']}/{raw['repeat']}", kind='performance',
                   request=request, source=dict(path=str(lab / f'{lid}.speed.json'), record=pointer),
                   sources=[dict(path=str(lab / f'{lid}.ttft.json'), record=f'/rows/{clock_index}')],
                   metrics=dict(ttft_ms=ttft['derived_ttft_ms'], total_ms=raw['request_total_ms'],
                                decode_tps=raw['decode_tokens_per_second'], prefill_tps=raw['prompt_tokens_per_second'],
                                server_prefill_ms=raw['prompt_ms']),
                   quiet=dict(eligible=quiet['status']=='accepted', reason=', '.join(quiet['reasons'])),
                   corrected_verdict=dict(status=quiet['status'], reasons=quiet['reasons']),
                   raw={k:v for k,v in raw.items() if isinstance(v,(str,float,int)) and k != 'text_head'})


def main():
    home = Path.home() / 'muse-demo'
    final, lab = home/'r8-final', home/'lab'/RUN
    if read(lab/'8.load.json')['status'] != 'complete':
        raise ValueError('Accuracy load has not closed successfully')
    observations = read(final/'graph/records/observations.json')
    before = next(o['values']['manifest']['census_by_type'] for o in observations
                  if o['obs_id'] == '8488b01eaf304a29be1773d5983a7a32')
    mixed = read(final/'curated-replay/projections/mixed-pack-census.json')['census']
    after = {}
    for family in mixed.values():
        for kind, n in family.items():
            after[kind] = after.get(kind, 0) + n
    rows = [*timed_rows(lab, 'A', 5, before), *timed_rows(lab, 'AQB', 3, after)]
    ref, cand = [read(lab/f'mmlu-{name}.json') for name in ('historical-A','8')]
    ids = ref['source']['question_ids_in_order']
    if cand['status'] != 'complete' or ids != cand['source']['question_ids_in_order'] or len(ids) != 250:
        raise ValueError('Accuracy question order or completion differs')
    look = paired.look(ref['rows'], cand['rows'], ids, 5, final=True)
    # Display observed answer counts. Only the recorded verifier can supply its decision.
    look['decision'] = read(lab/'mmlu-paired.json')['decision']
    accuracy = dict(schema='engine-bench/1', id=f'{RUN}/AQB/accuracy', run=RUN, arm='AQB', kind='accuracy',
                    label='measured', test='Paired MMLU', n=look['n'], acc=look['acc_cand'], reference_acc=look['acc_ref'],
                    delta=look['loss_pts']/100, interval=dict(lo=look['lo_pts']/100, hi=look['hi_pts']/100),
                    margin=.05, verdict=look['decision'],
                    source=dict(path=str(lab/'mmlu-8.json'), record='/rows'),
                    sources=[dict(path=str(lab/'mmlu-historical-A.json'), record='/rows')])
    rows.append(accuracy)
    cells = []
    for arm in ('A','AQB'):
        for name in ('p512','p2048'):
            for state in ('cold','warm'):
                match = [r for r in rows if r['kind']=='performance' and r['arm']==arm and r['request']['name']==name
                         and r['request']['state']==state and r['quiet']['eligible']]
                if match:
                    cells.append(dict(arm=arm, request=name, state=state, prompt_tokens=match[0]['request']['prompt_tokens'],
                                      generated_tokens=32, sources=[r['source'] for r in match],
                                      **{k:median(r['metrics'][k] for r in match) for k in ('ttft_ms','decode_tps','total_ms')}))
    report = dict(format=RUN, ended_utc=read(lab/'8.load.json')['ended_utc'], cells=cells, accuracy=look,
                  accuracy_sources=[accuracy['source'], *accuracy['sources']])
    history = final/'history/graph-lab'
    history.mkdir(parents=True,exist_ok=True)
    for name in ['report.json','engine-bench.jsonl','README.md','AUDIT.md']:
        if not (history/name).exists():
            (history/name).write_bytes((final/name).read_bytes())
    save(final/'report.json',json.dumps(report, indent=2)+'\n')
    serial = ''.join(json.dumps(r)+'\n' for r in rows)
    save(final/'engine-bench.jsonl',serial)
    readme = [
        '# Muse Spark Open · R8 engine factory', '',
        '8 of 8 nodes complete · Engine image delivered · Lab measured', '',
        'The pack compiler produced a 267.2 GB mixed 2-bit pack from 528.9 GB of NVFP4 weights. R8 checked and reused that pack, then planned a larger prefill microbatch.',
        'Both speed arms used the delivered engine image and generated 32 tokens per prompt.', '',
        '| Prompt | Warm result | A · NVFP4 | AQB · mixed 2-bit + prefill |',
        '| --- | --- | ---: | ---: |',
    ]
    for name in ('p512', 'p2048'):
        warm = {r['arm']: r for r in cells if r['request']==name and r['state']=='warm'}
        if set(warm) == {'A','AQB'}:
            for key, label, scale in [('ttft_ms','First token (s)',1000),('decode_tps','Decode (tokens/s)',1),
                                      ('total_ms','Total time (s)',1000)]:
                readme.append(f"| {name[1:]} | {label} | {warm['A'][key]/scale:.2f} | {warm['AQB'][key]/scale:.2f} |")
    readme += ['', f"MMLU zero-shot, {look['n']} questions: {100*look['acc_ref']:.1f}% vs {100*look['acc_cand']:.1f}% (A vs AQB).",
               '', '## Demo', '',
               'Start with the ten-step Factory Runs replay, open Capability Capsules, then compare the two arms in the Engine Report.',
               '', '## Files', '',
               '- [Final results](report.json) and [Engine Report dataset](engine-bench.jsonl)',
               '- [Ten-step Factory Runs replay](curated-replay/replay.json)',
               '- [Recorded graph](graph/) and [engine and pack manifests](manifests/)',
               '- [Final benchmark measurements](../lab/r8-final-bench/) and [historical NVFP4 accuracy](../acc/state.json)',
               '- [Original graph lab report](history/graph-lab/report.json) and [delivery mailbox](mailbox/)',
               '- [Presenter screenshots](screenshots/)']
    save(final/'README.md', '\n'.join(readme)+'\n')
    dataset = home/'bench/engine-bench.jsonl'
    past = [line for line in dataset.read_text().splitlines() if json.loads(line)['run'] != RUN]
    save(dataset,'\n'.join(past)+'\n'+serial)


if __name__ == '__main__':
    main()
