"""Builder evidence spans releases: each item is labelled with the release that produced it."""

from jiuwenswarm.gateway.channel_manager.web.capsule_evidence import (
    _capsule_version, _iteration_lab, _latest_builder_evidence)

CC = 'engine.build_expert_weight_cache'


def iteration():
    return {
        'schema': 'spark-factory-iteration/1', 'iteration_id': 'p4-cache60',
        'plan': {'builder_ccs': [{'id': CC, 'version': '1.3.0', 'release': 'f' * 64}]},
        'lab': {'result_artifact_ids': ['p4/raw/runs/p4-c3-pass-1-01/profile-activation.json@' + 'a' * 64]},
        'analysis': {
            'result_artifact': {'artifact_id': 'p4/analysis.json', 'sha256': 'b' * 64},
            'focused_comparison': {
                'profiles': {'A+': {'binary_sha256': '0' * 64}, 'C3': {'binary_sha256': '6' * 64}},
                'rows': [{'prompt_tokens': 512, 'paired_ttft_seconds_saved_vs_Aplus': {'estimate': 27.0817}}],
            },
        },
    }


def reader(files):
    def read(reference, digest):
        aid = reference.split('@', 1)[0]
        if aid not in files:
            return None, None
        return files[aid], dict(run_id='r', run_name='bench', artifact_id=aid, kind='lab', integrity='verified')
    return read


def test_iteration_lab_recomputes_parity_and_activation_from_published_artifacts():
    files = {
        'p4/analysis.json': {'mode': 'p4-abba', 'eligible': [
            {'arm': 'A+', 'prompt_tokens': 512, 'output_sha256': 'x'},
            {'arm': 'C3', 'prompt_tokens': 512, 'output_sha256': 'x'},
        ]},
        'p4/raw/runs/p4-c3-pass-1-01/profile-activation.json': {'marker': 'cache_native_profile: active seeds=7'},
    }
    lab = _iteration_lab(iteration(), CC, reader(files), 10)
    assert lab['parity'] is True and lab['activation'] is True
    assert lab['binary_sha256'] == '6' * 64 and lab['version'] == '1.3.0'
    assert lab['metrics'] == {'paired_ttft_saved_s_512': 27.08}
    files['p4/analysis.json']['eligible'][1]['output_sha256'] = 'y'
    assert _iteration_lab(iteration(), CC, reader(files), 10)['parity'] is False
    assert _iteration_lab(iteration(), CC, reader({}), 10)['parity'] is None


def test_latest_evidence_pairs_the_lab_with_its_build_across_runs_and_releases():
    build_old = dict(run_id='a', run_name='do-01', binary_sha256='6' * 64, created=1, version='1.3.0')
    build_new = dict(run_id='b', run_name='do-02', binary_sha256='3' * 64, created=5, version='1.4.1')
    lab = dict(run_id='c', run_name='bench', binary_sha256='6' * 64, parity=True, activation=True,
               created=4, version='1.3.0')
    report = dict(run_id='c', run_name='bench', artifact_id='report-v3.md', created=4, revision=3, version='1.3.0')
    summary = _latest_builder_evidence([
        dict(builds=[build_old], labs=[], reports=[]),
        dict(builds=[build_new], labs=[], reports=[]),
        dict(builds=[], labs=[lab], reports=[report]),
    ])
    assert summary['lab'] is lab and summary['build'] is build_old and summary['report'] is report
    assert summary['run_id'] == 'c'
    assert _latest_builder_evidence([]) is None


def test_run_capsule_version_comes_from_task_resources():
    task = {'resources': {'capsules': [f'{CC}@1.4.0', 'factory.builder']}}
    assert _capsule_version(task, CC) == '1.4.0'
    assert _capsule_version(task, 'factory.builder') is None
