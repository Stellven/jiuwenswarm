"""Installed pure-helper process policy; never applied to authority owners.

The generated prefix is part of the frozen worker-program digest. It installs
an irreversible kernel filter before any candidate source runs. Historical
program bytes remain separate. API/constants: https://github.com/seccomp/libseccomp
"""
import inspect

POLICY='single_process_seccomp_v1'


def install_process_policy():
    import ctypes
    import errno
    import os
    import sys
    if (sys.platform!='linux' or os.getuid()!=12003 or os.getgid()!=12003
            or any(group!=12003 for group in os.getgroups())):
        raise RuntimeError('Isolated Linux helper identity required')
    libc=ctypes.CDLL(None,use_errno=True)
    libc.prctl.restype=ctypes.c_int
    if libc.prctl(38,1,0,0,0)!=0 or libc.prctl(39,0,0,0,0)!=1:
        raise RuntimeError('Helper no-new-privileges unavailable')
    library=ctypes.CDLL('libseccomp.so.2',use_errno=True)
    library.seccomp_init.argtypes=[ctypes.c_uint32];library.seccomp_init.restype=ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];library.seccomp_syscall_resolve_name.restype=ctypes.c_int
    library.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    library.seccomp_rule_add.restype=ctypes.c_int
    library.seccomp_load.argtypes=[ctypes.c_void_p];library.seccomp_load.restype=ctypes.c_int
    library.seccomp_release.argtypes=[ctypes.c_void_p];library.seccomp_release.restype=None
    context=library.seccomp_init(0x7fff0000)
    if not context:raise RuntimeError('Helper process filter allocation failed')
    try:
        # Pure helpers retain their frozen credentials. Explicit denial also
        # makes the result independent of namespace UID/GID mapping: the kernel
        # may otherwise return EINVAL for an unmapped target before checking
        # privilege. Authority owners never install this helper-only filter.
        required={'clone','execve','execveat','setuid','setgid'};resolved=set()
        names=('clone','clone3','fork','vfork','execve','execveat','unshare','setns','ptrace',
               'socket','socketpair','mount','umount2','pivot_root','chroot','bpf',
               'perf_event_open','open_by_handle_at','keyctl','add_key','request_key',
               'reboot','kexec_load','kexec_file_load','swapon','swapoff','iopl','ioperm',
               'setuid','setgid','setreuid','setregid','setresuid','setresgid',
               'setfsuid','setfsgid','setgroups','capset',
               'setuid32','setgid32','setreuid32','setregid32','setresuid32','setresgid32',
               'setfsuid32','setfsgid32','setgroups32')
        for name in names:
            number=library.seccomp_syscall_resolve_name(name.encode('ascii'))
            if number<0 and name in required:
                raise RuntimeError('Required helper syscall unavailable')
            # libseccomp returns negative pseudo-numbers for recognized 32-bit
            # calls absent from the native ABI (not just -1 for unknown names).
            # Never submit such an unsupported variant or ignore a failed rule.
            if name.endswith('32') and number<0:continue
            if number==-1:continue # Architecture has no such syscall.
            resolved.add(name)
            if library.seccomp_rule_add(context,0x00050000|errno.EPERM,number,0)!=0:
                raise RuntimeError('Helper process filter rule failed')
        if not required<=resolved or library.seccomp_load(context)!=0:
            raise RuntimeError('Helper process filter unavailable')
    finally:library.seccomp_release(context)


def program_prefix():
    return (inspect.getsource(install_process_policy)+'\ninstall_process_policy()\n').encode('utf8')


def security_program(body):
    if not isinstance(body,bytes) or not body:raise ValueError('Fixed nonempty program bytes required')
    return program_prefix()+body


def apply_policy(program,policy):
    if policy is None:return program
    if policy!=POLICY:raise ValueError('Unknown installed helper process policy')
    return security_program(program)
