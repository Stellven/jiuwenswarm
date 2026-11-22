#!/usr/bin/env python3
"""Host-side om_run adapter; never invokes Docker or reads model contents to probe."""
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
if __package__:
    from . import page_cache
else:
    import page_cache


def model_path(modeldir, argv):
    override = os.environ.get('OM_CACHE_MODEL')
    if override:
        return Path(override).expanduser()
    model = None
    for index, arg in enumerate(argv):
        if arg in ('-m', '--model') and index + 1 < len(argv):
            model = argv[index + 1]
        elif arg.startswith(('-m=', '--model=')):
            model = arg.split('=', 1)[1]
    if not model:
        raise ValueError('model argument missing; set OM_CACHE_MODEL to its host path')
    if model.startswith('/om/'):
        return Path(modeldir) / model[4:]
    # Relative paths are relative to the engine working directory, not MODELDIR.
    raise ValueError('model must be under /om/; set OM_CACHE_MODEL to its host path')


def record(phase, out, modeldir, argv):
    protocol = os.environ.get('OM_CACHE_PROTOCOL') or 'carryover'
    result = dict(protocol=protocol, phase=phase, timestamp_ns=time.time_ns())
    rc = 0
    try:
        if protocol not in ('carryover', 'cold', 'warm'):
            raise ValueError(f'unknown OM_CACHE_PROTOCOL: {protocol}')
        path = model_path(modeldir, argv)
        result['path'] = str(path)
        if phase == 'start' and protocol in ('cold', 'warm'):
            # Validate all preparation inputs before evicting anything.
            ranges_file = os.environ.get('OM_CACHE_WARM_RANGES')
            ranges = page_cache.load_ranges(ranges_file) if protocol == 'warm' and ranges_file else None
            prefix = None
            if protocol == 'warm':
                if ranges is not None:
                    page_cache._check_ranges(ranges, path.stat().st_size)
                else:
                    prefix = int(os.environ['OM_CACHE_WARM_BYTES'])
                    if prefix < 0:
                        raise ValueError('OM_CACHE_WARM_BYTES must be nonnegative')
            result['eviction'] = page_cache.evict(path)
            if protocol == 'warm':
                result['warming'] = page_cache.warm(path, ranges, prefix)
                result.update(result['warming']['after'])
            else:
                result.update(result['eviction']['after'])
        else:
            result.update(page_cache.resident(path))
    except (OSError, ValueError, KeyError) as exc:
        result['error'] = str(exc)
        # Recording must not break legacy carryover runs. Preparation must fail closed.
        rc = int(phase == 'start' and protocol != 'carryover')
        print(f'page_cache {phase}: {exc}', file=sys.stderr)
    (Path(out) / f'page_cache.{phase}.json').write_text(json.dumps(result, indent=2) + '\n')
    return rc


if __name__ == '__main__':
    sys.exit(record(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
