"""Independent opaque ZIP qualification; no member import or execution authority."""
import copy
import hashlib
import io
import stat
import struct
import zipfile

import pytest

from jiuwenswarm.research.contracts import ResearchError
from tests.unit_tests.research.test_finite_e1 import finite_case_definition, visible_run


def archive_bytes(entries=(('nested/source.txt', b'visible bytes'),), *, compression=zipfile.ZIP_STORED):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=compression) as archive:
        for name, raw in entries:
            archive.writestr(name, raw)
    return output.getvalue()


def validate_bytes(raw, **changes):
    # Local import leaves the independent integration RED collectable before
    # the missing pure validator is implemented.
    from jiuwenswarm.research.finite_archive import validate_opaque_zip
    limits = {'max_members': 8, 'max_member_bytes': 64,
              'max_uncompressed_bytes': 128, 'max_total_bytes': 128}
    limits.update(changes)
    return validate_opaque_zip(raw, **limits)


def alter_single_member(raw, *, flags=None, method=None, size=None, crc=None):
    """Independent malformed bytes: change both original ZIP headers in place."""
    value = bytearray(raw)
    local, central = value.index(b'PK\x03\x04'), value.index(b'PK\x01\x02')
    for item, fmt, first, second in ((flags, '<H', 6, 8), (method, '<H', 8, 10),
                                    (size, '<I', 22, 24), (crc, '<I', 14, 16)):
        if item is not None:
            struct.pack_into(fmt, value, local + first, item)
            struct.pack_into(fmt, value, central + second, item)
    return bytes(value)


@pytest.mark.parametrize('compression', [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED], ids=['stored', 'deflated'])
def test_archive_bytes_validate_exact_usage_without_extraction(monkeypatch, compression):
    raw = archive_bytes((('one.txt', b'abc'), ('nested/.source', b'defg')), compression=compression)
    def forbidden(*args, **kwargs):
        raise AssertionError('Opaque qualification must never extract a filesystem member')
    monkeypatch.setattr(zipfile.ZipFile, 'extract', forbidden)
    monkeypatch.setattr(zipfile.ZipFile, 'extractall', forbidden)
    before = hashlib.sha256(raw).hexdigest()
    assert validate_bytes(raw, max_members=2, max_member_bytes=4,
                          max_uncompressed_bytes=7, max_total_bytes=7) == (2, 7)
    assert hashlib.sha256(raw).hexdigest() == before


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/drive', 'C:relative',
    'a\\b', 'a//b', 'a/./b', './file', 'a/../b', 'a\x01b', 'directory/'], ids=[
    'parent','absolute','drive','drive-relative','backslash','empty-part','dot-part',
    'dot-prefix','nested-parent','control','directory'])
def test_archive_bytes_refuse_noncanonical_paths(name):
    with pytest.raises(ResearchError) as error:
        validate_bytes(archive_bytes(((name, b'x'),)))
    assert error.value.code == 'finite_fixture'


@pytest.mark.parametrize('names', [('same', 'same'), ('Case', 'case'),
    ('node', 'node/child'), ('node/child', 'node')], ids=['duplicate', 'case', 'parent-first', 'child-first'])
def test_archive_bytes_refuse_duplicate_or_conflicting_tree(names):
    entries = tuple((name, b'x') for name in names)
    if names[0] == names[1]:
        with pytest.warns(UserWarning,match='Duplicate name:'):
            raw = archive_bytes(entries)
    else:
        raw = archive_bytes(entries)
    with pytest.raises(ResearchError):
        validate_bytes(raw)


@pytest.mark.parametrize('mode', [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFDIR, stat.S_IFSOCK],
                         ids=['link', 'fifo', 'device', 'directory-mode', 'socket'])
def test_archive_bytes_refuse_links_and_special_entries(mode):
    info = zipfile.ZipInfo('source')
    info.create_system = 3
    info.external_attr = (mode | 0o600) << 16
    with pytest.raises(ResearchError):
        validate_bytes(archive_bytes(((info, b'x'),)))


@pytest.mark.parametrize('fault', ['encrypted', 'strong-encrypted', 'nul-name', 'bad-crc',
    'oversized-declared', 'underreported-actual', 'invalid-deflate'])
def test_archive_bytes_validate_original_metadata_and_actual_content(fault):
    raw = archive_bytes((('source!name', b'abcdefghijk'),), compression=zipfile.ZIP_DEFLATED)
    if fault == 'encrypted':
        raw = alter_single_member(raw, flags=1)
    elif fault == 'strong-encrypted':
        raw = alter_single_member(raw, flags=64)
    elif fault == 'nul-name':
        raw = raw.replace(b'source!name', b'source\x00name')
    elif fault == 'bad-crc':
        raw = alter_single_member(raw, crc=0)
    elif fault == 'oversized-declared':
        raw = alter_single_member(raw, size=65)
    elif fault == 'underreported-actual':
        import zlib
        raw = alter_single_member(raw, size=1, crc=zlib.crc32(b'a'))
    else:
        data = bytearray(raw)
        offset = 30 + struct.unpack_from('<H', data, 26)[0] + struct.unpack_from('<H', data, 28)[0]
        data[offset] = 0xff
        raw = bytes(data)
    with pytest.raises(ResearchError) as error:
        validate_bytes(raw)
    assert error.value.code == 'finite_fixture'


def test_archive_bytes_unsupported_compression_is_explicit_unavailable():
    with pytest.raises(ResearchError) as error:
        validate_bytes(alter_single_member(archive_bytes(), method=99))
    assert error.value.code == 'unavailable'


@pytest.mark.parametrize('changes', [dict(max_members=1), dict(max_member_bytes=3),
    dict(max_uncompressed_bytes=7), dict(max_total_bytes=7)],
    ids=['member-count','member-bytes','inflated-bytes','total-bytes'])
def test_archive_bytes_enforce_each_explicit_budget(changes):
    with pytest.raises(ResearchError):
        validate_bytes(archive_bytes((('one', b'abcd'), ('two', b'efgh'))), **changes)


def test_archive_bytes_refuse_unreadable_original():
    with pytest.raises(ResearchError):
        validate_bytes(b'not a ZIP')


def test_archive_cardinality_is_bounded_before_zip_index_allocation(monkeypatch):
    raw = archive_bytes((('one',b'a'),('two',b'b')))
    def unexpected_index(*args,**kwargs):
        raise AssertionError('Over-budget central index must not be allocated')
    monkeypatch.setattr(zipfile,'ZipFile',unexpected_index)
    with pytest.raises(ResearchError) as error:
        validate_bytes(raw,max_members=1)
    assert error.value.code == 'finite_fixture'


@pytest.mark.parametrize('fault',['underreported-count','overreported-count','directory-size','multidisk','zip64','hidden-zip64-index'])
def test_archive_original_directory_metadata_cannot_hide_members(fault):
    value = bytearray(archive_bytes())
    end = value.rindex(b'PK\x05\x06')
    if fault.endswith('count'):
        count = 0 if fault == 'underreported-count' else 2
        struct.pack_into('<HH',value,end+8,count,count)
    elif fault == 'directory-size':
        struct.pack_into('<I',value,end+12,1)
    elif fault == 'multidisk':
        struct.pack_into('<H',value,end+4,1)
    elif fault == 'hidden-zip64-index':
        directory_size,directory_offset = struct.unpack_from('<II',value,end+12)
        final = bytearray(value[end:])
        struct.pack_into('<HHII',final,8,0,0,0,0)
        indexed = struct.pack('<4sQ2H2I4Q',b'PK\x06\x06',44,45,45,0,0,1,1,directory_size,directory_offset)
        locator = struct.pack('<4sIQI',b'PK\x06\x07',0,end,1)
        value = value[:end] + indexed + locator + final
    else:
        struct.pack_into('<HH',value,end+8,65535,65535)
    with pytest.raises(ResearchError) as error:
        validate_bytes(bytes(value))
    assert error.value.code == ('unavailable' if fault in {'multidisk','zip64','hidden-zip64-index'} else 'finite_fixture')


@pytest.mark.parametrize('fault', ['source', 'field'])
def test_policy_v1_has_no_archive_member_selector(fault):
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    case, policy, template = finite_case_definition()
    if fault == 'source':
        case['uploads'][0]['source'] = 'archive_member'
    else:
        case['uploads'][0]['member_path'] = 'brief.json'
    with pytest.raises(ResearchError):
        FiniteE1._validate_case(case, set(case['inputs']), policy, template)


async def owned_archive_case(tmp_path, *, count=1, limits=None, ambient_member=False, cumulative_budget=None, malformed_dataset=False):
    """Actual original uploads/intake/profile claims; no synthesized acceptance."""
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.finite_evaluation import FiniteE1
    from jiuwenswarm.research.intake import qualify_intake
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.profiles import EvaluationProfiles
    from jiuwenswarm.research.state import json_bytes
    from jiuwenswarm.research.uploads import UploadManager
    store, old_owner, protected, uploads, inputs, _, _ = await visible_run(
        tmp_path, ambient_ref=ambient_member)
    actor = Principal('owner', frozenset({'work'}), frozenset({'upload', 'ingest', 'submit', 'status'}))
    binding = store.read_record(old_owner.binding_ref)
    policy = store.read_record(binding['qualification_policy_ref'])
    policy['id'] += ':opaque-archive'
    if limits:
        policy['limits'].update(limits)
    case = policy['cases'][0]
    if ambient_member:
        brief = __import__('json').loads(next(store.read_upload(row['id'], 'owner') for row in uploads if row['filename']=='brief.json'))
        member = store.read_blob(brief['context_refs'][0])
    else:
        member = b'visible archive source'
    manager = UploadManager(store, store.input_root, None, extraction_timeout_s=10, max_upload_bytes=1048576)
    originals = []
    for index in range(count):
        raw = archive_bytes((('nested/member'+str(index)+'.txt', member),), compression=zipfile.ZIP_DEFLATED)
        kind = 'datasets' if malformed_dataset else 'repo'
        if malformed_dataset:
            raw = b'PK\x03\x04malformed original ZIP lacks central directory'
        filename = 'opaque' + str(index) + '.zip'
        uploaded = await manager.upload(actor, kind, 'work', filename, raw)
        uploads.append(uploaded)
        ref = {'id':'opaque-original:'+str(index),'sha256':hashlib.sha256(raw).hexdigest()}
        case['uploads'].append({'filename':filename,'kind':kind,'role':'visible_support',
            'contract_id':None,'artifact_ref':ref,'source':'original'})
        originals.append((uploaded,ref,raw,member))
    if cumulative_budget:
        actual_inflated = count * len(member)
        policy['limits'][cumulative_budget] = (actual_inflated - 1 if cumulative_budget == 'max_archive_uncompressed_bytes'
            else sum(row['size_bytes'] for row in uploads) + actual_inflated - 1)
    old_run = store.get_run('run:finite-visible')
    old_intake = store.read_record(old_run['submission']['intake_ref'])
    request = store.read_blob(old_intake['request_ref']).decode()
    intake_ref = qualify_intake(store,actor,request,[row['id'] for row in uploads],workspace_id='work',
        **{key:protected[key] for key in ('profile_ref','workspace_ref','input_directory_ref')})
    binding['id'] += ':opaque-archive'
    binding['qualification_policy_ref'] = store.append_record('finite-e1-qualification-policy',policy)
    protected = copy.deepcopy(protected)
    protected['finite_e1_binding_ref'] = store.append_record('finite-e1-binding',binding)
    submission = copy.deepcopy(old_run['submission'])
    submission.update(id='submission:opaque-archive',client_request_id='opaque-archive-1',intake_ref=intake_ref)
    run_id = 'run:opaque-archive'
    store.create_run(run_id,account_id='owner',workspace_id='work',submission=submission)
    operator = OperatorConfiguration.from_mapping(old_owner._operator,resolve_profile=store.read_record)
    EvaluationProfiles(store,operator).bind_run(run_id,submission,protected,principal=actor)
    owner = FiniteE1(store,operator,binding_ref=protected['finite_e1_binding_ref'],
        configuration_ref=binding['configuration_ref'],library=old_owner.library)
    return store,owner,protected,run_id,originals


def assert_no_effects(store):
    assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit','model-call','dispatch-start')))
    assert store.connection.execute('SELECT COUNT(*) FROM acceptance').fetchone()[0] == 0


@pytest.mark.asyncio
async def test_whole_owned_archive_qualifies_with_exact_original_and_no_member_alias(tmp_path):
    store,owner,protected,run_id,originals = await owned_archive_case(tmp_path)
    try:
        uploaded,ref,raw,member = originals[0]
        before = store.connection.execute('SELECT COUNT(*) FROM artifacts WHERE sha256=?',
            (hashlib.sha256(member).hexdigest(),)).fetchone()[0]
        receipt = store.read_record(owner.qualify(run_id,protected))
        assert receipt['status'] == 'qualified',receipt['reason']
        assert ref in receipt['visible_refs'] and store.read_blob(ref) == raw
        assert all(item['sha256'] != hashlib.sha256(member).hexdigest() for item in receipt['visible_refs'])
        assert store.connection.execute('SELECT COUNT(*) FROM artifacts WHERE sha256=?',
            (hashlib.sha256(member).hexdigest(),)).fetchone()[0] == before
        from jiuwenswarm.research import finite_archive
        from pathlib import Path
        assert Path(finite_archive.__file__).read_bytes() in [store.read_blob(item) for item in receipt['results'][-1]['evidence_refs']]
        owner.plan_context(run_id,protected)
        assert_no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_owned_dataset_claimed_zip_must_not_bypass_archive_validation(tmp_path):
    store,owner,protected,run_id,_ = await owned_archive_case(tmp_path,malformed_dataset=True)
    try:
        receipt = store.read_record(owner.qualify(run_id,protected))
        assert receipt['status'] == 'rejected' and receipt['reason'] == 'finite_fixture'
        assert_no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_two_archives_share_cumulative_member_budget(tmp_path):
    store,owner,protected,run_id,_ = await owned_archive_case(tmp_path,count=2,limits={'max_archive_members':1})
    try:
        receipt = store.read_record(owner.qualify(run_id,protected))
        assert receipt['status'] == 'rejected' and receipt['reason'] == 'finite_fixture'
        assert_no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('budget', ['max_archive_uncompressed_bytes', 'max_total_bytes'], ids=['inflated', 'all-bytes'])
async def test_two_original_archives_share_cumulative_inflated_budgets(tmp_path,budget):
    store,owner,protected,run_id,_ = await owned_archive_case(tmp_path,count=2,cumulative_budget=budget)
    try:
        receipt = store.read_record(owner.qualify(run_id,protected))
        assert receipt['status'] == 'rejected' and receipt['reason'] == 'finite_fixture'
        assert_no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_member_bytes_and_ambient_ref_do_not_become_visible_closure(tmp_path):
    store,owner,protected,run_id,_ = await owned_archive_case(tmp_path,ambient_member=True)
    try:
        receipt = store.read_record(owner.qualify(run_id,protected))
        assert receipt['status'] == 'rejected' and receipt['reason'] == 'finite_fixture'
        assert receipt['results'][1]['outcome'] == 'PASS'
        assert receipt['results'][2]['outcome'] == 'FAIL'
        assert_no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['deleted','changed'])
async def test_qualified_archive_rechecks_original_live_custody(tmp_path,fault):
    store,owner,protected,run_id,originals = await owned_archive_case(tmp_path)
    try:
        receipt = store.read_record(owner.qualify(run_id,protected))
        assert receipt['status'] == 'qualified'
        uploaded,ref,raw,_ = originals[0]
        if fault == 'deleted':
            store.delete_upload(uploaded['id'],'owner')
        else:
            path = store.input_root/'repo'/'work'/uploaded['filename']
            path.write_bytes(raw+b'changed after qualification')
        with pytest.raises(ResearchError):
            owner.plan_context(run_id,protected)
        assert store.read_blob(ref) == raw
        assert_no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_archive_qualification_reuses_exact_bytes_but_rejects_changed_helper_evidence(tmp_path,monkeypatch):
    from pathlib import Path
    from jiuwenswarm.research import finite_archive
    store,owner,protected,run_id,_ = await owned_archive_case(tmp_path)
    try:
        receipt = store.read_record(owner.qualify(run_id,protected))
        assert receipt['status'] == 'qualified'
        def repeat_validation(*args,**kwargs):
            raise AssertionError('Unchanged exact original validation must not decompress again')
        monkeypatch.setattr(finite_archive,'validate_opaque_zip',repeat_validation)
        owner.plan_context(run_id,protected)
        actual_read = Path.read_bytes
        helper = Path(finite_archive.__file__)
        def changed_helper(path):
            raw = actual_read(path)
            return raw+b'\n# changed helper evidence\n' if path == helper else raw
        monkeypatch.setattr(Path,'read_bytes',changed_helper)
        with pytest.raises(ResearchError) as error:
            owner.plan_context(run_id,protected)
        assert error.value.code == 'finite_fixture'
        assert_no_effects(store)
    finally:
        store.close()
