"""Finite relay boundary tests. No SSH, inference, or service mutations."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('rsi_spark', Path(__file__).parents[3] / 'deploy/m1/rsi_spark.py')
spark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spark)
TARGET = 'operator@spark.example'


class SparkTests(unittest.TestCase):
    def test_fixed_destination_and_strict_ssh(self):
        self.assertEqual(spark.ssh_command(spark.profile(TARGET)), [spark.SSH, '-T', '-o', 'BatchMode=yes', '-o',
            'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=12', '-W', '127.0.0.1:8000',
            TARGET])
        self.assertEqual(spark.profile(TARGET)['model'], 'Qwen3.8-27B-NVFP4')
        with self.assertRaises(SystemExit):
            spark.main(['serve', '--host', 'attacker'])

    def test_environment_keeps_interop_drops_credentials(self):
        with patch.dict(os.environ, {'WSL_INTEROP': '/run/WSL/interop', 'PATH': '/bin',
                                    'OPENAI_API_KEY': 'secret', 'SSH_AUTH_SOCK': 'private'}, clear=True):
            self.assertEqual(spark.ssh_environment(), {'WSL_INTEROP': '/run/WSL/interop', 'PATH': '/bin'})

    def test_peer_uid_is_finite(self):
        connection = Mock()
        for uid, allowed in [(0, True), (12001, True), (1000, False), (13000, False)]:
            connection.getsockopt.return_value = struct.pack('3i', 123, uid, 13000)
            self.assertEqual(spark.peer_allowed(connection), allowed)

    def test_rejected_peer_never_starts_ssh(self):
        connection, slots = Mock(), Mock()
        with patch.object(spark, 'peer_allowed', return_value=False), patch.object(spark.subprocess, 'Popen') as popen:
            spark.relay(connection, slots, spark.profile(TARGET))
            popen.assert_not_called()
        connection.close.assert_called_once()
        slots.release.assert_called_once()

    def test_prepare_refuses_existing_objects_before_writes(self):
        with patch.object(spark, 'require_root'), patch.object(spark.os.path, 'lexists', return_value=True), \
                patch.object(spark, 'write_new') as write:
            with self.assertRaisesRegex(ValueError, 'fresh'):
                spark.prepare(TARGET)
            write.assert_not_called()

    def test_profile_tampering_refused(self):
        with patch.object(spark, 'require_root'), patch.object(spark, 'checked'), \
                patch.object(Path, 'read_bytes', return_value=json.dumps({**spark.profile(TARGET), 'remote': 'evil:80'}).encode()):
            with self.assertRaisesRegex(ValueError, 'finite'):
                spark.load_profile()

    def test_stale_attestation_refused_before_probe(self):
        value = spark.profile(TARGET, 'a' * 32)
        attestation = {**spark.public_profile(value), 'pid': 123, 'start_ticks': '12', 'socket_inode': 4}
        with patch.object(spark, 'load_profile', return_value=value), patch.object(spark, 'checked', return_value=Mock(st_ino=5)), \
                patch.object(Path, 'read_bytes', return_value=json.dumps(attestation).encode()), \
                patch.object(spark, 'read_endpoint') as read:
            with self.assertRaisesRegex(ValueError, 'Stale'):
                spark.status()
            read.assert_not_called()

    def test_status_only_reads_metadata_and_refuses_model_drift(self):
        value = spark.profile(TARGET, 'a' * 32)
        attestation = {**spark.public_profile(value), 'pid': 123, 'start_ticks': '12', 'socket_inode': 4}
        with patch.object(spark, 'load_profile', return_value=value), patch.object(spark, 'checked', return_value=Mock(st_ino=4)), \
                patch.object(Path, 'read_bytes', return_value=json.dumps(attestation).encode()), \
                patch.object(spark, 'start_ticks', return_value='12'), \
                patch.object(spark, 'read_endpoint', side_effect=[None, {'data': [{'id': 'other'}]}]) as read:
            with self.assertRaisesRegex(ValueError, 'Served model differs'):
                spark.status()
            self.assertEqual([call.args for call in read.call_args_list], [('/health', 123), ('/v1/models', 123)])

    def test_public_projection_has_epoch_boot_and_no_ssh_identity(self):
        value = spark.profile(TARGET, 'a' * 32)
        public = spark.public_profile(value)
        self.assertEqual(public['source_epoch'], 'a' * 32)
        self.assertEqual(public['boot_id'], spark.boot_id())
        self.assertNotIn('ssh_user_host', public)
        self.assertEqual(set(value) - set(public), {'ssh_user_host'})

    def test_public_profile_drift_refused(self):
        value = spark.profile(TARGET, 'a' * 32)
        with patch.object(spark, 'require_root'), patch.object(spark, 'checked'), \
                patch.object(Path, 'read_bytes', side_effect=[json.dumps(value).encode(), b'{}']):
            with self.assertRaisesRegex(ValueError, 'Public Spark profile differs'):
                spark.load_profile()

    def test_public_atomic_publish_custody_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            spark.write_new(path, {'test': 'public'}, spark.GID, 0o640)
            self.assertEqual(json.loads(path.read_bytes()), {'test': 'public'})
            self.assertEqual((path.stat().st_uid, path.stat().st_gid, path.stat().st_mode & 0o777),
                             (0, spark.GID, 0o640))
            with self.assertRaises(FileExistsError):
                spark.write_new(path, {'test': 'replacement'}, spark.GID, 0o640)
            self.assertEqual(json.loads(path.read_bytes()), {'test': 'public'})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_probe_protocol_error_does_not_log_stream(self):
        output = io.StringIO()
        with patch.object(spark, 'status', side_effect=spark.http.client.BadStatusLine('private-stream-data')), \
                contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit):
                spark.main(['status'])
        self.assertNotIn('private-stream-data', output.getvalue())

    def test_operator_target_is_pinned_without_runtime_overrides(self):
        for target in ['operator@spark.example', 'user@192.0.2.10', 'user@2001:db8::1']:
            self.assertEqual(spark.ssh_command(spark.profile(target))[-1], target)
        for target in ['-oProxyCommand=evil', 'user@host\nanything', 'user@host;id', 'user@-option',
                       'user name@host', 'user@host/path', 'user@host@other', 'user@fe80::1%scope', '', None]:
            with self.assertRaises(ValueError):
                spark.validate_target(target)
        for operation in ['serve', 'status']:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                spark.main([operation, '--ssh-target', 'other@host.example'])

    def test_existing_closed_private_profile_with_operator_target_loads(self):
        value = spark.profile(TARGET, 'a' * 32)
        with patch.object(spark, 'require_root'), patch.object(spark, 'checked'), \
                patch.object(Path, 'read_bytes', side_effect=[json.dumps(value).encode(),
                    json.dumps(spark.public_profile(value)).encode()]):
            self.assertEqual(spark.load_profile(), value)

    def pump_process(self, code, seconds=2, byte_limit=1024 * 1024):
        client, relay = socket.socketpair()
        process = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        errors = []
        def run():
            try:
                spark.pump(relay, process, seconds, byte_limit)
            except BaseException as error:
                errors.append(error)
            finally:
                relay.close()
        thread = threading.Thread(target=run)
        thread.start()
        self.addCleanup(client.close)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.wait()
            for stream in [process.stdin, process.stdout]:
                if not stream.closed:
                    stream.close()
            thread.join(timeout=3)
        self.addCleanup(cleanup)
        return client, thread, errors

    def test_binary_duplex_and_half_close(self):
        client, thread, errors = self.pump_process('import sys; d=sys.stdin.buffer.read(); sys.stdout.buffer.write(d[::-1]); sys.stdout.buffer.flush()')
        payload = bytes(range(256)) * 512
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        result = bytearray()
        client.settimeout(3)
        while True:
            block = client.recv(65536)
            if not block:
                break
            result.extend(block)
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(bytes(result), payload[::-1])

    def test_stalled_stream_deadline(self):
        client, thread, errors = self.pump_process('import time; time.sleep(5)', seconds=0.15)
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])

    def test_output_flood_is_bounded(self):
        client, thread, errors = self.pump_process('import os; os.write(1, b"x" * 65536)', byte_limit=1024)
        client.settimeout(3)
        result = bytearray()
        while True:
            block = client.recv(65536)
            if not block:
                break
            result.extend(block)
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertLessEqual(len(result), 1024)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
