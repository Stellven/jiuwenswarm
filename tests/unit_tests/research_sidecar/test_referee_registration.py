"""Source-derived referee controls; constructed labels are unit fixtures only.

No model, operational profile, protected campaign label or product acceptance is
created here. Source: benchmark-runner.md Referee part; QA requirements 2.1/B05.
"""
import copy
import hashlib
import json

import pytest

from jiuwenswarm.research_sidecar import campaign, cli, referee
from jiuwenswarm.research_sidecar.evidence import canonical
from jiuwenswarm.research_sidecar.oracles import score_checks
from .test_campaign_loader import definitions, freeze, pin_cases, bind_visible


def label(case_id="loader_capsule", version=1):
    return dict(
        label_id="referee_" + case_id, case_id=case_id, case_version=version,
        expected_outcome=dict(population="isolated_module", expected_terminal="complete", expected_halt_decision=None),
        expected_tier_verdicts=None, prd_case_number=None, valid_capsule_choices=[],
        dependency_obligations=["independent exact output"],
        mandatory_checks=[dict(check_id="mechanics", kind="deterministic", check_family="schema",
                               weight=1, description="Independent exact output and provenance check.")],
        rubric=None, primary_metric="success", secondary_metrics=[], failure_conditions=["wrong exact output"],
        reference_reasons=["Exact original output matches the independently frozen fixture."],
        labels={"mechanics": dict(oracle="exact_output", parameters=dict(artifact_id="result", expected={"value": 1}))},
        judge_audit_ref=None,
    )


def run(case_id="loader_capsule", version=1):
    return dict(run_id="controlled_run", campaign_id="controlled_campaign", case_id=case_id,
                case_version=version, population="isolated_module", launched=True, outcome="completed",
                outcome_detail={"product_decision": None})


def scored(value, observations=None, **kwargs):
    return referee.score_run(run(value["case_id"], value["case_version"]), value,
        observations if observations is not None else {"mechanics": {"passed": True, "evidence": ["exact-output"]}},
        oracle_version="oracle:1", scored_at="2026-10-19T16:00:00Z", **kwargs)


def bind(case, value):
    case["referee_ref"] = dict(label_id=value["label_id"], referee_sha256=hashlib.sha256(canonical(value)).hexdigest(),
                              visible_sha256="0" * 64)
    bind_visible(case)


def test_empty_mandatory_checks_cannot_create_vacuous_success():
    value = label()
    value["mandatory_checks"] = []
    # Reproduce the old CLI call shape, which injected runtime oracle_version
    # into the object. This is a regression input, not a source-valid label.
    value["oracle_version"] = "oracle:1"
    with pytest.raises(ValueError, match="mandatory"):
        referee.score_run(run(), value, {}, scored_at="2026-10-19T16:00:00Z")


@pytest.mark.parametrize("checks", [
    [],
    [dict(check_id="same", kind="deterministic", check_family="f", weight=1),
     dict(check_id="same", kind="deterministic", check_family="f", weight=1)],
    [dict(check_id="bad", kind="deterministic", check_family="f", weight=float("nan"))],
    [dict(check_id="bad", kind="deterministic", check_family="f", weight=True)],
])
def test_direct_check_scoring_refuses_empty_duplicate_and_nonfinite_authority(checks):
    with pytest.raises(ValueError):
        score_checks(checks, {"same": {"passed": True}, "bad": {"passed": True}})


def test_known_good_bad_and_unavailable_are_distinct_and_no_self_score():
    value = label()
    good = scored(value)
    bad = scored(value, {"mechanics": {"passed": False, "reason": "Planted exact-output defect"}})
    absent = scored(value, {})
    assert good["result"] == "success" and good["checks"][0]["status"] == "pass"
    assert bad["result"] == "fail" and bad["checks"][0]["status"] == "fail"
    assert absent["result"] == "fail" and absent["checks"][0]["status"] == "unavailable"


@pytest.mark.parametrize("mutation", [
    lambda v: v.pop("failure_conditions"),
    lambda v: v.update(private_key="forbidden-extra-field"),
    lambda v: v.update(case_version=True),
    lambda v: v["expected_outcome"].update(expected_terminal="pass"),
    lambda v: v["mandatory_checks"].append(copy.deepcopy(v["mandatory_checks"][0])),
    lambda v: v["mandatory_checks"][0].update(weight=float("inf")),
    lambda v: v["mandatory_checks"][0].update(weight=True),
    lambda v: v["mandatory_checks"][0].update(kind="product_self_report"),
    lambda v: v["mandatory_checks"][0].pop("description"),
    lambda v: v.update(prd_case_number=11),
    lambda v: v.update(rubric={"rubric_id": "quality", "criteria": [{"criterion_id": "x", "weight": .9}]}),
])
def test_source_referee_contract_rejects_missing_unknown_and_invalid_authority(mutation):
    value = label()
    mutation(value)
    with pytest.raises(ValueError):
        referee.validate_referee(value)


def test_source_weight_boundaries_and_rubric_exact_sum():
    value = label()
    value["mandatory_checks"][0]["weight"] = 0
    value["rubric"] = {"rubric_id": "quality", "criteria": [
        {"criterion_id": "a", "weight": .1}, {"criterion_id": "b", "weight": .2},
        {"criterion_id": "c", "weight": .7}]}
    assert referee.validate_referee(value) == value


def test_runtime_oracle_version_is_not_injected_into_source_label():
    value = label()
    before = canonical(value)
    assert scored(value)["oracle_version"] == "oracle:1"
    assert canonical(value) == before and "oracle_version" not in value


def test_exact_raw_registration_and_case_join(definitions):
    _, _, _, cases, _ = definitions
    case = cases[0]
    value = label(case["case_id"])
    raw = json.dumps(value, indent=3).encode() + b"\n"
    bind(case, value)
    case["referee_ref"]["referee_sha256"] = hashlib.sha256(raw).hexdigest()
    original = copy.deepcopy(case)
    assert campaign.load_referee(case, raw) == value
    assert case == original


@pytest.mark.parametrize("part", ["raw", "case_id", "case_version", "label_id", "visible", "terminal", "missing_tiers"])
def test_registration_rejects_hash_case_version_and_visible_scope_drift(definitions, part):
    _, _, _, cases, _ = definitions
    case = cases[0]
    value = label(case["case_id"])
    if part == "case_id": value["case_id"] = "unrelated_case"
    elif part == "case_version": value["case_version"] = 2
    elif part == "label_id": value["label_id"] = "foreign_label"
    elif part == "terminal": value["expected_outcome"].update(expected_terminal="halt", expected_halt_decision="FAIL")
    elif part == "missing_tiers":
        case["entry_mode"] = "node_replay"
        case["node_bundle_ref"] = {"path": "replay.json", "sha256": "a" * 64}
    bind(case, value)
    raw = canonical(value)
    if part == "raw": raw += b" "
    elif part == "visible": case["task_prompt"] += " changed after freeze"
    if part == "label_id": case["referee_ref"]["label_id"] = "original_label"
    with pytest.raises(ValueError):
        campaign.load_referee(case, raw)


def test_duplicate_raw_json_fields_are_not_reinterpreted_as_labels(definitions):
    _, _, _, cases, _ = definitions
    case = cases[0]
    value = label(case["case_id"])
    raw = canonical(value)
    raw = b'{"case_id":"foreign",' + raw[1:]
    bind(case, value)
    case["referee_ref"]["referee_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        campaign.load_referee(case, raw)


def _cli_fixture(definitions, monkeypatch, label_value):
    bench, folder, spec, cases, _ = definitions
    for case in cases:
        value = label(case["case_id"])
        if case is cases[0]: value = label_value
        bind(case, value)
        target = bench / "protected-labels" / value["label_id"] / "referee.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(canonical(value))
    pin_cases(spec, cases)
    _, _, rows = freeze(definitions)
    row = next(r for r in rows if r['case_id'] == cases[0]['case_id'])
    records = bench / "results" / spec["campaign_id"] / "runs" / row['run_id']
    records.mkdir(parents=True)
    record = {**run(cases[0]["case_id"]), **{k:row[k] for k in ('run_id','campaign_id','case_id','case_version','config_id','repeat_index')}}
    (records / "run_record.json").write_bytes(canonical(record))
    monkeypatch.setenv("AI4R_QA_ROOT", str(bench))
    monkeypatch.setenv("AI4R_QA_LABELS", str(bench / "protected-labels"))
    for key in list(__import__("os").environ):
        if key in {"AI4R_QA_JOB", "AI4R_APP_TOKEN", "AI4R_RSI_JOB_SOCKET", "AI4R_RSI_CUSTODIAN_SOCKET"} or key.endswith("_API_KEY"):
            monkeypatch.delenv(key)
    return bench, spec


def test_real_referee_cli_rejects_empty_checks_before_score_publication(definitions, monkeypatch):
    value = label()
    value["mandatory_checks"] = []
    bench, spec = _cli_fixture(definitions, monkeypatch, value)
    # This reaches the real loader/CLI and used to publish success with no oracle.
    assert cli.referee_main(["score", "--campaign", spec["campaign_id"], "--oracle-version", "oracle:1",
                             "--case", "capsule"]) == 2
    assert not (bench / "scores").exists()


def test_real_referee_cli_rejects_mismatched_raw_label_before_score_publication(definitions, monkeypatch):
    value = label()
    bench, spec = _cli_fixture(definitions, monkeypatch, value)
    target = bench / "protected-labels" / value["label_id"] / "referee.json"
    target.write_bytes(target.read_bytes() + b" ")
    assert cli.referee_main(["score", "--campaign", spec["campaign_id"], "--oracle-version", "oracle:1",
                             "--case", "capsule"]) == 2
    assert not (bench / "scores").exists()


def test_raw_hash_is_checked_before_private_json_parse(definitions, monkeypatch):
    _, _, _, cases, _ = definitions
    case = cases[0]; value = label(case['case_id']); bind(case, value)
    def forbidden_parse(_):
        pytest.fail('Unverified label bytes reached the private JSON parser')
    monkeypatch.setattr(campaign, 'strict_json', forbidden_parse)
    with pytest.raises(ValueError, match='raw referee'):
        campaign.load_referee(case, b'not the frozen body')


@pytest.mark.parametrize('mutation', [
    lambda v:v['mandatory_checks'].append(copy.deepcopy(v['mandatory_checks'][0])),
    lambda v:v.update(unknown_authority=True),
    lambda v:v.update(case_version=2),
    lambda v:v.update(case_id='foreign_case'),
])
def test_real_cli_rejects_invalid_registered_authority_before_any_oracle(definitions, monkeypatch, mutation):
    value=label(); mutation(value)
    bench,spec=_cli_fixture(definitions,monkeypatch,value)
    from jiuwenswarm.research_sidecar import independent_oracles
    monkeypatch.setattr(independent_oracles,'evaluate_checks',lambda *args:pytest.fail('Invalid label reached oracle execution'))
    assert cli.referee_main(['score','--campaign',spec['campaign_id'],'--oracle-version','oracle:1','--case','capsule'])==2
    assert not (bench/'scores').exists()


@pytest.mark.parametrize('field,value', [('campaign_id','foreign_campaign'),('run_id','foreign_run'),
    ('case_version',True),('config_id','foreign_config'),('repeat_index',True)])
def test_real_cli_rejects_foreign_or_ambiguous_scheduled_result(definitions,monkeypatch,field,value):
    bench,spec=_cli_fixture(definitions,monkeypatch,label())
    path=next((bench/'results'/spec['campaign_id']/'runs').glob('*/run_record.json'))
    record=json.loads(path.read_bytes());record[field]=value;path.write_bytes(canonical(record))
    from jiuwenswarm.research_sidecar import independent_oracles
    monkeypatch.setattr(independent_oracles,'evaluate_checks',lambda *args:pytest.fail('Foreign scheduled row reached the independent oracle'))
    assert cli.referee_main(['score','--campaign',spec['campaign_id'],'--oracle-version','oracle:1','--case','capsule'])==2
    assert not (bench/'scores').exists()


def test_real_cli_valid_registration_executes_independent_oracle_without_mutating_label(definitions,monkeypatch):
    bench,spec=_cli_fixture(definitions,monkeypatch,label())
    original=(bench/'protected-labels'/label()['label_id']/'referee.json').read_bytes()
    from jiuwenswarm.research_sidecar import independent_oracles
    called=[]
    def observe(value,*args):
        called.append(copy.deepcopy(value))
        assert value==label() and 'oracle_version' not in value
        return {'mechanics':{'passed':True,'reason':'Controlled independent oracle result','evidence':['exact-output']}}
    monkeypatch.setattr(independent_oracles,'evaluate_checks',observe)
    assert cli.referee_main(['score','--campaign',spec['campaign_id'],'--oracle-version','oracle:1','--case','capsule'])==0
    scores=list((bench/'scores').glob('*/*/*/score_record.json'))
    assert len(called)==len(scores)==1
    assert json.loads(scores[0].read_bytes())['result']=='success'
    assert (bench/'protected-labels'/label()['label_id']/'referee.json').read_bytes()==original


@pytest.mark.parametrize('mutation', [
    lambda output:output['scores'][0].update(total=9),
    lambda output:output.update(selected_idea_id='gpu_only'),
    lambda output:output['ranking'].reverse(),
    lambda output:output['scores'][0].update(novelty=True),
    lambda output:output['scores'][0].update(novelty=6),
])
def test_independent_screening_oracle_known_good_planted_bad_and_scale_boundaries(mutation):
    from jiuwenswarm.research_sidecar.independent_oracles import screening_mechanics
    rows=[dict(idea_id='alpha',novelty=1,feasibility=5,compute_alignment=5,total=11,eligible=True),
          dict(idea_id='beta',novelty=5,feasibility=1,compute_alignment=5,total=11,eligible=True),
          dict(idea_id='gpu_only',novelty=5,feasibility=5,compute_alignment=5,total=15,eligible=False)]
    output=dict(scores=rows,ranking=[dict(idea_id='alpha',total=11,rank=1),dict(idea_id='beta',total=11,rank=2)],selected_idea_id='alpha')
    expected_ids=['alpha','beta','gpu_only'];eligibility={'alpha':True,'beta':True,'gpu_only':False}
    assert screening_mechanics(output,expected_ids=expected_ids,eligibility=eligibility)
    good=scored(label(),{'mechanics':{'passed':True,'evidence':['independent-recomputation']}})
    mutation(output)
    with pytest.raises(ValueError):screening_mechanics(output,expected_ids=expected_ids,eligibility=eligibility)
    bad=scored(label(),{'mechanics':{'passed':False,'evidence':['planted-mechanical-defect']}})
    assert good['result']=='success' and bad['result']=='fail'

