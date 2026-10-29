"""Preparation has no eligibility; literal predicates never release a capsule."""
import pytest
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.contracts import ResearchError


def test_plain_original_blob_is_product_material_but_corrupt_identity_still_rejects(tmp_path):
    store=SQLiteRunStore(tmp_path);ref=store.put_blob('Original user request λ'.encode())
    store.require_product_material([ref])
    store.require_product_material([store.put_blob(b'{"id":{},"sha256":[]}')])
    with pytest.raises(ResearchError):store.require_product_material([dict(ref,sha256='0'*64)])


@pytest.mark.asyncio
async def test_installed_calibration_checks_prepare_without_admission_or_model(tmp_path):
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.checks.calibration_runtime import prepare_calibration_checks
    from jiuwenswarm.research.library import LibraryService
    store=SQLiteRunStore(tmp_path);library=LibraryService(store);checks=CheckRegistry()
    assets=await prepare_calibration_checks(store,checks)
    assert len(assets)==11
    for stage,asset in assets.items():
        bundle=store.read_record(asset['bundle_ref'],contract_id='check-bundle')
        assert all(checks.contains(row['check_id']) for row in bundle['checks'])
        for row in bundle['checks']:assert store.read_blob(row['runner_ref'])
    assert library.entries()==[]
    assert not list(store.iter_records(kinds=('library-admission','activation-record','model-call','gate-decision')))


@pytest.mark.parametrize('fault',[None,'declaration','output','criterion'])
def test_literal_verifier_predicates_recompute_exact_refs_coverage_and_verdict(tmp_path,fault):
    from jiuwenswarm.research.checks.verifier import verifier_predicates
    from jiuwenswarm.research.gate import assemble_assessment
    store=SQLiteRunStore(tmp_path);declaration=store.put_blob(b'explicit unit declaration');output=store.put_blob(b'explicit unit output')
    review=store.put_blob(b'explicit unit review identity');criteria=[{'criterion_id':'shape','blocking':True}]
    assessment=store.put_record('verifier-assessment',assemble_assessment({'findings':[{'criterion_id':'shape','outcome':'PASS','reason':'Controlled predicate fixture'}],
        'uncertainties':[],'limitations':[],'required_correction':None},criteria,declaration,output,review))
    contract={'inputs':[{'name':'subject_declaration','artifact_refs':[declaration]},{'name':'subject_output','artifact_refs':[output]}]}
    if fault=='declaration':contract['inputs'][0]['artifact_refs']=[output]
    elif fault=='output':contract['inputs'][1]['artifact_refs']=[declaration]
    elif fault=='criterion':criteria=[{'criterion_id':'foreign','blocking':True}]
    predicates=verifier_predicates(store,contract,assessment,criteria,declaration,output)
    assert all(predicates.values()) is (fault is None)
    assert not list(store.iter_records(kinds=('library-admission','activation-record','model-call','gate-decision')))


def test_shipped_builder_field_contract_alias_uses_original_zip_projection(tmp_path):
    import io,json,zipfile
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research.calibration_authority import semantic_prompt
    from jiuwenswarm.research.gate import zip_projection
    store=SQLiteRunStore(tmp_path);asset=build_research_assets(store)['builder'];archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as output:
        for name,raw in [('requirements.txt',b''),('poc_patch.py',b'pass\n'),('run_benchmark.py',b'print("controlled alias")\n')]:output.writestr(name,raw)
    subject=store.put_blob(archive.getvalue());profile=store.read_record(asset['profile_ref'])
    case={'declaration_ref':asset['declaration_ref'],'subject_ref':subject,'output_port':'bundle'}
    text=semantic_prompt(store,case,profile)
    payload=json.loads(text.split('<subject_payload>\n')[1].split('\n</subject_payload>')[0])
    assert payload['subject_output']==zip_projection(archive.getvalue()).decode('utf-8')


def test_raw_report_field_alias_is_preserved_even_when_bytes_are_also_valid_json(tmp_path):
    from jiuwenswarm.research.runner import CapsuleRunner
    store=SQLiteRunStore(tmp_path);runner=object.__new__(CapsuleRunner);runner.store=store
    raw=b'{"markdown_is_also_json":true}';ref=store.put_blob(raw,media_type='text/markdown')
    assert runner._decode_outputs({'outputs':[{'name':'report','contract_id':'research-report:field-contract:1'}]},{'report':ref})=={'report':raw}
