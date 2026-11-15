"""Read-only SSE replay transports retained events on their recorded clock."""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
import httpx

from jiuwenswarm.software_factory.api import create_router
from jiuwenswarm.software_factory.engine import FactoryService
from jiuwenswarm.software_factory.recordings import RecordingsStore, default_recordings_directory

import test_recordings as fixtures


def frames(raw):
    result = []
    for block in raw.split('\n\n'):
        if not block:
            continue
        values = {}
        for line in block.splitlines():
            key, value = line.split(':', 1)
            values[key] = value[1:] if value.startswith(' ') else value
        result.append(values)
    return result


class RecordedEventStreamTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PortableRecordingsTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for event, seconds in zip(self.fixture.events, (0, 2, 5, 9)):
            event['time'] = f'2026-11-14T01:00:{seconds:02d}+00:00'
        self.fixture.run['updated_at'] = self.fixture.events[-1]['time']
        fixtures.write_json(self.fixture.run_dir / 'run.json', self.fixture.run)
        # Retain unusual but valid JSON spacing to catch silent reserialization.
        self.event_lines = ['  ' + json.dumps(event, ensure_ascii=False,
                                              separators=(', ', ' : ')) + '  '
                            for event in self.fixture.events]
        (self.fixture.run_dir / 'events.jsonl').write_text(
            '\n'.join(self.event_lines) + '\n', encoding='utf-8')
        self.fixture.export()
        service = FactoryService(self.fixture.root / 'empty-live-runs', [])
        self.addCleanup(service.pool.shutdown, wait=True)
        self.service = service
        self.app = FastAPI()
        self.app.include_router(create_router(
            service, lambda request, scope: request.headers.get('x-user'),
            recordings=RecordingsStore(self.fixture.store_dir)))
        self.url = f'/api/v1/factory/recordings/{self.fixture.run_id}/replay'

    def fetch(self, suffix='', user='alice'):
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                         base_url='http://localhost') as client:
                return await client.get(self.url + suffix, headers={'x-user': user})
        return asyncio.run(request())

    def paced_fetch(self, suffix=''):
        delays = []
        real_sleep = asyncio.sleep

        async def advance_recorded_clock(delay):
            if delay > 0:
                delays.append(delay)
            await real_sleep(0)

        with fixtures.no_factory_execution(), patch('jiuwenswarm.software_factory.api.asyncio.sleep',
                                           side_effect=advance_recorded_clock):
            response = self.fetch(suffix)
        return response, delays

    def assert_frames(self, response, events):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['content-type'].startswith('text/event-stream'))
        observed = frames(response.text)
        self.assertEqual(len(observed), len(events))
        self.assertEqual([frame['event'] for frame in observed], ['recorded'] * len(events))
        self.assertEqual([int(frame['id']) for frame in observed], [e['sequence'] for e in events])
        self.assertEqual([json.loads(frame['data']) for frame in observed], events)
        self.assertEqual([frame['data'].encode('utf-8') for frame in observed],
                         [self.event_lines[e['sequence'] - 1].encode('utf-8') for e in events])
        self.assertNotIn('event: snapshot', response.text)
        self.assertNotIn('event: completed', response.text)

    def test_original_event_objects_order_and_nonuniform_timestamp_pacing(self):
        response, delays = self.paced_fetch('?speed=4')
        self.assert_frames(response, self.fixture.events)
        self.assertEqual(delays, [0.5, 0.75, 1.0])
        self.assertEqual(list(self.service.root.glob('*/run.json')), [])

    def test_resume_skips_prefix_and_waits_from_original_previous_timestamp(self):
        response, delays = self.paced_fetch('?after=2&speed=4')
        self.assert_frames(response, self.fixture.events[2:])
        self.assertEqual(delays, [0.75, 1.0])
        ended, delays = self.paced_fetch('?after=4&speed=16')
        self.assertEqual(ended.status_code, 200)
        self.assertEqual(ended.content, b'')
        self.assertEqual(delays, [])

    def test_supported_speed_scales_actual_recorded_intervals(self):
        response, delays = self.paced_fetch('?speed=16')
        self.assert_frames(response, self.fixture.events)
        self.assertEqual(delays, [0.125, 0.1875, 0.25])

    def test_until_stops_at_exact_prefix_and_equal_cursor_is_empty(self):
        response, delays = self.paced_fetch('?after=1&until=3&speed=4')
        self.assert_frames(response, self.fixture.events[1:3])
        self.assertEqual(delays, [0.5, 0.75])
        for cursor in (0, 2, 4):
            response, delays = self.paced_fetch(f'?after={cursor}&until={cursor}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'')
            self.assertEqual(delays, [])

    def test_owner_and_invalid_replay_controls_fail_before_streaming(self):
        with fixtures.no_factory_execution():
            self.assertEqual(self.fetch(user='bob').status_code, 404)
            for suffix in ('?after=-1', '?after=5', '?after=1.5', '?speed=0',
                           '?speed=2', '?speed=17', '?speed=banana',
                           '?until=-1', '?until=1.5', '?until=5', '?after=3&until=2'):
                self.assertEqual(self.fetch(suffix).status_code, 422, suffix)

    def test_disconnect_cancels_recorded_wait_without_emitting_future_events(self):
        async def disconnect_after_first_frame():
            inbound = asyncio.Queue()
            await inbound.put({'type': 'http.request', 'body': b'', 'more_body': False})
            bodies = []

            async def receive():
                return await inbound.get()

            async def send(message):
                if message['type'] == 'http.response.body' and message.get('body'):
                    bodies.append(message['body'])
                    await inbound.put({'type': 'http.disconnect'})

            scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'},
                     'http_version': '1.1', 'method': 'GET', 'scheme': 'http',
                     'path': self.url, 'raw_path': self.url.encode(),
                     'query_string': b'speed=1', 'root_path': '',
                     'headers': [(b'x-user', b'alice')],
                     'client': ('127.0.0.1', 1234), 'server': ('localhost', 80)}
            await asyncio.wait_for(self.app(scope, receive, send), timeout=1)
            return bodies

        with fixtures.no_factory_execution():
            bodies = asyncio.run(disconnect_after_first_frame())
        self.assertEqual(len(bodies), 1)
        observed = frames(bodies[0].decode())
        self.assertEqual(json.loads(observed[0]['data']), self.fixture.events[0])
        self.assertEqual(list(self.service.root.glob('*/run.json')), [])


class ActualRecordedEventStreamTests(unittest.TestCase):
    def test_committed_core_stream_uses_original_event_bytes_with_zero_dispatch(self):
        self.check_committed_core_stream()

    def test_committed_core_bounded_stream_preserves_exact_events_10_through_20(self):
        self.check_committed_core_stream(after=9, until=20)

    def check_committed_core_stream(self, after=0, until=None):
        directory = default_recordings_directory()
        if not (directory / 'core.zip').is_file():
            self.skipTest('Committed core recording bundle is not present')
        store = RecordingsStore(directory)
        run_id = '6db7a2b968c8434eaa9a508a6d16a7cf'
        delays = []
        real_sleep = asyncio.sleep
        real_read = Path.read_bytes

        async def recorded_wait(delay):
            if delay > 0:
                delays.append(delay)
            await real_sleep(0)

        def reject_original_reads(path):
            if path.is_relative_to(Path('/workspace/factory-runs')):
                raise AssertionError('SSE replay consulted original run files')
            return real_read(path)

        async def replay(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url='http://localhost') as client:
                query = f'?speed=16&after={after}'
                if until is not None:
                    query += f'&until={until}'
                return await client.get(f'/api/v1/factory/recordings/{run_id}/replay{query}',
                                        headers={'x-user': 'local-operator'})

        with tempfile.TemporaryDirectory() as root, fixtures.no_factory_execution(), \
                patch.object(Path, 'read_bytes', reject_original_reads), \
                patch('jiuwenswarm.software_factory.api.asyncio.sleep', side_effect=recorded_wait):
            view = store.get(run_id, 'local-operator')
            original_lines = store.evidence(run_id, 'events.jsonl', 'local-operator').splitlines()
            service = FactoryService(root, [])
            self.addCleanup(service.pool.shutdown, wait=True)
            app = FastAPI()
            app.include_router(create_router(service, lambda request, action: request.headers.get('x-user'),
                                             recordings=store))
            response = asyncio.run(replay(app))
            self.assertEqual(list(service.root.glob('*/run.json')), [])
        self.assertEqual(response.status_code, 200)
        observed = frames(response.text)
        self.assertEqual([frame['data'].encode() for frame in observed], original_lines[after:until])
        self.assertEqual([json.loads(frame['data']) for frame in observed], view['events'][after:until])
        self.assertEqual([int(frame['id']) for frame in observed],
                         [event['sequence'] for event in view['events'][after:until]])
        times = [datetime.fromisoformat(event['time']) for event in view['events']]
        times = times[max(after - 1, 0):until]
        expected_delays = [(current - previous).total_seconds() / 16
                           for previous, current in zip(times, times[1:]) if current > previous]
        self.assertEqual(delays, expected_delays)


if __name__ == '__main__':
    unittest.main()
