"""Factory Runs uses the concrete checked product and native graph records."""
from jiuwenswarm.gateway.channel_manager.web import factory_nodes


def observation(obs_id, kind, values, created, artifacts=()):
    return dict(obs_id=obs_id, kind=kind, values=values, created=created, source_artifacts=list(artifacts))


def test_checked_pack_plan_and_image_use_linked_records_and_receipts():
    provenance = dict(run_id='original', job_id='123456789', duration_seconds=8160)
    pack = dict(files=[{'bytes': 4096}, {'bytes': 8192}], census={'routed_expert': {'nvfp4': 180}})
    plan = dict(format='factory.prefill-batch-plan/1', batch=2048, ubatch=2048, args=['-b', '2048', '-ub', '2048'],
                device_budget_mib=110000, estimate_mib=108900, moe_cache_mib=61000)
    records = [observation('replay', 'capped_run', dict(recipe='convert', replayed_from=provenance), 1),
               observation('manifest', 'pack_manifest', dict(manifest=pack, capped_run_id='replay'), 2),
               observation('plan', 'batch_plan', plan, 3)]
    records += [observation('check-pack', 'node_check', dict(refs={'evidence_ids': ['manifest']}), 4),
                observation('check-batch', 'node_check', dict(refs={'evidence_ids': ['plan']}), 5),
                observation('check-image', 'node_check', dict(refs={'build_attempt_id': 'builder'}), 6)]
    artifacts = {'builder:receipt': {'image_id': 'sha256:image'}, 'builder:build-record': {
        'image': {'Id': 'sha256:image', 'RepoTags': ['factory/llamacpp:tag']}, 'executable_sha256': 'binary'}}
    data = dict(observations=records, artifacts=[dict(artifact_id=aid) for aid in artifacts])
    checks = [dict(name=name, kind=kind, checks=[dict(state='finished', superseded=False, cited=True, obs_id=rid)])
              for name, kind, rid in [('nvfp4_pack', 'evidence', 'check-pack'), ('batch_plan', 'evidence', 'check-batch'),
                                      ('image', 'image', 'check-image')]]
    packed, planned, image = factory_nodes.outputs_view(data, {'node_id': 'example'}, checks,
                                                       lambda row: artifacts[row['artifact_id']])
    assert packed['summary'] == dict(census=pack['census'], shard_count=2, bytes=12288)
    assert packed['replayed_from'] == provenance and 'originally 136 min' in packed['replay_source']
    assert planned['summary'] == plan
    assert image['summary'] == dict(image_id='sha256:image', tag='factory/llamacpp:tag', binary_sha256='binary',
                                   build_receipt='builder:receipt')


def test_native_replay_keeps_revision_and_verified_keys_in_recorded_order():
    task = dict(task_id='r8', contract_id='muse-2bit-demo-r8', objective='demo')
    done = dict(node_id='wiring', state='done', title='Wire scales', evidence_ids=['check'], reason='Verified')
    check = observation('check', 'node_check', {}, 6, ['diff', 'bad'])
    revise = observation('revision', 'taskgraph_patch', dict(origin='operator', rev=2,
                         patch={'revise': [{'node_id': 'wiring', 'action': 'add'}]}), 4)
    output = [dict(path='artifacts/diff', display_path='Retained change', artifact_ids=['diff'], integrity='verified'),
              dict(path='artifacts/bad', display_path='Damaged', artifact_ids=['bad'], integrity='mismatch')]
    data = dict(tasks=[task], observations=[check, revise])
    assert factory_nodes.native_replay(data, {'nodes': [dict(done, state='proposed')]}, output, 'graph-r8') is None
    replay = factory_nodes.native_replay(data, {'nodes': [done]}, output, 'graph-r8')
    revision, step = replay['steps']
    assert revision['graph_rev'] == 2 and revision['primary_record'] == 'revision'
    assert step['event_cursor'] == 2 and step['node_id'] == 'wiring' and step['graph_nodes'] == ['wiring']
    assert step['key_files'] == [dict(path='artifacts/diff', label='Retained change')]


def test_stopped_run_cites_latest_matching_terminal_decision_and_is_not_curated():
    task = dict(task_id='r8', contract_id='muse-2bit-demo-r8', objective='demo')
    outcome = 'stop_missing_prerequisite'
    reason = 'The required eight-prompt suite is missing; the downstream checks remain open.'
    decision = dict(decision_id='r8:decision:17', rev=17, created=20, action={'type': outcome},
                    reason_for_change=reason, observations={'node_id': 'requant_2bit'})
    old_stop = dict(decision, rev=12, decision_id='r8:decision:12', reason_for_change='An older stop.')
    unrelated = dict(decision, rev=18, decision_id='r8:decision:18', reason_for_change='Unrelated evidence.',
                     action={'type': 'investigate'})
    controller_state = dict(finished=21, stop_reason='paused at a previous step checkpoint (STEP.md)')
    data = dict(tasks=[task], decisions=[unrelated, decision, old_stop], observations=[],
                _meta=dict(outcome=outcome, controller_state=controller_state))
    complete = dict(node_id='requant_2bit', state='done', title='Quantize', evidence_ids=['check'])
    assert factory_nodes.run_state(data, {'nodes': [dict(complete, state='proposed')]}, {}, False, 30) == dict(
        state='stopped', outcome=outcome, reason=reason, by=None, since=21, node_id='requant_2bit',
        job=None, markers={}, source='r8:decision:17')
    assert factory_nodes.native_replay(data, {'nodes': [complete]}, [], 'graph-r8') is None
    data['decisions'] = []
    assert factory_nodes.run_state(data, {'nodes': [complete]}, {}, False, 30)['reason'] is None


def test_terminal_decision_takes_precedence_over_stale_worker_and_cap_job():
    attempt = dict(attempt_id='old-job', state='running', request={'node_id': 'deliver'})
    decision = dict(decision_id='terminal', rev=12, created=16, action={'type': 'accept'})
    data = dict(tasks=[{'task_id': 'demo'}], observations=[], attempts=[attempt], decisions=[decision],
                _meta=dict(outcome='accept', controller_state=dict(finished=17, stop_reason='checkpoint')))
    state = factory_nodes.run_state(data, {'nodes': []}, {}, True, 20)
    assert (state['state'], state['source'], state['since']) == ('finished', 'terminal', 17)
    assert state['job'] is None and state['reason'] is None
    data['_meta'] = dict(outcome=None, controller_state={})
    state = factory_nodes.run_state(data, {'nodes': []}, {}, True, 20)
    assert (state['state'], state['source'], state['since']) == ('finished', 'terminal', 16)


def test_finished_capped_record_clears_stale_wait_while_a_new_job_can_run():
    old = dict(attempt_id='stale', state='running', request={'node_id': 'build'})
    data = dict(tasks=[{'task_id': 'demo'}], observations=[
        observation('final', 'capped_run', dict(attempt_id='stale', outcome='ok'), 12)
    ], attempts=[old], _meta=dict(outcome=None, controller_state={}))
    assert factory_nodes.run_state(data, {'nodes': []}, {}, False, 20)['state'] == 'idle'
    data['attempts'].append(dict(old, attempt_id='new'))
    assert factory_nodes.run_state(data, {'nodes': []}, {}, False, 20)['job']['attempt_id'] == 'new'


def test_pack_census_appears_on_the_pack_verifier_card_once(monkeypatch):
    pack = dict(id='pack', name='pack', kind='pack', summary={'census': {'q2_k': 62}})
    producer, runner = 'weights.pack_compiler', 'factory.capped_runner'
    final = {'work': {'bound_ccs': [producer, runner]}, 'outputs': [{'name': 'pack', 'kind': 'evidence'}]}
    monkeypatch.setattr(factory_nodes, 'contract_view', lambda *args: dict(final=final))
    monkeypatch.setattr(factory_nodes, 'outputs_view', lambda *args: [pack])
    monkeypatch.setattr(factory_nodes, 'cc_row', lambda catalog, cc, version, **kwargs: {'id': cc})
    data = dict(tasks=[{'task_id': 'demo'}])
    outputs = [dict(name='pack', verifier=f'{producer}.verify_pack', checks=[])]
    result = factory_nodes.node_detail(data, {'node_id': 'quantize'}, {'outputs': outputs}, None, [], [], {}, None)
    pack_card, runner_card = result['capsules']
    assert pack_card['outputs'] == [pack] and runner_card['outputs'] == []
    assert runner_card['checks'] == outputs


def test_checked_patch_reports_the_producing_check_when_reused_later():
    artifact = 'node-check-abcd-diff'
    old = observation('old-check', 'node_check', {'head': 'source-base'}, 10, [artifact])
    new = observation('new-check', 'node_check', {'head': 'later-base', 'reused_from': 'old-check'}, 12, [artifact])
    check = dict(state='finished', superseded=False, cited=True, obs_id='new-check', artifacts=[artifact])
    data = dict(observations=[old, new], artifacts=[dict(artifact_id=artifact, sha256='patch-sha')])
    [patch] = factory_nodes.outputs_view(data, {}, [dict(name='change', kind='diff', checks=[check])])
    assert patch['source'] == 'new-check'
    assert patch['summary'] == dict(diff_artifact_id=artifact, diff_source='old-check', base='source-base', sha256='patch-sha')
