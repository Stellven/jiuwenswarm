"""Protected workflow alternatives for the single installed AI4R Planner.

The Planner chooses a graph from the accepted Brief and frozen catalog. These
rules validate that graph; they never classify request text or generate a plan.
"""
from __future__ import annotations

from .contracts import ResearchError
from .summary_planning import (PAPER_SUMMARY_CC, PAPER_DELIVERY_CC,
                               is_document_summary_policy, summary_layout_issues)

AI4R_POLICY_ID = 'ai4r_integrated_policy_v2'
LEGACY_POLICY_ID = 'ai4r_integrated_policy_v1'
POC_STAGES = tuple('research.' + stage for stage in
                   ('search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery'))


def integrated_plan_policy():
    return {'schema_version': '1.0.0', 'id': AI4R_POLICY_ID, 'max_nodes': 12,
            'allowed_effect_classes': ['pure', 'read_only', 'idempotent', 'compensable'],
            'allow_network': True, 'required_stages': [],
            'aggregate_limits': {'time_s': 10800, 'model_calls': 80, 'memory_mb': 16384},
            'max_attempts_per_node': 1}


def legacy_integrated_plan_policy():
    value = integrated_plan_policy()
    value.update(id=LEGACY_POLICY_ID, max_nodes=7)
    return value


def is_integrated_policy(policy):
    if not isinstance(policy, dict) or policy.get('id') not in {AI4R_POLICY_ID, LEGACY_POLICY_ID}:
        return False
    expected = legacy_integrated_plan_policy() if policy['id'] == LEGACY_POLICY_ID else integrated_plan_policy()
    if policy != expected:
        raise ResearchError('integrated_plan_policy', 'Integrated AI4R policy differs from its exact protected version')
    return True


def paper_workflow_allowed(policy):
    return is_document_summary_policy(policy) or is_integrated_policy(policy)


def is_paper_graph(source):
    nodes = source.get('nodes', [])
    return (len(nodes) == 2 and sorted(n['cc']['cc_name'] for n in nodes)
            == sorted((PAPER_SUMMARY_CC, PAPER_DELIVERY_CC)))


def integrated_layout_issues(source, policy=None):
    """Enforce placement obligations; dependencies determine the graph shape."""
    if is_paper_graph(source):
        return summary_layout_issues(source)
    names = [node['cc']['cc_name'] for node in source['nodes']]
    if policy is not None and policy.get('id') == LEGACY_POLICY_ID:
        if len(names) != len(POC_STAGES) or set(names) != set(POC_STAGES):
            return ['Legacy policy requires the original complete scientific POC graph']
    else:
        from .capability_planning import layout_issues
        issues = layout_issues(source)
        scientific = {'research.' + stage for stage in ('hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery')}
        if scientific.intersection(names):
            required = ('research.search', 'research.screening', 'research.hypothesis')
            issues += [name + ' must occur exactly once in a scientific plan' for name in required if names.count(name) != 1]
        return issues
    return []


def _legacy_planner_instructions():
    return '''This protected policy admits two complete workflow alternatives in this same Planner assignment. Determine which installed capability fulfills the accepted Research Brief by reasoning over that Brief, the exact selectable catalog and available resources. A request to summarize one qualified uploaded PDF can use research.paper_summary followed by research.paper_summary_delivery; a request for a classification experiment/POC uses the complete seven scientific stages research.search, research.screening, research.hypothesis, research.builder, research.benchmark, research.evaluation, research.delivery. Select one complete alternative, with no hybrid or partial graph. Scientific datasets, baseline, environment and experiment resources are required only by selected scientific Capsules; their absence does not make a qualified PDF-summary Brief infeasible. Paper summary does not require Search, Screening, Hypothesis, Builder, Benchmark or Scientific Evaluation.

For the paper alternative select exactly research.paper_summary and research.paper_summary_delivery at the exact installed paper-m1-5 declaration pins. The Summary has no predecessors; Delivery has Summary as its sole direct predecessor. Summary inputs are brief (research_brief, accepted_ref key brief) and documents (local_document_buffer, accepted_ref key local_document_buffer). Delivery inputs are brief from accepted_ref brief, summary from future_output with Summary's node ID, public port summary and artifact_type paper_summary, and gate_decision_index from host_record key gate_decision_index. Preserve exact declared output ports: Summary summary/paper_summary; Delivery research_report/paper_report and delivery_manifest/paper_delivery_manifest. A Brief deliverable label text_summary describes the desired human-readable result carried by paper_report, not a renamed public port or missing producer. No scientific dataset, experiment, external search, model selection or tool call belongs to this graph. Use empty topic_hints and notes. Cover all mandatory requirements and deliverables with the ordinary exact inverse coverage map; Delivery is the sole leaf and covers every deliverable. Only exact selected declarations, typed ports, original qualified resources, existing independent checks and gates authorize execution. Every other ordinary schema, budget, coverage and output-only semantic criterion remains binding.'''



def integrated_planner_instructions(policy=None):
    if policy is not None and policy.get('id') == LEGACY_POLICY_ID:
        return _legacy_planner_instructions()
    return """Produce one bounded typed DAG from the exact selectable admitted library.
Do not select a graph from a hardcoded list of complete shapes. Choose nodes,
connections and ordering from the accepted Brief, actual declared input/output
ports, captured resources, exact pins and policy. Additional compatible capsules
and repeated instances are permitted; no stage order list grants eligibility.
A generic graph may terminate at any declared, checked leaf covering every deliverable.
For scientific work, research.search, research.screening and research.hypothesis
occur exactly once. Exactly one research.delivery leaf covers all deliverables
and has exactly one research.evaluation ancestor. Generic capsule outputs do not
become verified scientific results merely because their checks pass. The existing scientific port
contracts determine required dependencies; do not skip evidence or scientific
checking, invent resources, substitute ports or implicitly convert types.
The existing protected paper-summary exception remains: a qualified uploaded PDF
can use research.paper_summary followed by research.paper_summary_delivery with
its exact installed ports and pins, without scientific resources/stages. This
exception is not a requirement that other valid graphs have exactly seven nodes.
Every required port binds to a real accepted input key, an exact compatible
predecessor output, or a supported conditional host record. Every proposal
accepted_ref remains null. Coverage exactly inverts requirement/deliverable tags;
evidence-obligation entries name actual obligated work. Preserve all mandatory
checks, effects, limits and one dispatch attempt. Do not select compiler, verifier
or Planner capsules. Missing capabilities/resources means INFEASIBLE, never
invented pins, tools, code execution, grants or silent static fallback.
Generate one candidate per call. On host validation feedback, correct the complete proposal once against unchanged inputs; at most two generations, no ranking/search loop. Unknown reliability/cost
is unmeasured. No claim of plan optimization is warranted."""
