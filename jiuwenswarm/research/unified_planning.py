"""Protected workflow alternatives for the single installed AI4R Planner.

The Planner chooses a graph from the accepted Brief and frozen catalog. These
rules validate that graph; they never classify request text or generate a plan.
"""
from __future__ import annotations

from .contracts import ResearchError
from .summary_planning import (PAPER_SUMMARY_CC, PAPER_DELIVERY_CC,
                               is_document_summary_policy, summary_layout_issues)

AI4R_POLICY_ID = 'ai4r_integrated_policy_v1'
POC_STAGES = tuple('research.' + stage for stage in
                   ('search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery'))


def integrated_plan_policy():
    return {'schema_version': '1.0.0', 'id': AI4R_POLICY_ID, 'max_nodes': 7,
            'allowed_effect_classes': ['pure', 'read_only', 'idempotent', 'compensable'],
            'allow_network': True, 'required_stages': [],
            'aggregate_limits': {'time_s': 10800, 'model_calls': 80, 'memory_mb': 16384},
            'max_attempts_per_node': 1}


def is_integrated_policy(policy):
    if not isinstance(policy, dict) or policy.get('id') != AI4R_POLICY_ID:
        return False
    if policy != integrated_plan_policy():
        raise ResearchError('integrated_plan_policy', 'Integrated AI4R policy differs from its exact protected version')
    return True


def paper_workflow_allowed(policy):
    return is_document_summary_policy(policy) or is_integrated_policy(policy)


def is_paper_graph(source):
    nodes = source.get('nodes', [])
    return (len(nodes) == 2 and sorted(n['cc']['cc_name'] for n in nodes)
            == sorted((PAPER_SUMMARY_CC, PAPER_DELIVERY_CC)))


def integrated_layout_issues(source):
    """Close the union: no partial POC, hybrid, or unrelated library graph."""
    if is_paper_graph(source):
        return summary_layout_issues(source)
    names = [node['cc']['cc_name'] for node in source['nodes']]
    if len(names) != len(POC_STAGES) or set(names) != set(POC_STAGES):
        return ['Integrated AI4R requires exactly the two-node paper summary or the seven-stage scientific POC graph']
    return []


def integrated_planner_instructions():
    return '''This protected policy admits two complete workflow alternatives in this same Planner assignment. Determine which installed capability fulfills the accepted Research Brief by reasoning over that Brief, the exact selectable catalog and available resources. A request to summarize one qualified uploaded PDF can use research.paper_summary followed by research.paper_summary_delivery; a request for a classification experiment/POC uses the complete seven scientific stages research.search, research.screening, research.hypothesis, research.builder, research.benchmark, research.evaluation, research.delivery. Select one complete alternative, with no hybrid or partial graph. Scientific datasets, baseline, environment and experiment resources are required only by selected scientific Capsules; their absence does not make a qualified PDF-summary Brief infeasible. Paper summary does not require Search, Screening, Hypothesis, Builder, Benchmark or Scientific Evaluation.

For the paper alternative select exactly research.paper_summary and research.paper_summary_delivery at the exact installed paper-m1-4 declaration pins. The Summary has no predecessors; Delivery has Summary as its sole direct predecessor. Summary inputs are brief (research_brief, accepted_ref key brief) and documents (local_document_buffer, accepted_ref key local_document_buffer). Delivery inputs are brief from accepted_ref brief, summary from future_output with Summary's node ID, public port summary and artifact_type paper_summary, and gate_decision_index from host_record key gate_decision_index. Preserve exact declared output ports: Summary summary/paper_summary; Delivery research_report/paper_report and delivery_manifest/paper_delivery_manifest. A Brief deliverable label text_summary describes the desired human-readable result carried by paper_report, not a renamed public port or missing producer. No scientific dataset, experiment, external search, model selection or tool call belongs to this graph. Use empty topic_hints and notes. Cover all mandatory requirements and deliverables with the ordinary exact inverse coverage map; Delivery is the sole leaf and covers every deliverable. Only exact selected declarations, typed ports, original qualified resources, existing independent checks and gates authorize execution. Every other ordinary schema, budget, coverage and output-only semantic criterion remains binding.'''
