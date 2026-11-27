from jiuwenswarm.gateway.channel_manager.web.factory_planner_story import curated_with_plan, native_with_plan


def test_adds_plan_in_story_without_changing_native_records():
    planner = dict(source=dict(id='run:plan:1', created=2, revision=1), plan_order=['pin', 'build'],
                   artifact=dict(path='projections/planner-plan.json'), read_receipts=[])
    originals = [dict(step=1, primary_record='run'), dict(step=2, primary_record='final')]
    replay = curated_with_plan({'steps': originals}, planner, 'run', 'graph')
    assert [s['primary_record'] for s in replay['steps']] == ['run', 'run:plan:1', 'final']
    assert [s['event_cursor'] for s in replay['steps']] == [1, 2, 3]
    assert originals[-1]['step'] == 2
    assert replay['steps'][1]['key_files'][0]['path'] == planner['artifact']['path']

    task = dict(task_id='run', objective='test engine', created=1)
    events = [dict(id='run:plan:1', created=2), dict(id='final', created=3)]
    live = native_with_plan(events, planner, task, 'graph')
    assert [e['id'] for e in live] == ['run', 'run:plan:1', 'final']
    assert [e['cursor'] for e in live] == [1, 2, 3]
    assert live[1]['key_file'] == planner['artifact']['path']
