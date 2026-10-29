"""Finite producer of current IF015 verification identity from approved pins."""
from jiuwenswarm.research.contracts.rsi_security_cases import CASES,KERNEL_CASES,KERNEL_PROGRAMS,POLICY_PROGRAMS
from jiuwenswarm.research.contracts.rsi_security_profile import recompute_validation_profile,SOURCE_PATHS
from jiuwenswarm.research.contracts.rsi_security import _need,_json


def build_verification_profile(read,pins_ref,**installed_paths):
 """No receipt or claimed PASS is consulted when producing this profile."""
 _need(installed_paths.get('producer',True) is True,'producer verification cannot select consumer mode')
 installed_paths['producer']=True
 profile=recompute_validation_profile(read,pins_ref,**installed_paths)
 pins=_json(read(pins_ref));attacks=_json(read(pins['attack_pins_ref']))
 from .process_policy import program_prefix,security_program
 _need(read(attacks['program_prefix_ref'])==program_prefix(),'approved attack prelude differs from installed process policy')
 for case in CASES:
  expected=security_program(KERNEL_PROGRAMS[case]) if case in KERNEL_CASES else POLICY_PROGRAMS[case]
  _need(read(attacks['attacks'][case])==expected,'approved attack source differs from current finite installed program')
 return profile


def capture_verification_pins(store,*,worker_profile_refs):
 """Capture the actual fixed installed verifier, without running or approving it.

 This is a root preparation operation over an already isolated original-byte
 store. No source, command, procedure or module is selected by configuration.
 Independently approving these captured pins remains a separate owner action.
 """
 from .security_campaign import _protected_store
 from .security_scope import _root_bytes,_installed_roots,_installed_build
 from .worker import validate_profile,ref
 from .process_policy import program_prefix,security_program
 from .records import encoded
 import json
 from pathlib import Path
 _protected_store(store)
 _need(isinstance(worker_profile_refs,list) and 0<len(worker_profile_refs)<=100
   and len({encoded(pin) for pin in worker_profile_refs})==len(worker_profile_refs),'exact distinct current profile pins required')
 for pin in worker_profile_refs:
  ref(pin);profile=validate_profile(json.loads(store.read_blob(pin)))
  _need(profile['schema']=='ai4r-rsi-worker-profile:3','current process-policy profiles required')
 root,_,_=_installed_roots()
 def capture(path):return store.put_blob(_root_bytes(path,16*1024*1024))
 build_ref=capture(Path('/usr/local/share/ai4r-build-identity.json'))
 build=json.loads(store.read_blob(build_ref))
 runtime={'candidate_id':build['build_id'],'installed_build_ref':build_ref}
 class OriginalReader:
  def read(self,pin):return store.read_blob(pin)
 _installed_build(OriginalReader(),runtime)
 prefix=store.put_blob(program_prefix())
 attacks={'schema':'ai4r-rsi-security-attack-pins:1','program_prefix_ref':prefix,
  'attacks':{case:store.put_blob(security_program(KERNEL_PROGRAMS[case]) if case in KERNEL_CASES else POLICY_PROGRAMS[case]) for case in CASES}}
 pins={'schema':'ai4r-rsi-security-profile-pins:1','installed_build_ref':build_ref,
  'procedure_ref':capture(root/'research_contracts/resources/rsi-security-procedure.json'),
  'assertion_manifest_ref':capture(root/'research_contracts/resources/rsi-security-assertions.json'),
  'source_manifest_ref':capture(root/'research_contracts/source_manifest.json'),
  'source_refs':[{'path':path,'ref':capture(root/path)} for path in SOURCE_PATHS],
  'worker_profile_refs':worker_profile_refs,'attack_pins_ref':store.append_record('rsi-security-attack-pins',attacks)}
 pins_ref=store.append_record('rsi-security-profile-pins',pins)
 build_verification_profile(store.read_blob,pins_ref)
 return {'status':'CAPTURED_NOT_APPROVED','validation_profile_ref':pins_ref,'runtime_build_ref':store.put_blob(encoded(runtime)),
  'attack_pins_ref':pins['attack_pins_ref'],'procedure_ref':pins['procedure_ref'],'assertion_manifest_ref':pins['assertion_manifest_ref']}
