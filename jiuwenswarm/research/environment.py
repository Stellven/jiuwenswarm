"""Trusted frozen package preparation, separate from generated science."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from email.parser import BytesParser
from collections.abc import Callable, Mapping, Sequence


class EnvironmentError(ValueError):
    pass


_PIN = re.compile(r'([a-z0-9][a-z0-9._-]*)==([0-9]+(?:\.[0-9]+)*)')


def normalize_name(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def parse_requirements(content: bytes | str) -> dict[str, str]:
    text = content.decode('utf-8') if isinstance(content, bytes) else content
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = _PIN.fullmatch(line)
        if not match or normalize_name(match[1]) in result:
            raise EnvironmentError('requirements must contain unique exact name==version pins only')
        result[normalize_name(match[1])] = match[2]
    if len(result) > 500:
        raise EnvironmentError('environment lock exceeds 500 packages')
    return result


def verify_inventory(expected: Mapping[str, str], installed: Sequence[Mapping]) -> None:
    observed = {}
    for package in installed:
        name = normalize_name(package['name'])
        if name in observed:
            raise EnvironmentError('duplicate installed distribution')
        observed[name] = package['version']
    if observed != dict(expected):
        raise EnvironmentError('installed package inventory differs from frozen complete lock')


def verify_provisioned_inventory(expected: Mapping[str, str], installed: Sequence[Mapping]) -> None:
    """Check source InstalledPackage receipts against the independently frozen lock."""
    projection = []
    for package in installed:
        if set(package) != {'name', 'locked_version', 'installed_version', 'hash_verified'}:
            raise EnvironmentError('installed package receipt fields differ from source contract')
        name = normalize_name(package['name'])
        if package['locked_version'] != expected.get(name) or package['hash_verified'] is not True:
            raise EnvironmentError('installed package lock/hash verification is invalid')
        projection.append({'name': name, 'version': package['installed_version']})
    verify_inventory(expected, projection)


def verify_ref(ref: Mapping, content: bytes) -> None:
    if not isinstance(ref.get('id'), str) or hashlib.sha256(content).hexdigest() != ref.get('sha256'):
        raise EnvironmentError('immutable resource hash mismatch')


def inspect_wheel(content: bytes) -> tuple[str, str, list[str]]:
    """Read package metadata without importing, building or executing it."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        metadata = [n for n in names if n.endswith('.dist-info/METADATA')]
        if len(metadata) != 1 or sum(i.file_size for i in archive.infolist()) > 512 * 1024 * 1024:
            raise EnvironmentError('unsupported reviewed package format')
        message = BytesParser().parsebytes(archive.read(metadata[0]))
    if not message.get('Name') or not message.get('Version'):
        raise EnvironmentError('package metadata missing name/version')
    return normalize_name(message['Name']), message['Version'], message.get_all('Requires-Dist', [])


def validate_lock(lock: Mapping, read: Callable[[Mapping], bytes], platform: str) -> dict[str, str]:
    if lock.get('schema_version') != '1.0.0' or lock.get('platform') != platform:
        raise EnvironmentError('incompatible environment lock/platform')
    refs = lock.get('package_refs')
    if not isinstance(refs, list) or len(refs) > 500 or len({(r['id'], r['sha256']) for r in refs}) != len(refs):
        raise EnvironmentError('invalid package references')
    req = read(lock['requirements_ref']); verify_ref(lock['requirements_ref'], req)
    expected = parse_requirements(req)
    approval = read(lock['approval_ref']); verify_ref(lock['approval_ref'], approval)
    if not approval:
        raise EnvironmentError('missing protected environment approval')
    packages = {}
    for ref in refs:
        content = read(ref); verify_ref(ref, content)
        name, version, dependencies = inspect_wheel(content)
        if name in packages or expected.get(name) != version:
            raise EnvironmentError('reviewed package identity differs from requirements')
        packages[name] = version
        # Dependency declarations can be broader than the pinned reviewed choice,
        # but every active dependency must be present and satisfy its metadata.
        try:
            from packaging.requirements import Requirement
            for value in dependencies:
                dep = Requirement(value)
                if dep.marker and not dep.marker.evaluate():
                    continue
                selected = expected.get(normalize_name(dep.name))
                if selected is None or (dep.specifier and not dep.specifier.contains(selected)):
                    raise EnvironmentError('reviewed lock lacks transitive dependency closure')
        except ImportError as exc:
            if dependencies:
                raise EnvironmentError('locked package metadata validator unavailable') from exc
    if packages != expected:
        raise EnvironmentError('package bytes must cover the exact complete lock')
    return expected
