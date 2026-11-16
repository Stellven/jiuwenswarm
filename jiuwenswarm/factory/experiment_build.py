"""Attach an existing Builder job to an investigation before lab submission."""
import json
import os
import subprocess
from .builder import Builder
from .execution_binding import file_digest


def ensure_build(loop, cycle):
    if os.environ.get('FACTORY_BRIDGE_DIR'):
        from .bridge import call
        result=call('experiment_build_admit',task_id=loop.task_id,cycle_id=cycle['cycle_id'])
        result.check_returncode()
        payload=json.loads(result.stdout)
        return payload['cycle'],payload['ready']
    builder = Builder(loop.store)
    request = cycle['contract']['specification']['build']
    # Recheck frozen source/dependency/toolchain recipe before first submission.
    key = cycle['idem_key'] + '-build'
    prior = loop.store._db.execute('SELECT attempt_id FROM attempts WHERE task_id=? AND idem_key=?',
                                  (loop.task_id, key)).fetchone()
    if not prior:
        prior = loop.store._db.execute('SELECT attempt_id FROM builder_reuse_keys WHERE task_id=? AND idem_key=?',
                                      (loop.task_id, key)).fetchone()
    if prior:
        attempt = builder.status(prior['attempt_id'])
    else:
        if builder._request(request) != cycle['contract']['build_binding']:
            raise ValueError('Build source or dependencies changed after preparation')
        attempt = builder.submit(loop.task_id, request, key)
    with loop.store._transaction():
        cycle['build_attempt_id'] = attempt['attempt_id']
        loop._write(cycle, 'build_reconciled')
    if attempt['state'] not in {'succeeded','failed','cancelled'}:
        return dict(cycle, build_state=attempt['state']), False
    # Build receipts, not caller-supplied success or image tags, select the image.
    receipt_id = attempt['attempt_id'] + ':receipt'
    if attempt['state'] != 'succeeded':
        with loop.store._transaction():
            evidence = 'loop-build-failed:' + str(cycle['number'])
            from .store import NotFound
            try: loop.store.read(loop.task_id,evidence)
            except NotFound:
                loop.store._insert('observations',dict(task_id=loop.task_id,obs_id=evidence,kind='factory_loop_result',
                    values=dict(status='failed',build_attempt_id=attempt['attempt_id']),
                    source_artifacts=[],error={},host_run={},confidence=None,
                    limitations='Build failed; no lab execution or promotion.',created=loop.clock()))
            loop._finish_branch(cycle,evidence)
            cycle.update(state='collected',evidence_id=evidence,result=dict(state='failed',build_attempt_id=attempt['attempt_id']),ended=loop.clock())
            loop._write(cycle,'build_failed')
        return cycle, False
    artifact = loop.store.read(loop.task_id,receipt_id)
    path = loop.store.home/artifact['location']
    if file_digest(path)!=artifact['sha256']:
        raise ValueError('Build receipt changed')
    receipt=json.loads(path.read_text())
    image=receipt['image_id']
    from .manager import Manager
    admission=Manager(loop.store, loop.store.home/'lab-spool').admit(loop.task_id,dict(tag=request['tag'],id=image),attempt['attempt_id'])
    build_record=json.loads(loop.store.artifact_bytes(loop.task_id,receipt['build_record']['artifact_id']))
    binary='/opt/strata/'+request.get('build_target','strata-dsv41')
    checksum=subprocess.check_output(['docker','run','--rm','--pull=never','--network=none','--read-only',
        '--cap-drop=ALL','--security-opt=no-new-privileges','--entrypoint','sha256sum',image,binary],text=True,timeout=30).split()[0]
    if checksum != build_record['executable_sha256']:
        raise ValueError('Built executable differs from build receipt')
    inspected=json.loads(subprocess.check_output(['docker','image','inspect',image],text=True,timeout=30))[0]
    from .targets import validate_image
    validate_image('spark-gb10',inspected)
    if inspected['Id']!=image or inspected['Config']['Labels'].get('factory.source')!=request['source']['commit']:
        raise ValueError('Built image source identity differs')
    with loop.store._transaction():
        cycle['contract']['image']=image
        cycle['build_receipt_sha256']=artifact['sha256']
        cycle['build_admission_id']=admission['admission_id']
        loop._write(cycle,'build_admitted')
    return cycle, True
