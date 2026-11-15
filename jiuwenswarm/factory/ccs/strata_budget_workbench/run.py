import json
import sys
from component import TOOLS

try:
    packet=json.load(sys.stdin)
    result=TOOLS[packet['capability']](packet['inputs']['request'])
    print(json.dumps(dict(outcome='ok',outputs=dict(result=result))))
except (ValueError,KeyError,TypeError,IndexError) as exc:
    print(json.dumps(dict(outcome='error',error=dict(code='INVALID_INPUT',message=str(exc)))))
