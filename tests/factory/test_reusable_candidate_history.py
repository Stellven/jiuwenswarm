import json
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.experiment_library import ExperimentLibrary


def test_rejected_candidate_code_and_patch_survive_a_fresh_reader(tmp_path):
    home=tmp_path/'factory'
    commit='a'*40
    with Store(home) as store:
        store.create_task(dict(task_id='prior',objective='Improve decode throughput'))
        patch=store.put_artifact('prior','candidate-patch',b'diff --git a/pool.hpp b/pool.hpp\n+ yield();\n','text/x-diff','source-candidate')
        store.append_observation('prior',dict(obs_id='reusable-candidate',kind='reusable_candidate',
            source_artifacts=[patch['artifact_id']],values=dict(performance_status='target_not_met',
                reuse_status='available_for_optional_followup',source=dict(commit=commit,
                    repository='https://example.test/engine.git',branch='factory/candidate'),
                patch_artifact_id='candidate-patch'),limitations='Historical evidence, no automatic selection or admission.'))
    library=ExperimentLibrary(tmp_path/'library',[home/'factory.sqlite'])
    assert library.refresh()['added_snapshots']>0
    del library
    fresh=ExperimentLibrary(tmp_path/'library',[home/'factory.sqlite'])
    matches=fresh.search(commit,20)['matches']
    candidate=next(row for row in matches if row['record_id']=='reusable-candidate')
    record=json.loads(fresh.read(candidate['id'])['text'])
    assert record['values']['performance_status']=='target_not_met'
    assert record['values']['reuse_status']=='available_for_optional_followup'
    assert record['values']['source']['commit']==commit
    patch_record=next(row for row in fresh.search('candidate-patch',20)['matches'] if row['table']=='artifacts')
    stored=json.loads(fresh.read(patch_record['id'])['text'])
    assert stored['preview_status']=='verified_text' and stored['text_complete']
    assert stored['text'].endswith('+ yield();\n')
