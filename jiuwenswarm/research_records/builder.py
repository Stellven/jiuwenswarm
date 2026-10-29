"""Best-effort independent builder, consuming detached committed records only."""
import json
import hashlib
import os
from pathlib import Path

from .conformance import build_conformance
from .scorecard import build_scorecard


class DerivedBuilder:
    def __init__(self, destination, validate):
        self.destination=Path(destination);self.validate=validate
        self.destination.mkdir(parents=True,exist_ok=True,mode=0o700)

    def publish(self, contract, value):
        self.validate(contract,value)
        data=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode("utf-8")
        name=value["id"].replace(":","_")+".json"
        if "/" in name or "\\" in name or ".." in name: raise ValueError("unsafe derived identity")
        target=self.destination/name
        with target.open("xb") as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        return target

    def scorecards(self, source, records_ref):
        groups={};all_rows=list(source.iter_records());by_ref={(e['ref']['id'],e['ref']['sha256']):e for e in all_rows}
        verdicts={};checks={}
        def key(pin):return pin['id'],pin['sha256']
        try:
            snapshot=source.read_blob(records_ref)
            if hashlib.sha256(snapshot).hexdigest()!=records_ref['sha256']:raise ValueError('records snapshot changed')
            captured=[json.loads(line) for line in snapshot.splitlines()]
            for envelope in [e for e in all_rows if e['kind']=='capsule-run-record']:
                record=envelope['record']
                if record not in captured:continue # An exact earlier snapshot has a smaller population.
                links=[e['record'] for e in all_rows if e['kind']=='capsule-run-record-link' and e['record']['completed_ref']==envelope['ref']]
                if len(links)!=1 or record.get('failure_class') is None:raise ValueError('completed record link unavailable')
                link=links[0];original=by_ref.get(key(link['observation_ref']))
                if original is None or original['kind']!='invocation-observation' or original['record']['id']!=record['id']:raise ValueError('original observation join differs')
                own_snapshot=source.read_blob(link['records_snapshot_ref'])
                if hashlib.sha256(own_snapshot).hexdigest()!=link['records_snapshot_ref']['sha256'] or record not in [json.loads(line) for line in own_snapshot.splitlines()]:raise ValueError('completion snapshot join differs')
                gates=[]
                for pin in link['decision_refs']:
                    entry=by_ref.get(key(pin))
                    if entry is None or entry['kind']!='gate-decision' or link['observation_ref'] not in entry['record']['invocation_refs']:raise ValueError('original gate join differs')
                    gates.append(entry['record'])
                chosen=[g for g in gates if g['scope_kind']=='subnode'] or gates
                order={'PASS':0,'PASS_WITH_KNOWN_LIMITATIONS':1,'INCONCLUSIVE':2,'ENVIRONMENT_BLOCKED':3,'FAIL':4}
                if chosen:verdicts[record['id']]=max((g['verdict'] for g in chosen),key=lambda v:order[v])
                joined=[]
                for pin in record['check_result_refs']:
                    result=by_ref.get(key(pin))
                    if result is None or result['kind']!='deterministic-check-result':raise ValueError('completed check join unavailable')
                    joined.extend(result['record']['results'])
                checks[record['id']]=joined
                groups.setdefault((record['cc_name'],record['cc_version'],record['declaration_sha256']),[]).append(record)
        except (KeyError,ValueError,TypeError,OSError) as exc:
            return [{'status':'unavailable','reason':str(exc)}]
        results=[]
        for records in groups.values():
            try:results.append({"path":str(self.publish("capsule-scorecard",build_scorecard(records,records_ref,gate_verdicts=verdicts,check_results=checks))),"status":"built"})
            except (ValueError,OSError) as exc:results.append({"status":"unavailable","reason":type(exc).__name__})
        return results

