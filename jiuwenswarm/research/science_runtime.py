"""Closed captured science-runtime decoding; definitions carry no authority."""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from dataclasses import dataclass

from .contracts import ResearchError, validate
from .executor import ExecutorBlocked


OPERATIONS = frozenset(('provision','hardware_inventory','measure_job','run',
                        'collect_builder','builder_observation','invoke_builder','builder_test','builder_action'))


@dataclass(frozen=True)
class ScienceRuntimeDefinition:
    _encoded: bytes

    @property
    def record(self):
        return json.loads(self._encoded)


def _require(ok, reason='SCIENCE_BINDING_INVALID'):
    if not ok:
        raise ExecutorBlocked(reason)


def _ref_key(ref):
    validate('Ref', ref)
    return ref['id'], ref['sha256']


def decode_science_runtime_record(record, *, historical=False):
    """Decode closed v2/v3 or historical v1 without installing a factory.

    Original v1 data stays readable. A v1 profile cannot create a new native
    execution capability. Numeric/schema success never supplies service proof.
    """
    try:
        _require(type(record) is dict)
        version=record.get('schema')
        fields={'schema','id','build_id','profile','approved_environments','gpu_required'}
        if version=='ai4r-science-runtime:1':
            _require(historical and set(record)==fields,'SCIENCE_RUNTIME_V1_HISTORICAL_ONLY')
        else:
            _require(version in {'ai4r-science-runtime:2','ai4r-science-runtime:3','ai4r-science-runtime:4','ai4r-science-runtime:5'})
            extra={'execution_bindings'}|({'scoring_profile'} if version in {'ai4r-science-runtime:3','ai4r-science-runtime:4','ai4r-science-runtime:5'} else set())
            _require(set(record)==fields|extra|({'execution_mode'} if version=='ai4r-science-runtime:5' else set()))
            validate('urn:ai4r:private:science-runtime:'+version.rsplit(':',1)[1],record)
        if version=='ai4r-science-runtime:5':
            _require(record['execution_mode']=='m1_app_process','SCIENCE_EXECUTION_MODE_INVALID')
        if version=='ai4r-science-runtime:3' or (version=='ai4r-science-runtime:5' and (record.get('scoring_profile') or {}).get('protocol')=='ai4r-blind-classification:1'):
            scoring=record['scoring_profile']
            _ref_key(scoring['public_dataset_ref'])
            _require(scoring['protocol']=='ai4r-blind-classification:1'
                and scoring['public_file']=='data.json'
                and scoring['holdout_path']=='/run/ai4r-private-qa/holdout.json'
                and type(scoring['max_stdout_bytes']) is int and scoring['max_stdout_bytes']==8388608,
                'SCIENCE_SCORING_PROFILE_INVALID')
            for key in ('public_data_sha256','holdout_sha256','scorer_sha256'):
                _require(type(scoring[key]) is str and re.fullmatch(r'[0-9a-f]{64}',scoring[key]),
                    'SCIENCE_SCORING_PROFILE_INVALID')
        _require(all(isinstance(record[key],str) and record[key] for key in ('id','build_id')))
        _require(type(record['gpu_required']) is bool)
        profile=record['profile']
        expected={'asset_root','environment_root','memory_mb','pids_max','run_timeout_s','provision_timeout_s',
                  'baseline_arguments','treatment_arguments','uv_path','python_path'}
        _require(type(profile) is dict and set(profile)==expected,'SCIENCE_PROFILE_INVALID')
        for key in ('memory_mb','pids_max','run_timeout_s','provision_timeout_s'):
            value=profile[key]
            _require(type(value) in (int,float) and math.isfinite(value) and value>0,'SCIENCE_PROFILE_LIMIT_INVALID')
        paths={'asset_root':'/var/lib/ai4r-executor/assets',
               'environment_root':'/var/lib/ai4r-executor/environments','uv_path':'/usr/local/bin/uv',
               'python_path':sys._base_executable}
        _require(all(profile[key]==value for key,value in paths.items()),'SCIENCE_PROFILE_PATH_INVALID')
        for key in ('baseline_arguments','treatment_arguments'):
            _require(type(profile[key]) is list and all(type(value) is str and '\0' not in value for value in profile[key]),
                     'SCIENCE_ARGUMENT_PROFILE_INVALID')
        _require(type(record['approved_environments']) is list,'SCIENCE_ENVIRONMENT_CATALOG_INVALID')
        locks=set()
        for entry in record['approved_environments']:
            _require(type(entry) is dict and set(entry)=={'lock_ref','approval_ref','platform_fact','wheel_filenames'},
                     'SCIENCE_ENVIRONMENT_CATALOG_INVALID')
            lock=_ref_key(entry['lock_ref']);_ref_key(entry['approval_ref'])
            _require(lock[0] not in locks and lock[1] not in locks,'SCIENCE_ENVIRONMENT_CATALOG_INVALID')
            locks.update(lock)
            _require(type(entry['platform_fact']) is list and len(entry['platform_fact'])==3
                and all(type(value) is str and value and '\0' not in value for value in entry['platform_fact']),
                'SCIENCE_ENVIRONMENT_CATALOG_INVALID')
            _require(type(entry['wheel_filenames']) is dict and all(type(key) is str and type(value) is str
                and key and value and '\0' not in key and '\0' not in value
                for key,value in entry['wheel_filenames'].items()),'SCIENCE_ENVIRONMENT_CATALOG_INVALID')
        if version in {'ai4r-science-runtime:2','ai4r-science-runtime:3','ai4r-science-runtime:4','ai4r-science-runtime:5'}:
            seen=set()
            for entry in record['execution_bindings']:
                refs=tuple(_ref_key(entry[key]) for key in ('configuration_ref','policy_ref','resource_inventory_ref',
                                                           'declaration_ref','admission_ref'))
                arrays=[]
                for key in ('implementation_refs','dependency_refs'):
                    values=tuple(_ref_key(ref) for ref in entry[key])
                    _require(len(values)==len({ref[0] for ref in values})==len({ref[1] for ref in values}),
                             'SCIENCE_EXECUTION_MAPPING_DUPLICATE_PIN')
                    arrays.append(values)
                operations=entry['operations']
                _require(operations and len(operations)==len(set(operations))
                         and set(operations)<=OPERATIONS,'SCIENCE_EXECUTION_MAPPING_INVALID')
                identity=(*refs,*arrays)
                _require(identity not in seen,'SCIENCE_EXECUTION_MAPPING_AMBIGUOUS')
                seen.add(identity)
        encoded=json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        return ScienceRuntimeDefinition(encoded)
    except (ResearchError,ValueError,TypeError,KeyError,OverflowError) as error:
        raise ExecutorBlocked('SCIENCE_BINDING_INVALID') from error
