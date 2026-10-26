"""Closed cache-study observations; counts never imply elapsed-time speedup."""
from __future__ import annotations
import ast
import hashlib
import io
import stat
import zipfile
from collections import OrderedDict
from .contracts import ResearchError
from .trusted_scoring import _json
from .checks.research import BUNDLE_FILES, CheckError, _python_check
from .environment import parse_requirements

PROTOCOL = 'ai4r-cache-study:1'
OUTPUT_PROTOCOL = 'ai4r-cache-observations:1'
MAX_BYTES = 1048576


def require(ok, message):
    if not ok:
        raise ResearchError('cache_protocol', message)


def parse_cache_dataset(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'Cache public bytes exceed bound')
    value = _json(raw)
    require(type(value) is dict and set(value) == {'capacity_entries','replacement','traces','units','source_id'}, 'Closed cache input fields required')
    require(type(value['capacity_entries']) is int and 1 <= value['capacity_entries'] <= 100000 and value['replacement'] == 'LRU', 'Bounded LRU capacity required')
    require(type(value['source_id']) is str and 0 < len(value['source_id']) <= 128 and '\0' not in value['source_id'], 'Cache source identity required')
    require(value['units'] == {'hits':'requests','misses':'requests','miss_ratio':'fraction'}, 'Cache units differ')
    traces = value['traces']
    require(type(traces) is dict and 1 <= len(traces) <= 1000, 'Bounded named traces required')
    total = 0
    for name, trace in traces.items():
        require(type(name) is str and 0 < len(name) <= 128 and '\0' not in name and type(trace) is list and len(trace)>0, 'Invalid trace')
        require(all(type(key) is str and 0 < len(key) <= 256 and '\0' not in key for key in trace), 'Request keys must be bounded strings')
        total += len(trace)
    require(total <= 100000, 'Trace request bound exceeded')
    return value


def recompute_cache_results(public):
    result = {}
    for name, trace in public['traces'].items():
        cache, seen, hits = OrderedDict(), set(), 0
        for key in trace:
            if key in cache:
                hits += 1
                cache.move_to_end(key)
            else:
                cache[key] = None
                if len(cache) > public['capacity_entries']:
                    cache.popitem(last=False)
            seen.add(key)
        result[name] = {'hits':hits, 'misses':len(trace)-hits, 'unbounded_misses':len(seen)}
    return result


def parse_cache_output(raw, public, *, max_stdout_bytes=MAX_BYTES):
    require(type(raw) is bytes and 0 < len(raw) <= max_stdout_bytes, 'Cache stdout bound exceeded')
    value = _json(raw)
    require(type(value) is dict and set(value) == {'source_id','unit','results'} and value['source_id'] == public['source_id'] and value['unit'] == 'requests', 'Cache stdout identity or units differ')
    expected = recompute_cache_results(public)
    require(type(value['results']) is dict and set(value['results']) == set(expected), 'Every public trace must appear exactly once')
    for name, counts in value['results'].items():
        require(type(counts) is dict and set(counts)=={'hits','misses','unbounded_misses'} and all(type(n) is int and n >= 0 for n in counts.values()), 'Cache observations must be integer counts')
        require(counts == expected[name], 'Cache observations disagree with independent recomputation')
    return value


def inspect_cache_bundle(bundle, pins):
    if type(bundle) is not bytes or len(bundle)>MAX_BYTES:
        raise CheckError('archive_size')
    try:
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            entries = archive.infolist()
            if len(entries)!=3 or {e.filename for e in entries} != BUNDLE_FILES or any(e.flag_bits&1 or stat.S_ISLNK(e.external_attr>>16) or e.is_dir() for e in entries):
                raise CheckError('archive_members')
            if sum(e.file_size for e in entries)>MAX_BYTES:
                raise CheckError('archive_size')
            files = {e.filename:archive.read(e) for e in entries}
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise CheckError('archive_valid') from exc
    deps = parse_requirements(files['requirements.txt'])
    if len(deps)>50 or any(pins.get(k)!=v for k,v in deps.items()):
        raise CheckError('dependencies_match_lock')
    checks = [{'path':'requirements.txt','sha256':hashlib.sha256(files['requirements.txt']).hexdigest(),'syntax_result':'not_applicable','syntax_detail':None,'forbidden_imports':[]}]
    for name in ('poc_patch.py','run_benchmark.py'):
        tree, check = _python_check(name, files[name]); checks.append(check)
        if name == 'run_benchmark.py':
            prints = [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='print']
            valid = [n for n in prints if len(n.args)==1 and not n.keywords and isinstance(n.args[0],ast.Call) and isinstance(n.args[0].func,ast.Attribute) and isinstance(n.args[0].func.value,ast.Name) and n.args[0].func.value.id=='json' and n.args[0].func.attr=='dumps' and len(n.args[0].args)==1]
            # Emitted values may be assembled as a variable; original stdout is
            # validated independently after observed execution by the host.
            if len(prints)!=1 or len(valid)!=1:
                raise CheckError('output_log_format')
    return {'files':files,'file_checks':checks,'dependencies':[{'name':k,'version':v} for k,v in deps.items()],
            'output_format_check':{'result':'pass','json_print_calls':1,'metrics_key_found':False,'missing_metric_ids':[]}}
