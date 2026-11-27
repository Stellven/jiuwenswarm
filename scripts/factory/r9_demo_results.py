"""Append Run 2 measurements without changing Run 1's rows or promoting quiet exclusions."""
import argparse
import json
from pathlib import Path

from scripts.factory.r8_demo_results import save

RUN = 'r9-aqbc'


def read(path):
    return json.loads(path.read_bytes())


def normalized(folder, base_pack):
    receipt=read(folder/'load.json')
    speed=read(folder/'speed.json')
    stage=receipt['identity']
    observed=receipt['observed']
    argv=receipt['argv']
    def flag(name):
        return int(argv[argv.index(name)+1])
    settings=dict(ctx=flag('-c'),np=flag('-np'),b=flag('-b'),ub=flag('-ub'),moe_cache_mib=flag('--moe-cache-mib'),
                  fitt=flag('-fitt'),cpu_moe=True)
    device={k:v for k,v in observed['device_mib'].items() if k!='host_compute'}
    base=dict(schema='engine-bench/1',run=RUN,comparison_group=RUN,date=receipt['started_utc'][:10],label='measured',
              engine=dict(name='Run 2 prefix store',image=stage['image_id'],sha256=stage['executable_sha256']),
              pack=base_pack,settings=settings,memory=dict(device=device,budget=110000,fit_margin=110000-sum(device.values())))
    yield dict(base,id=RUN+'/AQBC/load',kind='load',arm='AQBC',metrics=dict(load_s=receipt['load_seconds']),
               source=dict(path=str(folder/'load.json'),record='/load_seconds'))
    for i,row in enumerate(speed['rows']):
        if row['role']=='followup_seed' or row['arm']=='AQB-control' and row['role']=='speed':
            continue
        if 'derived_ttft_ms' not in row:
            raise ValueError(f'Missing shared-clock TTFT in speed row {i}')
        arm='AQB' if row['arm']=='AQB-control' else row['arm']
        yield dict(base,kind='performance',arm=arm,id=f"{RUN}/{arm}/{row['role']}/{row['request']}/{row['repeat']}",
                   request=dict(name=row['request'],state=row['state'],repeat=row['repeat'],n_predict=32,
                                prompt_tokens=row.get('tokenized_prompt_tokens',row['prompt_tokens']),
                                generated_tokens=row['generated_tokens'],cached_tokens=(row.get('reuse') or {}).get('cached_tokens')),
                   metrics=dict(ttft_ms=row['derived_ttft_ms'],total_ms=row['request_total_ms'],
                                decode_tps=row['decode_tokens_per_second'],server_prefill_ms=row['prompt_ms']),
                   quiet=dict(eligible=row['quiet']['status']=='accepted',reason=', '.join(row['quiet']['reasons'])),
                   corrected_verdict=dict(status=row['quiet']['status'],reasons=row['quiet']['reasons']),
                   source=dict(path=str(folder/'speed.json'),record=f'/rows/{i}'),
                   sources=[dict(path=str(folder/'server.log'),record=f"task {(row.get('reuse') or {}).get('task_id')}")],
                   raw={k:row[k] for k in ('arm','role','client_ttft_ms','prompt_ms','generated_tokens','output_sha256')})
    scored=read(folder/'mmlu.json')
    scores = scored['comparison']
    ids = scored['source']['question_ids_in_order']
    if scores['mode'] != 'identity_check' or len(ids) != 250 or list(scored['rows']) != ids[:25]:
        raise ValueError('Incomplete evidence for the 25-question identity check')
    matches = scores['matched_letters']
    passed = scores['status'] == 'passed'
    if scores['question_count'] != 25 or (passed and (matches < 24 or scores['zero_external_reuse'] != 25)):
        raise ValueError('Identity verdict conflicts with the recorded checks')
    if passed and (scores['inherited_correct'], scores['inherited_accuracy']) != (229, 0.916):
        raise ValueError('Inherited accuracy differs from AQB load 8')
    verdict = (f'AQBC accuracy: 91.6% (same as AQB; identity check {matches}/25)'
               if passed else f'AQBC identity check refused ({matches}/25 matching letters)')
    yield dict(base, kind='accuracy', arm='AQBC', id=RUN+'/AQBC/accuracy',
               test='MMLU answer identity', n=25, verdict=verdict,
               acc=scores['inherited_accuracy'] if passed else None,
               source=dict(path=str(folder/'mmlu.json'), record='/comparison'),
               sources=[dict(path=str(folder.parent.parent/'r8-final-bench/mmlu-8.json'), record='/rows')])



def main(folder, datasets):
    first=[json.loads(line) for line in datasets[0].read_text().splitlines()]
    pack=next(row['pack'] for row in first if row['run']=='r8-final-bench' and row['kind']=='load' and row['arm']=='AQB')
    rows=list(normalized(folder,pack))
    for dataset in datasets:
        lines=[line for line in dataset.read_text().splitlines() if json.loads(line).get('run')!=RUN]
        save(dataset,'\n'.join([*lines,*(json.dumps(row) for row in rows)])+'\n')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder',type=Path)
    ap.add_argument('datasets',nargs='+',type=Path)
    opts=ap.parse_args()
    main(opts.folder,opts.datasets)
