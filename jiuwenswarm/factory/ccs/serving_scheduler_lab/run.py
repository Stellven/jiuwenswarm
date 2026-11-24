"""Native CC v2 entrypoint: inline JSON only, package-local stdlib implementation."""
import json
import sys
import reference
import verification

OPERATIONS = {'schedule': 'schedule', 'analyze': 'analyze', 'compare': 'compare'}

def main():
    try:
        packet = json.load(sys.stdin)
        cap = packet['capability']
        if cap == 'verify':
            result = verification.verify()
        else:
            result = getattr(reference, OPERATIONS[cap])(packet['inputs']['spec'])
        output = {'outcome':'ok','outputs':{'result':result}}
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        output = {'outcome':'error','error':{'code':'INVALID_REFERENCE_INPUT','message':str(error)}}
    print(json.dumps(output,allow_nan=False))

if __name__ == '__main__': main()
