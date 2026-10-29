"""Private record indexes must not depend on a launcher's ambient umask."""
import os
import stat
import pytest

from jiuwenswarm.research_rsi.records import RecordStore


@pytest.mark.parametrize('mode',[0o600,0o640])
def test_private_sqlite_index_wal_and_shm_remain_private_under_standard_umask(tmp_path,mode):
    if os.name!='posix':return
    prior=os.umask(0o022)
    try:
        store=RecordStore(tmp_path/'records',file_mode=mode)
        try:
            store.put({'unit':'private record, not operational evidence'})
            for name in ('index.sqlite','index.sqlite-wal','index.sqlite-shm'):
                path=store.root/name
                if path.exists():assert stat.S_IMODE(path.stat().st_mode)==mode,name
        finally:store.close()
    finally:os.umask(prior)
