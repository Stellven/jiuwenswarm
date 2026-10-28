"""Recompute IF015 verification identity from installed originals, not a receipt."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
from pathlib import Path

from .rsi_security import CASES,_need,_ref,_json
from .rsi_security_cases import CASE_TEST_IDS,KERNEL_CASES,POLICY_METHODS
from . import validate

SOURCE_PATHS=(
 'research/contracts/rsi_security.py','research/contracts/rsi_security_cases.py',
 'research/contracts/rsi_security_profile.py','research/contracts/rsi_installation.py',
 'research/contracts/rsi.py','research/contracts/rsi_publication.py','research/library.py',
 'research/library_operator.py','research/bootstrap_core.py','research/executor.py','research/_executor_probe.py',
 'research_rsi/worker.py','research_rsi/process_policy.py','research_rsi/controller.py',
 'research_rsi/mutation.py','research_rsi/proposer.py','research_rsi/custody.py',
 'research_rsi/signing.py','research_rsi/security_campaign.py','research_rsi/security_driver.py',
 'research_rsi/security_scope.py','research_rsi/security_profile.py','research_rsi/security_installation.py',
 'research_rsi/worker_bootstrap.py','research_rsi/security_runtime.py','research_rsi/security_custody.py',
 'research_rsi/security_publication.py')
CONSUMER_SOURCE_PATHS=tuple(path for path in SOURCE_PATHS if path.startswith('research/contracts/')
 or path in {'research/library.py','research/library_operator.py','research/bootstrap_core.py'})
PINS_FIELDS={'schema','installed_build_ref','procedure_ref','assertion_manifest_ref','source_manifest_ref',
 'source_refs','worker_profile_refs','attack_pins_ref'}


def _encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def recompute_validation_profile(read,pins_ref,*,package_root=None,
 installed_build_path='/usr/local/share/ai4r-build-identity.json',
 procedure_path=None,assertion_path=None,producer=False):
 """Only root installation supplies paths/pins; none are decoded as code."""
 def raw(pin):
  _ref(pin);value=read(pin)
  _need(isinstance(value,bytes) and 0<len(value)<=16*1024*1024
    and hashlib.sha256(value).hexdigest()==pin['sha256'],'current profile original bytes unavailable')
  return value
 def installed(path,pin):
  path=Path(path)
  _need(path.is_absolute() and path.is_file() and not any(item.is_symlink() for item in (path,*path.parents)),
    'current profile installed file is not an original regular source')
  value=path.read_bytes();_need(value==raw(pin),'current profile differs from installed source/procedure/assertions')
  return value
 pins=_json(raw(pins_ref))
 validate('urn:ai4r:private:rsi-security-profile-pins:1',pins)
 _need(isinstance(pins,dict) and set(pins)==PINS_FIELDS and pins['schema']=='ai4r-rsi-security-profile-pins:1',
   'closed independent verification pins required')
 if package_root is not None:root=Path(package_root)
 elif producer:root=Path(importlib.metadata.distribution('workswarm').locate_file('jiuwenswarm'))
 else:root=Path(__file__).resolve().parents[2]
 _need(root.is_absolute() and root.is_dir() and not root.is_symlink(),'current installed source root unavailable')
 # Consumers authenticate the current producer through the live scope owner;
 # their own application image must not impersonate the producer image. They
 # still independently measure the local neutral verifier and fixed resources.
 build=_json(installed(installed_build_path,pins['installed_build_ref']) if producer else raw(pins['installed_build_ref']))
 payload={key:value for key,value in build.items() if key!='build_id'}
 _need(build.get('schema')=='ai4r-installed-build:2' and build.get('build_id')==hashlib.sha256(_encoded(payload)).hexdigest(),
   'actual installed build identity is invalid')
 rows=pins['source_refs']
 _need(isinstance(rows,list) and len(rows)==len(SOURCE_PATHS) and all(isinstance(row,dict)
   and set(row)=={'path','ref'} for row in rows) and {row['path'] for row in rows}==set(SOURCE_PATHS),
   'complete fixed current security source inventory required')
 inventory={row['path']:row['sha256'] for row in build['files']}
 source={}
 for row in rows:
  value=raw(row['ref'])
  if producer or row['path'] in CONSUMER_SOURCE_PATHS:installed(root/row['path'],row['ref'])
  digest=hashlib.sha256(value).hexdigest()
  _need(inventory.get(row['path'])==digest,'current security source is outside installed build identity')
  source[row['path']]=digest
 manifest=_json(installed(root/'research_contracts/source_manifest.json',pins['source_manifest_ref']))
 _need(inventory.get('research_contracts/source_manifest.json')==pins['source_manifest_ref']['sha256'],
   'native source publication differs from producer build identity')
 _need(manifest.get('schema_version')=='1.0.0' and manifest.get('interfaces',{}).get('M1-IF-015')=='r1'
   and isinstance(manifest.get('sources'),list) and manifest['sources'],'current independently published native pins missing')
 native={row['path']:row['sha256'] for row in manifest['sources']}
 _need(len(native)==len(manifest['sources']),'ambiguous native source inventory')
 procedure_path=procedure_path or root/'research_contracts/resources/rsi-security-procedure.json'
 assertion_path=assertion_path or root/'research_contracts/resources/rsi-security-assertions.json'
 procedure=installed(procedure_path,pins['procedure_ref']);assertion_raw=installed(assertion_path,pins['assertion_manifest_ref'])
 expected_procedure={'schema':'ai4r-rsi-security-procedure:1','check_id':'M1-008/V15','required_dependency_mode':'real_boundary',
   'case_ids':list(CASES),'case_test_ids':dict(CASE_TEST_IDS),'case_modes':{case:'kernel' if case in KERNEL_CASES else 'policy' for case in CASES},
   'process_policy':'single_process_seccomp_v1','policy_methods':dict(POLICY_METHODS)}
 _need(_json(procedure)==expected_procedure,'current procedure does not specify the finite independently implemented cases')
 assertions=_json(assertion_raw)
 _need(set(assertions)=={'schema','id','check_id','procedure_sha256','required_dependency_mode','required_assertion_ids','required_case_ids'}
   and assertions.get('schema')=='ai4r-rsi-security-assertions:1' and assertions.get('id')=='rsi-security-assertions-v1'
   and assertions.get('check_id')=='M1-008/V15' and assertions.get('procedure_sha256')==hashlib.sha256(procedure).hexdigest()
   and assertions.get('required_dependency_mode')=='real_boundary' and assertions.get('required_assertion_ids')==list(CASES)
   and assertions.get('required_case_ids')==list(CASE_TEST_IDS.values()),'current thirteen-case procedure/assertion inventory differs')
 profiles={}
 _need(isinstance(pins['worker_profile_refs'],list) and pins['worker_profile_refs'],'current independently approved worker profiles missing')
 for pin in pins['worker_profile_refs']:
  profile=_json(raw(pin))
  _need(pin['id'] not in profiles and profile.get('schema')=='ai4r-rsi-worker-profile:3'
    and profile.get('process_policy')=='single_process_seccomp_v1','current profiles lack the fixed process policy')
  profiles[pin['id']]=pin['sha256']
 # Resolve attack pins now so missing/stale originals cannot be laundered into
 # a current receipt. The fixed observer independently checks their programs.
 attacks=_json(raw(pins['attack_pins_ref']))
 _need(attacks.get('schema')=='ai4r-rsi-security-attack-pins:1' and set(attacks.get('attacks',{}))==set(CASES),
   'current independently pinned attack inventory missing')
 raw(attacks['program_prefix_ref'])
 for pin in attacks['attacks'].values():raw(pin)
 return {'candidate_id':build['build_id'],'procedure_sha256':hashlib.sha256(procedure).hexdigest(),
   'source_baseline_sha256':hashlib.sha256(_encoded(source)).hexdigest(),'native_pins':native,
   'interface_revisions':manifest['interfaces'],'profile_pins':profiles,
   'assertion_manifest_sha256':hashlib.sha256(assertion_raw).hexdigest(),'required_case_ids':dict(CASE_TEST_IDS)}
