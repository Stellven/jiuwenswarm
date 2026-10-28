"""Pinned Ubuntu Compose extraction into its own Root-private helper prefix.

No package installation, maintainer scripts, daemon or container operation.
The existing native host payload and shared Docker client paths are untouched.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_compose_host', HERE / 'rsi_host.py')
host = importlib.util.module_from_spec(spec); spec.loader.exec_module(host)
PREFIX = Path('/opt/ai4r-rsi-compose/2.40.3-ubuntu24.04.1')
PACKAGE = {'package':'docker-compose-v2','version':'2.40.3+ds1-0ubuntu1~24.04.1','architecture':'amd64',
    'filename':'pool/universe/d/docker-compose-v2/docker-compose-v2_2.40.3+ds1-0ubuntu1~24.04.1_amd64.deb',
    'bytes':14788638,'sha256':'192f3df16d0c832e1cbf2362889da56522267835cfb19541241b3dd0ed964039'}
SIGNER = 'F6ECB3762474EDA9D21B7022871920D1991BC93C'
RELEASE = host.ROOT / 'apt/lists/archive.ubuntu.com_ubuntu_dists_noble-updates_InRelease'
INDEX = host.ROOT / 'apt/lists/archive.ubuntu.com_ubuntu_dists_noble-updates_universe_binary-amd64_Packages'
KEYRING = Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg')


def need(value, reason):
    if not value: raise ValueError(reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def root_identity():
    need(os.name == 'posix' and os.geteuid() == os.getegid() == 0, 'LINUX_ROOT_REQUIRED')


def read(path):
    host.secure(path)
    meta = path.stat()
    need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and meta.st_size <= 128*1024*1024, 'UNSAFE_HELPER_FILE')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
        return source.read(128*1024*1024+1)


def metadata():
    release = read(RELEASE); index = read(INDEX); keyring = read(KEYRING)
    status = host.run(['/usr/bin/gpgv','--status-fd','1','--keyring',KEYRING,RELEASE])
    need(any(line.startswith('[GNUPG:] VALIDSIG ' + SIGNER + ' ') for line in status.splitlines()), 'UBUNTU_ARCHIVE_SIGNATURE_DIFFERS')
    fields = dict(re.findall(r'^([A-Za-z-]+): (.*)$', release.decode(), re.M))
    date = parsedate_to_datetime(fields['Date'])
    need(fields['Origin'] == 'Ubuntu' and fields['Suite'] == 'noble-updates'
         and 0 <= (datetime.now(timezone.utc)-date).total_seconds() <= 172800, 'STALE_OR_WRONG_APT_RELEASE')
    if 'Valid-Until' in fields:
        need(datetime.now(timezone.utc) <= parsedate_to_datetime(fields['Valid-Until']), 'EXPIRED_APT_RELEASE')
    lines = release.decode().splitlines(); start = lines.index('SHA256:') + 1; sums = {}
    for line in lines[start:]:
        if not line.startswith(' '): break
        digest, size, name = line.split(); need(name not in sums, 'DUPLICATE_SIGNED_INDEX')
        sums[name] = (digest, int(size))
    need(sums['universe/binary-amd64/Packages'] == (sha(index),len(index)), 'APT_INDEX_SIGNATURE_JOIN_DIFFERS')
    matches = []
    for paragraph in index.decode().split('\n\n'):
        value = dict(re.findall(r'^([A-Za-z0-9-]+): (.*)$', paragraph, re.M))
        if value.get('Package') == PACKAGE['package'] and value.get('Version') == PACKAGE['version']:
            matches.append((paragraph,value))
    need(len(matches) == 1, 'EXACT_PACKAGE_METADATA_REQUIRED')
    paragraph, value = matches[0]
    need(value['Architecture'] == PACKAGE['architecture'] and value['Filename'] == PACKAGE['filename']
         and value['SHA256'] == PACKAGE['sha256'] and int(value['Size']) == PACKAGE['bytes']
         and value['Depends'] == 'libc6 (>= 2.34)' and not value.get('Pre-Depends'), 'PACKAGE_PIN_OR_DEPENDENCY_DIFFERS')
    dependencies = host.run(['/usr/bin/dpkg-query','-W','-f=${Package}|${Version}|${Architecture}|${Status}|${Pre-Depends}|${Depends}\n',
                             'libc6','libgcc-s1','gcc-14-base'])
    closure = {}
    for line in dependencies.splitlines():
        name,version,arch,state,pre,depends = line.split('|')
        need(state == 'install ok installed' and arch == 'amd64' and not pre, 'REQUIRED_RUNTIME_NOT_INSTALLED')
        closure[name] = {'version':version,'architecture':arch,'depends':depends}
    need(set(closure) == {'libc6','libgcc-s1','gcc-14-base'} and closure['libc6']['depends'] == 'libgcc-s1'
         and closure['gcc-14-base']['depends'] == '' and closure['libgcc-s1']['depends'] ==
         'gcc-14-base (= ' + closure['gcc-14-base']['version'] + '), libc6 (>= 2.35)', 'RUNTIME_DEPENDENCY_CLOSURE_CHANGED')
    host.run(['/usr/bin/dpkg','--compare-versions',closure['libc6']['version'],'ge','2.35'])
    return {'package':PACKAGE,'uri':'http://archive.ubuntu.com/ubuntu/' + PACKAGE['filename'],
        'signed_release':{'sha256':sha(release),'signer':SIGNER,'date':fields['Date'],'valid_until':fields.get('Valid-Until')},
        'index':{'sha256':sha(index),'bytes':len(index),'signed_path':'universe/binary-amd64/Packages'},
        'keyring_sha256':sha(keyring),'package_stanza_sha256':sha(paragraph.encode()),
        'runtime_dependency_closure':closure,'dpkg_status_sha256':sha(read(Path('/var/lib/dpkg/status')))}, (release,index,keyring,paragraph.encode())


def plan():
    root_identity(); need(not os.path.lexists(PREFIX), 'HELPER_PREFIX_ALREADY_EXISTS')
    facts, _ = metadata()
    return {'schema':'ai4r-rsi-compose-install-plan:1','prefix':str(PREFIX),'facts':facts,
            'package_installation':False,'maintainer_scripts':False,'native_host_payload_changes':False}


def inventory(root):
    files = {}; links = {}
    for path in root.rglob('*'):
        name = str(path.relative_to(root))
        if path.is_symlink(): links[name] = os.readlink(path)
        elif path.is_file(): files[name] = sha(read(path))
        else: need(path.is_dir(), 'UNSUPPORTED_HELPER_PAYLOAD_ENTRY')
    return {'files':files,'links':links}


def verified_archive(path):
    raw = read(path)
    need(len(raw) == PACKAGE['bytes'] and sha(raw) == PACKAGE['sha256'], 'HELPER_ARCHIVE_HASH_DIFFERS')
    return raw


def verify():
    root_identity(); host.secure(PREFIX)
    manifest_raw = read(PREFIX / 'manifest.json'); manifest = json.loads(manifest_raw)
    need(manifest['schema'] == 'ai4r-rsi-compose-helper:1' and manifest['plan']['prefix'] == str(PREFIX)
         and manifest['plan']['facts']['package'] == PACKAGE, 'HELPER_MANIFEST_DIFFERS')
    need(sha(encoded(manifest['plan'])) == manifest['plan_sha256'], 'HELPER_PLAN_HASH_DIFFERS')
    verified_archive(PREFIX/'package.deb')
    need(inventory(PREFIX/'payload') == manifest['inventory'], 'HELPER_PAYLOAD_INVENTORY_DIFFERS')
    need(set(manifest['proof_files']) == {'InRelease','Packages','ubuntu-archive-keyring.gpg','package-stanza.txt'},
         'HELPER_PROOF_CLOSURE_DIFFERS')
    for name, digest in manifest['proof_files'].items():
        host.archive_path(name); need(sha(read(PREFIX/name)) == digest, 'HELPER_PROOF_BYTES_DIFFER')
    facts = manifest['plan']['facts']
    need(manifest['proof_files'] == {'InRelease':facts['signed_release']['sha256'], 'Packages':facts['index']['sha256'],
        'ubuntu-archive-keyring.gpg':facts['keyring_sha256'], 'package-stanza.txt':facts['package_stanza_sha256']},
        'HELPER_PROOF_PLAN_JOIN_DIFFERS')
    status = host.run(['/usr/bin/gpgv','--status-fd','1','--keyring',PREFIX/'ubuntu-archive-keyring.gpg',PREFIX/'InRelease'])
    need(any(line.startswith('[GNUPG:] VALIDSIG ' + SIGNER + ' ') for line in status.splitlines()), 'ARCHIVED_UBUNTU_SIGNATURE_DIFFERS')
    binary = PREFIX / manifest['binary']; host.archive_path(manifest['binary'])
    need(binary.is_file() and not binary.is_symlink() and os.access(binary,os.X_OK)
         and sha(read(binary)) == manifest['binary_sha256'], 'HELPER_BINARY_DIFFERS')
    return {'schema':'ai4r-rsi-compose-helper-verification:1','binary':str(binary),'binary_sha256':manifest['binary_sha256'],
            'manifest':str(PREFIX/'manifest.json'),'manifest_sha256':sha(manifest_raw),'package':PACKAGE}


def install(review_sha256):
    reviewed = plan(); need(sha(encoded(reviewed)) == review_sha256, 'EXACT_HELPER_PLAN_REQUIRED')
    facts, originals = metadata(); need(facts == reviewed['facts'], 'HELPER_METADATA_CHANGED')
    parent = PREFIX.parent
    if not parent.exists(): parent.mkdir(mode=0o700)
    host.secure(parent); PREFIX.mkdir(mode=0o700); os.chmod(PREFIX,0o700)
    debs = PREFIX/'debs'; debs.mkdir(mode=0o700)
    host.run(['/usr/bin/apt-get',*host.apt_options(),'-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=',
              'download',PACKAGE['package']+'='+PACKAGE['version']],cwd=debs)
    downloaded = list(debs.iterdir()); need(len(downloaded) == 1, 'AMBIGUOUS_HELPER_ARCHIVE')
    verified_archive(downloaded[0])
    downloaded[0].rename(PREFIX/'package.deb'); debs.rmdir()
    payload = PREFIX/'payload'; payload.mkdir(mode=0o700)
    host.extract_payload(host.run(['/usr/bin/dpkg-deb','--fsys-tarfile',PREFIX/'package.deb'],binary=True),payload)
    binaries = [p for p in payload.rglob('docker-compose') if p.is_file() and not p.is_symlink() and os.access(p,os.X_OK)]
    need(len(binaries) == 1, 'EXACT_COMPOSE_BINARY_REQUIRED'); binary = binaries[0]
    proofs = {}
    for name, body in zip(('InRelease','Packages','ubuntu-archive-keyring.gpg','package-stanza.txt'),originals):
        path = PREFIX/name
        with path.open('xb') as output: os.fchmod(output.fileno(),0o600); output.write(body)
        proofs[name] = sha(body)
    manifest = {'schema':'ai4r-rsi-compose-helper:1','plan':reviewed,'plan_sha256':review_sha256,
        'inventory':inventory(payload),'binary':str(binary.relative_to(PREFIX)),'binary_sha256':sha(read(binary)),'proof_files':proofs}
    with (PREFIX/'manifest.json').open('xb') as output:
        os.fchmod(output.fileno(),0o600); output.write(encoded(manifest)); output.flush(); os.fsync(output.fileno())
    result = verify()
    result['version_output'] = host.run([result['binary'],'version'],env=host.ENV).strip()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('plan','install','verify')); parser.add_argument('--review-sha256')
    args = parser.parse_args(argv)
    try:
        result = plan() if args.operation == 'plan' else install(args.review_sha256) if args.operation == 'install' else verify()
        print(json.dumps(result,sort_keys=True)); return 0
    except Exception as error:
        print(json.dumps({'status':'BLOCKED','reason':str(error)})); return 2


if __name__ == '__main__': raise SystemExit(main())
