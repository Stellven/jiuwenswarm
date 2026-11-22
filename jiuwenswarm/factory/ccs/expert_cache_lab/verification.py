import json
from pathlib import Path
from components import replay, predict

def check():
    data=json.loads((Path(__file__).parent/'fixtures/example.json').read_text())
    for policy in ('lru','lfu','hybrid'):
        result=replay(dict(data,policy=policy))
        assert result['hits']+result['misses']==len(data['trace'])
        assert all(e['resident_bytes']<=data['capacity_bytes'] for e in result['events'])
    a=predict(data)
    suffix=dict(data,trace=data['trace'][:-1]+[dict(data['trace'][-1],expert=17)])
    assert a['predictions'][:-1]==predict(suffix)['predictions'][:-1]
    return {'certification':'CPU reference only','passed':True}
if __name__=='__main__':print(json.dumps(check()))
