"""Step-through history retains the meaning and provenance of each stage."""
from jiuwenswarm.factory import corrections, story
from jiuwenswarm.gateway.channel_manager.web.factory_nodes import native_replay


def obs(key, when, kind, **values):
    return dict(obs_id=key, kind=kind, values=values, created=when)


def check(key, when, *, review=None, refs=(), node='a', passed=True, verifier=True, **extra):
    return obs(key, when, 'node_check', node_id=node, output='recipe', state='finished', passed=passed,
               review=review, entry={'review': 'advisory'}, verifier={'passed': verifier}, refs={'evidence_ids': list(refs)},
               **extra)


def test_note_repair_and_pass_have_distinct_sources_and_leave_unresolved_findings():
    first = check('original-check', 10, review={'verdict': 'fail', 'reviewer': 'lead-reviewer', 'findings': [
        {'severity': 'blocker', 'problem': 'Recipe pin omits the production commit.', 'file': 'recipe.json', 'line': 8},
        {'severity': 'minor', 'problem': 'Keep the held-out comparison pending.'},
    ]})
    repaired = obs('repair-proof', 30, 'worker_correction', node_id='a',
                   addresses_findings=['original-check#reviewer-1'], summary='Recorded the production commit.')
    unchanged = check('unchanged-pass', 24, review={'verdict': 'pass'})
    wrong_output = check('other-output-pass', 31, review={'verdict': 'pass'}, refs=['repair-proof'])
    wrong_output['values']['output'] = 'different'
    fixed = check('later-pass', 40, refs=['repair-proof'], review={'verdict': 'pass'})
    data = dict(tasks=[{'task_id': 'r8', 'contract_id': 'muse-2bit-demo-r8', 'objective': 'Demo'}],
                observations=[first, unchanged, repaired, wrong_output, fixed], _operator_notes=[
                    dict(note_id='step-release', created=20, text='Operator release on plan node a: original-check.'),
                    dict(note_id='targeted', created=22, by='operator',
                         text='On original-check#reviewer-1. Use the receipt to record the production commit.'),
                ])
    trail = corrections.project(data)['a']
    assert trail['counts'] == {'findings': 2, 'notes': 1, 'repairs': 1}
    minor = next(e for e in trail['events'] if e.get('severity') == 'minor')
    assert minor['status'] == 'open'
    blocker, _, initial = trail['events'][:3]
    assert blocker['verdict'] == 'fail' and blocker['advisory'] and blocker['host_passed']
    assert blocker['status'] == 'verified_repair' and blocker['file'] == 'recipe.json' and blocker['line'] == 8
    assert initial['kind'] == 'passing_check' and initial['reviewer_verdict'] == 'fail' and not initial['finding_ids']
    note, repair, final = [next(e for e in trail['events'] if e['source'] == source)
                           for source in ('targeted', 'repair-proof', 'later-pass')]
    assert note['by'] == 'operator' and note['finding_ids'] == [blocker['id']]
    assert repair['note_ids'] == ['targeted'] and repair['passing_check_id'] == 'later-pass'
    assert final['finding_ids'] == [blocker['id']] and final['host_passed'] and final['verifier_passed']
    live_events = [e['correction'] for e in story.build_events(data) if e.get('correction')]
    assert [e['source'] for e in live_events] == [e['source'] for e in trail['events']]
    nodes = [dict(node_id='a', title='Recipe', state='done', evidence_ids=['later-pass'])]
    replay = native_replay(data, {'nodes': nodes}, [], 'graph-r8', trails={'a': trail})
    assert [e['source'] for step in replay['steps'] if (e := step.get('correction'))] == [e['source'] for e in live_events]


def test_blocking_verifier_refusal_and_advisory_failure_without_rows_survive():
    failed = check('blocked', 10, passed=False, verifier=False, reason='Verifier call blocked: missing input.')
    advisory = check('advisory', 12, review={'verdict': 'fail', 'summary': 'Independent review failed.'})
    reused = check('reused', 13, review=advisory['values']['review'], reused_from='advisory')
    data = dict(tasks=[{'task_id': 'case'}], observations=[failed, advisory, reused], _operator_notes=[
        dict(note_id='precise', created=11, text='For blocked. Supply the missing input.'),
        dict(note_id='similar', created=11, text='For blocked-sibling. Supply the missing input.'),
    ])
    trail = corrections.project(data)['a']
    assert trail['counts'] == {'findings': 2, 'notes': 1, 'repairs': 0}
    verifier, note, reviewer, passed = trail['events']
    assert verifier['actor'] == 'verifier' and not verifier['advisory'] and not verifier['host_passed']
    assert note['source'] == 'precise' and note['finding_ids'] == [verifier['id']]
    assert reviewer['actor'] == 'reviewer' and reviewer['advisory'] and reviewer['verdict'] == 'fail'
    assert passed['host_passed'] and passed['verifier_passed'] and passed['reviewer_verdict'] == 'fail'


def test_repeated_findings_count_once_per_output_and_keep_source_events():
    finding = {'severity': 'minor', 'problem': 'Missing source pin', 'file': 'recipe.json', 'line': 8}
    first = check('first', 10, review={'verdict': 'fail', 'findings': [finding]})
    repeat = check('repeat', 20, review={'verdict': 'fail', 'findings': [dict(finding, problem='Missing  source pin')]})
    other = check('other', 30, review={'verdict': 'fail', 'findings': [finding]})
    other['values']['output'] = 'pack'
    data = dict(tasks=[{'task_id': 'case'}], observations=[first, repeat, other])
    trail = corrections.project(data)['a']
    assert trail['counts']['findings'] == 2
    findings = [r for r in trail['events'] if r['kind'] == 'finding']
    assert [r['source'] for r in findings] == ['first', 'repeat', 'other']
    assert findings[0]['finding_key'] == findings[1]['finding_key'] != findings[2]['finding_key']
