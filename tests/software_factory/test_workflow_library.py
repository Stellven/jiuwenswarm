"""Immutable library versions bind executable dependencies, not just card text."""
from copy import deepcopy
from pathlib import Path

import pytest

from jiuwenswarm.software_factory.contracts import StageFailure
from jiuwenswarm.software_factory.workflow_library import WorkflowLibrary, _implementation_files


def bundle():
    return {'id': 'strata', 'name': 'STRATA construction', 'source': {'revision': 'a' * 40},
            'subworkflows': [{'id': 'report', 'name': 'Report actual extracted source',
                             'inputs': {'algorithm': {'semantic_type': 'source.algorithm'}},
                             'outputs': {'report': {'semantic_type': 'analysis.report'}},
                             'implementation': {'type': 'python',
                                                'entrypoint': 'jiuwenswarm.software_factory.library_operations:report'}}]}


def test_registration_pins_actual_generator_and_native_dependency_bytes(tmp_path):
    library = WorkflowLibrary(tmp_path)
    registered = library.register(bundle())
    implementation = registered['subworkflows'][0]['implementation']
    assert set(implementation['source_files']) >= {'library_operations.py', 'core_codegen.py', 'cuda_lowering.py',
                                                   'ascend_codegen.py', 'native_build.py', 'oracle_validation.py'}
    assert all(len(value) == 64 for value in implementation['source_files'].values())
    assert library.resolve('strata', registered['version'], 'report')['implementation'] == implementation
    assert library.get('strata')['version'] == registered['version']


@pytest.mark.parametrize('changed_name', ['library_operations.py', 'ascend_codegen.py', 'native_build.py'])
def test_changed_runtime_source_or_embedded_dependency_invalidates_version(tmp_path, monkeypatch, changed_name):
    library = WorkflowLibrary(tmp_path)
    registered = library.register(bundle())
    original_read = Path.read_bytes

    def changed_read(path):
        raw = original_read(path)
        if path.name == changed_name and path.parent.name == 'software_factory':
            return raw + b'\n# isolated-test changed implementation\n'
        return raw

    monkeypatch.setattr(Path, 'read_bytes', changed_read)
    with pytest.raises(StageFailure) as caught:
        library.get('strata', registered['version'])
    assert caught.value.code == 'implementation_changed'
    new_version = library.register(bundle())
    assert new_version['version'] != registered['version']
    assert library.resolve('strata', new_version['version'], 'report')


@pytest.mark.parametrize('version', [None, '', 'latest'])
def test_executable_reference_requires_explicit_version_while_browsing_can_use_latest(tmp_path, version):
    library = WorkflowLibrary(tmp_path)
    registered = library.register(bundle())
    assert library.get('strata')['version'] == registered['version']
    with pytest.raises(StageFailure) as caught:
        library.resolve('strata', version, 'report')
    assert caught.value.code == 'invalid_version'


def test_ast_dependency_closure_includes_lazy_imports_and_embedded_source(tmp_path):
    (tmp_path / 'library_operations.py').write_text('def execute():\n from .core import generate\n')
    (tmp_path / 'core.py').write_text('from .native import lower\nsource = Path(__file__).with_name("native_build.py").read_text()\n')
    (tmp_path / 'native.py').write_text('def lower():\n return 1\n')
    (tmp_path / 'native_build.py').write_text('def compile():\n return 2\n')
    (tmp_path / 'unrelated.py').write_text('unrelated = 3\n')
    assert set(_implementation_files(tmp_path / 'library_operations.py', tmp_path)) == {
        'library_operations.py', 'core.py', 'native.py', 'native_build.py'}


def test_unpinned_legacy_python_definition_cannot_execute(tmp_path):
    library = WorkflowLibrary(tmp_path)
    registered = library.register(bundle())
    value = deepcopy(registered)
    value['subworkflows'][0]['implementation'].pop('source_files')
    from jiuwenswarm.software_factory.workflow_library import digest, write_json
    value['version'] = 'sha256:' + digest(library._canonical(value))
    path = library.definitions / 'strata' / value['version'].split(':')[1] / 'workflow.json'
    write_json(path, value)
    with pytest.raises(StageFailure) as caught:
        library.resolve('strata', value['version'], 'report')
    assert caught.value.code == 'implementation_unpinned'


@pytest.mark.parametrize('invalid', ['source.algorithm', {'kind': 'source.algorithm'},
                                    {'semantic_type': 'source.algorithm', 'required': 'yes'}])
def test_port_declarations_are_concrete_runtime_compatible_objects(tmp_path, invalid):
    value = bundle()
    value['subworkflows'][0]['inputs']['algorithm'] = invalid
    with pytest.raises(StageFailure) as caught:
        WorkflowLibrary(tmp_path).register(value)
    assert caught.value.code == 'invalid_ports'


def test_unreadable_pinned_dependency_is_explicitly_rejected(tmp_path, monkeypatch):
    library = WorkflowLibrary(tmp_path)
    registered = library.register(bundle())
    original = Path.read_bytes

    def missing(path):
        if path.name == 'native_build.py':
            raise FileNotFoundError('isolated test removed a pinned implementation dependency')
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', missing)
    with pytest.raises(StageFailure) as caught:
        library.resolve('strata', registered['version'], 'report')
    assert caught.value.code == 'implementation_changed'


def test_source_reads_fixed_git_object_instead_of_changed_worktree(tmp_path):
    import subprocess
    checkout=tmp_path/'upstream'
    checkout.mkdir()
    def git(*arguments):
        return subprocess.run(['git','-C',str(checkout),*arguments],check=True,capture_output=True,text=True).stdout.strip()
    git('init','-q')
    original='int fixed_source() { return 1; }\n'
    source=checkout/'core.cpp'
    source.write_text(original)
    git('add','core.cpp')
    git('-c','user.name=Isolated test','-c','user.email=test@example.invalid','commit','-qm','pin source')
    value=bundle()
    value['source'].update(checkout=str(checkout),revision=git('rev-parse','HEAD'))
    library=WorkflowLibrary(tmp_path/'library')
    registered=library.register(value)
    source.write_text('int changed_worktree() { return 999; }\n')
    result=library.read_source('strata',registered['version'],'core.cpp')
    assert result['content']==original
    assert source.read_text()!=original


def test_cc_definition_requires_real_runtime_adapter(tmp_path):
    value=bundle()
    value['subworkflows'][0]['implementation']={'type':'cc','bundle':'test-only','capability':'test-only'}
    with pytest.raises(StageFailure) as caught:
        WorkflowLibrary(tmp_path/'library').register(value)
    assert caught.value.code=='unsupported_executor'
