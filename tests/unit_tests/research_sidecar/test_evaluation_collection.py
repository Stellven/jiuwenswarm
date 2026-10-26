"""GET-only generations retain original submission history, never execute again."""
import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
import httpx
from jiuwenswarm.research_sidecar.evidence import canonical
from jiuwenswarm.research_sidecar.evaluation_collection import collect,GetOnlyTransport


class CollectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        old=self.root/'original';old.mkdir();path=old/'runs'/'one';path.mkdir(parents=True)
        self.row=dict(run_id='one',campaign_id='campaign',case_id='case',case_version='1',config_id='config',repeat_index=1)
        self.request=dict(request_id='request',campaign_id='campaign',case_id='case')
        prior={**self.row,'entry_mode':'single_cc','request_id':'request','launched':False,
            'submitted_at':'2026-10-26T01:00:00Z','started_at':None,'app_run_id':None,
            'app_pins':{'app_build':'original'},'pins_match':True,'limitations':[],
            'outcome':'blocked','exports':[]}
        (path/'run_record.json').write_bytes(canonical(prior));(path/'evaluation-request.json').write_bytes(canonical(self.request))
        db=sqlite3.connect(old/'ledger.sqlite');db.executescript('CREATE TABLE attempts(id TEXT,fingerprint TEXT);CREATE TABLE events(seq INTEGER,id TEXT,kind TEXT,payload TEXT);')
        db.execute('INSERT INTO attempts VALUES (?,?)',('one',hashlib.sha256(canonical({'entry_mode':'single_cc','request':self.request})).hexdigest()))
        db.execute('INSERT INTO events VALUES (?,?,?,?)',(1,'one','evaluation_submitting',json.dumps({'entry_mode':'single_cc','request_id':'request'})))
        db.commit();db.close()
        self.pins={str(p.relative_to(old)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in old.rglob('*') if p.is_file()}
        self.config=dict(schema='evaluation-collection:1',original_root=str(old),new_root=str(self.root/'generation'),
            row=self.row,expected_request=self.request,original_pins=self.pins,base_url='http://app',http_authority=None)
        self.terminal={'status':'completed','reason':None}
        self.client=SimpleNamespace(evaluation_request=AsyncMock(return_value={'request_id':'request','status':'completed',
            'invalid_for_product':True,'result':self.terminal}),evaluation_export_archive=AsyncMock(return_value=b'originalzip'),
            evaluate=AsyncMock(side_effect=AssertionError('POST forbidden')),evaluation_http_captures=[])
        self.frozen=Mock();self.frozen.request={'entry_point':'E3'};self.frozen.entries={'evaluation_export.json':b'original'}
        self.frozen.response.return_value=self.terminal;self.frozen.model_call_rows.return_value=[]
        self.loader=patch('jiuwenswarm.research_sidecar.evaluation_collection.EvaluationRecords.from_archive',return_value=self.frozen)
        self.loader.start()

    def tearDown(self):self.loader.stop();self.temp.cleanup()

    def assert_old_unchanged(self):
        old=Path(self.config['original_root'])
        self.assertEqual({str(p.relative_to(old)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in old.rglob('*') if p.is_file()},self.pins)

    async def test_completed_scoped_get_creates_new_generation_without_submission_or_history_rewrite(self):
        record=await collect(self.config,self.client)
        self.assertTrue(record['launched']);self.assertEqual(record['outcome'],'completed')
        self.assertIsNone(record['started_at']);self.assertIsNone(record['elapsed_s']);self.assertIsNone(record['app_run_id'])
        self.assertEqual(record['app_pins'],{'app_build':'original'})
        self.client.evaluation_request.assert_awaited_once_with('request')
        self.client.evaluation_export_archive.assert_awaited_once_with('request')
        self.client.evaluate.assert_not_awaited();self.frozen.require_complete.assert_called_once()
        history=Path(self.config['new_root'])/'runs/one/source-history/run_record.json'
        self.assertEqual(history.read_bytes(),(Path(self.config['original_root'])/'runs/one/run_record.json').read_bytes())
        self.assert_old_unchanged()

    async def test_record_tamper_and_wrong_expected_request_rejected_before_get(self):
        for changed in ('record','request'):
            with self.subTest(changed=changed):
                config={**self.config,'expected_request':{**self.request,'request_id':'other'}} if changed=='request' else self.config
                path=Path(config['original_root'])/'runs/one/run_record.json';raw=path.read_bytes()
                if changed=='record':path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError):await collect(config,self.client)
                path.write_bytes(raw)
        self.client.evaluation_request.assert_not_awaited();self.assert_old_unchanged()

    async def test_wrong_claim_or_missing_submission_event_rejected(self):
        old=Path(self.config['original_root']);db=sqlite3.connect(old/'ledger.sqlite')
        db.execute('DELETE FROM events');db.commit();db.close()
        pins={**self.pins,'ledger.sqlite':hashlib.sha256((old/'ledger.sqlite').read_bytes()).hexdigest()}
        with self.assertRaises(ValueError):await collect({**self.config,'original_pins':pins},self.client)
        self.client.evaluation_request.assert_not_awaited()

    async def test_committed_submission_in_wal_is_read_without_touching_source_db_or_shm(self):
        old=Path(self.config['original_root']);db=sqlite3.connect(old/'ledger.sqlite')
        try:
            db.execute('PRAGMA journal_mode=WAL');db.execute('DELETE FROM events');db.commit()
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            db.execute('INSERT INTO events VALUES (?,?,?,?)',(2,'one','evaluation_submitting',
                json.dumps({'entry_mode':'single_cc','request_id':'request'})));db.commit()
            before={p.name:p.read_bytes() for p in old.iterdir() if p.is_file()}
            pins={name:digest for name,digest in self.pins.items() if name!='ledger.sqlite'}
            pins.update({name:hashlib.sha256(before[name]).hexdigest() for name in ('ledger.sqlite','ledger.sqlite-wal')})
            result=await collect({**self.config,'original_pins':pins},self.client)
            self.assertEqual(result['outcome'],'completed')
            self.assertEqual({p.name:p.read_bytes() for p in old.iterdir() if p.is_file()},before)
        finally:db.close()

    async def test_incomplete_or_mismatched_original_export_never_publishes_record(self):
        for condition in ('incomplete','different_response','wrong_entry'):
            with self.subTest(condition=condition):
                self.frozen.require_complete.side_effect=ValueError() if condition=='incomplete' else None
                self.frozen.response.return_value={} if condition=='different_response' else self.terminal
                self.frozen.request={'entry_point':'E2' if condition=='wrong_entry' else 'E3'}
                with self.assertRaises(ValueError):await collect(self.config,self.client)
                self.assertFalse(Path(self.config['new_root']).exists())
        self.client.evaluate.assert_not_awaited();self.assert_old_unchanged()

    async def test_get_only_transport_rejects_post_before_underlying_transport(self):
        inner=Mock(spec=httpx.AsyncBaseTransport);inner.handle_async_request=AsyncMock()
        transport=GetOnlyTransport(inner)
        with self.assertRaises(ValueError):await transport.handle_async_request(httpx.Request('POST','http://app/api'))
        inner.handle_async_request.assert_not_awaited()


if __name__=='__main__':unittest.main()
