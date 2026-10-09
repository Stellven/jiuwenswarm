"""Independent read-only R08 durable release, source attribution and export audit."""
from pathlib import Path, PurePosixPath
import hashlib, json, sqlite3, zipfile, traceback

HERE = Path(__file__).resolve().parent
BASE = HERE / 'live-R08-reference-resource'
READ = BASE / 'read-only-verification'
case = json.loads((BASE / 'frozen-case.json').read_text(encoding='utf-8'))
outcome = json.loads((READ / 'outcome.json').read_text(encoding='utf-8'))
status = json.loads((READ / 'status.json').read_text(encoding='utf-8'))
consumer = json.loads((READ / 'consumer-result.json').read_text(encoding='utf-8'))
report = {'verification': 'V06 independent affected reference_document release/export boundary',
          'command': '.venv-intent/Scripts/python.exe docs/code/Missions/M0/M0-001/evidence/v06-r08-export-check.py',
          'candidate': outcome['candidate'], 'run_id': outcome['run_id'], 'working_directory': str(Path.cwd()),
          'expected': 'Four actual roles and three committed gates; exact Brief2 consumer/receipt/output; every named hash/reference resolves; original resource bytes/license/qualified source/disclosed constraint spans preserved',
          'dependency_mode': 'Original actual terminal SQLite opened read-only; fresh authenticated NoDispatch captured ZIP/consumer; no model invocation or replay',
          'limitations': ['One affected-role positive sample, no reliability threshold.', 'Browser/container prerequisites remain blocked.', 'Original evidence helper KeyError retained as CHECK_SCRIPT_FAILED despite product completed; later authenticated reads and this independent audit resolve verification only.']}
try:
    run = outcome['run_id']
    database = BASE / 'state/runs.sqlite3'
    connection = sqlite3.connect('file:' + database.as_posix() + '?mode=ro', uri=True)
    rows = connection.execute('SELECT scope,subject,gate_ref,record_ref FROM acceptance WHERE run_id=?', (run,)).fetchall()
    connection.close()
    released = {scope: {'subject': json.loads(subject), 'gate': json.loads(gate), 'receipt': json.loads(receipt)} for scope, subject, gate, receipt in rows}
    assert set(released) == {'intention', 'requirements', 'node'}
    assert status['status'] == 'completed' and status['stage'] == 'released'
    assert case['documents'] == [] and len(case['resources']) == 1 and case['resources'][0]['role'] == 'reference_document'
    with zipfile.ZipFile(READ / 'evidence.zip') as archive:
        manifest = json.loads(archive.read('manifest.json'))
        entries = manifest['files']
        index = {item['artifact_ref']['id']: item for item in entries}
        assert len(index) == len(entries)
        for item in entries:
            path, ref = item['path'], item['artifact_ref']
            parts = PurePosixPath(path)
            assert not parts.is_absolute() and '..' not in parts.parts and path == ref['id']
            assert hashlib.sha256(archive.read(path)).hexdigest() == ref['sha256'], path
        assert set(archive.namelist()) == {item['path'] for item in entries} | {'manifest.json'}
        resolved = set()
        def walk(value):
            if isinstance(value, dict):
                pin = None
                if isinstance(value.get('id'), str) and isinstance(value.get('sha256'), str):
                    pin = value['id'], value['sha256']
                elif isinstance(value.get('ref'), str) and isinstance(value.get('sha256'), str):
                    pin = value['ref'], value['sha256']
                if pin:
                    assert pin[0] in index and index[pin[0]]['artifact_ref']['sha256'] == pin[1], pin
                    resolved.add(pin)
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(manifest)
        for item in entries:
            if item['media_type'].startswith('application/json') and not item['path'].endswith('.schema.json'):
                walk(json.loads(archive.read(item['path'])))
        def read(ref): return json.loads(archive.read(ref['id'] if isinstance(ref, dict) else ref))
        node = released['node']
        receipt, gate, brief = read(node['receipt']), read(node['gate']), read(node['subject'])
        assert consumer['node_acceptance_ref'] == node['receipt']
        assert consumer['output_refs'] == receipt['output_refs'] == gate['accepted_refs'] == [node['subject']]
        assert consumer['research_brief'] == brief and brief['schema_version'] == '2.0.0'
        assert node['subject'] == released['requirements']['subject'] and gate['action'] == 'advance'
        inner = [read(released[scope]['gate']) for scope in ('intention', 'requirements')]
        assert all(item['action'] == 'advance' for item in inner)
        assert gate['invocation_refs'] == inner[0]['invocation_refs'] + inner[1]['invocation_refs']
        assert gate['assessment_ref'] == inner[1]['assessment_ref']
        observations = [read(item['path']) for item in entries if item['path'].endswith('_Invocation_Observation.json')]
        assert len(observations) == 4 and sum(item['model_calls'] for item in observations) == 4
        assert {item['subnode_id'] for item in observations} == {'intention', 'intention.verifier', 'requirements', 'requirements.verifier'}
        assert consumer['ext']['m0.intent']['invalid_for_product'] is False
        assert consumer['ext']['m0.intent']['profile_id'] == 'compiler-only'
        disclosed = read('intention_Disclosed_Input.json')
        intake = disclosed['intake']
        source_ref = intake['source_refs'][0]
        text = disclosed['sources'][source_ref['id']]['text']
        assert text == case['source_text']
        resource_bindings = disclosed['resource_bindings']
        assert resource_bindings[0]['role'] == 'reference_document'
        resource = read(resource_bindings[0]['resource_ref'])
        assert resource['kind'] == 'reference_document' and resource['license'] == case['resources'][0]['license']
        raw = archive.read(resource['files'][0]['artifact_ref']['id'])
        assert raw == (BASE / 'visible-input/reference-only.md').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == case['source_bytes_sha256']
        intent = read('Intent_IR.json')
        for term in case['expected_material_constraints']:
            matches = [item for item in intent['constraints'] if term in item['text'].lower()]
            assert matches, term
            assert any(any(span['source_ref'] == source_ref and 0 <= span['start'] < span['end'] <= len(text) and term in text[span['start']:span['end']].lower() for span in item['source_spans']) for item in matches), term
            assert any(term in item['text'].lower() and item['origin'] != 'system_default' for item in brief['constraints']), term
        with zipfile.ZipFile(BASE / 'evidence.zip') as original_archive:
            assert original_archive.namelist() == archive.namelist()
            assert all(original_archive.read(name) == archive.read(name) for name in archive.namelist())
        assert (BASE / 'consumer-result.json').read_bytes() == (READ / 'consumer-result.json').read_bytes()
        original = json.loads((BASE / 'outcome.json').read_text(encoding='utf-8'))
        assert original['result'] == 'FAIL' and original['actual'] == 'completed' and original['reason'] == "KeyError: 'invalid_for_product'"
        assert hashlib.sha256((BASE / 'outcome.json').read_bytes()).hexdigest() == outcome['original_outcome_sha256']
        report.update(result='PASS', named_exact_hash_files=len(entries), resolved_unique_refs=len(resolved), durable_scopes=sorted(released),
                      dispatch_roles=[item['subnode_id'] for item in observations], exact_durable_consumer_release=True,
                      exact_original_source_and_license=True, source_disclosure_and_attributed_spans=True, preserved_material_brief_constraints=True,
                      original_helper_failure_preserved=True, fresh_export_member_bytes_identical=True, brief_ref=node['subject'], node_receipt_ref=node['receipt'])
except Exception as error:
    report.update(result='FAIL', reason=type(error).__name__ + ': ' + str(error), diagnostic=traceback.format_exc())
(HERE / 'v06-r08-export-independent.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['result'] == 'PASS' else 1)
