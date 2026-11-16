import json
import sqlite3
import pytest

from jiuwenswarm.factory.experiment_library import ExperimentLibrary


def database(path, task, objective):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE tasks (task_id TEXT, objective TEXT)')
        db.execute('INSERT INTO tasks VALUES (?,?)', (task, objective))


def test_history_persists_versions_and_restricts_read_scope(tmp_path):
    first, second = tmp_path/'first.sqlite', tmp_path/'second.sqlite'
    database(first, 'a', 'throughput: cpu6 regressed; preserve negative evidence')
    database(second, 'b', 'throughput: source experiment failed')
    root=tmp_path/'library'
    lib=ExperimentLibrary(root,[first,second])
    assert lib.refresh()['total_snapshots']==2
    assert lib.refresh()['added_snapshots']==0
    original=lib.search('cpu6')['matches'][0]
    with sqlite3.connect(first) as db:
        db.execute("UPDATE tasks SET objective='throughput: cpu6 followup inconclusive'")
    assert lib.refresh()['total_snapshots']==3
    restarted=ExperimentLibrary(root,[first])
    matches=restarted.search('throughput',20)['matches']
    assert len(matches)==2 and all(m['task_id']=='a' for m in matches)
    assert 'regressed' in restarted.read(original['id'])['text']
    unadmitted=next(m for m in lib.search('throughput',20)['matches'] if m['task_id']=='b')
    with pytest.raises(ValueError,match='unadmitted'):
        restarted.read(unadmitted['id'])
    with sqlite3.connect(second) as db:
        assert db.execute('SELECT objective FROM tasks').fetchone()[0]=='throughput: source experiment failed'


def test_query_is_not_sql_or_fts_injection(tmp_path):
    source=tmp_path/'source.sqlite';database(source,'a','throughput evidence')
    lib=ExperimentLibrary(tmp_path/'library',[source])
    lib.search('" OR * ; DROP TABLE records --')
    assert lib.refresh()['total_snapshots']==1
    with pytest.raises(ValueError):lib.search('x',1000)
