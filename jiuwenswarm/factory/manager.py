"""Deterministic admission, durable lab submission and evidence upload boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from . import contract as contracts
from .jobs import Jobs
from .lab_runner import ENV_KEYS, collect, inspect_image
from .store import ArtifactConflict, FactoryError, NotFound, Store, encoded

from .config import BASELINE_RECORD, BASELINE_IMAGE, LAB_TIMEOUT, SIMINFENG_ROOT


class AdmissionError(FactoryError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class UploadConflict(FactoryError):
    code = 'UPLOAD_CONFLICT'


class Manager:
    def __init__(self, store, spool_root):
        self.store = store
        self.spool_root = Path(spool_root).resolve()
        self.spool_root.mkdir(parents=True, exist_ok=True)
        self.jobs = Jobs(store)

    def admit(self, task_id, image_ref, build_attempt_id):
        self.store.get_task(task_id)
        if not isinstance(image_ref, dict) or set(image_ref) != {'tag', 'id'}:
            raise ValueError('image requires tag and id')
        if (not isinstance(image_ref['tag'], str) or not image_ref['tag'] or image_ref['tag'].startswith('-')
                or not re.fullmatch(r'sha256:[a-f0-9]{64}', image_ref['id'])):
            raise ValueError('Invalid image tag or immutable Id')
        build = self.store._get('attempts', task_id, build_attempt_id)
        if build['kind'] != 'build':
            raise ValueError('build_attempt_id must name a build')
        # Reconcile the durable build lifecycle before accepting its receipt.
        if build['jobq_id'] or build['state'] != 'succeeded':
            build = self.jobs.status(build_attempt_id)
        if build['state'] != 'succeeded':
            raise ValueError('Admission requires a successful build attempt')
        receipt = json.loads(self.store.artifact_bytes(task_id, build_attempt_id + ':receipt'))
        row = inspect_image(image_ref['tag'])
        if row['Id'] != receipt.get('image_id') or row['Id'] != image_ref['id']:
            raise AdmissionError('BAD_DIGEST', 'Local image Id differs from build receipt or requested Id')
        if row.get('Architecture') != 'arm64' or (row.get('Config', {}).get('Labels') or {}).get('campaign.target.profile') != 'jetson-orin':
            raise AdmissionError('WRONG_TARGET', 'Image requires arm64 and campaign.target.profile=jetson-orin')
        admission = dict(task_id=task_id, image=dict(image_ref), build_attempt_id=build_attempt_id,
            delivery='same_host_local_image', architecture='arm64', target_profile='jetson-orin')
        key = hashlib.sha256(encoded(admission).encode()).hexdigest()
        admission['admission_id'] = 'admission:' + key
        self.store.put_artifact(task_id, admission['admission_id'], encoded(admission).encode(),
                                'application/json', build_attempt_id)
        return admission

    def _admission(self, task_id, admission_id):
        record = json.loads(self.store.artifact_bytes(task_id, admission_id))
        if record['task_id'] != task_id or record['admission_id'] != admission_id:
            raise ValueError('Admission identity differs')
        return record

    def submit_run(self, task_id, admission_id, contract_id, run_config, idem_key, role='candidate', node_id=None):
        # role is set only by the Manager (freeze_reference -> 'reference'); agents cannot pass it.
        if role not in {'candidate', 'reference'}:
            raise ValueError('role must be candidate or reference')
        admission = self._admission(task_id, admission_id)
        contract = contracts.load(contract_id)
        if not isinstance(run_config, dict) or set(run_config) - {'env', 'argv_overrides', 'profile'}:
            raise ValueError('run_config allows env, argv_overrides and profile')
        profile = run_config.get('profile')
        if profile not in (None, 'nsys'):
            raise ValueError('run_config.profile must be nsys when given')
        from .components import environment
        env = environment(contract, run_config.get('env', {}))
        argv = contract['workload']['argv']
        if run_config.get('argv_overrides') not in (None, {}, [], argv):
            raise ValueError('Scored workload argv is fixed; use a version+1 contract for changes')
        config = dict(admission=admission, contract=dict(contract), env=env, argv=argv, role=role)
        if node_id is not None:
            config['node_id'] = node_id
        if profile:
            # A traced run is an explanation, not a measurement; it never feeds a gate.
            config['profile'] = profile
        digest = hashlib.sha256(encoded(config).encode()).hexdigest()
        path = self.spool_root / 'configs' / (digest + '.json')
        if not path.exists():
            contracts.atomic_json(path, config)
        argv = [sys.executable, '-m', 'jiuwenswarm.factory.lab_runner', '--task', task_id,
            '--run', '{attempt_id}', '--admission', admission_id, '--contract', contract['contract_id'],
            '--config', str(path), '--spool', str(self.spool_root)]
        env_extra = dict(FACTORY_HOME=str(self.store.home))
        # Only these explicit executable seams are inherited for offline tests.
        for key in ('FACTORY_DOCKER', 'FACTORY_OM_RUN'):
            if key in os.environ:
                env_extra[key] = os.environ[key]
        return self.jobs.submit(task_id, 'lab', config, idem_key, 'gpu', argv, LAB_TIMEOUT, env_extra)

    def ab_submit(self, task_id, base_image, candidate_image, base_env, candidate_env,
                  rounds, idem_key, component, contract_id=None, node_id=None):
        from .ab import submit
        return submit(self, task_id, base_image, candidate_image, base_env, candidate_env,
                      rounds, idem_key, component, contract_id, node_id=node_id)

    def ab_status(self, attempt_id):
        return self.status(attempt_id)

    def ab_result(self, attempt_id):
        attempt = self.jobs._get(attempt_id)
        root = self.spool_root / attempt_id
        if (root / 'manifest.json').is_file():
            self.ingest_upload(attempt['task_id'], attempt_id, root)
        result = self.result(attempt_id)
        try:
            observation = self.store._get('observations', attempt['task_id'], attempt_id + ':observation')
        except NotFound:
            observation = None
        return dict(result, ab_result=observation['values'] if observation else None)

    def status(self, attempt_id):
        return self.jobs.status(attempt_id)

    def cancel(self, attempt_id):
        attempt = self.jobs.cancel(attempt_id)
        root = self.spool_root / attempt_id
        # jobq can SIGKILL an unresponsive worker. Reap only that run's recorded
        # container too, even if the worker's finally block could not execute.
        for container_path in root.rglob('container.id'):
            from .lab_runner import docker
            cid = container_path.read_text().strip()
            if re.fullmatch(r'[a-f0-9]{12,64}', cid):
                docker(['rm', '-f', cid])
        return attempt

    def result(self, attempt_id):
        result = self.jobs.result(attempt_id)
        attempt = self.jobs._get(attempt_id)
        evaluation = None
        try:
            evaluation = self.store._get('evaluations', attempt['task_id'], attempt_id + ':evaluation')
        except NotFound:
            pass
        if evaluation and 'acceptance' in evaluation.get('inputs', {}):
            evaluation['acceptance'] = evaluation['inputs']['acceptance']
        outcome = evaluation['execution_outcome'] if evaluation else (
            'cancelled' if result['state'] == 'cancelled' else 'upload_pending')
        return dict(result, execution_outcome=outcome, evaluation=evaluation,
                    evidence_refs=attempt['result_refs'])

    def ingest_upload(self, task_id, lab_run_id, bundle_dir):
        """Verify bytes, commit evidence, then acknowledge. Identical retries replay."""
        root = Path(bundle_dir).resolve()
        if root != self.spool_root / lab_run_id or not root.is_dir():
            raise ValueError('Bundle must be the lab run directory in the configured spool')
        attempt = self.store._get('attempts', task_id, lab_run_id)
        if attempt['request'].get('mode') == 'ab':
            from .ab import ingest
            return ingest(self, task_id, lab_run_id, root)
        raw_manifest = (root / 'manifest.json').read_bytes()
        digest = hashlib.sha256(raw_manifest).hexdigest()
        manifest = json.loads(raw_manifest)
        if manifest['task_id'] != task_id or manifest['lab_run_id'] != lab_run_id:
            raise ValueError('Upload task or lab run identity differs')
        with self.jobs.locked():
            attempt = self.store._get('attempts', task_id, lab_run_id)
            if attempt['kind'] != 'lab':
                raise ValueError('Upload requires a lab attempt')
            request = attempt['request']
            if (manifest['admission_id'] != request['admission']['admission_id'] or
                    manifest['contract_id'] != request['contract']['contract_id']):
                raise ValueError('Upload admission or contract identity differs')
            previous = self.store._db.execute('SELECT * FROM uploads WHERE task_id=? AND lab_run_id=?',
                                              (task_id, lab_run_id)).fetchone()
            if previous and previous['sha256'] != digest:
                raise UploadConflict('Lab run already names a different manifest')
            files = manifest['files']
            if not isinstance(files, dict) or 'config.json' not in files or 'worker.json' not in files:
                raise ValueError('Manifest requires config.json and worker.json')
            # Snapshot the verified bytes; concurrent changes cannot enter storage.
            content = {}
            for name, sha in files.items():
                if name in {'manifest.json', 'ack.json'} or Path(name).name != name or name in {'.', '..'}:
                    raise ValueError('Manifest paths must be bundle file basenames')
                path = (root / name).resolve()
                if path.parent != root or not path.is_file():
                    raise ValueError('Manifest path escapes bundle or is missing')
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != sha:
                    if previous:
                        raise UploadConflict('Previously uploaded lab run bytes have changed')
                    raise ValueError('Manifest SHA256 mismatch: ' + name)
                content[name] = data
            config = json.loads(content['config.json'])
            if config != dict(request, lab_run_id=lab_run_id):
                raise ValueError('Bundle configuration differs from submitted run')
            ack = dict(upload_id=lab_run_id + ':upload', sha256=digest, ack_state='durable')
            if not previous:
                # Analyse only a private copy of the hash-verified evidence.
                import tempfile
                with tempfile.TemporaryDirectory(dir=self.spool_root) as directory:
                    for name, data in content.items():
                        (Path(directory) / name).write_bytes(data)
                    run = collect(directory, config)
                evaluation = contracts.evaluate(request['contract'], run)
                refs = []
                for name, data in {'manifest.json': raw_manifest, **content}.items():
                    try:
                        artifact = self.store.put_artifact(task_id, lab_run_id + ':' + name, data,
                            'application/json' if name.endswith('.json') else
                            'application/octet-stream' if name.endswith('.nsys-rep') else 'text/plain', lab_run_id)
                    except ArtifactConflict as exc:
                        raise UploadConflict('Lab run already names different upload bytes') from exc
                    refs.append(artifact['artifact_id'])
                now = time.time()
                # All semantic records and the upload marker commit together.
                with self.store._transaction():
                    obs_id, eval_id = lab_run_id + ':observation', lab_run_id + ':evaluation'
                    self.store._insert('observations', dict(obs_id=obs_id, task_id=task_id,
                        source_artifacts=refs.copy(), kind='lab_result', values=run, error={},
                        host_run=dict(attempt_id=lab_run_id), confidence=None,
                        limitations=request['contract']['scope'], created=now))
                    self.store._insert('evaluations', dict(eval_id=eval_id, task_id=task_id,
                        contract_id=request['contract']['contract_id'], contract_version=str(request['contract']['version']),
                        contract=request['contract'], inputs=dict(run=run, source_artifacts=refs.copy(),
                            observation_id=obs_id, details=evaluation['details']),
                        **{k: evaluation[k] for k in ('execution_outcome', 'correctness', 'evidence_completeness')}, created=now))
                    refs += [obs_id, eval_id]
                    self.store._db.execute('UPDATE attempts SET result_refs=? WHERE task_id=? AND attempt_id=?',
                                           (encoded(refs), task_id, lab_run_id))
                    self.store._insert('uploads', dict(task_id=task_id, lab_run_id=lab_run_id,
                        upload_id=ack['upload_id'], sha256=digest, ack_state='durable', created=now))
            contracts.atomic_json(root / 'ack.json', ack)
            return ack

    def retry_spool(self):
        results = []
        for path in sorted(self.spool_root.glob('*/manifest.json')):
            try:
                manifest = json.loads(path.read_text())
                results.append(self.ingest_upload(manifest['task_id'], manifest['lab_run_id'], path.parent))
            except (FactoryError, OSError, ValueError, KeyError, TypeError) as exc:
                results.append(dict(lab_run_id=path.parent.name, execution_outcome='upload_pending',
                                    error=str(exc)[:200]))
        return results


def freeze_reference(manager, contract_id, image):
    contract = contracts.load(contract_id)
    reference = contracts.reference_info(contract)
    if reference.get('stdout_sha256') is not None:
        raise contracts.ContractFrozen('Contract is frozen; create a version+1 contract file')
    image = image or reference['image_tag']
    if image != reference['image_tag']:
        raise ValueError('Reference image must match the contract image tag')
    # Import the existing baseline build receipt, without invoking a build.
    # It passes the identical admission checks as a newly built candidate.
    record_path = BASELINE_RECORD
    if contract.get('reference') is None:
        record_path = Path(os.environ.get('FACTORY_REFERENCE_RECORD',
            SIMINFENG_ROOT / 'cc/build_engine/results/jetson-up1108/build-record.json'))
    record = json.loads(record_path.read_text())
    if record.get('status', 'success') not in {'success', 'succeeded'} or not record.get('image'):
        raise ValueError('Reference freeze needs a successful bare build record (FACTORY_REFERENCE_RECORD)')
    if reference.get('image_id') is not None and record['image']['Id'] != reference['image_id']:
        raise ValueError('Baseline build receipt differs from contract')
    if contract.get('reference') is None:
        contract['reference_image']['image_id'] = record['image']['Id']
        contracts.atomic_json(contract.path, contract)
    task = 'reference-' + contract['contract_id']
    try:
        manager.store.get_task(task)
    except NotFound:
        manager.store.create_task(dict(task_id=task, objective='Operator reference freeze', target={'profile': 'jetson-orin'}))
    key = 'reference-build-receipt'
    manager.store.put_artifact(task, key + ':receipt', encoded(dict(image_id=record['image']['Id'])).encode(), 'application/json', key)
    try:
        build = manager.store._get('attempts', task, key)
    except NotFound:
        build = manager.store.create_attempt(task, dict(attempt_id=key, kind='build', idem_key=key,
            fingerprint=hashlib.sha256(record_path.read_bytes()).hexdigest(), request=dict(imported_build_record=str(record_path))))
    if build['state'] == 'queued':
        build = manager.store.transition_attempt(task, key, 'running')
    if build['state'] == 'running':
        manager.store.transition_attempt(task, key, 'succeeded')
    # Imported historical builds have no jobq id to reconcile. Validate the raw
    # image and use admit's receipt check with the already observed terminal state.
    admission = manager.admit(task, dict(tag=image, id=record['image']['Id']), build['attempt_id'])
    # Key binds the contract content: an amended (still unfrozen) contract can never reuse an older run.
    ckey = hashlib.sha256(encoded(dict(contract)).encode()).hexdigest()[:12]
    handle = manager.submit_run(task, admission['admission_id'], contract_id, {'env': {}}, 'reference-run-' + ckey, role='reference')
    n = 1
    while handle['state'] in {'failed', 'cancelled', 'unknown'}:
        # A terminal prior attempt stays visible; the operator rerun is a new linked attempt.
        n += 1
        handle = manager.jobs.retry(handle['attempt_id'], f'reference-run-{ckey}-r{n}')
    while True:
        result = manager.result(handle['attempt_id'])
        if result['evaluation']:
            run = result['evaluation']['inputs']['run']
            frozen = contracts.freeze(contract.path, run)
            print(frozen['reference']['stdout_sha256'])
            return
        if result['state'] in {'failed', 'cancelled', 'unknown'}:
            raise ValueError('Reference run did not produce durable successful evidence; inspect result or retry-spool')
        time.sleep(.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['ingest', 'retry-spool', 'freeze-reference'])
    parser.add_argument('--spool', type=Path)
    parser.add_argument('--task')
    parser.add_argument('--run')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--contract', default='qwen36-greedy-v1')
    parser.add_argument('--image')
    args = parser.parse_args()
    with Store(Path(os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory'))) as store:
        manager = Manager(store, args.spool or store.home / 'lab-spool')
        if args.operation == 'ingest':
            print(json.dumps(manager.ingest_upload(args.task, args.run, args.bundle)))
        elif args.operation == 'retry-spool':
            print(json.dumps(manager.retry_spool()))
        else:
            freeze_reference(manager, args.contract, args.image)


if __name__ == '__main__':
    main()
