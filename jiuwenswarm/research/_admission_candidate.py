"""Fixed pure candidate adapter. Runs only inside the isolated candidate child."""
import asyncio
import inspect
import json
import sys
from pathlib import Path


class DeclaredFailure(Exception):
    pass


class Context:
    def __init__(self, reasons): self.reasons = reasons
    def fail(self, reason):
        if reason not in self.reasons: raise RuntimeError('Undeclared candidate failure')
        raise DeclaredFailure(reason)


def main():
    root = Path('/resources/input')
    manifest = json.loads((root / 'manifest.json').read_bytes())
    body = root / 'body'
    sys.path.insert(0, str(body))
    path = body / manifest['carrier']
    namespace = {'__name__': '__admission_candidate__', '__file__': str(path)}
    exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
    try:
        output = namespace['execute'](Context(manifest['failure_modes']), manifest['inputs'])
        if inspect.isawaitable(output): output = asyncio.run(output)
        result = {'end_state': 'pass', 'outputs': output, 'reason_code': None}
    except DeclaredFailure as error:
        result = {'end_state': str(error), 'outputs': {}, 'reason_code': str(error)}
    print(json.dumps(result, allow_nan=False, separators=(',', ':')), flush=True)


if __name__ == '__main__': main()
