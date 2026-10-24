"""Policy tests for the filesystem-free protected Builder host boundary."""
import hashlib
import io
import json
import zipfile

import pytest

from jiuwenswarm.research.builder_agent_service import BuilderAgentService


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _files():
    return {"requirements.txt": "# stdlib\n", "poc_patch.py": "def predict(train, test):\n    return []\n",
            "run_benchmark.py": "import json\npredictions = []\nprint(json.dumps({'predictions': predictions}))\n"}


@pytest.mark.asyncio
async def test_compile_rejects_parseable_but_noncompilable_module():
    async def no_execution(*args):raise AssertionError('compilation must not execute code')
    files=_files()
    files['poc_patch.py']='return 1\n'
    session=BuilderAgentService(initial_files=files,execute_check=no_execution)
    await session.dispatch('write_file',{'path':'tests.py','content':'import unittest\n',
        'expected_sha256':_hash('')},1)
    result=await session.dispatch('run_checks',{'check':'compile'},2)
    assert result['ok'] is False and session.inspect()['jobs']==0


@pytest.mark.asyncio
async def test_later_failed_check_revokes_a_previously_passing_snapshot():
    passing=True
    async def check(*args):return {'passed':passing}
    session=BuilderAgentService(initial_files=_files(),execute_check=check)
    await session.dispatch('write_file',{'path':'tests.py','content':'import unittest\n',
        'expected_sha256':_hash('')},1)
    for ordinal,phase in enumerate(('compile','unit','smoke'),2):
        assert (await session.dispatch('run_checks',{'check':phase},ordinal))['ok'] is True
    assert session.inspect()['passing_snapshot']==session.snapshot_sha256
    passing=False
    assert (await session.dispatch('run_checks',{'check':'unit'},5))['ok'] is False
    result=await session.dispatch('submit_candidate',{},6)
    assert result.get('submitted') is not True


@pytest.fixture
def service_factory():
    calls = []

    async def execute_check(check, files, test_name):
        calls.append((check, files, test_name))
        return {"passed": True, "evidence_ref": {"id": "host-proof", "check": check}}

    def make(**kwargs):
        return BuilderAgentService(initial_files=_files(), execute_check=execute_check, **kwargs)
    return make, calls


@pytest.mark.asyncio
async def test_workspace_is_allowlisted_and_rejects_path_escape_and_refs(service_factory):
    make, _ = service_factory
    service = make()
    assert (await service.dispatch("list_files", {}, 1))["files"] == ["poc_patch.py", "requirements.txt", "run_benchmark.py", "tests.py"]
    assert (await service.dispatch("read_file", {"path": "../outside"}, 2))["ok"] is False
    assert (await service.dispatch("read_file", {"path": "/etc/passwd"}, 3))["ok"] is False
    assert (await service.dispatch("read_log", {"ref": {"id": "external"}}, 4))["ok"] is False
    assert not service.inspect()["files"].get("/etc/passwd")


@pytest.mark.asyncio
async def test_write_requires_current_hash_and_edit_invalidates_all_passes(service_factory):
    make, _ = service_factory
    service = make()
    assert (await service.dispatch("write_file", {"path": "tests.py", "content": "assert 1\n", "expected_sha256": "0" * 64}, 1))["error"] == "stale_file_hash"
    before = service.snapshot_sha256
    updated = await service.dispatch("write_file", {"path": "tests.py", "content": "assert 1\n", "expected_sha256": _hash("")}, 2)
    assert updated["ok"] and updated["snapshot_sha256"] != before
    assert service.inspect()["passing_snapshot"] is None


@pytest.mark.asyncio
async def test_patch_is_exactly_once_and_hash_guarded(service_factory):
    make, _ = service_factory
    service = make()
    current = _files()["poc_patch.py"]
    bad = await service.dispatch("apply_patch", {"path": "poc_patch.py", "old": "return ['missing']", "new": "return ['x']", "expected_sha256": _hash(current)}, 1)
    assert bad["ok"] is False
    good = await service.dispatch("apply_patch", {"path": "poc_patch.py", "old": "return []", "new": "return [row['label'] for row in train[:len(test)]]", "expected_sha256": _hash(current)}, 2)
    assert good["ok"] is True


@pytest.mark.asyncio
async def test_compile_unit_smoke_evidence_binds_exact_snapshot_and_packages_three_files(service_factory):
    make, calls = service_factory
    service = make()
    tests = "import unittest\nclass T(unittest.TestCase):\n def test_true(self): self.assertTrue(True)\n"
    assert (await service.dispatch("write_file", {"path": "tests.py", "content": tests, "expected_sha256": _hash("")}, 1))["ok"]
    compile_result = await service.dispatch("run_checks", {"check": "compile"}, 2)
    unit = await service.dispatch("run_checks", {"check": "unit", "test_name": "T"}, 3)
    smoke = await service.dispatch("run_checks", {"check": "smoke"}, 4)
    assert compile_result["ok"] and unit["ok"] and smoke["ok"]
    assert [row[0] for row in calls] == ["unit", "smoke"]
    result = await service.dispatch("submit_candidate", {}, 5)
    assert result["submitted"]
    assert result["snapshot_sha256"] == service.snapshot_sha256
    with zipfile.ZipFile(io.BytesIO(result["bundle_bytes"])) as archive:
        assert archive.namelist() == ["poc_patch.py", "requirements.txt", "run_benchmark.py"]
        assert "tests.py" not in archive.namelist()
    assert result["journal"][-1]["action"] == "submit_candidate"


@pytest.mark.asyncio
async def test_compile_failure_empty_tests_and_edit_after_pass_block_submission(service_factory):
    make, _ = service_factory
    service = make()
    assert not (await service.dispatch("run_checks", {"check": "compile"}, 1))["ok"]
    broken = "def test(:\n"
    await service.dispatch("write_file", {"path": "tests.py", "content": broken, "expected_sha256": _hash("")}, 2)
    assert not (await service.dispatch("run_checks", {"check": "compile"}, 3))["ok"]
    valid = "assert True\n"
    await service.dispatch("write_file", {"path": "tests.py", "content": valid, "expected_sha256": _hash(broken)}, 4)
    for ordinal, check in enumerate(("compile", "unit", "smoke"), 5):
        assert (await service.dispatch("run_checks", {"check": check}, ordinal))["ok"]
    await service.dispatch("write_file", {"path": "poc_patch.py", "content": "changed\n", "expected_sha256": _hash(_files()["poc_patch.py"])}, 8)
    submit = await service.dispatch("submit_candidate", {}, 9)
    assert submit["ok"] is False and "lacks" in submit["error"]


@pytest.mark.asyncio
async def test_auth_ordinal_unknown_action_and_job_limits_fail_closed(service_factory):
    make, calls = service_factory
    async def deny(action, args, ordinal):
        return False
    service = make(action_authorizer=deny, max_jobs=1, max_tool_calls=6)
    assert (await service.dispatch("list_files", {}, 1))["error"] == "action_not_authorized"
    assert (await service.dispatch("nuke", {}, 2))["error"] == "unknown_action"
    assert (await service.dispatch("list_files", {}, 2))["error"] == "invalid_model_ordinal"
    assert (await service.dispatch("list_files", {}, 3))["error"] == "action_not_authorized"
    assert not calls

    service2 = make(max_jobs=1)
    await service2.dispatch("write_file", {"path": "tests.py", "content": "assert True\n", "expected_sha256": _hash("")}, 1)
    assert (await service2.dispatch("run_checks", {"check": "compile"}, 2))["ok"]
    assert (await service2.dispatch("run_checks", {"check": "unit"}, 3))["ok"]
    assert (await service2.dispatch("run_checks", {"check": "smoke"}, 4))["error"] == "job_limit"


@pytest.mark.asyncio
async def test_journal_binds_arguments_fingerprints_results_and_bounded_output(service_factory):
    make, _ = service_factory
    service = make()
    result = await service.dispatch("read_file", {"path": "requirements.txt"}, 1)
    row = service.inspect()["journal"][0]
    assert row["arguments_sha256"] == hashlib.sha256(b'{"path":"requirements.txt"}').hexdigest()
    assert row["before_snapshot_sha256"] == row["after_snapshot_sha256"]
    assert row["result_sha256"] == hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.asyncio
async def test_tool_call_ceiling_and_strict_argument_keys_are_journaled(service_factory):
    make, _ = service_factory
    service = make(max_tool_calls=2)
    extra = await service.dispatch("list_files", {"extra": True}, 1)
    assert extra["ok"] is False
    assert "schema" in extra["error"]
    assert (await service.dispatch("list_files", {}, 2))["ok"] is True
    limited = await service.dispatch("list_files", {}, 3)
    assert limited["error"] == "tool_call_limit"
    journal = service.inspect()["journal"]
    assert [row["sequence"] for row in journal] == [1, 2, 3]


@pytest.mark.asyncio
async def test_blocked_action_is_terminal_host_owned_diagnostic(service_factory):
    make, _ = service_factory
    service = make()
    result = await service.dispatch("report_blocked", {"reason": "missing approved dependency"}, 1)
    assert result["blocked"] is True
    assert result["reason"] == "missing approved dependency"


@pytest.mark.asyncio
async def test_read_log_accepts_only_a_reported_reference(service_factory):
    make, _ = service_factory
    ref = {"id": "unit-log", "sha256": "a" * 64}
    async def read_log(issued):
        assert issued == ref
        return {"content": "check output"}
    service = BuilderAgentService(initial_files=_files(), execute_check=make()._execute_check,
                                  read_log=read_log)
    await service.dispatch("write_file", {"path": "tests.py", "content": "assert True\n", "expected_sha256": _hash("")}, 1)
    await service.dispatch("run_checks", {"check": "unit"}, 2)
    # The standard fixture did not issue this ref, so it remains inaccessible.
    assert not (await service.dispatch("read_log", {"ref": ref}, 3))["ok"]

    async def issue_ref(check, files, test_name):
        return {"passed": True, "log_refs": [ref]}
    service2 = BuilderAgentService(initial_files=_files(), execute_check=issue_ref, read_log=read_log)
    await service2.dispatch("write_file", {"path": "tests.py", "content": "assert True\n", "expected_sha256": _hash("")}, 1)
    await service2.dispatch("run_checks", {"check": "unit"}, 2)
    observed = await service2.dispatch("read_log", {"ref": ref}, 3)
    assert observed["ok"] and observed["log"]["content"] == "check output"


@pytest.mark.asyncio
async def test_protected_executor_failure_propagates(service_factory):
    make, _ = service_factory
    async def failed(*args):
        raise RuntimeError("executor unavailable")
    service = BuilderAgentService(initial_files=_files(), execute_check=failed)
    await service.dispatch("write_file", {"path": "tests.py", "content": "assert True\n", "expected_sha256": _hash("")}, 1)
    with pytest.raises(RuntimeError, match="protected check runner failed"):
        await service.dispatch("run_checks", {"check": "unit"}, 2)
