"""Source bundles: the factory ships a diff, the lab assembles and builds the exact tree."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from jiuwenswarm.factory import lab_build
from jiuwenswarm.factory.lab_agent import CommandAdapter, LabAgent, serve
from jiuwenswarm.factory.lab_build import BuildError, assemble, make_bundle, read_bundle
from jiuwenswarm.factory.lab_manager import LabManager

from test_lab_manager import lab_task

RECIPES = {'hello': dict(does='test program', machine=None, targets=['hello'], executable='hello', flags=['-DCMAKE_BUILD_TYPE=Release'],
                         env={}, library_roots=[], runtime=None)}


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *args],
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(lab_build, 'RECIPES', RECIPES)
    root = tmp_path / 'engine'
    root.mkdir()
    git(tmp_path, 'init', '-q', str(root))
    (root / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.10)\nproject(hello C)\n'
                                         'add_executable(hello main.c util.c)\n'
                                         'if(DEFINED DEP_DIR)\n  target_compile_definitions(hello PRIVATE HAVE_DEP=1)\n'
                                         '  target_include_directories(hello PRIVATE ${DEP_DIR})\nendif()\n')
    (root / 'main.c').write_text('#include <stdio.h>\nint util(void);\nint main(void){printf("stock %d\\n", util());return 0;}\n')
    (root / 'util.c').write_text('int util(void){return 1;}\n')
    git(root, 'add', '-A')
    git(root, 'commit', '-q', '-m', 'base')
    return root, git(root, 'rev-parse', 'HEAD')


def run_app(record):
    return subprocess.run([str(Path(record['app']) / 'hello')], capture_output=True, text=True).stdout.strip()


def test_lab_rebuilds_the_exact_tree_and_rebuilds_warm(repo, tmp_path):
    root, base = repo
    (root / 'main.c').write_text('#include <stdio.h>\nint util(void);\nint main(void){printf("cache %d\\n", util());return 0;}\n')
    (root / 'new.txt').write_bytes(b'\x00binary\xff')  # untracked files travel too
    made = make_bundle(root, base, tmp_path / 'a.tar', 'hello', include_base=True)
    assert made['repository'] is None and read_bundle(tmp_path / 'a.tar')['source']['base_bundle']
    first = assemble(tmp_path / 'a.tar', tmp_path / 'cache')
    assert first['head_tree'] == made['head_tree'] and not first['warm'] and run_app(first) == 'cache 1'

    # A second diff on the same base reuses the slot: no configure, only the touched file recompiles.
    (root / 'main.c').write_text('#include <stdio.h>\nint util(void);\nint main(void){printf("stock %d\\n", util());return 0;}\n')
    (root / 'util.c').write_text('int util(void){return 2;}\n')
    second_bundle = make_bundle(root, base, tmp_path / 'b.tar', 'hello', include_base=True)
    second = assemble(tmp_path / 'b.tar', tmp_path / 'cache')
    assert second['warm'] and second['slot'] == first['slot'] and 'configure' not in second['seconds']
    assert run_app(second) == 'stock 2' and second['head_tree'] == second_bundle['head_tree']


def test_a_changed_patch_or_tree_is_refused(repo, tmp_path):
    root, base = repo
    (root / 'util.c').write_text('int util(void){return 3;}\n')
    make_bundle(root, base, tmp_path / 'a.tar', 'hello', include_base=True)
    work = tmp_path / 'x'
    with tarfile.open(tmp_path / 'a.tar') as archive:
        archive.extractall(work, filter='data')
    (work / 'patch.diff').write_bytes((work / 'patch.diff').read_bytes().replace(b'return 3', b'return 4'))
    with tarfile.open(tmp_path / 'tampered.tar', 'w') as archive:
        for path in sorted(work.iterdir()):
            archive.add(path, path.name)
    with pytest.raises(BuildError, match='differs from its digest'):
        assemble(tmp_path / 'tampered.tar', tmp_path / 'cache')
    document = json.loads((work / 'source.json').read_text())
    document['source']['patch']['sha256'] = lab_build.sha256_file(work / 'patch.diff')
    (work / 'source.json').write_text(json.dumps(document))
    with tarfile.open(tmp_path / 'retree.tar', 'w') as archive:
        for path in sorted(work.iterdir()):
            archive.add(path, path.name)
    with pytest.raises(BuildError, match='is not the tree under test'):
        assemble(tmp_path / 'retree.tar', tmp_path / 'cache')


def test_recipes_and_flags_are_the_lab_s_choice(repo, tmp_path):
    root, base = repo
    with pytest.raises(BuildError, match='Unknown recipe'):
        make_bundle(root, base, tmp_path / 'a.tar', 'rm-rf')
    with pytest.raises(BuildError, match='-DNAME=value'):
        make_bundle(root, base, tmp_path / 'a.tar', 'hello', extra_flags=['$(reboot)'])
    make_bundle(root, base, tmp_path / 'a.tar', 'hello', include_base=True, extra_flags=['-DHELLO_EXTRA=1'])
    with pytest.raises(BuildError, match='no recipe'):
        assemble(tmp_path / 'a.tar', tmp_path / 'cache', recipes={})


def test_source_dependencies_are_assembled_and_passed_to_cmake(repo, tmp_path):
    root, base = repo
    dep = tmp_path / 'dep'
    dep.mkdir()
    git(tmp_path, 'init', '-q', str(dep))
    (dep / 'dep.h').write_text('#define DEP_VALUE 7\n')
    git(dep, 'add', '-A')
    git(dep, 'commit', '-q', '-m', 'dep')
    dep_base = git(dep, 'rev-parse', 'HEAD')
    (dep / 'dep.h').write_text('#define DEP_VALUE 9\n')
    (root / 'util.c').write_text('#ifdef HAVE_DEP\n#include "dep.h"\nint util(void){return DEP_VALUE;}\n#else\nint util(void){return 0;}\n#endif\n')
    make_bundle(root, base, tmp_path / 'a.tar', 'hello', include_base=True,
                deps=[dict(name='ggml', checkout=dep, base=dep_base, cmake_var='DEP_DIR', include_base=True)])
    record = assemble(tmp_path / 'a.tar', tmp_path / 'cache')
    assert run_app(record) == 'stock 9' and record['deps'][0]['name'] == 'ggml'


def test_lab_manager_ships_source_and_the_command_lab_builds_it(repo, store, tmp_path, monkeypatch):
    root, base = repo
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    monkeypatch.setenv('FACTORY_LAB_BUILD_CACHE', str(tmp_path / 'lab-cache'))
    store.create_task(dict(task_id='lt', objective='o', contract_id='star-deepseek-v2'))
    (root / 'util.c').write_text('int util(void){return 5;}\n')
    manager = LabManager(store, route='mailbox')
    shipped = manager.source_bundle('lt', root, base, 'hello', include_base=True)
    subjects = dict(stock=dict(kind='stock', identity=dict(name='stock llama.cpp')), cache=shipped['subject'])
    composed = manager.compose('lt', lab_task(subjects))
    assert composed['payloads']['cache']['format'] == 'source-bundle'
    request = manager.send('lt', composed['package_id'], 'src')['request_id']
    script = tmp_path / 'lab.py'
    script.write_text('''import json, subprocess, sys
from pathlib import Path
payloads = json.loads(Path(sys.argv[3]).read_text())
out = Path(sys.argv[2])
ran = subprocess.run([payloads["cache"]["build"]["app"] + "/hello"], capture_output=True, text=True).stdout
(out / "files" / "samples").write_text(ran)
report = dict(outcome="completed", summary="built from source and ran",
  results=[dict(test_id="ttft", arm=a, request="p512", metric="client_ttft_ms", unit="ms", samples=[1.0]) for a in ("A", "C3")],
  checks=[dict(test_id="parity", check="gate_unset_parity", arm="C3", verdict="pass")], limits=["test"])
(out / "report.json").write_text(json.dumps(report))
''')
    agent = LabAgent(manager.mailbox, 'builder-lab', 'command')
    adapter = CommandAdapter(f'{sys.executable} {script} {{package}} {{output}} {{payloads}}', tmp_path / 'work', build_sources=True)
    monkeypatch.setattr(lab_build, 'RECIPES', RECIPES)
    serve(agent, adapter, once=True, log=lambda line: None)
    serve(agent, adapter, once=True, log=lambda line: None)
    recorded = manager.report('lt', request)
    assert recorded['valid'], recorded['problems']
    assert store.artifact_bytes('lt', recorded['report']['files'][0]['artifact_id']).decode().strip() == 'stock 5'
    observation = store.read('lt', recorded['evidence_id'])
    assert observation['values']['valid']
    report_message = manager.mailbox.latest(request, 'report')
    assert report_message['body']['builds']['cache']['head_tree'] == shipped['subject']['identity']['head_tree']


def test_agent_checkouts_must_be_in_the_workspace(repo, store, tmp_path, monkeypatch):
    from jiuwenswarm.factory.lab_manager import dispatch
    from jiuwenswarm.factory.store import ScopeDenied
    root, base = repo
    store.create_task(dict(task_id='lt', objective='o', contract_id='star-deepseek-v2'))
    monkeypatch.setenv('FACTORY_WORKSPACE', str(tmp_path / 'workspace'))
    with pytest.raises(ScopeDenied):
        dispatch(store.scoped('lt'), 'lt', 'source_bundle', dict(checkout=str(root), base=base, recipe='hello'))


def test_base_fetched_shallow_from_the_repository(repo, tmp_path, monkeypatch):
    """Without a shipped base, the lab fetches only the base commit (depth 1) and builds on it."""
    root, base = repo
    git(root, 'config', 'uploadpack.allowAnySHA1InWant', 'true')
    monkeypatch.setattr(lab_build, '_public_repository', lambda url: url)
    (root / 'util.c').write_text('int util(void){return 8;}\n')
    made = make_bundle(root, base, tmp_path / 'a.tar', 'hello', repository=f'file://{root}')
    assert 'base_bundle' not in read_bundle(tmp_path / 'a.tar')['source']
    record = assemble(tmp_path / 'a.tar', tmp_path / 'cache')
    assert record['head_tree'] == made['head_tree'] and run_app(record) == 'stock 8'
    mirror = next((tmp_path / 'cache' / 'git').iterdir())
    assert (mirror / 'shallow').is_file()
