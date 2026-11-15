"""Run inside the factory container; never execute build tools in this process."""
import json,os
from pathlib import Path
from jiuwenswarm.factory.store import Store,NotFound
from jiuwenswarm.factory.builder import Builder
root=Path(os.environ['FACTORY_HOME']).parent
with Store(root/'port-store') as s:
    try:s.get_task('spark-deepseek-port')
    except NotFound:s.create_task(dict(task_id='spark-deepseek-port',objective='Build and validate pinned DeepSeek on GB10',target={'profile':'spark-gb10'},allowed_effects=['process.exec']))
    request=dict(target='spark-gb10',source=dict(path=str(root/'sources/strata-deepseek'),commit='ffa80d73133ea5c548aefe57889a16e8085a938f'),dependency=dict(path=str(root/'sources/strata-ggml'),commit='3cf03257f219afbe7334045ff7c6a06ac68c627d'),tag='factory/strata:cc-dgx-spark-deepseek',deadline_s=5400,env={'PATH':'/home/user2/strata-baseline/Strata/.venv-build/bin:/usr/local/cuda/bin:/usr/bin:/bin','BUILD_JOBS':'8'})
    result=Builder(s).submit('spark-deepseek-port',request,'deepseek-build-001')
    (root/'results/port-build-handle.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
