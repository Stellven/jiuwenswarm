"""Explicit protected policy for the user-authorized PDF summary workflow.

This is an additional policy, never inferred from request text or a proposal.
The operator captures/selects it before intake and all ordinary checks and
independent Capsule reviews still apply. The scientific POC policy is unchanged.
"""
from __future__ import annotations

import copy

from .contracts import ResearchError


PAPER_POLICY_ID = 'paper_summary_policy_v1'
PAPER_SUMMARY_CC = 'research.paper_summary'
PAPER_DELIVERY_CC = 'research.paper_summary_delivery'
PAPER_PLANNER_CC = 'workflow.paper_planner'
PAPER_CC_VERSION = 'paper-m1-5'
PAPER_PLANNER_VERSION = 'paper-m1-10'


def document_summary_policy():
    """Return the closed policy for explicit protected configuration capture."""
    return {
        'schema_version': '1.0.0', 'id': PAPER_POLICY_ID, 'max_nodes': 2,
        'allowed_effect_classes': ['read_only'], 'allow_network': False,
        'required_stages': [PAPER_SUMMARY_CC, PAPER_DELIVERY_CC],
        # The same protected ceiling bounds the complete run: Compiler four
        # calls, Planner two, Summary two and Delivery two, with finite margin.
        'aggregate_limits': {'time_s': 1800, 'model_calls': 12, 'memory_mb': 16384},
        'max_attempts_per_node': 1,
    }


def is_document_summary_policy(policy):
    """Recognize only the exact captured policy, not a caller-supplied label."""
    if not isinstance(policy, dict) or policy.get('id') != PAPER_POLICY_ID:
        return False
    if policy != document_summary_policy():
        raise ResearchError('paper_summary_policy', 'Paper summary policy differs from the exact protected version')
    return True


def summary_layout_issues(source):
    """Additional closure for the explicitly selected two-Capsule graph."""
    issues = []
    nodes = source['nodes']
    if source['plan_source'] != 'planned':
        issues.append('Paper summary requires the genuine planned path')
    if (len(nodes) != 2 or sorted(n['cc']['cc_name'] for n in nodes)
            != sorted([PAPER_SUMMARY_CC, PAPER_DELIVERY_CC])):
        return [*issues, 'Paper summary requires exactly the Summary and Summary Delivery Capsules']
    summary = next(n for n in nodes if n['cc']['cc_name'] == PAPER_SUMMARY_CC)
    delivery = next(n for n in nodes if n['cc']['cc_name'] == PAPER_DELIVERY_CC)
    if any(n['cc']['cc_version'] != PAPER_CC_VERSION for n in nodes):
        issues.append('Paper summary Capsule version differs from the protected workflow')
    if summary['predecessors'] or delivery['predecessors'] != [summary['node_id']]:
        issues.append('Paper summary requires one direct Summary to Delivery edge')
    expected = {
        summary['node_id']: {
            'brief': ('research_brief', 'accepted_ref', 'brief', None),
            'documents': ('local_document_buffer', 'accepted_ref', 'local_document_buffer', None),
        },
        delivery['node_id']: {
            'brief': ('research_brief', 'accepted_ref', 'brief', None),
            'summary': ('paper_summary', 'future_output', None,
                        {'producer_node': summary['node_id'], 'port': 'summary', 'artifact_type': 'paper_summary'}),
            'gate_decision_index': ('gate_decision_index', 'host_record', 'gate_decision_index', None),
        },
    }
    for node in nodes:
        ports = node['inputs']
        if len(ports) != len(expected[node['node_id']]) or {p['name'] for p in ports} != set(expected[node['node_id']]):
            issues.append('Paper summary input population differs from its protected workflow')
            continue
        for port in ports:
            actual = tuple(port[key] for key in ('artifact_type', 'source_kind', 'run_input_key', 'future'))
            if actual != expected[node['node_id']][port['name']] or not port['required']:
                issues.append('Paper summary input does not name the exact qualified source or accepted predecessor')
    return issues


def validate_summary_documents(store, brief, resources, inventory_ref, authority):
    """Join the existing ordinary qualified PDF buffer and source read ceiling."""
    from .run_inputs import local_document_refs
    matches = [r for r in resources['resources'] if r['resource_key'] == 'local_document_buffer'
               and r['available'] and r['ref'] is not None]
    if len(matches) != 1:
        raise ResearchError('plan_infeasible', 'Paper summary needs one exact qualified local document buffer')
    ref = matches[0]['ref']
    documents = local_document_refs(store, ref, inventory_ref=inventory_ref, intake_ref=brief['intake_ref'])
    if len(documents) != 1:
        raise ResearchError('plan_infeasible', 'Paper summary accepts exactly one qualified PDF document')
    if (not isinstance(authority, dict)
            or any(item not in authority.get('resource_reads', []) for item in [ref, *documents])):
        raise ResearchError('plan_infeasible', 'Paper source exceeds the original protected read ceiling')
    intake = store.read_record(brief['intake_ref'], contract_id='qualified-intake')
    if len(intake['upload_refs']) != 1 or intake['resource_refs']:
        raise ResearchError('plan_infeasible', 'Paper summary accepts one PDF upload and no experimental resources')
    upload = store.read_record(intake['upload_refs'][0], contract_id='client-upload')
    if upload['kind'] != 'docs' or not upload['filename'].lower().endswith('.pdf'):
        raise ResearchError('plan_infeasible', 'Paper summary source is not the qualified PDF upload')
    return copy.deepcopy(documents)


def document_summary_planner_instructions():
    """Public producer guidance for the separate immutable Paper Planner CC."""
    return '''You are the one-shot native paper-summary Planner. Return one data-only plan_proposal schema 3.0.0 for the accepted Research Brief and the exact supplied library, resource and policy refs. This is the explicitly protected paper_summary_policy_v1 workflow, not a scientific POC. Select exactly one research.paper_summary and one research.paper_summary_delivery, both paper-m1-4 with exact selectable library declaration pins. Use node IDs paper_summary and paper_delivery, with paper_summary having no predecessor and paper_delivery having only paper_summary as direct predecessor. No Search, Screening, Hypothesis, Builder, Benchmark or Scientific Evaluation node belongs to this PDF summary workflow. No model selection, tools, network, external facts or experiments are authorized.

Summary inputs are brief (research_brief, accepted_ref key brief) and documents (local_document_buffer, accepted_ref key local_document_buffer). The buffer is already captured from the current qualified PDF intake; it is an inventory resource, not a missing producer. Delivery inputs are brief from accepted_ref brief; summary from future_output producer paper_summary, public port summary, artifact_type paper_summary; gate_decision_index from the existing host_record key of the same name. Leave every proposal accepted_ref null; accepted/host inputs have future null and future inputs have run_input_key null. Preserve the exact consumer input names and artifact types from the frozen library. Summary publicly outputs summary/paper_summary. Delivery publicly outputs research_report/paper_report and delivery_manifest/paper_delivery_manifest. The paper_report is the ordinary human-readable plain-text paper summary: it can fulfill a Brief deliverable described as text_summary. Such a requested deliverable label describes the user's desired result; it does not rename a Capsule port, create an artifact-type alias or require a new producer. Keep the Brief unchanged and all actual Capsule port bindings exactly type-compatible. Do not declare INFEASIBLE solely because that desired-result label differs from the admitted paper_report carrier type. The host gate index is constructed only from actual committed predecessor gates, never manufactured by the proposal.

Cover every concrete Brief mandatory requirement and deliverable by node tags, with coverage exactly their inverse. Delivery is the sole leaf and covers every deliverable. Select only the exact listed check pins and stay within each library max_limits and the protected aggregate limits. Time and calls sum; memory is the maximum. Each node has one attempt. Use empty topic_hints and empty notes. Every objective is one declarative sentence describing the intended result for a human, with no imperative command, permission grant, check waiver, code, path or claim of already-completed results.

Internally self-review all eight existing semantic criteria: declared_output_conformance (declared fields, types and shape); internal_consistency (agreeing fields and resolving local references); limitations_consistency (uncertainties and limitations consistent with planned outputs); graph_self_consistent (resolved predecessor/future graph without cycles); output_ports_named (every future output lists an existing same-type producer port); coverage_tags_present (each node has a requirement or deliverable tag); coverage_map_consistent (coverage exactly inverts those tags); no_authority_claims (notes, objectives and suggested_checks contain no commands, code, permission grants or check weakening). The protected host still checks exact Brief coverage, library membership, ports, dependencies, budget, authority and resources; the independent verifier and gates still decide acceptance. Do not return executable content or perform any tool call. If a genuine required capability or qualified PDF source is absent, return only one nonempty INFEASIBLE: line of at most 300 characters. No fallback, repair, second generation or silent static plan is allowed.'''
