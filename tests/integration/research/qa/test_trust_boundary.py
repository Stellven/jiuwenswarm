"""Actual launched role/mount checks; execute once under each production UID."""
import errno
import os
from pathlib import Path
import uuid


def cannot_create(root):
    root=Path(root)
    assert root.is_dir(),'Required actual mounted root is absent; absence is not a write-denial proof.'
    candidate=root/('.owned-boundary-probe-'+uuid.uuid4().hex)
    try:
        fd=os.open(candidate,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except OSError as exc:assert exc.errno in {errno.EACCES,errno.EPERM,errno.EROFS}
    else:
        os.close(fd);candidate.unlink()
        raise AssertionError('Required read-only role mount accepted a write')


def test_actual_runner_or_referee_has_only_its_required_authority():
    uid=os.geteuid();assert uid in {11001,11002},'Required launched runner/referee UID is absent.'
    status=Path('/proc/self/status').read_text()
    assert next(row.split()[1] for row in status.splitlines() if row.startswith('CapEff:'))=='0000000000000000'
    assert next(row.split()[1] for row in status.splitlines() if row.startswith('NoNewPrivs:'))=='1'
    for value in ('/var/run/docker.sock','/var/lib/ai4r','/var/lib/ai4r-accounts','/run/ai4r-executor',
                  '/var/lib/ai4r-rsi/custodian','/var/lib/ai4r-rsi/controller','/var/lib/ai4r-rsi-inbox',
                  '/run/ai4r-rsi/signing-key','/run/ai4r-rsi/custodian','/run/ai4r-rsi-worker'):
        assert not os.path.lexists(value),'Forbidden private authority exists in this optional client role.'
    assert not any(key.endswith('_API_KEY') for key in os.environ)
    assert Path('/bench/results').is_dir()
    cannot_create('/bench/campaigns')
    if uid==11001:
        assert Path(os.environ.get('AI4R_QA_JOB','/run/ai4r-qa/job.json')).is_file()
        assert Path('/run/ai4r-qa/token').is_file()
        assert not os.path.lexists('/bench-private/labels')
        cannot_create('/bench/scores');cannot_create('/bench/reports')
    else:
        assert not os.path.lexists('/run/ai4r-qa/job.json') and not os.path.lexists('/run/ai4r-qa/token')
        assert 'AI4R_QA_JOB' not in os.environ and not os.path.lexists('/run/ai4r-rsi/jobs')
        labels=Path(os.environ.get('AI4R_QA_LABELS','/bench-private/labels'))
        assert labels.is_dir() and list(labels.iterdir()),'Actual separately registered oracle labels are absent.'
        cannot_create(labels)
        assert {p.name for p in Path('/sys/class/net').iterdir()}=={'lo'},'Referee received an external network interface.'
