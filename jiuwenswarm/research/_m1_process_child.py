"""Finite M1 child launcher. Ordinary app processes, not a namespace sandbox."""
import ctypes
import json
import os
import resource
import signal
import sys


def main():
    if os.geteuid() != 0 or len(sys.argv) != 3:
        raise SystemExit('PROTECTED_EXECUTOR_BROKER_REQUIRED')
    gate, manifest = map(int, sys.argv[1:])
    if os.read(gate, 1) != b'1':
        raise SystemExit('EXECUTOR_ADMISSION_ABORTED')
    os.close(gate)
    with os.fdopen(manifest) as stream:
        value = json.load(stream)
    os.chdir(value['cwd'])
    os.setgroups([])
    os.setgid(value['gid'])
    os.setuid(value['uid'])
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise SystemExit('EXECUTOR_PROCESS_CONTROLS_FAILED')
    memory = value['memory_mb'] * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_NPROC, (value['pids_max'], value['pids_max']))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with open('/proc/self/status') as stream:
        status = dict(line.split(':', 1) for line in stream if ':' in line)
    proof = dict(value['proof'], executor_uid=os.geteuid(), executor_gid=os.getegid(),
        no_new_privileges=status['NoNewPrivs'].strip(), cap_effective=status['CapEff'].strip(),
        cpu_affinity=sorted(os.sched_getaffinity(0)), cwd=os.getcwd(), ready=True)
    if proof['executor_uid'] != 10002 or int(proof['cap_effective'], 16) != 0:
        raise SystemExit('EXECUTOR_IDENTITY_MISMATCH')
    print('AI4R_M1_PROCESS_V1 '+json.dumps(proof, separators=(',', ':')), flush=True)
    os.execve(value['argv'][0], value['argv'], value['environment'])


if __name__ == '__main__':
    main()
