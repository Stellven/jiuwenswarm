from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(r'D:\research\ai_for_research\jiuwenswarm')))
from jiuwenswarm.ai4research.capsules import CapsuleLibrary
from jiuwenswarm.ai4research.admission import validate_admission_receipt
from jiuwenswarm.ai4research.common import canonical_json, sha256_bytes

ROOT=Path(r'D:\research\ai_for_research\jiuwenswarm')
OUT=ROOT/'docs/code/Missions/M0/M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-2'
library=CapsuleLibrary(ROOT/'.codex-tmp/observed-definition-pins-2/library.sqlite',ROOT/'jiuwenswarm/ai4research')
definitions=library.seed_builtin()
pins={'compiler':definitions['intent_compiler'],'verifier':definitions['intent_verifier']}
hashes={role:pin.decl_hash for role,pin in pins.items()}
assert hashes=={'compiler':'c9ecd7509e50a1a272f5293bfa7f090ccc8e969f456aad400e5b8d6db73286d4','verifier':'ccf644cb29293e0385313dd5c7c1458f6c2a5eafa274c7298efbfdfe25f5d786'}
reasons={
'two_cc_scope':'Exactly two text-only authored definitions remain. The native protocol fixes add protected route validation and evidence metadata, without another CC, composition, repair, dynamic routing or RSI.',
'closure_and_provenance':'A fresh isolated library captured both exact implementation closures into inactive candidates. Updated bridge and runner bytes produce new declaration, closure and contract identities. Templates, prompts, schema/check code, profile, adaptation and retained upstream resources match the previous assessment. Authored lineage remains explicit with unavailable generation provenance null.',
'typed_contracts':'Strict attributed Intent and exact-subject Assessment contracts are unchanged. Native standard-schema model, provider and CLI-version configuration is validated before turn dispatch; missing or conflicting identity halts. Evidence distinguishes requested/configured model from unavailable independently served-model identity.',
'protected_fidelity_rubric':'The unchanged host-frozen F1-F6 profile covers completeness, support, relevance, ambiguity, evidence and instruction resistance. Producer content cannot choose or waive criteria. Mandatory uncertainty or failure still prevents release.',
'upstream_adaptation':'Adaptation, both fixed-revision upstream bodies and retained license are byte-identical to the prior public-source verification. F1-F6 mappings and justified scientific/statistical/citation-retrieval/repair/advancement exclusions remain intact.',
'no_gate_authority':'Model output remains read-only findings with no gate capability. Native rerouting and error notifications, including willRetry, halt the owned invocation without replay; queued completion cannot conceal an observed refusal. Protected host aggregation and durable custody retain sole authority to release the exact compiler artifact.'}
review={'schema_revision':'definition-review-r2','pins':hashes,'source':'independently scoped code and source assessment','observations':[{'obligation':key,'result':'PASS','reason':reason} for key,reason in reasons.items()],'result':'PASS','limitations':['Actual independent assessment by /root/native_inventory on the current pins; fresh scratch seeding produced candidates only, without admission, activation or model invocation.','Provisional definition eligibility only; no real model fidelity, instruction resistance or connected acceptance established.','Configured model/provider identity is native thread configuration; independently served-model identity remains unavailable.','One owned native turn does not establish undisclosed provider-internal request counts.','Separate invocations do not guarantee independent model errors; stage/full-M1 exits remain incomplete.','Windows storage capability checks do not certify ACL or process isolation.','Changed closure bytes require new pins and renewed applicable evidence.']}
(OUT/'definition-review.json').write_bytes(canonical_json(review)+b'\n')
report=ET.parse(OUT/'pytest.xml').getroot()
required=[case.get('classname')+'::'+case.get('name') for case in report.iter('testcase') if any(group+'::' in case.get('classname')+'::'+case.get('name') for group in ('test_m0_003','test_intent_compiler','test_m0_007'))]
def ref(name): return {'path':name,'sha256':sha256_bytes((OUT/name).read_bytes())}
receipt={'schema_revision':'definition-admission-r2','scope':'provisional-definition-eligibility; not connected trial acceptance','pins':hashes,'checks':{'junit':ref('pytest.xml'),'required_cases':required},'independent_review':ref('definition-review.json')}
(OUT/'definition-admission.json').write_bytes(canonical_json(receipt)+b'\n')
observed=validate_admission_receipt(OUT/'definition-admission.json',pins)
(OUT/'definition-admission-validation.json').write_bytes(canonical_json({'result':'PASS','required_cases':len(required),'observed':observed,'pins':hashes,'standing':'candidate; no activation performed by this check'})+b'\n')
print(json.dumps({'result':'PASS','required_cases':len(required),'observed_cases':observed['observed_cases'],'pins':hashes,'activation':False}))
