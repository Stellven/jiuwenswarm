"""Frozen eligibility custody and binding projection, using controlled E3 work.

These exercise the real export/reader; controlled model replies are unit data.
"""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest

from benchmarks.harbor_suite.evidence import project_evaluation
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.evaluation_history import EvaluationReader
from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords
from jiuwenswarm.research_sidecar.evidence import canonical
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime


def without_kinds(raw, removed):
    """Recreate an older export with neither optional eligibility source kind."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members={name:archive.read(name) for name in archive.namelist()}
    manifest=json.loads(members['evaluation_export.json'])
    discarded={row['path'] for row in manifest['files'] if row['kind'] in removed}
    manifest['files']=[row for row in manifest['files'] if row['path'] not in discarded]
    manifest['required_evidence']=[row for row in manifest['required_evidence'] if row['path'] not in discarded]
    unsigned={key:value for key,value in manifest.items() if key!='id'}
    manifest['id']='evaluation-export:'+hashlib.sha256(canonical(unsigned)).hexdigest()
    members['evaluation_export.json']=canonical(manifest)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        for name,payload in members.items():
            if name not in discarded:archive.writestr(name,payload)
    return output.getvalue()


@pytest.mark.asyncio
async def test_original_snapshot_profile_closure_projects_positive_binding_and_preserves_legacy(tmp_path, benchmark_case_assets):
    store,provider,actor,request,prompts=await source_fixture(tmp_path)
    try:
        runtime_ref=capture_runtime(store,provider,[request])
        provider.resources.bind_runtime(runtime_ref)
        assert (await provider.single_cc(actor,request))['status']=='completed'
        audience=Principal(actor.account_id,actor.workspace_ids,actor.operations,frozenset({'reviewer'}))
        raw=EvaluationReader(store,runtime_ref=runtime_ref).export_bytes(audience,request['request_id'],audience='reviewer')
        def read(payload):
            return EvaluationRecords.from_archive(payload,request_id=request['request_id'],
                campaign_id=request['campaign_id'],audience='reviewer',expected_request=request).require_complete()
        records=read(raw)
        for kind,field in [('evaluation-profile','profile_ref'),('library-snapshot','library_snapshot_ref')]:
            assert [row['artifact_ref'] for row in records.rows(kind)]==[records.runtime[field]]
            assert records.bytes_ref(records.runtime[field])==store.read_blob(records.runtime[field])
        task={'case_id':'cc02-binding','variant_id':'valid-pinned','entrypoint':'single_cc'}
        normalized=project_evaluation(records,task)
        join=normalized['module_observations']['cc02_binding']
        assert join['snapshot_ref']==records.runtime['library_snapshot_ref']
        root=benchmark_case_assets/'cc02-binding'
        spec=importlib.util.spec_from_file_location('cc02_snapshot_unit_oracle',root/'oracle.py')
        oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
        result=oracle.evaluate(normalized,json.loads((root/'referee/criteria.json').read_bytes()))
        assert result['metrics']['binding_conformance']==1,result
        assert result['metrics']['assignment_execution_success'] is True
        for fault in ('foreign_subject','contradictory_subject','wrong_schema'):
            changed=copy.deepcopy(normalized)
            observed=next(row['record'] for row in changed['records'] if row['kind']=='observation')
            actual=next(row['record'] for row in changed['records'] if row['ref']==observed['contract_ref'])
            assert actual['schema']=='ai4r-evaluation-subnode-context:1'
            if fault=='foreign_subject':actual['source_subject_ref']=join['request_ref']
            elif fault=='contradictory_subject':actual['source_contract_ref']=join['request_ref']
            else:actual['schema']='unknown-private-context:1'
            assert oracle.evaluate(changed,json.loads((root/'referee/criteria.json').read_bytes()))['metrics']['binding_conformance']==0
        # Old authentic source closure remains readable, without acquiring a
        # snapshot join or claiming CC02 coverage it cannot independently show.
        legacy=read(without_kinds(raw,{'evaluation-profile','library-snapshot'}))
        assert not project_evaluation(legacy,task)['module_observations']
        for removed in ({'library-snapshot'},{'evaluation-profile'}):
            with pytest.raises(ValueError,match='partial original frozen eligibility closure'):
                read(without_kinds(raw,removed))
        # A valid source object cannot silently point at another frozen Ref.
        records.runtime['library_snapshot_ref']=records.runtime['profile_ref']
        with pytest.raises(ValueError,match='typed Ref mismatch'):
            records._source_closure()
    finally:
        store.close()
