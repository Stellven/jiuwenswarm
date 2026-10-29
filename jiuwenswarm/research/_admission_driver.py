"""Fixed self-test driver. Its only host capability invokes this job's candidate."""
import json
import socket
import struct
from pathlib import Path


def exact(stream, count):
    value = bytearray()
    while len(value) < count:
        part = stream.recv(count - len(value))
        if not part: raise RuntimeError('Candidate invocation outcome unknown')
        value.extend(part)
    return bytes(value)


def main():
    root = Path('/resources/input')
    manifest = json.loads((root / 'manifest.json').read_bytes())
    def invoke(inputs):
        request = {k: manifest[k] for k in ('protocol', 'session_id', 'capability')}
        request.update(operation='invoke', payload={'inputs': inputs})
        data = json.dumps(request, allow_nan=False, separators=(',', ':')).encode()
        if len(data) > 4 * 1024 * 1024: raise RuntimeError('Candidate input frame too large')
        with socket.socket(socket.AF_UNIX) as stream:
            stream.connect('/resources/invoke.sock')
            stream.sendall(struct.pack('!I', len(data)) + data)
            size = struct.unpack('!I', exact(stream, 4))[0]
            if not 0 < size <= 4 * 1024 * 1024: raise RuntimeError('Invalid candidate reply frame')
            reply = json.loads(exact(stream, size))
        if reply.get('protocol') != manifest['protocol'] or 'error' in reply: raise RuntimeError('Candidate invocation failed')
        return reply['result']
    if manifest['kind'] == 'fixture':
        result = invoke(json.loads((root / 'test').read_bytes()))
    elif manifest['kind'] == 'command':
        namespace = {'__name__': '__admission_command__', '__file__': str(root / 'test')}
        exec(compile((root / 'test').read_bytes(), str(root / 'test'), 'exec'), namespace)
        result = namespace['run'](invoke)
    else:
        raise RuntimeError('Unsupported self-test kind')
    print(json.dumps(result, allow_nan=False, separators=(',', ':')), flush=True)


if __name__ == '__main__': main()
