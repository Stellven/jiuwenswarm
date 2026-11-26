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
