"""Bounded user-supplied numeric acceptance cases for actual generated CLIs.

Oracle input is data, never Python, shell code, a command, or a file path. These
checks establish CPU task arithmetic only; they cannot certify model inference
or native-device correctness.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


class OracleError(RuntimeError):
    def __init__(self,code,message,details=None):
        super().__init__(message)
        self.code,self.details = code,details or {}


MAX_CASES = 16
MAX_INPUT_BYTES = 64 * 1024
MAX_TOTAL_INPUT_BYTES = 256 * 1024
MAX_EXPECTED_VALUES = 8192
MAX_EXPECTED_NODES = 16384
MAX_DEPTH = 12
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
NUMERIC = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
OPERATION = re.compile(r'[A-Za-z_][A-Za-z0-9_./:@-]{0,511}\Z')


def _invalid(message):
    raise OracleError('invalid_task_oracle',message)


def _number(value):
    if type(value) not in (int,float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def normalize_oracle(raw):
    if not isinstance(raw,dict) or set(raw) != {'cases'} or not isinstance(raw['cases'],list) or not 1 <= len(raw['cases']) <= MAX_CASES:
        _invalid(f'Oracle requires between one and {MAX_CASES} numeric cases')
    total_bytes = total_values = total_nodes = 0

    def expected(value,depth=0):
        nonlocal total_values,total_nodes
        total_nodes += 1
        if depth > MAX_DEPTH or total_nodes > MAX_EXPECTED_NODES:
            _invalid('Oracle expected structure exceeds its depth or size bound')
        if _number(value):
            total_values += 1
            if total_values > MAX_EXPECTED_VALUES:
                _invalid('Oracle has too many expected numeric values')
            return value
        if isinstance(value,list):
            return [expected(item,depth+1) for item in value]
        if isinstance(value,dict):
            if any(not isinstance(key,str) or not key or len(key)>256 for key in value):
                _invalid('Oracle expected object keys must be bounded nonempty strings')
            return {key:expected(item,depth+1) for key,item in value.items()}
        _invalid('Oracle expected leaves must be finite numbers; Boolean, string and null expectations are unsupported')

    cases = []
    for index,case in enumerate(raw['cases'],1):
        if not isinstance(case,dict) or set(case)-{'input','operation','expected','atol','rtol'}:
            _invalid(f'Oracle case {index} contains undeclared fields')
        text = case.get('input')
        if not isinstance(text,str) or not text.strip() or len(text.encode()) > MAX_INPUT_BYTES:
            _invalid(f'Oracle case {index} requires bounded numeric CLI input')
        total_bytes += len(text.encode())
        if total_bytes > MAX_TOTAL_INPUT_BYTES:
            _invalid('Combined oracle inputs exceed the size bound')
        if re.search(r'[^0-9eE+.\- \t\r\n]',text):
            _invalid('Oracle input accepts numeric CLI text only')
        if any(not NUMERIC.fullmatch(token) or not _number(float(token)) for token in text.split()):
            _invalid('Oracle input contains an invalid or nonfinite numeric token')
        operation = case.get('operation')
        if operation is not None and (not isinstance(operation,str) or not OPERATION.fullmatch(operation)):
            _invalid('Oracle operation must be a bounded discovered function name or source ID')
        if not isinstance(case.get('expected'),dict) or not case['expected']:
            _invalid(f'Oracle case {index} requires a nonempty expected object subset')
        before = total_values
        normalized_expected = expected(case['expected'])
        if total_values == before:
            _invalid(f'Oracle case {index} must contain at least one expected numeric value')
        normalized = {'input':text,'expected':normalized_expected}
        if operation is not None:
            normalized['operation'] = operation
        for name,default in (('atol',1e-5),('rtol',1e-4)):
            tolerance = case.get(name,default)
            if not _number(tolerance) or tolerance < 0:
                _invalid(f'Oracle {name} must be a finite nonnegative number')
            normalized[name] = float(tolerance)
        cases.append(normalized)
    return {'cases':cases}


def compare_expected(actual,expected,atol=1e-5,rtol=1e-4):
    """Compare an expected object subset; arrays have exact shape and order."""
    comparisons = mismatch_count = 0
    maximum = 0.0
    mismatches = []

    def mismatch(path,reason,**values):
        nonlocal mismatch_count
        mismatch_count += 1
        if len(mismatches) < 16:
            mismatches.append({'path':path,'reason':reason,**values})

    def visit(received,wanted,path='$'):
        nonlocal comparisons,maximum
        if isinstance(wanted,dict):
            if not isinstance(received,dict):
                mismatch(path,'expected_object');return
            for key,value in wanted.items():
                if key not in received:
                    mismatch(path+'.'+key,'missing_key')
                else:
                    visit(received[key],value,path+'.'+key)
        elif isinstance(wanted,list):
            if not isinstance(received,list) or len(received) != len(wanted):
                mismatch(path,'array_shape_mismatch',expected_length=len(wanted),actual_length=len(received) if isinstance(received,list) else None)
                return
            for index,(value,reference) in enumerate(zip(received,wanted)):
                visit(value,reference,f'{path}[{index}]')
        elif not _number(wanted) or not _number(received):
            mismatch(path,'nonfinite_or_nonnumeric_value')
        else:
            comparisons += 1
            error = abs(received-wanted)
            if not _number(error):
                mismatch(path,'numeric_difference_overflow');return
            maximum = max(maximum,float(error))
            if error > atol+rtol*abs(wanted):
                mismatch(path,'tolerance_exceeded',expected=wanted,actual=received,abs_error=error)
    visit(actual,expected)
    return {'comparisons':comparisons,'mismatched_values':mismatch_count,
            'max_abs_error':maximum,'mismatches':mismatches}


def _operation_choices(source_dir):
    # Source-generated CLI comparisons contain the exact accepted names and IDs.
    # Decode JSON string literals only; never eval source or execute a parser.
    cli = Path(source_dir)/'src/main.cpp'
    choices = set()
    for encoded in re.findall(r'\boperation\s*==\s*("(?:[^"\\]|\\.)*")',cli.read_text()):
        choices.add(json.loads(encoded))
    return choices


def load_operations(source_dir):
    try:
        project = json.loads((Path(source_dir)/'project.json').read_text())
        operations = project['operations']
    except (KeyError,ValueError,UnicodeDecodeError) as error:
        raise OracleError('operation_coverage_missing','Generated project does not declare every selected source operation') from error
    if (not isinstance(operations,list) or not operations or
        any(not isinstance(record,dict) or any(not isinstance(record.get(key),str) or not record[key]
            for key in ('source_id','name','operation')) for record in operations) or
        len({record['source_id'] for record in operations}) != len(operations)):
        raise OracleError('operation_coverage_missing','Generated operation coverage identities are incomplete or duplicated')
    return operations


def operation_coverage(operations,numerical,oracle_report):
    checks = numerical.get('operation_checks')
    selected = {record['source_id']:record for record in operations}
    if (not isinstance(checks,list) or any(not isinstance(check,dict) for check in checks) or
        {check.get('source_id') for check in checks} != set(selected) or
        len(checks) != len(selected)):
        raise OracleError('operation_coverage_missing','Numerical self-test must account for every exact selected source operation')
    ledger = []
    for check in checks:
        source_id = check['source_id']
        record = selected[source_id]
        count,error,status = check.get('outputs_compared'),check.get('max_abs_error'),check.get('status')
        if (check.get('name') != record['name'] or check.get('operation') != record['operation'] or
            type(count) is not int or count < 0 or not _number(error) or error < 0 or
            status not in {'passed','failed','unverified'} or (status=='passed' and count<=0) or
            (status=='unverified' and count!=0)):
            raise OracleError('operation_coverage_invalid','Self-test coverage is incompatible with its exact selected source operation',{'source_id':source_id})
        cases = [case for case in (oracle_report or {}).get('cases',[]) if case['source_id']==source_id]
        external = sum(case['comparison']['comparisons'] for case in cases)
        failed = status=='failed' or error>1e-5 or any(case['comparison']['mismatched_values'] for case in cases)
        covered = status=='passed' and count>0 or external>0
        ledger.append({'source_id':source_id,'name':record['name'],'operation':record['operation'],
            'built_in_status':status,'built_in_comparisons':count,'oracle_comparisons':external,
            'oracle_cases':[case['case'] for case in cases],
            'status':'failed' if failed else 'passed' if covered else 'unverified'})
    return ledger


def run_oracle_cases(ctx,binary,source_dir,oracle,requirements_sha256):
    normalized = normalize_oracle(oracle)
    choices = _operation_choices(source_dir)
    operations = load_operations(source_dir)
    planned = []
    for index,case in enumerate(normalized['cases'],1):
        requested = case.get('operation')
        candidates = ([record for record in operations if requested in {record['source_id'],record['name']}]
                      if requested is not None else operations if len(operations)==1 else [])
        if len(candidates)!=1 or candidates[0]['source_id'] not in choices:
            raise OracleError('oracle_operation_unknown',
                'Oracle operation must identify one exact discovered function or source ID; multi-operation cases require an explicit operation.',
                {'case':index,'operation':requested,'available':[record['source_id'] for record in operations],
                 'requirements_sha256':requirements_sha256})
        planned.append((case,candidates[0]))
    reports = []
    failures = []
    total = 0
    maximum = 0.0
    for index,(case,operation) in enumerate(planned,1):
        path = ctx.workspace/f'oracle-case-{index}.input'
        path.write_text(case['input'])
        expected_bytes = json.dumps(case['expected'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        receipt = {'case':index,'input_path':str(path),'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'expected':case['expected'],'expected_sha256':hashlib.sha256(expected_bytes).hexdigest(),
            'atol':case['atol'],'rtol':case['rtol'],'requirements_sha256':requirements_sha256,
            'source_id':operation['source_id'],'name':operation['name'],'operation':operation['operation'],
            'requested_operation':case.get('operation')}
        argv = [str(binary),'--input',str(path),'--operation',operation['source_id']]
        receipt['argv'] = argv
        try:
            command = ctx.run_command(argv,timeout=120)
        except RuntimeError as error:
            if not isinstance(getattr(error,'code',None),str) or not isinstance(getattr(error,'details',None),dict):
                raise
            receipt['error'] = {'code':error.code,'message':str(error),'details':error.details}
            if error.details.get('command'):
                receipt.update(stdout_path=error.details['command']['stdout_path'],stderr_path=error.details['command']['stderr_path'])
            failure_path = ctx.write_json(f'oracle-case-{index}.json',receipt)
            failures.append({'case':index,'code':error.code,'receipt_path':str(failure_path)})
            continue
        receipt.update(stdout_path=command['stdout_path'],stderr_path=command['stderr_path'])
        stdout = Path(command['stdout_path'])
        def nonfinite(value):
            raise ValueError('nonfinite JSON number: '+value)
        def finite_float(text):
            value = float(text)
            if not math.isfinite(value):
                raise ValueError('nonfinite JSON float')
            return value
        try:
            if stdout.stat().st_size > MAX_OUTPUT_BYTES:
                raise ValueError('Oracle CLI output exceeds the bounded JSON size')
            actual = json.loads(stdout.read_text(),parse_constant=nonfinite,parse_float=finite_float)
        except (ValueError,UnicodeDecodeError) as error:
            receipt['error'] = str(error)
            failure_path = ctx.write_json(f'oracle-case-{index}.json',receipt)
            failures.append({'case':index,'code':'oracle_output_invalid','receipt_path':str(failure_path)})
            continue
        receipt['actual'] = actual
        comparison = compare_expected(actual,case['expected'],case['atol'],case['rtol'])
        receipt['comparison'] = comparison
        receipt_path = ctx.write_json(f'oracle-case-{index}.json',receipt)
        receipt['receipt_path'] = str(receipt_path)
        receipt['receipt_sha256'] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        reports.append(receipt)
        total += comparison['comparisons']
        maximum = max(maximum,comparison['max_abs_error'])
        if comparison['mismatched_values']:
            failures.append({'case':index,'code':'oracle_numerical_mismatch','receipt_path':str(receipt_path),
                 'receipt_sha256':receipt['receipt_sha256'],**comparison})
    if failures:
        failure_code = 'oracle_numerical_mismatch' if any(failure['code']=='oracle_numerical_mismatch' for failure in failures) else 'oracle_execution_failed'
        raise OracleError(failure_code,'Task acceptance oracle cases failed after executing every provided case',
            {'failures':failures,'cases_executed':len(planned),'requirements_sha256':requirements_sha256,
             'successful_or_compared_cases':reports,'native_device_validated':False,'full_inference_validated':False})
    return {'status':'passed','cases':reports,'comparisons':total,'max_abs_error':maximum,
            'requirements_sha256':requirements_sha256,
            'scope':'User-supplied independent numeric acceptance cases on the generated CPU CLI',
            'native_device_validated':False,'full_inference_validated':False}


def validate_project(ctx,binary,self_test,source_dir,oracle,requirements_sha256):
    """Run the same complete acceptance check in the factory and delivered ZIP."""
    process_failure = None
    try:
        command = ctx.run_command([str(self_test)],timeout=120)
    except RuntimeError as failure:
        details = getattr(failure,'details',{})
        if getattr(failure,'code',None) != 'command_failed' or not details.get('command'):
            raise
        process_failure = failure
        command = details['command']
    # Cases execute even when the independent built-in process failed. An oracle
    # never overrides that failure; the final ledger retains it as a failure.
    try:
        external = run_oracle_cases(ctx,binary,source_dir,oracle,requirements_sha256) if oracle is not None else None
    except OracleError as failure:
        failure.details = {**failure.details,'built_in_stdout_path':command['stdout_path'],
                           'built_in_stderr_path':command['stderr_path']}
        raise
    try:
        numerical = json.loads(Path(command['stdout_path']).read_text().strip().splitlines()[-1])
    except (ValueError,IndexError,UnicodeDecodeError) as error:
        raise OracleError('numerical_output_invalid','Separate numerical test did not emit its actual JSON result',
            {'stdout_path':command['stdout_path'],'stderr_path':command['stderr_path'],'oracle_validation':external}) from error
    coverage = operation_coverage(load_operations(source_dir),numerical,external)
    error = numerical.get('max_abs_error')
    invalid = (not _number(error) or error<0 or error>1e-5 or
               type(numerical.get('outputs_compared')) is not int or numerical['outputs_compared']<0)
    if process_failure is not None or invalid or any(item['status']=='failed' for item in coverage):
        raise OracleError('numerical_mismatch','Generated CPU core failed independent numerical validation',
            {'numerical_result':numerical,'operation_coverage':coverage,'oracle_validation':external,
             'stdout_path':command['stdout_path'],'stderr_path':command['stderr_path']})
    uncovered = [item['source_id'] for item in coverage if item['status']!='passed']
    if uncovered:
        raise OracleError('numerical_oracle_missing',
            'Every selected source operation requires its own independent numerical checks; supply task.oracle cases for uncovered functions.',
            {'built_in_comparisons':numerical['outputs_compared'],'uncovered_operations':uncovered,
             'operation_coverage':coverage,'oracle_validation':external,'requirements_sha256':requirements_sha256,
             'stdout_path':command['stdout_path'],'stderr_path':command['stderr_path'],
             'native_device_validated':False,'full_inference_validated':False})
    count = external['comparisons'] if external else 0
    return {'self_test_command':command,'numerical_result':numerical,'operation_coverage':coverage,
            'oracle_validation':external,'numerical_validation':{'built_in_comparisons':numerical['outputs_compared'],
                'oracle_comparisons':count,'total_comparisons':numerical['outputs_compared']+count}}


def main(argv=None):
    """Standalone, stdlib-only acceptance runner copied verbatim into the ZIP."""
    import argparse
    import subprocess
    import sys
    parser = argparse.ArgumentParser(description='Execute the generated CPU project against its supplied numeric acceptance cases')
    parser.add_argument('--binary',required=True)
    parser.add_argument('--project',required=True)
    parser.add_argument('--oracle',required=True)
    args = parser.parse_args(argv)

    class LocalContext:
        def __init__(self,workspace):
            self.workspace = workspace
            workspace.mkdir(exist_ok=True)
            self.index = 0

        def write_json(self,name,value):
            path = self.workspace/name
            if not path.resolve().is_relative_to(self.workspace.resolve()):
                raise OracleError('invalid_path','Oracle evidence escaped its output directory')
            path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
            return path

        def run_command(self,argv,timeout=120):
            self.index += 1
            stdout,stderr = (self.workspace/f'command-{self.index}.{stream}' for stream in ('stdout','stderr'))
            record = {'argv':argv,'stdout_path':str(stdout),'stderr_path':str(stderr)}
            with stdout.open('wb') as out,stderr.open('wb') as err:
                try:
                    result = subprocess.run(argv,stdout=out,stderr=err,timeout=timeout,check=False)
                except subprocess.TimeoutExpired as error:
                    raise OracleError('command_timeout','Numeric acceptance command exceeded its timeout',{'command':record}) from error
            record.update(exit_code=result.returncode,stdout=stdout.read_text(),stderr=stderr.read_text())
            if result.returncode:
                raise OracleError('command_failed','Numeric acceptance process exited with a nonzero code',{'command':record})
            return record

    context = None
    try:
        binary = Path(args.binary).resolve(strict=True)
        project = Path(args.project).resolve(strict=True)
        oracle_path = Path(args.oracle).resolve(strict=True)
        if not binary.is_file() or not project.is_file() or not oracle_path.is_file():
            raise OracleError('oracle_files_missing','Standalone validation requires the actual binary, project manifest, and oracle JSON')
        self_test = binary.with_name('strata_core_test')
        if not self_test.is_file():
            raise OracleError('oracle_files_missing','Build the separate strata_core_test target before validating the delivered project')
        oracle = normalize_oracle(json.loads(oracle_path.read_text()))
        context = LocalContext(binary.parent/'task-oracle-evidence')
        report = validate_project(context,binary,self_test,project.parent,oracle,
                                  hashlib.sha256(oracle_path.read_bytes()).hexdigest())
        report.update(status='passed',schema='strata.task.oracle.execution.v1',
            provenance='Delivered task oracle executed by standalone stdlib runner',
            binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),
            oracle_sha256=hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
            native_device_validated=False,full_inference_validated=False)
        path = context.write_json('task-oracle-evidence.json',report)
        print(json.dumps({'status':'passed','numerical_validation':report['numerical_validation'],
                          'evidence_path':str(path),'native_device_validated':False,'full_inference_validated':False}))
        return 0
    except (OracleError,OSError,ValueError) as failure:
        report = {'status':'failed','code':getattr(failure,'code','oracle_runner_failed'),
                  'message':str(failure),'details':getattr(failure,'details',{}),
                  'native_device_validated':False,'full_inference_validated':False}
        if context is not None:
            context.write_json('task-oracle-evidence.json',report)
        print(json.dumps(report,allow_nan=False),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
