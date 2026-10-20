"""Fixed harmless tool-context probe, staged read-only by the trusted qualifier.

This program never reads provider credentials. Protected paths are synthetic
positive-control canaries, and network endpoints are live owned loopback probes.
"""
import json
import os
from pathlib import Path
import socket
import sys


def main():
    value = json.loads(Path(sys.argv[1]).read_bytes())
    if set(value) != {'schema', 'nonce', 'canaries', 'listeners'} or value['schema'] != 'ai4r-builder-tool-probe-input:1':
        raise SystemExit(2)
    nonce = value['nonce']
    if not isinstance(nonce, str) or len(nonce) != 64 or any(c not in '0123456789abcdef' for c in nonce):
        raise SystemExit(2)
    roles = {'run_state', 'main_credential', 'fixture', 'library'}
    if set(value['canaries']) != roles or set(value['listeners']) != {'ipv4', 'ipv6'}:
        raise SystemExit(2)
    denied = {}
    for role, name in value['canaries'].items():
        if not isinstance(name, str) or not name.startswith('/var/lib/ai4r-executor/qualification/') or '..' in Path(name).parts:
            raise SystemExit(2)
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK)
        except (FileNotFoundError, PermissionError):
            denied[role] = True
        else:
            os.close(fd)
            denied[role] = False
    network = {}
    for kind, family, host in [('ipv4', socket.AF_INET, '127.0.0.1'), ('ipv6', socket.AF_INET6, '::1')]:
        port = value['listeners'][kind]
        if type(port) is not int or not 1024 <= port <= 65535:
            raise SystemExit(2)
        try:
            with socket.socket(family) as connection:
                connection.settimeout(1)
                connection.connect((host, port))
        except OSError as error:
            network[kind] = {'denied': True, 'errno': error.errno}
        else:
            network[kind] = {'denied': False, 'errno': 0}
    status = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if ':' in line:
            key, content = line.split(':', 1)
            status[key] = content.strip()
    marker = Path('/workspace/poc/qualification-write')
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(nonce.encode('ascii'))
    observed = {'schema': 'ai4r-builder-tool-probe-result:1', 'nonce': nonce, 'uid': os.getuid(), 'gid': os.getgid(),
                'cap_eff': status.get('CapEff'), 'no_new_privs': status.get('NoNewPrivs'),
                'workspace_write': marker.read_text() == nonce, 'denied_paths': denied, 'network': network}
    print('AI4R_BUILDER_TOOL_PROBE:' + json.dumps(observed, sort_keys=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
