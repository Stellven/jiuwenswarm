"""Finite, historical public evidence import for a fresh development Core.

This administrator helper never measures, admits, dispatches, or copies an
account store.  A Root-reviewed plan selects two existing Library entries and
their exact checking records.  A later launch guard reobserves the originals.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading

HERE = Path(__file__).resolve().parent
ROOT = Path('/var/lib/ai4r-rsi-codex')
SOURCE = ROOT/'controller/operational-bootstrap.host-codex-v6'
SELECTION = ROOT/'config/bootstrap-supersessions/host-codex-v6'
LEDGER = Path('/var/lib/ai4r-rsi-host-codex/relay/requests.sqlite3')
INPUT_SCHEMA = 'ai4r-rsi-development-seed-input:1'
COMPLETE_SCHEMA = 'ai4r-rsi-development-seed-completion:1'
GUARD_SCHEMA = 'ai4r-rsi-development-launch-guard:1'
MAX_FILE = 4*1024*1024
MAX_FILES = 1024
MAX_TOTAL = 16*1024*1024
TABLES = {
    'calibration_profiles': ('profile_sha','profile_ref','registration_ref','closure','actor'),
    'calibration_attempts': ('profile_sha','case_id','state','receipt_ref'),
    'checking_asset_admissions': ('closure_sha','asset_kind','profile_sha','receipt_ref'),
    'library_versions': ('name','version','declaration_ref','admission_ref','standing','effect_scope','body_refs','origin'),
    'check_associations': ('declaration_sha256','bundle_ref','profile_ref','evidence_refs','actor'),
}
OPTION_REFS = frozenset({'calibration_runtime_ref','compiler_template_ref','default_policy_ref',
    'finalization_profile_ref','input_directory_ref','planner_template_ref','profile_ref',
    'resource_inventory_ref','search_bounds_ref','workspace_ref'})
COMPLETE_FIELDS = {'schema','id','plan_sha256','input_sha256','destination','original_guards',
    'imported_historical_ref','row_artifact_pins_sha256','source_pins','zero_dispatch','recorded_at'}
GUARD_FIELDS = {'schema','id','seed_receipt_sha256','source_guards_sha256','bootstrap_operations_frozen',
    'relay_idle','original_guards','source_pins','recorded_at'}
DESTINATION_FIELDS = {'isolation_root','core_root','input_root','account_root','record_root',
    'native_lease_root','work_root','parent_directory','native_scope_ref'}


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'NONFINITE_JSON'))


def ref(value):
    need(isinstance(value, dict) and set(value) == {'id','sha256'}
         and isinstance(value['id'], str) and 0 < len(value['id']) <= 512
         and isinstance(value['sha256'], str) and len(value['sha256']) == 64
         and all(c in '0123456789abcdef' for c in value['sha256']), 'INVALID_REF')
    return value


def protected(path, owner=0, *, directory=False, maximum=MAX_FILE):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_PROTECTED_PATH_REQUIRED')
    for current in (path, *path.parents):
        info = current.lstat()
        need(not stat.S_ISLNK(info.st_mode) and info.st_uid in {0, owner}
             and not info.st_mode & 0o022, 'UNPROTECTED_PATH_ANCESTRY')
    info = path.stat()
    need(info.st_uid == owner and (stat.S_ISDIR(info.st_mode) if directory else
         stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= maximum),
         'PROTECTED_PATH_CUSTODY_DIFFERS')
    return path


def read(path, owner=0, maximum=MAX_FILE):
    path = protected(path, owner, maximum=maximum)
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW)
    try:
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(maximum+1)
        need(len(raw) <= maximum, 'FILE_LIMIT_EXCEEDED')
        return raw
    finally:
        os.close(fd)


def exclusive(path, value, *, owner=0, gid=12001, mode=0o440):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        os.fchown(stream.fileno(), owner, gid)
        os.fchmod(stream.fileno(), mode)
        stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sibling(name):
    spec = importlib.util.spec_from_file_location('_seed_'+name, HERE/(name+'.py'))
    owner = importlib.util.module_from_spec(spec); spec.loader.exec_module(owner)
    return owner


def source_pins():
    return {name: digest((HERE/name).read_bytes()) for name in
            ('rsi_development_seed.py','rsi_bootstrap_supersession.py','rsi_host_codex.py')}


def database(path, owner=12001):
    path = protected(path, owner, maximum=256*1024*1024)
    for suffix in ('-wal','-journal'):
        other = Path(str(path)+suffix)
        need(not other.exists() or other.stat().st_size == 0, 'STOPPED_DATABASE_REQUIRED')
    result = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)
    result.row_factory = sqlite3.Row
    return result


def refs(value):
    """Only applied to literal trusted control-record positions, never subjects."""
    if isinstance(value, dict):
        if set(value) == {'id','sha256'}:
            yield ref(value)
        else:
            for item in value.values():
                yield from refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from refs(item)


class SourceReader:
    def __init__(self, root):
        self.root = Path(root)
        self.connection = database(self.root/'state/research.sqlite3')
        self._lock = threading.RLock()

    def artifact(self, pin):
        ref(pin)
        row = self.connection.execute('SELECT rowid,* FROM artifacts WHERE id=?', (pin['id'],)).fetchone()
        need(row is not None and row['sha256'] == pin['sha256'], 'INDEXED_ORIGINAL_DIFFERS')
        raw = read(self.root/'artifacts/sha256'/pin['sha256'][:2]/pin['sha256'], 12001)
        need(digest(raw) == pin['sha256'], 'ORIGINAL_HASH_DIFFERS')
        return dict(row), raw

    def read_blob(self, pin):
        return self.artifact(pin)[1]

    def read_record(self, pin, *, contract_id=None):
        result = parse(self.read_blob(pin))
        if contract_id:
            from jiuwenswarm.research.contracts import validate
            validate(contract_id, result)
        return result

    def record_kind(self, pin):
        row = self.connection.execute('SELECT kind FROM records WHERE id=?', (pin['id'],)).fetchone()
        return None if row is None else row['kind']

    def iter_records(self,kinds):
        for row in self.connection.execute('SELECT r.kind,a.id,a.sha256 FROM records r JOIN artifacts a ON a.id=r.id ORDER BY r.rowid'):
            if row['kind'] not in kinds:continue
            pin={'id':row['id'],'sha256':row['sha256']}
            yield {'kind':row['kind'],'ref':pin,'record':self.read_record(pin)}

    def close(self):
        self.connection.close()


def canonical_require(reader, selected, entries):
    """Use the canonical reader methods without its CREATE TABLE constructor."""
    from jiuwenswarm.research.checks.assets import CheckAssetAdmissions
    checks = object.__new__(CheckAssetAdmissions)
    checks.store = reader
    checks._runners = {}; checks._validated_profiles = {}; checks._development_authorizations = {}
    checks._runtime_scope = checks._runtime_profiles = None
    checks.bind_calibration_runtime(selected['calibration_runtime_ref'], **{key:selected[key]
        for key in ('configuration_ref','model_selection_profile_ref','deployment_ref')})
    for entry in entries.values():
        association = reader.connection.execute('SELECT * FROM check_associations WHERE declaration_sha256=?',
                                                (entry['declaration_ref']['sha256'],)).fetchone()
        need(association is not None, 'EXACT_CHECK_ASSOCIATION_REQUIRED')
        checks.require(parse(association['bundle_ref']), parse(association['profile_ref']))


def collect(reader, selected, work_capsules):
    """Literal SQL subset and typed reference positions; no full-Core copy."""
    need(set(work_capsules) == {'intent','verifier'}, 'EXACT_INTENT_VERIFIER_REQUIRED')
    stages = {row['stage']:row for row in selected['stages']}
    entries = {}; rows = {name:[] for name in TABLES}; roots = []
    corpus_refs = {}
    for stage in ('intent','verifier'):
        need(work_capsules[stage] == stages[stage]['declaration_ref'], 'CROSS_STAGE_DECLARATION')
        declaration = reader.read_record(work_capsules[stage], contract_id='capsule-declaration')
        identity = declaration['identity']
        need(identity['name'] == {'intent':'intent.compiler','verifier':'research.verifier'}[stage], 'LITERAL_WORK_CAPSULE_DIFFERS')
        found = reader.connection.execute('SELECT rowid,* FROM library_versions WHERE name=? AND version=?',
                                         (identity['name'], identity['version_label'])).fetchone()
        need(found is not None, 'ACTIVE_LIBRARY_ENTRY_REQUIRED')
        row = dict(found)
        need(parse(row['declaration_ref']) == work_capsules[stage] and row['standing'] == 'active'
             and row['effect_scope'] == 'live_plans', 'LIBRARY_ENTRY_DIFFERS')
        admission = reader.read_record(parse(row['admission_ref']), contract_id='library-admission')
        need(admission['status'] == 'admitted' and admission['candidate_ref'] == work_capsules[stage], 'REAL_ADMISSION_REQUIRED')
        entries[stage] = dict(row, declaration_ref=work_capsules[stage])
        rows['library_versions'].append(row)
        association = reader.connection.execute('SELECT rowid,* FROM check_associations WHERE declaration_sha256=?',
                                                (work_capsules[stage]['sha256'],)).fetchone()
        need(association is not None, 'CHECK_ASSOCIATION_ABSENT')
        association = dict(association); rows['check_associations'].append(association)
        roots.extend((pin,'leaf') for pin in refs(parse(association['evidence_refs'])))
        roots.extend([(work_capsules[stage],'leaf'), (parse(row['admission_ref']),'leaf')])
        roots.extend((pin,'leaf') for pin in refs(parse(row['body_refs'])))
        profile_ref = stages[stage]['profile_ref']
        profile_row = reader.connection.execute('SELECT rowid,* FROM calibration_profiles WHERE profile_sha=?',
                                                (profile_ref['sha256'],)).fetchone()
        need(profile_row is not None and parse(profile_row['profile_ref']) == profile_ref, 'PROFILE_REGISTRATION_ABSENT')
        profile_row = dict(profile_row); rows['calibration_profiles'].append(profile_row)
        profile = reader.read_record(profile_ref)
        roots.extend([(profile_ref,'profile'), (parse(profile_row['registration_ref']),'leaf')])
        for pin in refs(parse(profile_row['closure'])): roots.append((pin,'leaf'))
        attempts = [dict(x) for x in reader.connection.execute(
            'SELECT rowid,* FROM calibration_attempts WHERE profile_sha=? ORDER BY rowid', (profile_ref['sha256'],))]
        need(len(attempts) == len(profile['cases']) and {x['case_id'] for x in attempts}
             == {x['case_id'] for x in profile['cases']}, 'INCOMPLETE_CALIBRATION_CASES')
        for attempt in attempts:
            need(attempt['state'] == 'matched' and attempt['receipt_ref'] is not None, 'UNMATCHED_CALIBRATION_CASE')
            pin = parse(attempt['receipt_ref']); measured = reader.read_record(pin)
            need(measured['profile_ref'] == profile_ref and measured['case_id'] == attempt['case_id']
                 and measured['status'] == 'matched', 'CALIBRATION_RECEIPT_DIFFERS')
            roots.append((pin,'leaf')); corpus_refs[encoded(pin)] = pin
        rows['calibration_attempts'].extend(attempts)
        admissions = [dict(x) for x in reader.connection.execute(
            'SELECT rowid,* FROM checking_asset_admissions WHERE profile_sha=? ORDER BY rowid', (profile_ref['sha256'],))]
        need(len(admissions) == 2 and {x['asset_kind'] for x in admissions} == {'bundle','criteria'}, 'BOTH_ADMISSIONS_REQUIRED')
        for asset in admissions:
            pin = parse(asset['receipt_ref']); value = reader.read_record(pin)
            need(value['status'] == 'admitted' and value['calibration_profile_ref'] == profile_ref
                 and value['asset_kind'] == asset['asset_kind'], 'CHECK_ADMISSION_DIFFERS')
            roots.append((pin,'leaf')); corpus_refs[encoded(pin)] = pin
        rows['checking_asset_admissions'].extend(admissions)
    canonical_require(reader, selected, entries)
    binding = reader.read_record(selected['binding_ref'])
    need(binding['protected_options'].get('development_builtin_catalog') is False, 'BUILTIN_BYPASS_DENIED')
    roots.append((selected['binding_ref'],'leaf'))
    roots.extend((selected[key],'control') for key in ('configuration_ref','model_selection_profile_ref','deployment_ref'))
    options = binding['protected_options']
    actual_option_refs = {key for key,value in options.items() if isinstance(value,dict) and set(value)=={'id','sha256'}}
    need(actual_option_refs <= OPTION_REFS, 'UNREVIEWED_CONTROL_REFERENCE_POSITION')
    roots.extend((options[key], 'runtime' if key=='calibration_runtime_ref' else 'control') for key in sorted(actual_option_refs))
    artifacts = {}; records = {}; total = 0
    queue = list(roots); visited = set()
    while queue:
        pin, purpose = queue.pop(0); key = encoded(pin)
        if (key,purpose) in visited: continue
        visited.add((key,purpose))
        metadata, raw = reader.artifact(pin)
        need(len(artifacts) < MAX_FILES or pin['id'] in artifacts, 'PUBLIC_CLOSURE_FILE_LIMIT')
        kind = reader.record_kind(pin)
        need(kind in {None,'model-selection-profile','model-profile'} or not (kind.startswith('model-') or kind.startswith('private-')
             or kind.startswith('native-') or kind.startswith('rsi-')), 'NONPUBLIC_RECORD_KIND_DENIED:'+str(kind))
        if pin['id'] not in artifacts:
            total += len(raw); need(total <= MAX_TOTAL, 'PUBLIC_CLOSURE_BYTE_LIMIT')
            artifacts[pin['id']] = dict(metadata=metadata, raw=raw, purpose=purpose)
            row = reader.connection.execute('SELECT rowid,* FROM records WHERE id=?', (pin['id'],)).fetchone()
            if row is not None: records[pin['id']] = dict(row)
        if purpose == 'profile':
            value = parse(raw)
            need(set(value) == {'schema','id','bundle_ref','profile_ref','measurement_runner_ref','cases'}
                 and value['schema']=='ai4r-check-calibration:1', 'CLOSED_CALIBRATION_PROFILE_REQUIRED')
            queue.extend((value[k],'control') for k in ('bundle_ref','profile_ref','measurement_runner_ref'))
            for case in value['cases']:
                for name in ('declaration_ref','subject_ref','expected_ref'):
                    current = ref(case[name]); queue.append((current,'leaf')); corpus_refs[encoded(current)] = current
        elif purpose == 'runtime':
            value = parse(raw)
            queue.extend((value[k],'control') for k in ('configuration_ref','model_selection_profile_ref','deployment_ref'))
            # Other approved profiles retain their opaque identities only.
        elif purpose == 'control':
            try: value = parse(raw)
            except (ValueError,UnicodeError): continue
            queue.extend((current,'control') for current in refs(value))
    need({x['profile_sha'] for x in rows['calibration_profiles']} ==
         {stages[x]['profile_ref']['sha256'] for x in ('intent','verifier')}, 'CROSS_PROFILE_IMPORT')
    # Preserve the ordinary store's own non-product markers for these exact
    # authored checking objects.  Copying bytes must not erase their origin.
    imported={(ident,item['metadata']['sha256']) for ident,item in artifacts.items()}
    for row in reader.connection.execute("SELECT r.rowid,r.*,a.sha256 FROM records r JOIN artifacts a ON a.id=r.id WHERE r.kind='calibration-material' ORDER BY r.rowid"):
        pin={'id':row['id'],'sha256':row['sha256']};marker=reader.read_record(pin)
        subject=marker.get('artifact_ref')
        if not (isinstance(subject,dict) and set(subject)=={'id','sha256'}
                and (subject['id'],subject['sha256']) in imported):continue
        need(marker.get('calibration_only') is True,'CHECKING_ORIGIN_MARKER_DIFFERS')
        metadata,body=reader.artifact(pin)
        need(len(artifacts)<MAX_FILES and total+len(body)<=MAX_TOTAL,'PUBLIC_CLOSURE_LIMIT')
        artifacts[pin['id']]=dict(metadata=metadata,raw=body,purpose='historical-origin')
        record=reader.connection.execute('SELECT rowid,* FROM records WHERE id=?',(pin['id'],)).fetchone()
        records[pin['id']]=dict(record);total+=len(body)
    return {'tables':rows,'artifacts':artifacts,'records':sorted(records.values(), key=lambda x:x['rowid']),
            'checking_corpus_refs':list(corpus_refs.values()),'entries':entries}


def validate_input(value):
    fields = {'schema','id','source_namespace','selection_directory','selection_completion_sha256',
              'work_capsule_refs','material_packet','destination_root'}
    need(isinstance(value,dict) and set(value)==fields and value['schema']==INPUT_SCHEMA,
         'CLOSED_SEED_INPUT_REQUIRED')
    need(isinstance(value['id'],str) and 1<=len(value['id'])<=64
         and all(c.isalnum() or c in '-_.' for c in value['id']), 'INVALID_SEED_ID')
    need(Path(value['source_namespace'])==SOURCE and Path(value['selection_directory'])==SELECTION,
         'FIXED_ORIGINAL_BOOTSTRAP_REQUIRED')
    need(Path(value['destination_root'])==ROOT/'development'/value['id'], 'FIXED_FRESH_DESTINATION_REQUIRED')
    need(set(value['work_capsule_refs'])=={'intent','verifier'}, 'EXACT_WORK_SUBSET_REQUIRED')
    for pin in value['work_capsule_refs'].values(): ref(pin)
    packet=value['material_packet']
    need(isinstance(packet,dict) and set(packet)=={'path','sha256'}, 'ROOT_PUBLIC_PACKET_REQUIRED')
    ref({'id':'selection','sha256':value['selection_completion_sha256']})
    return value


def validate_public_preparation(value, packet, visible, development_export):
    """Only the reviewed development projection crosses the private boundary."""
    fields = {'schema','parent_declaration_ref','target_profile_ref','visible_context_ref',
              'required_test_refs','development_export_ref','security_campaigns','qualification'}
    need(isinstance(value,dict) and set(value)==fields
         and value['schema']=='ai4r-rsi-development-public-preparation:1',
         'CLOSED_PUBLIC_PREPARATION_REQUIRED')
    need(value['parent_declaration_ref']==packet['parent_declaration_ref']
         and value['target_profile_ref']==packet['target_profile_ref']
         and value['visible_context_ref']==packet['visible_context_ref']
         and value['required_test_refs']==visible['required_test_refs']
         and value['security_campaigns']=='DEFERRED' and value['qualification'] is False,
         'PUBLIC_PREPARATION_BINDING_DIFFERS')
    ref(value['development_export_ref'])
    need(development_export==visible['context'], 'PUBLIC_DEVELOPMENT_EXPORT_DIFFERS')
    return value


def packet_materials(packet_ref):
    raw=read(packet_ref['path']);need(digest(raw)==packet_ref['sha256'],'PUBLIC_PACKET_HASH_DIFFERS')
    packet=parse(raw)
    fields={'schema','parent_declaration_ref','parent_body_refs','target_profile_ref',
            'visible_context_ref','preparation_ref','materials'}
    need(isinstance(packet,dict) and set(packet)==fields
         and packet['schema']=='ai4r-rsi-development-public-materials:1', 'CLOSED_PUBLIC_PACKET_REQUIRED')
    need(isinstance(packet['materials'],list) and 1<=len(packet['materials'])<=96, 'FINITE_PUBLIC_MATERIALS_REQUIRED')
    materials={};total=0
    for row in packet['materials']:
        need(isinstance(row,dict) and set(row)=={'ref','bytes_base64'},'CLOSED_PUBLIC_ROW_REQUIRED')
        pin=ref(row['ref']);body=base64.b64decode(row['bytes_base64'],validate=True)
        need(0<len(body)<=MAX_FILE and digest(body)==pin['sha256'] and pin['id'] not in materials,
             'PUBLIC_MATERIAL_BYTES_OR_ID_DIFFER')
        total+=len(body);need(total<=MAX_TOTAL,'PUBLIC_PACKET_BYTE_LIMIT')
        materials[pin['id']]=(pin,body)
    def get(pin):
        ref(pin);need(pin['id'] in materials and materials[pin['id']][0]==pin,'PUBLIC_MATERIAL_MISSING')
        return parse(materials[pin['id']][1])
    parent=get(packet['parent_declaration_ref']);target=get(packet['target_profile_ref'])
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research_rsi.profiles import freeze_profile
    validate('capsule-declaration',parent);freeze_profile(target,parent,validate)
    need(target['parent_declaration_ref']==packet['parent_declaration_ref'],'PUBLIC_PARENT_DIFFERS')
    expected={x['path']:x['sha256'] for x in parent['identity']['body']}
    for dependency in parent['needs']['external']:
        pin=dependency.get('pin')
        if isinstance(pin,dict) and set(pin)=={'ref','sha256'}:expected[pin['ref']]=pin['sha256']
    need(set(packet['parent_body_refs'])==set(expected),'EXACT_PUBLIC_PARENT_CLOSURE_REQUIRED')
    for name,pin in packet['parent_body_refs'].items():
        ref(pin);need(pin['sha256']==expected[name] and materials.get(pin['id'],(None,))[0]==pin,
                      'PUBLIC_PARENT_BYTES_ABSENT')
    visible=get(packet['visible_context_ref'])
    need(set(visible)=={'context','mandatory_fixtures','required_test_refs'}
         and len(visible['mandatory_fixtures'])==12
         and visible['required_test_refs']==target['required_test_refs'],'EXACT_PUBLIC_TWELVE_CASES_REQUIRED')
    from jiuwenswarm.research_rsi.targets import registered_helper
    helper=registered_helper('ranking-v1')
    tests=set()
    for item in visible['mandatory_fixtures']:
        need(set(item)=={'input_ref','test_ref'},'CLOSED_VISIBLE_BINDING_REQUIRED')
        tests.add(encoded(ref(item['test_ref'])))
        helper.validate_visible_inputs(get(item['input_ref']))
        definition=get(item['test_ref'])
        need(definition.get('schema')=='ai4r-rsi-frozen-helper-test:1'
             and definition.get('input_ref')==item['input_ref'],'PUBLIC_TEST_INPUT_DIFFERS')
    need(len(tests)==12 and tests=={encoded(pin) for pin in target['required_test_refs']},'DUPLICATE_PUBLIC_TEST')
    preparation=get(packet['preparation_ref'])
    need(isinstance(preparation,dict) and set(preparation)=={'schema','parent_declaration_ref',
         'target_profile_ref','visible_context_ref','required_test_refs','development_export_ref',
         'security_campaigns','qualification'}, 'CLOSED_PUBLIC_PREPARATION_REQUIRED')
    validate_public_preparation(preparation,packet,visible,get(ref(preparation['development_export_ref'])))
    return packet,materials


def observe_originals(value):
    """Reobserve current real completion, every Root recovery link and idle RPC."""
    recovery=sibling('rsi_bootstrap_supersession')
    recovery.verify_deployment_selections(ROOT)
    original_raw=read(SOURCE/'bootstrap.json',12001)
    generation=recovery.get(SELECTION/'generation.json')
    selected,metadata=recovery.selected_bootstrap(parse(original_raw),original_raw,path=SELECTION,
                                                expected=generation['selection_required'])
    completion=read(SELECTION/'complete.json')
    need(digest(completion)==value['selection_completion_sha256'],'ROOT_SELECTION_CHANGED')
    history=recovery.historical_capacity_dispositions(ROOT,'host-codex-v6')
    scope={'schema':'ai4r-rsi-bootstrap-native-scope:1','account_root':'/var/lib/ai4r-rsi/controller/accounts',
           'root':selected['root']}
    scope_ref={'id':digest(encoded(scope))+'.json','sha256':digest(encoded(scope))}
    leases=recovery.ReadLeases(SOURCE/'native-leases')
    try:
        row=leases.db.execute('SELECT state,ref FROM native_effect_leases WHERE scope=?',
                              (encoded(scope_ref).decode(),)).fetchone()
        need(row is not None and row[0]=='complete','ORIGINAL_NATIVE_SCOPE_NOT_COMPLETE')
        current=parse(row[1]);leases.get(scope_ref);leases.get(current)
    finally:leases.close()
    import subprocess
    result=subprocess.run(['/usr/bin/python3','-B',str(HERE/'rsi_host_codex.py'),'check'],
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LANG':'C.UTF-8',
             'PYTHONPATH':str(HERE.parents[1])+':/opt/ai4r-rsi-host-codex/site-packages',
             'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,timeout=20)
    need(result.returncode==0,'ORIGINAL_RPC_OBSERVATION_UNAVAILABLE')
    rpc=parse(result.stdout);need(rpc['active'] is False and rpc['unresolved'] is False,'GLOBAL_RPC_NOT_IDLE')
    core_path=SOURCE/'core/state/research.sqlite3';lease_path=SOURCE/'native-leases/index.sqlite'
    for path in (core_path,lease_path):
        connection=database(path);connection.close()
    facts={'source_namespace':str(SOURCE),'source_bootstrap_sha256':digest(original_raw),
        'core_sha256':digest(read(core_path,12001,256*1024*1024)),
        'native_lease_index_sha256':digest(read(lease_path,12001,256*1024*1024)),
        'original_scope_ref':scope_ref,'original_completed_lease_ref':current,
        'scope_receipt_sha256':scope_ref['sha256'],'completed_lease_receipt_sha256':current['sha256'],
        'selection_completion_sha256':digest(completion),'selected_manifest_sha256':digest(encoded(selected)),
        'completed_capacity_history_sha256':digest(encoded(history)),
        'native_ledger_sha256':digest(read(LEDGER,0,256*1024*1024)),
        'rpc_idle':True,'source_pins':source_pins(),
        'foreign_development_scopes':development_registry(value['id'])}
    return selected,facts


def development_registry(exclude_id):
    """A new name never avoids an earlier uncertain development lease."""
    parent=ROOT/'config/development-seeds'
    if not parent.exists():return []
    protected(parent,0,directory=True);children=sorted(parent.iterdir())
    need(len(children)<=16,'FINITE_DEVELOPMENT_REGISTRY_EXHAUSTED')
    result=[]
    for directory in children:
        protected(directory,0,directory=True)
        if directory.name==exclude_id:continue
        path=directory/'complete.json'
        need(path.exists(),'PRIOR_PARTIAL_SEED_REQUIRES_RECONCILIATION')
        raw=read(path);done=parse(raw)
        need(set(done)==COMPLETE_FIELDS and done['schema']==COMPLETE_SCHEMA
             and done['id']==directory.name and done['zero_dispatch'] is True,
             'PRIOR_SEED_RECEIPT_DIFFERS')
        dest=done['destination'];need(set(dest)==DESTINATION_FIELDS,'PRIOR_DESTINATION_DIFFERS')
        need(Path(dest['isolation_root'])==ROOT/'development'/done['id'],'PRIOR_SCOPE_ESCAPES_NAMESPACE')
        scope={'schema':'ai4r-rsi-native-profile-scope:1','isolation_root':dest['isolation_root'],
               'account_root':dest['account_root']}
        need(dest['native_scope_ref']=={'id':digest(encoded(scope))+'.json','sha256':digest(encoded(scope))},
             'PRIOR_NATIVE_SCOPE_DIFFERS')
        core=Path(dest['core_root'])/'state/research.sqlite3';db=database(core)
        try:
            calls=db.execute('SELECT count(*) FROM model_calls').fetchone()[0]
            tools=db.execute('SELECT count(*) FROM tool_calls').fetchone()[0]
        finally:db.close()
        index=Path(dest['native_lease_root'])/'index.sqlite';db=database(index)
        try:rows=[tuple(row) for row in db.execute('SELECT scope,state,ref FROM native_effect_leases')]
        finally:db.close()
        need(len(rows)<=1,'PRIOR_SCOPE_INDEX_AMBIGUOUS')
        if rows:
            encoded_scope,state,encoded_ref=rows[0]
            need(parse(encoded_scope)==dest['native_scope_ref'] and state=='complete',
                 'PRIOR_DEVELOPMENT_EFFECT_ACTIVE_OR_UNCERTAIN')
            pin=ref(parse(encoded_ref));body=read(Path(dest['native_lease_root'])/pin['id'],12001)
            need(digest(body)==pin['sha256'],'PRIOR_COMPLETION_HASH_DIFFERS')
            receipt=parse(body)
            need(receipt.get('scope_ref')==dest['native_scope_ref']
                 and receipt.get('record_kind')=='rsi-native-effect-completion:1' and receipt.get('state')=='complete',
                'PRIOR_DEVELOPMENT_COMPLETION_UNPROVED')
            previous=ref(receipt['prior_lease_ref']);start_raw=read(Path(dest['native_lease_root'])/previous['id'],12001)
            need(digest(start_raw)==previous['sha256'],'PRIOR_START_HASH_DIFFERS');start=parse(start_raw)
            need(start.get('record_kind')=='rsi-native-effect-start:1'
                 and start.get('scope_ref')==dest['native_scope_ref'],'PRIOR_START_SCOPE_DIFFERS')
            reader=SourceReader(Path(dest['core_root']))
            try:
                starts=[e for e in reader.iter_records({'model-call-start'})
                        if e['record'].get('contract_ref')==start['contract_ref']]
                from jiuwenswarm.research_rsi.native_lease import native_completion_proof
                known,proof=native_completion_proof(reader,starts)
                need(known and proof==receipt['proof'],'PRIOR_NATIVE_COMPLETION_PROOF_DIFFERS')
            finally:reader.close()
        else:need(calls==tools==0,'UNLEASED_PRIOR_DEVELOPMENT_DISPATCH')
        result.append({'id':done['id'],'completion_sha256':digest(raw),'core_sha256':digest(read(core,12001,256*1024*1024)),
            'native_index_sha256':digest(read(index,12001,256*1024*1024)),'model_calls':calls,
            'tool_calls':tools,'scope_states':[row[1] for row in rows]})
    return result


def destination(value):
    root=Path(value['destination_root'])
    result={'isolation_root':str(root),**{key:str(root/name) for key,name in
        (('core_root','core'),('input_root','input'),('account_root','accounts'),('record_root','records'),
         ('native_lease_root','native-leases'),('work_root','work'),('parent_directory','parent'))}}
    scope={'schema':'ai4r-rsi-native-profile-scope:1','isolation_root':str(root),'account_root':result['account_root']}
    result['native_scope_ref']={'id':digest(encoded(scope))+'.json','sha256':digest(encoded(scope))}
    return result


def snapshot(value):
    validate_input(value)
    need(not Path(value['destination_root']).exists(),'FRESH_DESTINATION_ALREADY_EXISTS_NO_REPLAY')
    need(not (ROOT/'config/development-seeds'/value['id']).exists(),'SEED_ALREADY_CLAIMED_NO_REPLAY')
    selected,guards=observe_originals(value)
    reader=SourceReader(SOURCE/'core')
    try: result=collect(reader,selected,value['work_capsule_refs'])
    finally:reader.close()
    packet,materials=packet_materials(value['material_packet'])
    need(parse(materials[packet['target_profile_ref']['id']][1])['configuration_ref']==selected['configuration_ref'],
         'TARGET_CONFIGURATION_DIFFERS_FROM_IMPORTED_CAPSULES')
    corpus={encoded(pin) for pin in result['checking_corpus_refs']}
    need(not any(encoded(pin) in corpus for pin,_ in materials.values()),'CHECKING_CORPUS_MUST_NOT_ENTER_MODEL_INTAKE')
    row_pins={'tables':{name:sorted(rows,key=lambda x:x['rowid']) for name,rows in result['tables'].items()},
        'artifacts':[dict(item['metadata']) for _,item in sorted(result['artifacts'].items())],
        'records':result['records'],'checking_corpus_refs':result['checking_corpus_refs']}
    facts={'schema':'ai4r-rsi-development-seed-plan:1','id':value['id'],'input_sha256':digest(encoded(value)),
        'destination':destination(value),'original_guards':guards,'source_pins':source_pins(),
        'row_artifact_pins_sha256':digest(encoded(row_pins)),
        'row_counts':{name:len(rows) for name,rows in result['tables'].items()},
        'historical_artifacts':[{key:item['metadata'][key] for key in ('id','sha256','media_type','captured_at')}
                               for _,item in sorted(result['artifacts'].items())],
        'record_rowids':[row['rowid'] for row in result['records']],
        'public_material_packet_sha256':value['material_packet']['sha256'],
        'public_material_refs':[pin for pin,_ in materials.values()],
        'checking_corpus_not_for_intake_refs':result['checking_corpus_refs'],
        'parent_body_refs':packet['parent_body_refs'],'zero_dispatch':True,'new_admission_or_measurement':False}
    return facts,result,packet,materials,row_pins,selected


def plan(input_path):
    value=parse(read(input_path));validate_input(value)
    need(Path(input_path)==ROOT/'config/development-seed-inputs'/value['id']/'input.json','FIXED_ROOT_SEED_INPUT_REQUIRED')
    return snapshot(value)[0]


def insert_rows(db,table,columns,rows):
    names=('rowid',*columns)
    for row in sorted(rows,key=lambda x:x['rowid']):
        need(set(row)==set(names),'ORIGINAL_TABLE_COLUMNS_DIFFER')
        db.execute('INSERT INTO '+table+' ('+','.join(names)+') VALUES('+','.join('?' for _ in names)+')',
                   tuple(row[name] for name in names))


def root_directory(path):
    path=Path(path);protected(path.parent,0,directory=True)
    if path.exists():protected(path,0,directory=True)
    else:path.mkdir(mode=0o750);os.chown(path,0,12001)
    return path


def seed(input_path,review_sha256):
    need(os.geteuid()==0,'ROOT_SEED_REQUIRED')
    value=parse(read(input_path));validate_input(value)
    need(Path(input_path)==ROOT/'config/development-seed-inputs'/value['id']/'input.json','FIXED_ROOT_SEED_INPUT_REQUIRED')
    facts,data,packet,materials,row_pins,selected=snapshot(value)
    need(digest(encoded(facts))==review_sha256,'EXACT_SEED_PLAN_REVIEW_REQUIRED')
    need(plan(input_path)==facts,'ORIGINALS_CHANGED_BEFORE_SEED')
    admin=ROOT/'config/development-seeds'/value['id']
    root_directory(admin.parent);admin.mkdir(mode=0o750);os.chown(admin,0,12001)
    exclusive(admin/'claim.json',{'schema':'ai4r-rsi-development-seed-claim:1',
        'id':value['id'],'plan_sha256':review_sha256,'input_sha256':facts['input_sha256'],'zero_dispatch':True})
    dest=facts['destination'];base=Path(dest['isolation_root'])
    root_directory(base.parent)
    base.mkdir(mode=0o700);os.chown(base,12001,12001)
    for key in DESTINATION_FIELDS-{'isolation_root','native_scope_ref'}:
        path=Path(dest[key]);path.mkdir(mode=0o700);os.chown(path,12001,12001)
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.native_lease import NativeEffectLease
    core=SQLiteRunStore(dest['core_root'],input_root=dest['input_root'],recover=False)
    try:
        LibraryService(core)
        need(not core.connection.execute('SELECT 1 FROM artifacts LIMIT 1').fetchone(),'NEW_CORE_NOT_EMPTY')
        with core.transaction() as db:
            for ident,item in data['artifacts'].items():
                metadata=item['metadata'];path=Path(dest['core_root'])/'artifacts/sha256'/metadata['sha256'][:2]/metadata['sha256']
                path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                if not path.exists():
                    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    with os.fdopen(fd,'wb') as stream:stream.write(item['raw']);stream.flush();os.fsync(stream.fileno())
                insert_rows(db,'artifacts',('id','sha256','media_type','provenance','captured_at'),[metadata])
            insert_rows(db,'records',('id','kind','run_id','node_id','attempt_id','captured_at'),data['records'])
            for table,columns in TABLES.items():insert_rows(db,table,columns,data['tables'][table])
        for pin,raw in materials.values():
            existing=core.connection.execute('SELECT sha256 FROM artifacts WHERE id=?',(pin['id'],)).fetchone()
            if existing:
                need(existing[0]==pin['sha256'],'PUBLIC_ALIAS_CONFLICT');continue
            stored=core.put_blob(raw,media_type='application/octet-stream',provenance={'kind':'Root-approved-public-development-material','packet_sha256':value['material_packet']['sha256']})
            if stored!=pin:
                row=core.connection.execute('SELECT * FROM artifacts WHERE id=?',(stored['id'],)).fetchone()
                with core.transaction() as db:db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',
                    (pin['id'],pin['sha256'],row['media_type'],row['provenance'],row['captured_at']))
        imported=core.append_record('imported-historical-evidence',{
            'id':'development-seed:'+value['id'],'schema':'ai4r-rsi-imported-historical-public-evidence:1',
            'source_namespace':str(SOURCE),'original_guards':facts['original_guards'],
            'row_artifact_pins_sha256':facts['row_artifact_pins_sha256'],
            'rows_and_artifacts':row_pins,'checking_corpus_refs':data['checking_corpus_refs'],
            'new_measurement':False,'new_admission':False,'model_intake_includes_checking_corpus':False})
        canonical_require(core,selected,data['entries'])
    finally:core.close()
    leases=RecordStore(dest['native_lease_root'])
    try:
        scope=leases.put({'schema':'ai4r-rsi-native-profile-scope:1','isolation_root':dest['isolation_root'],'account_root':dest['account_root']})
        need(scope==dest['native_scope_ref'],'NEW_CANONICAL_SCOPE_DIFFERS')
        need(NativeEffectLease(leases,scope).current() is None,'NEW_SCOPE_HAS_DISPATCH_HISTORY')
    finally:leases.close()
    for name,pin in packet['parent_body_refs'].items():
        relative=Path(name);need(not relative.is_absolute() and '..' not in relative.parts,'PARENT_PATH_ESCAPE')
        path=Path(dest['parent_directory'])/relative;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        path.write_bytes(materials[pin['id']][1]);path.chmod(0o600)
    for path in [base,*base.rglob('*')]:
        need(not path.is_symlink(),'SEEDED_SYMLINK_DENIED');os.chown(path,12001,12001)
        if path.is_dir():path.chmod(0o700)
        elif path.is_file():path.chmod(0o600)
    need(observe_originals(value)[1]==facts['original_guards'],'HISTORICAL_ORIGINAL_CHANGED_DURING_SEED')
    result={'schema':COMPLETE_SCHEMA,'id':value['id'],'plan_sha256':review_sha256,
        'input_sha256':facts['input_sha256'],'destination':dest,'original_guards':facts['original_guards'],
        'imported_historical_ref':imported,'row_artifact_pins_sha256':facts['row_artifact_pins_sha256'],
        'source_pins':source_pins(),'zero_dispatch':True,'recorded_at':utc()}
    exclusive(admin/'complete.json',result)
    return {'status':'HISTORICAL_PUBLIC_SEED_COMPLETE_NOT_DISPATCHED','receipt':{
        'path':str(admin/'complete.json'),'sha256':digest(encoded(result))},'destination':dest,'zero_dispatch':True}


def launch_guard(input_path,seed_ref,*,bootstrap_operations_frozen):
    """Caller holds its Root lifecycle lock until the preview worker exits."""
    need(os.geteuid()==0 and bootstrap_operations_frozen is True,'ROOT_BOOTSTRAP_FREEZE_REQUIRED')
    completed=read_completed_seed(seed_ref);value=parse(read(input_path))
    need(value['id']==completed['id'] and digest(encoded(value))==completed['input_sha256'],'SEED_INPUT_DIFFERS')
    _,guards=observe_originals(value)
    need(guards==completed['original_guards'],'ORIGINALS_CHANGED_BEFORE_LAUNCH')
    result={'schema':GUARD_SCHEMA,'id':completed['id'],'seed_receipt_sha256':seed_ref['sha256'],
        'source_guards_sha256':digest(encoded(guards)),'bootstrap_operations_frozen':True,'relay_idle':True,
        'original_guards':guards,'source_pins':source_pins(),'recorded_at':utc()}
    path=Path(seed_ref['path']).with_name('launch-guard.json');exclusive(path,result)
    return {'path':str(path),'sha256':digest(encoded(result))}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('plan','seed'))
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--review-sha256')
    args=parser.parse_args(argv)
    need(os.geteuid()==0,'ROOT_REQUIRED')
    result=plan(args.input) if args.operation=='plan' else seed(args.input,args.review_sha256)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()


def read_completed_seed(receipt_ref):
    need(isinstance(receipt_ref,dict) and set(receipt_ref)=={'path','sha256'}, 'ROOT_RECEIPT_REFERENCE_REQUIRED')
    raw = read(receipt_ref['path']); need(digest(raw)==receipt_ref['sha256'], 'SEED_RECEIPT_HASH_DIFFERS')
    value = parse(raw)
    need(set(value)==COMPLETE_FIELDS and value['schema']==COMPLETE_SCHEMA and value['zero_dispatch'] is True,
         'CLOSED_ZERO_DISPATCH_SEED_RECEIPT_REQUIRED')
    need(set(value['destination'])==DESTINATION_FIELDS and value['source_pins'].get('rsi_development_seed.py')
         ==digest(Path(__file__).read_bytes()), 'SEED_SOURCE_OR_DESTINATION_DIFFERS')
    ref(value['destination']['native_scope_ref']); ref(value['imported_historical_ref'])
    return value


def read_launch_guard(guard_ref, seed_ref):
    seed = read_completed_seed(seed_ref)
    need(isinstance(guard_ref,dict) and set(guard_ref)=={'path','sha256'}, 'ROOT_GUARD_REFERENCE_REQUIRED')
    raw = read(guard_ref['path']); need(digest(raw)==guard_ref['sha256'], 'LAUNCH_GUARD_HASH_DIFFERS')
    value = parse(raw)
    need(set(value)==GUARD_FIELDS and value['schema']==GUARD_SCHEMA and value['id']==seed['id']
         and value['seed_receipt_sha256']==seed_ref['sha256'] and value['bootstrap_operations_frozen'] is True
         and value['relay_idle'] is True and value['original_guards']==seed['original_guards']
         and value['source_guards_sha256']==digest(encoded(value['original_guards']))
         and value['source_pins']==seed['source_pins'], 'EXACT_LAUNCH_GUARD_REQUIRED')
    return value
