import json
from pathlib import Path
from components import fixture_read, coalesce

def check():
    data=json.loads((Path(__file__).parent/'fixtures/example.json').read_text())
    result=fixture_read(data)
    payload=data['data'].encode()
    assert result['hex_data']==[payload[o:o+n].hex() for o,n in data['ranges']]
    assert result['peak_inflight']<=2
    assert coalesce([[0,3],[2,4],[9,1]])==[(0,6),(9,1)]
    return {'certification':'CPU reference only','passed':True}
if __name__=='__main__':print(json.dumps(check()))
