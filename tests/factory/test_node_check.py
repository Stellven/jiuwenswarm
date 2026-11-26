"""Node checks: the host verifies a node's diff, then an independent reviewer judges it."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from jiuwenswarm.factory import node_check
from jiuwenswarm.factory.node_check import NodeChecks, parse_review, validate_spec
from jiuwenswarm.factory.store import ScopeDenied
from jiuwenswarm.factory.taskgraph import plan_get, plan_patch

VERIFY = '''import json, sys
import subprocess
packet = json.load(sys.stdin)
inputs = packet["inputs"]
diff = open(inputs["diff_path"]).read() if inputs.get("diff_path") else subprocess.run(
    ["git", "-C", inputs["checkout"], "diff", "HEAD"], capture_output=True, text=True).stdout
ok = "BAD" not in diff
checks = [dict(name="no_bad_marker", status="pass" if ok else "fail", stage="native CC execution", detail=""),
          dict(name="syntax", status="pass" if "COMPILES" in diff else "skipped", stage="compile", detail="")]
print(json.dumps(dict(outcome="ok", outputs=dict(done=ok, checks=checks))))
'''
CC_YAML = '''cc: '2'
id: test.build_thing
version: 1.0.0
materials:
  method:
    path: METHOD.md
bindings:
  default:
    kind: native
    command: ['{python}', '{bundle}/run.py']
capabilities:
  verify:
    does: Check a thing diff.
    takes:
      checkout: text
      diff_path: {kind: text, optional: true}
    gives:
      done: json
      checks: json
    needs: [python]
    changes: [workspace.read, process.exec]
'''


class Reviewer:
    identity = 'fake-reviewer'

    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


PASS = dict(verdict='pass', summary='does what the method says', findings=[])


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *args],
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def setup(store, tmp_path):
    ccs = tmp_path / 'ccs'
    (ccs / 'thing').mkdir(parents=True)
    (ccs / 'thing/cc.yaml').write_text(CC_YAML)
    (ccs / 'thing/run.py').write_text(VERIFY)
    (ccs / 'thing/METHOD.md').write_text('# Method\nKeep the feature off by default.\n')
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    git(tmp_path, 'init', '-q', str(checkout))
    (checkout / 'a.c').write_text('int a;\n')
    git(checkout, 'add', '-A')
    git(checkout, 'commit', '-q', '-m', 'base')
    store.advance_decision('t', 0, {'hypothesis': 'SECRET-BUILDER-REASONING build the thing'})
    plan_patch(store, 't', {'add': [dict(node_id='integrate', kind='integrate', title='Integrate the thing',
                                         capability='test.build_thing.verify',
                                         check=dict(verifier='test.build_thing.verify', stage='native CC execution',
                                                    review=True))]}, 0, 1)
    return store, ccs, checkout


def checks(store, ccs, reviewer):
    return NodeChecks(store, reviewer=reviewer, ccs_roots=[ccs])


def done(store, evidence, rev):
    return plan_patch(store, 't', {'update': [dict(node_id='integrate', state='done', evidence_ids=evidence)]}, rev, 1)


def test_spec_validation():
    validate_spec(dict(verifier='a.b.verify', stage='compile', review=True))
    validate_spec(dict(review=True))
    for bad in (dict(), dict(stage='compile', review=True), dict(verifier='verify'), dict(verifier='a.b.verify', stage='fast'),
                dict(review='yes'), dict(verifier='a.b.verify', extra=1)):
        with pytest.raises(ValueError):
            validate_spec(bad)


def test_node_needs_its_latest_passing_check(setup):
    store, ccs, checkout = setup
    with pytest.raises(ValueError, match='needs a passing node check'):
        done(store, ['t'], 1)
    (checkout / 'a.c').write_text('int a = 1; /* COMPILES */\n')
    reviewer = Reviewer(PASS)
    passed = checks(store, ccs, reviewer).start('t', 'integrate', checkout=checkout, background=False)
    assert passed['passed'] and passed['verifier']['stage_reached'] == 'compile' and passed['review']['passed']
    with pytest.raises(ValueError, match='cite the latest passing node check'):
        done(store, ['t'], 1)

    # A newer failing check of other work replaces it: the old pass no longer counts.
    (checkout / 'a.c').write_text('int a = 2; /* BAD */\n')
    failed = checks(store, ccs, reviewer).start('t', 'integrate', checkout=checkout, background=False)
    assert not failed['passed'] and 'no_bad_marker' in failed['reason']
    assert failed['review'] is None and len(reviewer.prompts) == 1  # no review of a diff the verifier failed
    with pytest.raises(ValueError, match='failed'):
        done(store, [passed['obs_id']], 1)

    # Going back to the passing work reuses the earlier result without running anything.
    (checkout / 'a.c').write_text('int a = 1; /* COMPILES */\n')
    again = checks(store, ccs, reviewer).start('t', 'integrate', checkout=checkout, background=False)
    assert again['cached'] and again['passed'] and again['obs_id'] != passed['obs_id'] and len(reviewer.prompts) == 1
    graph = done(store, [again['obs_id']], 1)
    assert next(n for n in graph['nodes'] if n['node_id'] == 'integrate')['state'] == 'done'


def test_reviewer_sees_only_the_step_method_checks_and_diff(setup):
    store, ccs, checkout = setup
    sessions = store.home / 'sessions'
    sessions.mkdir(exist_ok=True)
    (sessions / 't.jsonl').write_text(json.dumps({'event': 'chat', 'text': 'SECRET-SESSION-LOG'}) + '\n')
    (checkout / 'a.c').write_text('int a = 1;\n')
    reviewer = Reviewer(PASS)
    result = checks(store, ccs, reviewer).start('t', 'integrate', checkout=checkout, background=False)
    prompt = reviewer.prompts[0]
    assert 'Keep the feature off by default.' in prompt and '+int a = 1;' in prompt and 'no_bad_marker' in prompt
    assert 'Integrate the thing' in prompt and 'offline build' in prompt
    assert 'SECRET-BUILDER-REASONING' not in prompt and 'SECRET-SESSION-LOG' not in prompt
    review = result['review']
    assert review['reviewer'] == 'fake-reviewer' and review['context'].startswith('objective, step')
    assert store.artifact_bytes('t', review['packet_artifact']).decode() == prompt


@pytest.mark.parametrize('reply,reason', [
    (dict(verdict='pass', summary='ok', findings=[dict(severity='blocker', file='a.c', line=1, problem='gate missing')]), 'blocker'),
    (dict(verdict='fail', summary='wrong approach', findings=[]), 'verdict fail'),
    ('I think it is fine', 'not JSON'),
    (dict(verdict='maybe', findings=[]), 'schema'),
])
def test_reviewer_failures_fail_the_check(setup, reply, reason):
    store, ccs, checkout = setup
    (checkout / 'a.c').write_text('int a = 3;\n')
    result = checks(store, ccs, Reviewer(reply)).start('t', 'integrate', checkout=checkout, background=False)
    assert not result['passed'] and reason in result['reason']
    with pytest.raises(ValueError, match='failed'):
        done(store, [result['obs_id']], 1)


def test_stage_and_task_default_checks(store, tmp_path, setup):
    store, ccs, checkout = setup
    store._db.execute('UPDATE tasks SET constraints=? WHERE task_id=?',
                      (json.dumps({'node_checks': {'tune': {'verifier': 'test.build_thing.verify', 'stage': 'compile'}}}), 't'))
    plan_patch(store, 't', {'add': [dict(node_id='b', kind='tune', title='Tune')]}, 1, 1)
    (checkout / 'a.c').write_text('int a = 4;\n')  # passes, but its syntax check is skipped: no compile stage
    result = checks(store, ccs, None).start('t', 'b', checkout=checkout, background=False)
    assert not result['passed'] and 'needs compile' in result['reason']
    with pytest.raises(ValueError, match='Node b cannot be done'):
        plan_patch(store, 't', {'update': [dict(node_id='b', state='done', evidence_ids=[result['obs_id']])]}, 2, 1)


def test_agents_cannot_forge_or_escape(setup, monkeypatch):
    store, ccs, checkout = setup
    scoped = store.scoped('t')
    with pytest.raises(ScopeDenied):
        scoped.append_observation('t', dict(obs_id='fake', kind='node_check', values=dict(node_id='integrate', passed=True)))
    monkeypatch.setenv('FACTORY_WORKSPACE', str(checkout.parent / 'workspace'))
    with pytest.raises(ScopeDenied):
        node_check.dispatch(scoped, 't', 'start', dict(node_id='integrate', checkout=str(checkout)))
    with pytest.raises(ValueError, match='plan fields'):  # the check is fixed once the node exists
        plan_patch(store, 't', {'update': [dict(node_id='integrate', check=dict(review=True))]}, 1, 1)


def test_background_worker_and_command_reviewer(setup, tmp_path, monkeypatch):
    store, ccs, checkout = setup
    script = tmp_path / 'review.py'
    script.write_text('import json, os, sys\nprompt = sys.stdin.read()\n'
                      'leaked = [k for k in os.environ if k.startswith(("FACTORY_", "JIUWENSWARM_"))]\n'
                      'print(json.dumps(dict(verdict="pass" if not leaked and "+int a = 5;" in prompt else "fail", '
                      'summary=os.getcwd() + " " + ",".join(leaked), findings=[])))\n')
    monkeypatch.setenv('FACTORY_REVIEW_CMD', f'{sys.executable} {script}')
    monkeypatch.setenv('FACTORY_WORKSPACE', str(tmp_path))
    monkeypatch.setattr(node_check, 'capsule_folder', lambda cc_id, roots=None: ccs / 'thing')
    (checkout / 'a.c').write_text('int a = 5;\n')
    started = node_check.dispatch(store.scoped('t'), 't', 'start', dict(node_id='integrate', checkout=str(checkout)))
    assert started['state'] == 'running'
    deadline = time.time() + 60
    while time.time() < deadline:
        status = node_check.dispatch(store.scoped('t'), 't', 'status', dict(node_id='integrate'))['outputs']['change']
        if status['latest'] and not status['running']:
            break
        time.sleep(0.2)
    latest = status['latest']
    assert latest and latest['passed'], (latest, list((store.home / 'node-checks').glob('*/worker.log')))
    assert latest['review']['reviewer'].startswith('cmd:') and 'factory-review-' in latest['review']['summary']


def test_codex_reviewer_runs_a_fresh_read_only_session(tmp_path, monkeypatch):
    fake = tmp_path / 'codex'
    fake.write_text('#!' + sys.executable + '\nimport json, sys\nargs = sys.argv[1:]\n'
                    'open(args[args.index("-o") + 1], "w").write(json.dumps(dict(verdict="pass", summary=" ".join(args), findings=[])))\n')
    fake.chmod(0o755)
    reply = node_check.CodexReviewer(model='small', codex=str(fake))('review this')
    args = parse_review(reply)['summary']
    assert all(flag in args for flag in ('exec --ephemeral', '-s read-only', '--output-schema', '-m small'))


def test_contract_pinned_verifier_inputs():
    entry = dict(name='q2_pack', kind='evidence', verifier='weights.build_x.verify_pack',
                 inputs={'target': 'q2_k', 'expect_bytes_range': [250, 320]})
    validate_spec({'outputs': [entry]})
    assert node_check.pin_inputs(entry, {'pack': 'p'}) == {'pack': 'p', 'target': 'q2_k', 'expect_bytes_range': [250, 320]}
    assert node_check.pin_inputs(entry, {'target': 'q2_k'})['target'] == 'q2_k'  # the same value is fine
    with pytest.raises(node_check.CheckError, match='pins verifier inputs expect_bytes_range, target'):
        node_check.pin_inputs(entry, {'target': 'nvfp4', 'expect_bytes_range': [0, 10 ** 15]})
    assert node_check.pin_inputs(dict(name='x', kind='diff', verifier='a.b.c'), None) is None
    for bad in ({'checkout': '/x'}, {}, 'q2_k'):
        with pytest.raises(ValueError, match='pinned inputs'):
            validate_spec({'outputs': [dict(entry, inputs=bad)]})
    with pytest.raises(ValueError, match='pinned inputs'):
        validate_spec({'outputs': [dict(name='d', kind='diff', review=True, inputs={'t': 1})]})


def test_reopen_needs_a_check_recorded_after_it(setup):
    from jiuwenswarm.factory.taskgraph import operator_patch
    store, ccs, checkout = setup
    (checkout / 'a.c').write_text('int a = 1; /* COMPILES */\n')
    passed = checks(store, ccs, Reviewer(PASS)).start('t', 'integrate', checkout=checkout, background=False)
    graph = done(store, [passed['obs_id']], 1)
    graph = operator_patch(store, 't', 'reopen', 'integrate', 'rerun after the driver fix')
    node = next(n for n in graph['nodes'] if n['node_id'] == 'integrate')
    assert node['state'] == 'proposed' and node['checks_after'] == f"t:plan:{graph['rev']}" and node['evidence_ids'] == []
    with pytest.raises(ValueError, match='needs a passing node check'):  # the pass before the reopen no longer counts
        done(store, [passed['obs_id']], graph['rev'])
    again = checks(store, ccs, Reviewer(PASS)).start('t', 'integrate', checkout=checkout, background=False)
    assert again['passed'] and again['obs_id'] != passed['obs_id']
    assert next(n for n in done(store, [again['obs_id']], graph['rev'])['nodes'] if n['node_id'] == 'integrate')['state'] == 'done'


# ---- advisory reviews: recorded and shown, the verifier and host checks decide ----------------------------
BLOCKER = dict(verdict='fail', summary='the gate is missing',
               findings=[dict(severity='blocker', file='a.c', line=1, problem='no off switch')])


class BrokenReviewer:
    identity = 'broken-reviewer'

    def __call__(self, prompt):
        raise RuntimeError('reviewer endpoint unreachable')


@pytest.fixture
def advisory(setup):
    store, ccs, checkout = setup
    plan_patch(store, 't', {'add': [
        dict(node_id='adv', kind='integrate', title='Integrate the thing (advisory review)',
             check=dict(verifier='test.build_thing.verify', stage='native CC execution', review='advisory')),
        dict(node_id='ev', kind='report', title='Report records',
             check={'outputs': [dict(name='records', kind='evidence', review='advisory')]})]}, 1, 1)
    return store, ccs, checkout


@pytest.mark.parametrize('reviewer,reason', [
    (Reviewer(BLOCKER), 'blocker'),
    (Reviewer('I think it is fine'), 'not JSON'),
    (BrokenReviewer(), 'could not run: RuntimeError'),
])
def test_an_advisory_review_is_recorded_but_does_not_decide(advisory, reviewer, reason):
    store, ccs, checkout = advisory
    (checkout / 'a.c').write_text('int a = 7;\n')
    result = checks(store, ccs, reviewer).start('t', 'adv', checkout=checkout, background=False)
    assert result['passed'] and result['verifier']['passed']
    review = result['review']
    assert review['advisory'] is True and not review['passed'] and reason in review['reason']
    assert result['reason'].startswith('passed; advisory review (does not decide)')
    if isinstance(reviewer, Reviewer) and isinstance(reviewer.reply, dict):
        assert review['findings'][0]['problem'] == 'no off switch' and review['verdict'] == 'fail'
    graph = plan_patch(store, 't', {'update': [dict(node_id='adv', state='done', evidence_ids=[result['obs_id']])]}, 2, 1)
    assert next(n for n in graph['nodes'] if n['node_id'] == 'adv')['state'] == 'done'


def test_an_advisory_review_runs_without_a_reviewer_and_the_verifier_still_decides(advisory, monkeypatch):
    store, ccs, checkout = advisory
    monkeypatch.setattr(node_check, 'default_reviewer', lambda: None)
    (checkout / 'a.c').write_text('int a = 8;\n')
    result = checks(store, ccs, None).start('t', 'adv', checkout=checkout, background=False)
    assert result['passed'] and result['review']['advisory'] and 'no reviewer is configured' in result['review']['reason']
    (checkout / 'a.c').write_text('int a = 9;\n')
    with pytest.raises(node_check.CheckError, match='No reviewer is configured'):  # a blocking review still needs one
        checks(store, ccs, None).start('t', 'integrate', checkout=checkout, background=False)
    (checkout / 'a.c').write_text('int a = 2; /* BAD */\n')
    failed = checks(store, ccs, Reviewer(PASS)).start('t', 'adv', checkout=checkout, background=False)
    assert not failed['passed'] and 'no_bad_marker' in failed['reason'] and failed['review'] is None


def test_an_advisory_review_of_evidence_and_the_status_shows_the_mode(advisory):
    store, ccs, checkout = advisory
    result = checks(store, ccs, Reviewer(BLOCKER)).start('t', 'ev', refs={'evidence_ids': ['t']}, background=False)
    assert result['passed'] and result['review']['advisory'] and result['review']['verdict'] == 'fail'
    status = checks(store, ccs, Reviewer(BLOCKER)).status('t', 'ev')
    assert status['outputs']['records']['review'] == 'advisory' and status['done_blocked_by'].startswith('output records: cite')
    missing = checks(store, ccs, Reviewer(PASS)).start('t', 'ev', refs={'evidence_ids': ['nothing-here']}, background=False)
    assert not missing['passed']  # the host check still decides


def test_advisory_spec_validation():
    validate_spec(dict(verifier='a.b.verify', review='advisory'))
    validate_spec({'outputs': [dict(name='r', kind='evidence', review='advisory')]})
    for bad in (dict(review='advisory'), dict(verifier='a.b.verify', review='maybe'),
                {'outputs': [dict(name='i', kind='image', review='advisory')]}):
        with pytest.raises(ValueError):
            validate_spec(bad)
