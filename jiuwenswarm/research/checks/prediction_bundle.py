"""Versioned archive/static prediction-output checks; never execute generated code."""
import ast
import hashlib
import io
import stat
import zipfile

from .research import BUNDLE_FILES, CheckError, _python_check
from ..environment import parse_requirements
from ..metric_contract import metric_protocol, validate_metric_ids


def inspect_bundle(content, metric_ids, lock_pins, *, output_protocol='ai4r-predictions:1'):
    validate_metric_ids(metric_ids)
    if output_protocol != metric_protocol()['prediction_protocol']:
        raise CheckError('output_log_format')
    if len(content) > 1024 * 1024:
        raise CheckError('archive_size')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) != 3 or {row.filename for row in entries} != BUNDLE_FILES:
                raise CheckError('archive_members')
            if any(row.flag_bits & 1 or stat.S_ISLNK(row.external_attr >> 16) or row.is_dir() for row in entries):
                raise CheckError('archive_members')
            if sum(row.file_size for row in entries) > 1024 * 1024:
                raise CheckError('archive_size')
            files = {row.filename: archive.read(row) for row in entries}
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise CheckError('archive_valid') from error
    dependencies = parse_requirements(files['requirements.txt'])
    if len(dependencies) > 50 or any(lock_pins.get(key) != value for key, value in dependencies.items()):
        raise CheckError('dependencies_match_lock')
    checks = [{'path': 'requirements.txt', 'sha256': hashlib.sha256(files['requirements.txt']).hexdigest(),
               'syntax_result': 'not_applicable', 'syntax_detail': None, 'forbidden_imports': []}]
    for name in ('poc_patch.py', 'run_benchmark.py'):
        tree, checked = _python_check(name, files[name]); checks.append(checked)
        if name != 'run_benchmark.py':
            continue
        prints = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'print']
        matching = [node for node in prints if len(node.args) == 1 and not node.keywords
            and isinstance(node.args[0], ast.Call) and isinstance(node.args[0].func, ast.Attribute)
            and isinstance(node.args[0].func.value, ast.Name) and node.args[0].func.value.id == 'json'
            and node.args[0].func.attr == 'dumps' and len(node.args[0].args) == 1]
        found = any(isinstance(node.args[0].args[0], ast.Dict) and len(node.args[0].args[0].keys) == 1
            and isinstance(node.args[0].args[0].keys[0], ast.Constant)
            and node.args[0].args[0].keys[0].value == 'predictions' for node in matching)
        output = {'result': 'pass' if len(prints) == len(matching) == 1 and found else 'fail',
            'json_print_calls': len(matching), 'output_protocol': output_protocol, 'predictions_key_found': found}
    if output['result'] != 'pass':
        raise CheckError('output_log_format')
    return {'file_checks': checks, 'output_format_check': output, 'files': files,
            'dependencies': [{'name': key, 'version': value} for key, value in dependencies.items()]}
