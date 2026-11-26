"""Host configuration; environment overrides retain the campaign defaults."""
import os
from pathlib import Path


def path(key, default):
    return Path(os.environ.get(key, default)).expanduser()


# The lab kit holds the host-side lab tools the factory drives: the job queue (bin/jobq), the
# A/B runner and gate (cc/abrun), the image builder (cc/build_engine), the guarded engine run
# (cc/om_run) and the default Jetson recipe (builds/). A copy ships in this package. Point
# FACTORY_LAB_ROOT at any checkout with the same layout to use another one (SIMINFENG_ROOT is
# still read for older hosts). Writable lab state lives under FACTORY_LAB_STATE, never in the kit.
BUNDLED_LAB = Path(__file__).resolve().parent / 'labkit'


def _lab_root():
    for key in ('FACTORY_LAB_ROOT', 'SIMINFENG_ROOT'):
        if os.environ.get(key):
            return path(key, '')
    return BUNDLED_LAB


LAB_ROOT = _lab_root()
SIMINFENG_ROOT = LAB_ROOT  # older name, kept for callers outside this package
LAB_STATE = path('FACTORY_LAB_STATE', '~/.jiuwenswarm-factory/lab')
JOBQ_BIN = path('FACTORY_JOBQ_BIN', LAB_ROOT / 'bin/jobq')
ENGINE = path('FACTORY_BUILD_ENGINE', LAB_ROOT / 'cc/build_engine/build_engine.py')
RECIPE = path('FACTORY_BUILD_RECIPE', LAB_ROOT / 'builds/llamacpp-jetson/Dockerfile')
OM_RUN = str(path('FACTORY_OM_RUN', LAB_ROOT / 'cc/om_run/om_run.sh'))
ABRUN = path('FACTORY_ABRUN', LAB_ROOT / 'cc/abrun/abrun.py')
AB_GATE = LAB_ROOT / 'cc/abrun/gate.py'
PROBE = path('FACTORY_PROBE_MODEL', Path.home() / 'models/campaign/gguf/granite-3.1-1b-a400m-instruct-Q8_0.gguf')
# Jetson reference build receipts are site records, not code: they come from the lab root.
BASELINE_RECORD = path('FACTORY_BASELINE_RECORD', LAB_ROOT / 'cc/build_engine/results/jetson-up1108-om11/build-record.json')
REFERENCE_RECORD = path('FACTORY_REFERENCE_RECORD', LAB_ROOT / 'cc/build_engine/results/jetson-up1108/build-record.json')
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


# External sources. Every checkout, pack, model or run directory the factory reads from outside
# this package is named here, so one environment variable switches it to another copy:
#   FACTORY_LLAMA_SOURCE       clean stock llama.cpp checkout (task build dependency, copy_from)
#   FACTORY_LLAMA_CMAKE_CACHE  CMakeCache.txt of the stock native CUDA build of that checkout
#   FACTORY_MODELS             model root holding the campaign GGUF files
#   FACTORY_STRATA_PACK        Strata DeepSeek pack; its tokenizer/ tables score the ARC benchmark
#   FACTORY_STRATA_SOURCE      Strata engine source tree (tokenizer script, docs, LICENSE);
#                              default <workspace root>/sources/strata-deepseek
#   FACTORY_ONE_SHOT           one_shot.sh-style wrapper used by the capsule parity helpers
#                              (the helpers run standalone, so they read it themselves)
#   FACTORY_OVERLAP_WATCH_RUN  run directory of the capped control allowed to hold the GPU during
#                              an owner-overlap native build (spark_engine); no default, so a busy
#                              GPU refuses the build unless it is set
# Task JSON may name the first group as "${FACTORY_...}" in any string; expand_sources() resolves
# them when a task is loaded, from the environment first and SOURCE_DEFAULTS otherwise.
SOURCE_DEFAULTS = {
    'FACTORY_LLAMA_SOURCE': '~/predemo-spark/llama.cpp-stock',
    'FACTORY_LLAMA_CMAKE_CACHE': '~/predemo-spark/build-stock-cuda121/CMakeCache.txt',
    'FACTORY_MODELS': '~/models',
    'FACTORY_STRATA_PACK': '~/strata-baseline/Strata-data/packs/deepseek-v4.1-flash-ist-das-2.00bpw',
    'FACTORY_ONE_SHOT': '~/predemo/one_shot.sh',
    # Muse demo (Spark): the demo directory, the spike checkouts' parent and the capsule test fixtures
    'FACTORY_MUSE_DEMO': '~/muse-demo',
    'FACTORY_MUSE_SPIKES': '~',
    'FACTORY_MUSE_CAPS': '/tmp/cc-muse-caps',
    'FACTORY_HOME': '~/.jiuwenswarm-factory',
    'FACTORY_REPO': str(Path(__file__).resolve().parents[2]),
}


def source(key):
    """The configured location of one external source (environment first, then the default)."""
    value = os.environ.get(key) or SOURCE_DEFAULTS.get(key)
    if not value:
        raise ValueError(f'Unknown or unset source {key}; set it in the environment')
    return str(Path(value).expanduser())


def expand_sources(value):
    """Replace ${FACTORY_*} references in every string of a task document; unknown names fail."""
    import re
    if isinstance(value, dict):
        return {key: expand_sources(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_sources(item) for item in value]
    if isinstance(value, str):
        return re.sub(r'\$\{(FACTORY_[A-Z0-9_]+)\}', lambda match: source(match.group(1)), value)
    return value
