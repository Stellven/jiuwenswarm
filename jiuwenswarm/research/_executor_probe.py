"""Trusted before-exec observation, mounted read-only by the root broker.

The first stdout frame is a bounded trusted observation. It is flushed before
exec; the broker consumes exactly that first frame as host metadata, retaining
subsequent bytes as target stdout. Failure never dispatches the target program.
"""
import errno
import json
import os
import socket
import sys


def main():
    expected = json.loads(sys.argv[1])
    proof = {"executor_uid": os.getuid(), "executor_gid": os.getgid(), "groups": os.getgroups(),
             "network_namespace": os.readlink('/proc/self/ns/net'), "network": None,
             "interfaces": socket.if_nameindex(), "denied_paths": {}, "ready": False}
    try:
        status = dict(line.split(':', 1) for line in open('/proc/self/status', encoding='utf-8') if ':' in line)
        proof['cap_effective'] = status['CapEff'].strip()
        proof['cpu_affinity'] = sorted(os.sched_getaffinity(0))
        proof['no_new_privileges'] = status['NoNewPrivs'].strip()
        if (proof['executor_uid'] != expected['uid'] or proof['executor_gid'] != expected['gid']
                or int(proof['cap_effective'], 16) != 0 or proof['no_new_privileges'] != '1'
                or proof['network_namespace'] == expected['parent_network_namespace']
                or any(name != 'lo' for _, name in proof['interfaces'])):
            raise RuntimeError('namespace identity observation failed')
        network_results = []
        for family, address in ((socket.AF_INET, ('192.0.2.1', 9)), (socket.AF_INET6, ('2001:db8::1', 9))):
            try:
                with socket.socket(family, socket.SOCK_STREAM) as probe:
                    probe.settimeout(0.2)
                    result = probe.connect_ex(address)
            except OSError as error:
                result = error.errno
            network_results.append(result)
            if result not in {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EADDRNOTAVAIL,
                              errno.EAFNOSUPPORT, errno.EACCES, errno.EPERM}:
                raise RuntimeError('network denial was not observed')
        proof['network_probe_errors'] = network_results
        for path in expected['denied_paths']:
            try:
                descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as error:
                proof['denied_paths'][path] = error.errno in {errno.ENOENT, errno.EACCES, errno.EPERM}
            else:
                os.close(descriptor)
                proof['denied_paths'][path] = False
        if not all(proof['denied_paths'].values()):
            raise RuntimeError('protected path became readable')
        proof['network'] = 'none'
        proof['ready'] = True
    except Exception:
        proof['failure'] = 'EXECUTOR_ISOLATION_OBSERVATION_FAILED'
    payload = json.dumps(proof, separators=(',', ':'), allow_nan=False).encode()
    if len(payload) > 4096:
        payload = b'{"ready":false,"failure":"PROBE_FRAME_LIMIT"}'
    sys.stdout.buffer.write(b'AI4R_EXECUTOR_PROBE_V1 ' + payload + b'\n')
    sys.stdout.buffer.flush()
    if not proof['ready']:
        raise SystemExit(126)
    os.execvpe(sys.argv[2], sys.argv[2:], os.environ)


if __name__ == '__main__':
    main()
