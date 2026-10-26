"""Host registered pi protocol. Reference bytes never enter a generated-code mount."""
from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import stat
import uuid
from pathlib import Path

from .contracts import ResearchError
from .pi_protocol import create_reference, parse_pi_output
from .state import json_bytes

PROTOCOL = 'ai4r-pi:1'


def capture_pi_profile(directory, public_dataset_ref):
    """Explicit operator authoring, before any build or measured job."""
    if os.name != 'posix' or os.geteuid() != 0:
        raise ResearchError('auth', 'Root custody is required for pi reference authoring')
    root = Path(directory)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise ResearchError('auth', 'Private reference directory custody is invalid')
    reference = create_reference(100000)
    raw = reference['decimal'].encode('ascii')
    path = root / 'pi-reference.txt'
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o400)
    return {'protocol': PROTOCOL, 'public_dataset_ref': public_dataset_ref,
            'reference_path': str(path), 'reference_sha256': hashlib.sha256(raw).hexdigest(),
            'source_sha256': reference['source_sha256'], 'methods': reference['methods'],
            'unseen_precisions': secrets.SystemRandom().sample(range(20000, 100001), 3),
            'measured_precisions': [10000, 100000], 'repetitions': 5,
            'max_stdout_bytes': 1048576}


class RootPiScorer:
    protocol = PROTOCOL

    def __init__(self, store, profile):
        if os.name != 'posix' or os.geteuid() != 0:
            raise ResearchError('auth', 'Pi scoring requires root custody')
        self.store, self.profile = store, dict(profile)
        selected = profile.get('unseen_precisions')
        if (profile.get('protocol') != PROTOCOL or profile.get('measured_precisions') != [10000, 100000]
                or profile.get('repetitions') != 5 or type(selected) is not list or len(set(selected)) != 3
                or any(type(n) is not int or not 20000 <= n <= 100000 for n in selected)):
            raise ResearchError('validation', 'Pi protocol profile is not the registered protocol')
        path = Path(profile['reference_path'])
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ResearchError('auth', 'Private pi reference path is unsafe')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as stream:
            meta = os.fstat(stream.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o277 or meta.st_nlink != 1:
                raise ResearchError('auth', 'Private pi reference custody is invalid')
            raw = stream.read(100003)
        if len(raw) != 100002 or hashlib.sha256(raw).hexdigest() != profile['reference_sha256']:
            raise ResearchError('validation', 'Pinned pi reference bytes changed')
        self.reference = raw.decode('ascii')
        # Do not publish reference_path or unseen precision selection to workers.
        self.profile_ref = store.put_blob(json_bytes({'protocol': PROTOCOL,
            'profile_sha256': hashlib.sha256(json_bytes(profile)).hexdigest(),
            'reference_sha256': profile['reference_sha256'], 'source_sha256': profile['source_sha256']}))

    def digits_for(self, case_id):
        if case_id in ('pi-10000', 'pi-100000'):
            return int(case_id[3:])
        if case_id in ('pi-unseen-1', 'pi-unseen-2', 'pi-unseen-3'):
            return self.profile['unseen_precisions'][int(case_id[-1]) - 1]
        if case_id in ('pi-boundary-0','pi-boundary-1','pi-boundary-2','pi-boundary-17'):
            return int(case_id.rsplit('-',1)[1])
        raise ResearchError('validation', 'Unknown host pi case')

    def score(self, job, raw, public):
        case_id, digits = public['case_id'], public['digits']
        if (digits != self.digits_for(case_id) or 'trusted_scoring_ref' in raw
                or raw.get('job_id') != job.job_id or raw.get('contract_ref') != dict(job.contract_ref)
                or raw.get('invocation_id') != job.invocation_id):
            raise ResearchError('auth','Pi score request differs from the exact issued host case')
        if raw.get('observed_runtime') is not True:
            raise ResearchError('auth','Pi scoring requires an observed protected execution')
        completed=raw.get('exit_code')==0 and raw.get('termination_reason')=='completed'
        correct, reason = False, raw.get('termination_reason') if not completed else None
        if completed:
            try:
                parse_pi_output(self.store.read_blob(raw['stdout_ref']), digits, self.reference[:digits+2])
                correct = True
            except (ResearchError, ValueError, TypeError) as exc:
                reason = str(exc)[:300]
        elapsed = raw.get('wall_time_s')
        if (type(elapsed) not in (float, int) or not math.isfinite(elapsed) or elapsed < 0
                or (completed and elapsed > job.timeout_s)):
            raise ResearchError('validation', 'Protected execution clock is missing')
        record = {'schema': 'ai4r-pi-score:1', 'id':'pi-score:'+uuid.uuid4().hex,
            'case_id': case_id, 'digits': digits,
            'correct': correct, 'reason': reason, 'elapsed_s': elapsed if correct else None,
            'reference_sha256': self.profile['reference_sha256'], 'protocol_profile_ref': self.profile_ref,
            'cpu_affinity':raw.get('observed_limits',{}).get('cpu_affinity'),
            **{key: raw[key] for key in ('job_id','contract_ref','invocation_id','role','repeat_index',
                                       'sequence','subject_ref','stdout_ref','stderr_ref')}}
        ref = self.store.append_record('pi_scoring_receipt', record)
        return dict(raw, trusted_scoring_ref=ref)
