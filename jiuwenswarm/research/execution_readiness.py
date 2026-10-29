"""Read-only startup scope observation; this never issues execution authority."""
from __future__ import annotations

from .contracts import ResearchError, validate


def _require(condition):
    if not condition:
        raise ResearchError('core_bindings', 'Exact protected finite execution scope is unavailable')


def _integrated_scope(composition, bindings, operator, *, library_pins, principal, model_port):
    """Observe the admitted read-only path, without qualifying scientific effects."""
    import os
    from .binding import Binder, ContractFactory
    from .bootstrap_core import CoreComposition
    from .compiler import IntentionCompiler
    from .control import ResearchService
    from .planning import PlanningCoordinator
    from .runner import CapsuleRunner
    from .scheduler import Scheduler
    from .unified_planning import is_integrated_policy
    from .uploads import UploadManager

    options = bindings['protected_options']
    store, service = composition.library.store, composition.service
    settings = operator.snapshot()['cc']
    policy = store.read_record(settings['plan_policy_ref'], contract_id='plan-policy')
    _require(is_integrated_policy(policy) and settings['evaluation_profile_ref'] is None
        and options.get('finite_e1_binding_ref') is None)
    runner, scheduler, compiler, planner = (composition.runner, composition.scheduler,
        composition.compiler, composition.planner)
    _require(type(composition) is CoreComposition and type(service) is ResearchService
        and type(runner) is CapsuleRunner and type(scheduler) is Scheduler
        and type(compiler) is IntentionCompiler and type(planner) is PlanningCoordinator
        and type(scheduler.binder) is Binder and type(scheduler.factory) is ContractFactory
        and service.compiler is compiler and service.scheduler is scheduler
        and service.binder is scheduler.binder and scheduler.planning is planner
        and scheduler.runner is runner and scheduler.library is composition.library
        and scheduler.binder.library is composition.library
        and scheduler.factory.library is composition.library
        and compiler.runner is runner and planner.runner is runner
        and compiler.factory is scheduler.factory and planner.factory is scheduler.factory
        and all(owner.store is store for owner in (runner, scheduler, scheduler.binder,
            scheduler.factory, compiler, planner, service))
        and model_port is not None and runner.model is model_port and service.model is model_port
        and compiler.policy_ref == settings['plan_policy_ref']
        and scheduler.factory.finalization_profile_ref == options['finalization_profile_ref'])
    store.read_record(options['finalization_profile_ref'], contract_id='node-finalization-profile')
    _require(principal is not None)
    _, context = service._workspace(principal, bindings['workspace_id'])
    _require(all(context[key] == bindings[key] for key in
        ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref'))
        and context['resource_inventory_ref'] == options['resource_inventory_ref']
        and context['run_limits'] == policy['aggregate_limits'])
    inventory = store.read_record(options['resource_inventory_ref'], contract_id='resource-inventory')
    resources = {row['resource_key']: row for row in inventory['resources']}
    _require(len(resources) == len(inventory['resources']))
    uploads = service.upload_manager
    _require(type(uploads) is UploadManager and uploads.store is store
        and uploads.root == store.input_root.resolve() and uploads.root.is_dir()
        and os.access(uploads.root, os.R_OK | os.W_OK | os.X_OK)
        and callable(uploads.extractor) and uploads.timeout > 0)
    selected = {'intent': compiler.intent_pin, 'requirements': compiler.requirements_pin,
        'planner': planner.planner_pin, 'verifier': scheduler.factory.verifier_pin}
    for stage in ('paper_summary', 'paper_delivery'):
        selected[stage] = composition.installed[stage]['pin']
    for stage, pin in selected.items():
        asset = composition.installed[stage]
        entry = composition.library.get(pin['cc_name'], pin['cc_version'])
        admission = store.read_record(entry['admission_ref'], contract_id='library-admission')
        _require(pin == asset['pin'] and entry['standing'] == 'active'
            and entry['effect_scope'] == 'live_plans' and admission['status'] == 'admitted'
            and admission['cc'] == pin and entry['declaration_ref'] == asset['declaration_ref']
            and admission['candidate_ref'] == entry['declaration_ref']
            and pin['declaration_sha256'] == entry['declaration_ref']['sha256'])
        declaration = store.read_record(entry['declaration_ref'], contract_id='capsule-declaration')
        association = composition.library.eligible_association(entry['declaration_ref'])
        _require(admission['check_pins']['check_bundle_sha256'] == association['bundle_ref']['sha256']
            and admission['check_pins']['checking_profile_sha256'] == association['profile_ref']['sha256'])
        for body in declaration['identity']['body']:
            ref = entry['body_refs'][body['path']]
            _require(ref['sha256'] == body['sha256'])
            store.read_blob(ref)
        for resource in declaration['needs']['resources']:
            # These aliases are captured from the authenticated qualified
            # intake only after submit. Startup cannot invent their Refs.
            if resource['resource_key'] in {'original_request', 'local_document_buffer'}:
                continue
            _require(resource['resource_key'] in resources
                and resources[resource['resource_key']]['available'] is True)
    _require(library_pins is not None
        and library_pins.get('plan_policy_ref', settings['plan_policy_ref']) == settings['plan_policy_ref'])
    return {'kind': 'integrated_submission', 'profile_id': options.get('profile_id'),
        'stages': ['research.paper_summary', 'research.paper_summary_delivery']}


def assess_execution_scope(composition, bindings, operator, *, library_pins=None, principal=None, model_port=None):
    """Return (available, finite_scope, reason) from actual protected composition.

    Ordinary mode retains the Compiler requirement. Only the exact installed
    finite owner can select the separately approved module execution path.
    """
    ordinary_reason = 'Exact catalog admission or protected compiler/planner bindings are incomplete'
    if composition is None or composition.diagnostics or composition.scheduler is None:
        return False, None, ordinary_reason
    options = (bindings or {}).get('protected_options', {})
    if options.get('integrated_workflows') is True:
        try:
            scope = _integrated_scope(composition, bindings, operator,
                library_pins=library_pins, principal=principal, model_port=model_port)
            return True, scope, 'Admitted integrated Compiler/Planner and read-only paper execution are installed; scientific execution retains its resource guards'
        except (ResearchError, KeyError, TypeError, ValueError, AttributeError):
            return False, None, 'Exact integrated policy, Compiler/Planner, paper releases or current eligibility are unavailable'
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
