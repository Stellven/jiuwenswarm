"""Copy actual night JSONs into a new owned Store and call the digest native CC.

No original mission Store is opened. Source files are read-only inputs. Byte
counts describe serialization, not provider tokens, scientific quality or speed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.evidence_digest import encoded, select
from jiuwenswarm.factory.store import Store

REPO=Path(__file__).resolve().parents[1]
SOURCE=REPO.parents[1]/'night-branch-jiuwen-v1/factory/agent-workspace/inputs'
SPECS=[('engine-analysis','engine-analysis.json',['/pooled','/exact_tokens','/limitations','/promotion_authorized']),
       ('quality-analysis','extra-2-analysis.json',['/all_answers_valid','/per_question_regressions','/fewshot','/exact_tokens','/limitations','/promotion_authorized']),
       ('factory-analysis','extra-3-measurements.json',['/scope','/python','/platform','/comparisons','/negative_checks','/instrumented_fixture','/rss_scope','/gpu_tested','/admission_granted','/input_sha256','/fixture_sha256'])]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--source-dir',default=str(SOURCE),help='Use retained source-copies to reproduce without the original mission')
    args=parser.parse_args()
    source_dir=Path(args.source_dir).resolve()
    output=Path(args.output_dir).resolve()
    if output.exists():raise ValueError('Use a new owned qualification directory')
    output.mkdir(parents=True)
    (output/'source-copies').mkdir()
    originals,origins,sources=[],[],[]
    with Store(output/'factory') as store:
        store.create_task({'task_id':'digest-qualification','objective':'Exact CPU projection of copies of night evidence'})
        for identity,name,pointers in SPECS:
            path=source_dir/name
            raw=path.read_bytes()
            value=json.loads(raw)
            originals.append(value)
            (output/'source-copies'/name).write_bytes(raw)
            record=store.put_artifact('digest-qualification',identity,raw,'application/json',None)
            assert record['sha256']==hashlib.sha256(raw).hexdigest()
            origins.append({'artifact_id':identity,'source_path':str(path),'source_sha256':record['sha256'],'raw_bytes':len(raw)})
            sources.append({'artifact_id':identity,'pointers':pointers})
    os.environ.update(FACTORY_HOME=str(output/'factory'),FACTORY_TASK_ID='digest-qualification',FACTORY_READ_TASKS='',FACTORY_PYTHON=sys.executable)
    host=Host(output/'ccstore',python=sys.executable)
    release=host.prepare(REPO/'jiuwenswarm/factory/ccs/evidence_digest_lab')
    inputs={'sources':sources,'max_output_bytes':32768}
    index=host.call(release,'index',{'artifact_ids':[s['artifact_id'] for s in sources]},grants=['process.exec'])
    receipt=host.call(release,'project',inputs,grants=['process.exec'])
    assert index['state']=='succeeded',index
    assert receipt['state']=='succeeded',receipt
    result=receipt['outputs']['result']
    for original,source,origin in zip(originals,result['sources'],origins):
        assert source['source_sha256']==origin['source_sha256']
        for row in source['selections']:
            assert row['value']==select(original,row['pointer'])
            assert row['value_json_sha256']==hashlib.sha256(encoded(row['value'])).hexdigest()
    bad=host.call(release,'project',{'sources':[{'artifact_id':'engine-analysis','pointers':['/nonexistent']}]},grants=['process.exec'])
    assert bad['state']=='failed',bad
    serialized_inputs=encoded(originals)
    native_success=encoded({'outcome':'ok','outputs':receipt['outputs']})
    report={'scope':'Exact CPU JSON projection on read-only copies; source field equality verified; no scientific summaries or model token/latency savings inferred',
            'release':release,'origins':origins,'inputs':inputs,
            'serialized_parsed_input_documents_bytes':len(serialized_inputs),
            'source_raw_bytes':sum(s['raw_bytes'] for s in origins),
            'projected_native_success_envelope_bytes':len(native_success),
            'projected_result_bytes':len(encoded(result)),
            'source_field_equality':True,'source_hash_equality':True,
            'missing_pointer_rejected':True,'failed_call':bad['call'],
            'index_call':index['call'],'project_call':receipt['call'],
            'gpu_executed':False,'frozen_mission_mutated':False}
    (output/'projection.json').write_bytes(encoded(result)+b'\n')
    (output/'index.json').write_bytes(encoded(index['outputs']['result'])+b'\n')
    (output/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
