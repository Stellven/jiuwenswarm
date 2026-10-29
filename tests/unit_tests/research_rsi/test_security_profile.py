"""Current-profile byte identity controls; synthetic sources grant no security."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.contracts.rsi_security_cases import CASES,CASE_TEST_IDS,KERNEL_CASES,KERNEL_PROGRAMS,POLICY_PROGRAMS
from jiuwenswarm.research.contracts.rsi_security_profile import recompute_validation_profile,SOURCE_PATHS,CONSUMER_SOURCE_PATHS
from jiuwenswarm.research_rsi.security_profile import build_verification_profile
from jiuwenswarm.research_rsi.process_policy import program_prefix,security_program
from tests.unit_tests.research.test_rsi_security_cases import OriginalVectors


@pytest.fixture
def installed(tmp_path):
 store=OriginalVectors();root=tmp_path/'jiuwenswarm';root.mkdir()
 def write(path,raw):
  path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);return store.put(raw)
 source=[];files=[]
 for name in SOURCE_PATHS:
  raw=('# controlled installed source '+name).encode();pin=write(root/name,raw)
  source.append({'path':name,'ref':pin});files.append({'path':name,'bytes':len(raw),'sha256':pin['sha256']})
 native={'schema_version':'1.0.0','interfaces':{'M1-IF-015':'r1'},
  'sources':[{'path':'reference/rsi-contracts.md','sha256':'a'*64}]}
 native_raw=json.dumps(native).encode();native_ref=write(root/'research_contracts/source_manifest.json',native_raw)
 files.append({'path':'research_contracts/source_manifest.json','bytes':len(native_raw),'sha256':native_ref['sha256']})
 repository=Path(__file__).resolve().parents[3]
 resources=repository/'jiuwenswarm/research_contracts/resources'
 procedure=(resources/'rsi-security-procedure.json').read_bytes()
 assertions=(resources/'rsi-security-assertions.json').read_bytes()
 procedure_ref=write(root/'research_contracts/resources/rsi-security-procedure.json',procedure)
 assertion_ref=write(root/'research_contracts/resources/rsi-security-assertions.json',assertions)
 prefix_ref=store.put(program_prefix())
 attacks={'schema':'ai4r-rsi-security-attack-pins:1','program_prefix_ref':prefix_ref,
  'attacks':{case:store.put(security_program(KERNEL_PROGRAMS[case]) if case in KERNEL_CASES else POLICY_PROGRAMS[case]) for case in CASES}}
 attack_ref=store.put(attacks)
 profile_ref=store.put({'schema':'ai4r-rsi-worker-profile:3','process_policy':'single_process_seccomp_v1'})
 build={'schema':'ai4r-installed-build:2','files':files,'links':[],'dependencies':[{'name':'controlled','version':'1'}],
   'components':{},'uv_lock_sha256':'b'*64,'pyproject_sha256':'c'*64}
 build['build_id']=hashlib.sha256(json.dumps(build,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 build_path=tmp_path/'build.json';build_ref=write(build_path,json.dumps(build).encode())
 pins={'schema':'ai4r-rsi-security-profile-pins:1','installed_build_ref':build_ref,'procedure_ref':procedure_ref,
  'assertion_manifest_ref':assertion_ref,'source_manifest_ref':native_ref,'source_refs':source,
  'worker_profile_refs':[profile_ref],'attack_pins_ref':attack_ref}
 return dict(store=store,root=root,pins=pins,pins_ref=store.put(pins),build=build,build_path=build_path,
  kwargs=dict(package_root=root,installed_build_path=build_path))


def test_producer_measures_current_original_build_all_sources_and_fixed_resources(installed):
 data=installed;profile=build_verification_profile(data['store'].read,data['pins_ref'],**data['kwargs'])
 assert set(profile)=={'candidate_id','procedure_sha256','source_baseline_sha256','native_pins','interface_revisions',
   'profile_pins','assertion_manifest_sha256','required_case_ids'}
 assert profile['candidate_id']==data['build']['build_id'] and profile['required_case_ids']==CASE_TEST_IDS
 assert profile['interface_revisions']=={'M1-IF-015':'r1'}


@pytest.mark.parametrize('fault',['source','procedure','assertion','build','native'])
def test_producer_rejects_changed_installed_source_or_procedure_not_claimed_receipt(installed,fault):
 data=installed
 path={'source':data['root']/SOURCE_PATHS[0], 'procedure':data['root']/'research_contracts/resources/rsi-security-procedure.json',
  'assertion':data['root']/'research_contracts/resources/rsi-security-assertions.json', 'build':data['build_path'],
  'native':data['root']/'research_contracts/source_manifest.json'}[fault]
 path.write_bytes(b'changed current source')
 with pytest.raises((ValueError,ResearchError)):
  build_verification_profile(data['store'].read,data['pins_ref'],**data['kwargs'])


def test_consumer_measures_local_neutral_subset_and_authenticates_producer_originals(installed):
 data=installed
 # A consumer need not carry side-system sources or the producer's build file.
 for name in set(SOURCE_PATHS)-set(CONSUMER_SOURCE_PATHS):(data['root']/name).unlink()
 data['build_path'].unlink()
 profile=recompute_validation_profile(data['store'].read,data['pins_ref'],**data['kwargs'])
 assert profile['candidate_id']==data['build']['build_id']
 (data['root']/CONSUMER_SOURCE_PATHS[0]).write_bytes(b'changed local verifier')
 with pytest.raises(ValueError,match='installed source'):
  recompute_validation_profile(data['store'].read,data['pins_ref'],**data['kwargs'])


def test_current_profile_rejects_historical_weak_process_policy_and_missing_case_pins(installed):
 data=installed;store=data['store'];pins=copy.deepcopy(data['pins'])
 pins['worker_profile_refs']=[store.put({'schema':'ai4r-rsi-worker-profile:2'})]
 with pytest.raises(ValueError,match='process policy'):
  recompute_validation_profile(store.read,store.put(pins),**data['kwargs'])
 pins=copy.deepcopy(data['pins']);pins['source_refs']=pins['source_refs'][:-1]
 with pytest.raises(ValueError,match='source inventory'):
  recompute_validation_profile(store.read,store.put(pins),**data['kwargs'])


def test_producer_cannot_select_consumer_mode(installed):
 with pytest.raises(ValueError,match='cannot select consumer'):
  build_verification_profile(installed['store'].read,installed['pins_ref'],producer=False,**installed['kwargs'])
