"""Read-only dependency context: machine-selected from the worker's imports only."""
import hashlib
from pathlib import Path

import pytest

from jiuwenswarm.research_rsi.targets import capsule_context
from jiuwenswarm.research_rsi.targets.capsule_context import dependency_context, render_dependency_context
from jiuwenswarm.research_rsi.targets.capsules import registered_capsule

ROOT = Path(__file__).resolve().parents[3]


def worker(name):
    return (ROOT / 'jiuwenswarm' / registered_capsule(name).carrier_path).read_bytes()


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
def test_context_is_the_workers_imports_with_exact_pinned_excerpts(name):
    value = dependency_context(name, worker(name))
    selected = {(row['path'], row['selection']) for row in value['sources']}
    # Codex's hand-picked set is what the import graph yields, plus the
    # contracts symbols the worker and packet.py actually import.
    assert {('jiuwenswarm/research/capsule_extensions/packet.py', 'whole_file'),
            ('jiuwenswarm/research/runner.py', 'ProducedArtifact'),
            ('jiuwenswarm/research/state.py', 'json_bytes')} <= selected
    assert {selection for _, selection in selected} >= {'ResearchError', 'validate'}
    assert value['mutable_path'] == registered_capsule(name).carrier_path and not value['omitted']
    for row in value['sources']:
        raw = (ROOT / row['path']).read_bytes()
        lines = raw.decode().splitlines(keepends=True)
        assert row['mutable'] is False and row['truncated'] is False
        assert row['source_sha256'] == hashlib.sha256(raw).hexdigest()
        assert row['text'] == ''.join(lines[row['first_line'] - 1:row['last_line']])
        assert row['excerpt_sha256'] == hashlib.sha256(row['text'].encode()).hexdigest()
    assert value['total_bytes'] <= capsule_context.MAX_TOTAL_BYTES
    # Machine-generated only: no operator free text, no model identity.
    assert not {'diagnosis_facts', 'requirements', 'generating_model', 'model'} & set(value)
    text = render_dependency_context(value)
    assert 'capsule_extensions/packet.py' in text and 'class ProducedArtifact' in text


def test_context_follows_the_candidate_body_and_is_bounded():
    name = 'utility.calculate'
    body = b'from jiuwenswarm.research.contracts import ResearchError\n'
    paths = {row['path'] for row in dependency_context(name, body)['sources']}
    # This candidate replaces the delegated implementation and imports only ResearchError.
    assert paths == {'jiuwenswarm/research/contracts/types.py'}
    small = dependency_context(name, worker(name), max_file_bytes=200, max_total_bytes=600)
    assert small['truncated'] is True and small['total_bytes'] <= 600 and small['omitted']
    limited = dependency_context(name, worker(name), max_modules=1)
    assert limited['truncated'] and any(':module_limit' in item for item in limited['omitted'])
    byte_limited = dependency_context(name, worker(name), max_source_bytes=1)
    assert byte_limited['truncated'] and any(':source_byte_limit' in item for item in byte_limited['omitted'])
    broken = dependency_context(name, b'def broken(:\n')
    assert broken['sources'] == [] and broken['parse_error'].startswith('SyntaxError')


def test_context_reads_an_explicit_source_root_without_importing(tmp_path):
    name = 'utility.calculate'
    release_paths = {'jiuwenswarm/' + path for path, _ in registered_capsule(name).dependency_pins}
    for relative in sorted(release_paths | {'jiuwenswarm/research/runner.py',
                     'jiuwenswarm/research/state.py', 'jiuwenswarm/research/contracts/__init__.py',
                     'jiuwenswarm/research/contracts/types.py', 'jiuwenswarm/research/contracts/validators.py'}):
        target = tmp_path / relative; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    runner = tmp_path / 'jiuwenswarm/research/runner.py'
    runner.write_bytes(b'# distinct evaluated tree\n' + runner.read_bytes())
    value = dependency_context(name, worker(name), source_root=tmp_path)
    here = dependency_context(name, worker(name))
    pins = lambda v: {row['path']: row['source_sha256'] for row in v['sources']}
    assert pins(value)['jiuwenswarm/research/runner.py'] != pins(here)['jiuwenswarm/research/runner.py']
    assert pins(value)['jiuwenswarm/research/capsule_extensions/packet.py'] == pins(here)[
        'jiuwenswarm/research/capsule_extensions/packet.py']

    # An arbitrary declared delegate chain is traversed by source budgets,
    # rather than losing symbols after a fixed number of wrapper releases.
    package = registered_capsule(name).selected_worker_module.rpartition('.')[0]
    directory = tmp_path.joinpath(*package.split('.'))
    for index in range(6):
        source = (f'from .context_delegate_{index + 1} import execute\n' if index < 5
                  else 'from ..packet import produced as execute\n')
        (directory / f'context_delegate_{index}.py').write_text(source)
    delegated = dependency_context(name, b'from .context_delegate_0 import execute\n', source_root=tmp_path)
    assert ('jiuwenswarm/research/runner.py', 'ProducedArtifact') in {
        (row['path'], row['selection']) for row in delegated['sources']}
    assert not delegated['omitted']
