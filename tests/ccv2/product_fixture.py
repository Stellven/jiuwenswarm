"""Synthetic source-change fixture for source_build tests (no Strata or GPU claim)."""
import json
from pathlib import Path
import shutil
import subprocess

REFERENCE = Path(__file__).resolve().parent


def fixture(directory, host):
    directory = Path(directory); directory.mkdir(parents=True)
    repository = directory/'repository'; repository.mkdir()
    example = REFERENCE/'examples/http_product'
    (repository/'server.py').write_bytes((example/'payload/server.py').read_bytes())
    (repository/'.gitignore').write_text('dist/\n', encoding='utf-8')
    (repository/'dependencies.json').write_text('{"python":">=3.10","packages":[],"runtime":"stdlib"}\n', encoding='utf-8')
    (repository/'build.py').write_text("from pathlib import Path\nimport shutil\nPath('dist').mkdir(exist_ok=True)\nshutil.copyfile('server.py', 'dist/server.py')\n", encoding='utf-8')
    def git(*arguments):
        return subprocess.check_output(['git', '-c', 'core.autocrlf=false', *arguments], cwd=repository, stderr=subprocess.PIPE)
    git('init'); git('add', '.')
    git('-c', 'user.name=CC synthetic fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Synthetic base')
    base = git('rev-parse', 'HEAD').decode().strip()
    source = (repository/'server.py').read_text(encoding='utf-8').replace('FACTOR = 1', 'FACTOR = 2')
    (repository/'server.py').write_text(source, encoding='utf-8', newline='\n')
    git('add', 'server.py')
    patch = directory/'candidate.patch'; patch.write_bytes(git('diff', '--cached', '--binary', '--full-index', base))
    tree = git('write-tree').decode().strip()
    template = directory/'template'; template.mkdir()
    for name in ('cc.yaml', 'inspect.py', 'api.json'):
        shutil.copyfile(example/name, template/name)
    change = {'format': 'cc-source-change/1', 'repository': str(repository), 'base': base,
              'patch': host.put_artifact(patch), 'tree': tree,
              'build': {'command': ['{python}', 'build.py'], 'lock': 'dependencies.json', 'output': 'dist'}}
    (directory/'source-change.json').write_text(json.dumps(change, indent=2), encoding='utf-8')
    return template, change

