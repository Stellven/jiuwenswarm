"""Read-only startup scope observation; this never issues execution authority."""
from __future__ import annotations

from .contracts import ResearchError, validate


def _require(condition):
    if not condition:
        raise ResearchError('core_bindings', 'Exact protected finite execution scope is unavailable')


def assess_execution_scope(composition, bindings, operator, *, library_pins=None, principal=None, model_port=None):
    """Return (available, finite_scope, reason) from actual protected composition.

    Ordinary mode retains the Compiler requirement. Only the exact installed
    finite owner can select the separately approved module execution path.
    """
    ordinary_reason = 'Exact catalog admission or protected compiler/planner bindings are incomplete'
    if composition is None or composition.diagnostics or composition.scheduler is None:
        return False, None, ordinary_reason
    options = (bindings or {}).get('protected_options', {})
    selected = options.get('finite_e1_binding_ref')
    service = getattr(composition, 'service', None)
    owner = getattr(service, 'finite_e1', None)
    if selected is None and owner is None:
        return composition.compiler is not None, None, ordinary_reason
    try:
        from .binding import Binder, ContractFactory
        from .bootstrap_core import CoreComposition
        from .control import ResearchService
        from .finite_evaluation import FiniteE1
        from .runner import CapsuleRunner
        from .scheduler import Scheduler
        validate('Ref', selected)
        _require(type(composition) is CoreComposition and type(service) is ResearchService
            and type(owner) is FiniteE1 and owner.binding_ref == selected
            and owner.library is composition.library and owner.store is composition.library.store)
        runner, scheduler = composition.runner, composition.scheduler
        _require(type(runner) is CapsuleRunner and type(scheduler) is Scheduler
            and type(scheduler.binder) is Binder and scheduler.runner is runner
            and service.scheduler is scheduler and service.binder is scheduler.binder
            and scheduler.library is owner.library and scheduler.binder.library is owner.library
            and scheduler.binder.finite_e1 is owner and runner.store is owner.store
            and scheduler.store is owner.store and scheduler.binder.store is owner.store
            and model_port is not None and runner.model is model_port and service.model is model_port)
        _require(type(scheduler.factory) is ContractFactory and scheduler.factory.store is owner.store
            and scheduler.factory.library is owner.library
            and scheduler.factory.finalization_profile_ref == options['finalization_profile_ref'])
        owner.store.read_record(scheduler.factory.finalization_profile_ref, contract_id='node-finalization-profile')
        owner._intact()
        binding, profile, template = owner._binding, owner._profile, owner._template
        settings = operator.snapshot()
        _require(settings == owner._operator
            and binding['configuration_ref'] == bindings['configuration_ref']
            and binding['profile_ref'] == settings['cc']['evaluation_profile_ref']
            and composition.static_template_ref == binding['template_ref']
            and binding['template_ref'] == settings['cc']['static_template_ref']
            and binding['policy_ref'] == settings['cc']['plan_policy_ref'])
        stages = [node['cc']['cc_name'] for node in template['nodes']]
        _require(stages == owner._qualification['stages']
            and stages in (['research.screening'], ['research.screening', 'research.hypothesis']))
        _require(principal is not None)
        _, context = service._workspace(principal, bindings['workspace_id'])
        _require(context['finite_e1_binding_ref'] == selected
            and context['configuration_ref'] == bindings['configuration_ref']
            and context['resource_inventory_ref'] == options['resource_inventory_ref']
            and context['model_selection_profile_ref'] == bindings['model_selection_profile_ref']
            and context['deployment_ref'] == bindings['deployment_ref']
            and context['profile_id'] == profile['profile_id']
            and context['verifier_cc_ref'] == profile['verifier_cc_ref']
            and context['candidate_pins'] == profile['candidate_pins']
            and context['run_limits'] == owner._policy['aggregate_limits']
            and context['authority_ceiling'] == options['authority_ceiling']
            and context['host_records'] == options.get('host_records', {}))
        for key in ('profile_ref', 'workspace_ref', 'input_directory_ref'):
            _require(context[key] == options[key])
        inventory = owner.store.read_record(options['resource_inventory_ref'], contract_id='resource-inventory')
        resources = {row['resource_key']: row for row in inventory['resources']}
        _require(len(resources) == len(inventory['resources']))
        selected_pins = [node['cc'] for node in template['nodes']]
        verifier = owner.store.read_record(profile['verifier_cc_ref'], contract_id='capsule-declaration')
        selected_pins.append({'cc_name': verifier['identity']['name'],
            'cc_version': verifier['identity']['version_label'],
            'declaration_sha256': profile['verifier_cc_ref']['sha256']})
        _require(scheduler.factory.verifier_pin == selected_pins[-1])
        for pin in selected_pins:
            entry = owner.library.get(pin['cc_name'], pin['cc_version'])
            admitted = owner.store.read_record(entry['admission_ref'], contract_id='library-admission')
            _require(entry['standing'] == 'active' and entry['effect_scope'] == 'live_plans'
                and entry['declaration_ref']['sha256'] == pin['declaration_sha256']
                and admitted['status'] == 'admitted' and admitted['cc'] == pin
                and admitted['candidate_ref'] == entry['declaration_ref'])
            declaration = owner.store.read_record(entry['declaration_ref'], contract_id='capsule-declaration')
            _require(declaration['identity']['name'] == pin['cc_name']
                and declaration['identity']['version_label'] == pin['cc_version'])
            for body in declaration['identity']['body']:
                ref = entry['body_refs'][body['path']]
                _require(ref['sha256'] == body['sha256'])
                owner.store.read_blob(ref)
            association = owner.library.eligible_association(entry['declaration_ref'])
            # Authored static templates pin the CC. Admission owns the checks;
            # the Binder copies these exact pins only when building a RunPlan.
            _require(admitted['check_pins']['check_bundle_sha256'] == association['bundle_ref']['sha256']
                and admitted['check_pins']['checking_profile_sha256'] == association['profile_ref']['sha256'])
            for resource in declaration['needs']['resources']:
                _require(resource['resource_key'] in resources
                    and resources[resource['resource_key']]['available'] is True)
        _require(library_pins is not None
            and library_pins['library_snapshot_sha256'] == profile['library_snapshot_sha256']
            and library_pins.get('plan_policy_ref', binding['policy_ref']) == binding['policy_ref'])
        return True, {'profile_id': profile['profile_id'], 'stages': stages}, 'Exact protected finite execution scope is installed'
    except (ResearchError, KeyError, TypeError, ValueError, AttributeError):
        return False, None, 'Exact protected finite binding, installed composition or current eligibility is unavailable'
