"""Place the recorded planner seed between contract admission and scheduler work."""
TITLE = 'The plan: the planner turns the contract into a task graph and rough node contracts'
LINE = 'The planner lays out the jobs and suggests capsules. The scheduler then binds the capsules and finalizes each node contract.'


def planner_step(planner, task_id, home):
    source = planner['source']
    node_ids = planner['plan_order']
    summary = f'{len(node_ids)} planned nodes. Open the plan to see their order, draft contracts and suggested capsules.'
    receipts = planner.get('read_receipts') or []
    if receipts:
        summary += f' The plan includes {len(receipts)} recorded planner read receipts.'
    return dict(primary_record=source['id'], created=source['created'], graph_rev=source['revision'],
                presentation_title=TITLE, original_kind='taskgraph_patch', original_summary=summary,
                say=summary, presenter_line=LINE, graph_nodes=[], recorded_plan_nodes=[],
                key_files=[dict(path=planner['artifact']['path'], label='Planner’s plan record',
                                why='Recorded task graph, rough node contracts and available planner read receipts.')],
                records=[dict(table='observations', id=source['id'], source_home=home, task_id=task_id)])


def curated_with_plan(replay, planner, task_id, home):
    if not planner or not replay or not replay['steps']:
        return replay
    steps = list(replay['steps'])
    if not any(step['primary_record'] == planner['source']['id'] for step in steps):
        steps.insert(1, planner_step(planner, task_id, home))
    return dict(replay, steps=[dict(step, step=index, event_cursor=index) for index, step in enumerate(steps, 1)])


def native_with_plan(events, planner, task, home):
    if not planner:
        return events
    step = planner_step(planner, task['task_id'], home)
    record_id = step['primary_record']
    contract_id = task['task_id']
    rows = [e for e in events if e['id'] not in (record_id, contract_id)]
    rows.extend([
        dict(id=contract_id, created=task['created'], kind='task', summary=task['objective'],
             presentation_title='The contract', mark='·'),
        dict(id=record_id, created=step['created'], kind='taskgraph_patch', summary=step['say'],
             presentation_title=TITLE, presenter_line=LINE, key_file=step['key_files'][0]['path'],
             rev=step['graph_rev'], mark='·'),
    ])
    rows.sort(key=lambda e: e['created'])
    return [dict(row, cursor=i) for i, row in enumerate(rows, 1)]
