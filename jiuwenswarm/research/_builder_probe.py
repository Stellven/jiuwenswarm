"""Trusted Builder-parent probe; deliberately does not certify tool networking."""
import json
import os
import socket
import sys


def main():
    expected = json.loads(sys.argv[1])
    proof = {'profile':'builder-parent','executor_uid':os.getuid(),'executor_gid':os.getgid(),
             'network_namespace':os.readlink('/proc/self/ns/net'),'network':None,'denied_paths':{},'ready':False}
    try:
        status = dict(line.split(':',1) for line in open('/proc/self/status',encoding='utf-8') if ':' in line)
        proof['cap_effective'],proof['no_new_privileges'] = status['CapEff'].strip(),status['NoNewPrivs'].strip()
        if (proof['executor_uid'] != expected['uid'] or proof['executor_gid'] != expected['gid']
                or int(proof['cap_effective'],16) != 0 or proof['no_new_privileges'] != '1'
                or proof['network_namespace'] != expected['parent_network_namespace']):
            raise RuntimeError()
        for path in expected['denied_paths']:
            try: descriptor = os.open(path,os.O_RDONLY|os.O_NONBLOCK)
            except (FileNotFoundError,PermissionError): proof['denied_paths'][path] = True
            else:
                os.close(descriptor);proof['denied_paths'][path] = False
        if not all(proof['denied_paths'].values()): raise RuntimeError()
        controls = expected.get('qualification_connectivity')
        if controls is not None:
            if set(controls) != {'nonce', 'ipv4', 'ipv6'} or not isinstance(controls['nonce'], str) or len(controls['nonce']) != 64:
                raise RuntimeError()
            proof['parent_connectivity'] = {}
            for kind, family, address in [('ipv4', socket.AF_INET, '127.0.0.1'), ('ipv6', socket.AF_INET6, '::1')]:
                port = controls[kind]
                if type(port) is not int or not 1024 <= port <= 65535: raise RuntimeError()
                with socket.socket(family) as connection:
                    connection.settimeout(2); connection.connect((address, port))
                    connection.sendall(b'AI4R_PARENT_POSITIVE:' + controls['nonce'].encode('ascii'))
                proof['parent_connectivity'][kind] = True
        proof['ready'] = True
    except Exception:
        proof['failure'] = 'BUILDER_PARENT_OBSERVATION_FAILED'
    sys.stdout.buffer.write(b'AI4R_EXECUTOR_PROBE_V1 '+json.dumps(proof,separators=(',',':')).encode()+b'\n')
    sys.stdout.buffer.flush()
    if not proof['ready']: raise SystemExit(126)
    os.execvpe(sys.argv[2],sys.argv[2:],os.environ)


if __name__ == '__main__': main()
