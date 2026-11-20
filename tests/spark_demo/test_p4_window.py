from argparse import Namespace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

OPS = Path(__file__).resolve().parents[2] / 'ops/spark'


@pytest.fixture
def window(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(OPS))
    spec = importlib.util.spec_from_file_location('run_p4_window', OPS / 'run_p4_window.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'check_scope', lambda *_: tmp_path)
    monkeypatch.setattr(module, 'boundary_resources', lambda path, *_: module.json_write(path, {'quiet': False}))
    monkeypatch.setattr(module, 'snapshot', lambda *_: {'synthetic': True})
    preflight = tmp_path / 'quiet.json'
    preflight.write_text('{"quiet": true}')
    regions = tmp_path / 'manifest.json'
    regions.write_text('{}')
    invoked = []

    def bench(command, **_):
        args = dict(zip(command[2::2], command[3::2]))
        prompt = int(args['--prompt-tokens'])
        repeat = int(args['--repeat'])
        out = Path(args['--out'])
        out.mkdir()
        cache = 0 if repeat != 5 or not bench.contaminate else 1
        output = (str(prompt)[0]) * 64
        module.json_write(out / 'result.json', dict(arm=args['--arm'], prompt_tokens=prompt, repeat=repeat,
            discard=repeat == 0, ok=True, ttft_s=1.0, prompt_sha256=module.sha(Path(args['--prompt']).read_bytes()),
            usage={'prompt_tokens': prompt, 'completion_tokens': 32, 'prompt_tokens_details': {'cached_tokens': cache}},
            timings={'cache_n': cache}, output_sha256=output, reasoning_sha256='0' * 64))
        invoked.append((repeat, prompt))
        return SimpleNamespace(returncode=0)

    bench.contaminate = False
    monkeypatch.setattr(module.subprocess, 'run', bench)

    def launch(number, first_window=None):
        scope = tmp_path / f'scope-{number}'
        scope.mkdir()
        start = {'binary_sha256': '1' * 64, 'start': (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()}
        (scope / 'start.json').write_text(json.dumps(start))
        (scope / 'scope.json').write_text('{"pid":123}')
        return module.run_window(Namespace(scope=scope, quiet_preflight=preflight, regions=regions, arm='A', port=8082,
                                           view='llama', launch_pass=number, first_window=first_window,
                                           pages_per_sample=4096, seed=20261120))

    return launch, invoked, bench


def test_mirrored_window_cells_and_pre_measure_receipts(window):
    launch, invoked, _ = window
    first = launch(1)
    warm = [(0, 512), (0, 2048)] * 2
    assert invoked == warm + [(1, 512), (1, 2048), (2, 2048), (2, 512)]
    invoked.clear()
    second = launch(2, first)
    assert invoked == warm + [(3, 512), (3, 2048), (4, 2048), (4, 512), (5, 512), (5, 2048)]
    data = json.loads(second.read_bytes())
    assert data['status'] == 'complete'
    assert (second.parent / data['requests'][4]['residency']).is_file()


def test_cache_contamination_gives_failed_receipt(window):
    launch, _, bench = window
    first = launch(1)
    bench.contaminate = True
    with pytest.raises(ValueError, match='cache reuse'):
        launch(2, first)
    failed = first.parents[2] / 'scope-2/p4-window/window.json'
    assert json.loads(failed.read_bytes())['status'] == 'failed'
