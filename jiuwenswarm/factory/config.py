"""Host configuration; environment overrides retain the campaign defaults."""
import os
from pathlib import Path


def path(key, default):
    return Path(os.environ.get(key, default)).expanduser()


_HOME_LAB = Path.home() / 'projects/siminfeng'
_SUBMODULE_LAB = Path(__file__).resolve().parents[2] / 'lab/siminfeng'
# Live host lab (shared job queue) first; the pinned submodule is the fallback on a fresh clone.
SIMINFENG_ROOT = path('SIMINFENG_ROOT', _HOME_LAB if _HOME_LAB.is_dir() or not (_SUBMODULE_LAB / 'bin/jobq').exists() else _SUBMODULE_LAB)
JOBQ_BIN = path('FACTORY_JOBQ_BIN', SIMINFENG_ROOT / 'bin/jobq')
ENGINE = path('FACTORY_BUILD_ENGINE', SIMINFENG_ROOT / 'cc/build_engine/build_engine.py')
RECIPE = path('FACTORY_BUILD_RECIPE', SIMINFENG_ROOT / 'builds/llamacpp-jetson/Dockerfile')
OM_RUN = str(path('FACTORY_OM_RUN', SIMINFENG_ROOT / 'cc/om_run/om_run.sh'))
PROBE = path('FACTORY_PROBE_MODEL', Path.home() / 'models/campaign/gguf/granite-3.1-1b-a400m-instruct-Q8_0.gguf')
BASELINE_RECORD = path('FACTORY_BASELINE_RECORD', SIMINFENG_ROOT / 'cc/build_engine/results/jetson-up1108-om11/build-record.json')
BASELINE_IMAGE = os.environ.get('FACTORY_BASELINE_IMAGE', 'campaign/llamacpp:jetson-up1108-om11')
DOCKER_PREFIX = os.environ.get('DOCKER_PREFIX', 'sg docker -c')
MIN_AVAIL_MIB = int(os.environ.get('FACTORY_MIN_AVAIL_MIB', '600'))
BUILD_MIN_AVAIL_MIB = int(os.environ.get('FACTORY_BUILD_MIN_AVAIL_MIB', '8192'))
BUILD_TIMEOUT = int(os.environ.get('FACTORY_BUILD_TIMEOUT', '5400'))
LAB_TIMEOUT = int(os.environ.get('FACTORY_LAB_TIMEOUT', '1800'))
CANCEL_TIMEOUT = float(os.environ.get('FACTORY_CANCEL_TIMEOUT', '60'))
TOOL_TIMEOUT = float(os.environ.get('FACTORY_TOOL_TIMEOUT', '1800'))
INSPECT_TIMEOUT = float(os.environ.get('FACTORY_INSPECT_TIMEOUT', '48'))
DOCKER_TIMEOUT = float(os.environ.get('FACTORY_DOCKER_TIMEOUT', '15'))
UPLOAD_TIMEOUT = float(os.environ.get('FACTORY_UPLOAD_TIMEOUT', '30'))
EXPORT_TIMEOUT = float(os.environ.get('FACTORY_EXPORT_TIMEOUT', '20'))
