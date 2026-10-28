"""Fixed producer installation, sharing the neutral consumer qualification.

Only the actual root WorkerBroker may provide current producer observations.
Controllers, custodian and app use the neutral live producer client instead.
"""
from jiuwenswarm.research.contracts.rsi_installation import (
    InstalledQualification,InstallationUnavailable,load_installation,
    installed_consumer_qualification,installation_public_roots,
    RUNTIME_OBSERVATION_FILE,SCOPE_SOCKET,SCOPE_PROTOCOL,
)
from .security_scope import RuntimeScopeObserver


class WorkerInstalledQualification(InstalledQualification):
    def verification_profile(self):
        # The side wrapper additionally reconciles actual source-controlled
        # process-policy prefixes against the neutral independently frozen pins.
        from .security_profile import build_verification_profile
        installation=self.installation
        pins=installation.get(installation._value['validation_profile_ref'])
        if (pins['assertion_manifest_ref']!=installation._value['assertion_manifest_ref']
                or pins['attack_pins_ref']!=installation._value['attack_pins_ref']
                or pins['worker_profile_refs']!=installation.scope['worker_profile_refs']):
            raise InstallationUnavailable('Independent current RSI profile pins differ')
        return build_verification_profile(installation.read,installation._value['validation_profile_ref'])


def build_worker_qualification(worker_owner,store=None,*,candidate_resolver=None):
    installation=load_installation()
    if installation is None:return None
    observer=RuntimeScopeObserver(worker_owner=worker_owner,approved_scope=installation.scope,
        runtime_capture_file=RUNTIME_OBSERVATION_FILE)
    return WorkerInstalledQualification(installation,scope_observer=observer,store=store,candidate_resolver=candidate_resolver)


class WorkerQualificationOwner:
    """Observe a later root publication in this same running worker process.

    Restarting the worker to discover an installation would invalidate its
    captured process/container identity. Every effect still loads the fixed
    installation and independently checks the complete current qualification.
    """
    def __init__(self,worker_owner,*,store=None,candidate_resolver=None):
        from .worker import WorkerBroker
        if type(worker_owner) is not WorkerBroker:raise InstallationUnavailable('Actual worker owner required')
        self.worker,self.store,self.resolver=worker_owner,store,candidate_resolver

    def current(self):
        authority=build_worker_qualification(self.worker,self.store,candidate_resolver=self.resolver)
        if authority is not None:
            from jiuwenswarm.research.contracts.rsi_installation import ORIGINALS_ROOT
            root=ORIGINALS_ROOT.resolve(strict=True)
            if root not in self.worker.public.roots:self.worker.public.roots=(*self.worker.public.roots,root)
        return authority

    def require(self,operation,**subject):
        authority=self.current()
        if authority is None:raise InstallationUnavailable('Protected RSI security installation is absent')
        return authority.require(operation,**subject)


def current_scope_handler(authority):
    """Install only as the root broker's finite current_scope RPC method."""
    if type(authority) is not WorkerInstalledQualification:
        raise InstallationUnavailable('Actual root worker installation is required')
    def observe(payload):
        installation=authority.installation;installation.assert_current()
        installation.current_runtime_observation()
        if not isinstance(payload,dict) or set(payload)!={'scope_ref'} or payload['scope_ref']!=installation.scope_ref:
            raise InstallationUnavailable('Requested producer scope is outside root approval')
        # This is an observation, not a qualification effect. Calling the full
        # authority here would recursively require its own producer socket.
        return authority.scope_observer(installation.scope)
    return observe


def scope_server(authority):
    """Return the fixed existing private RPC server; caller controls lifecycle."""
    from jiuwenswarm.research.private_rpc import PrivateRPCServer
    handler=current_scope_handler(authority)
    installation=authority.installation
    request=installation.scope_request()
    return PrivateRPCServer(SCOPE_SOCKET,protocol=SCOPE_PROTOCOL,session_id=request['session_id'],
        capability=request['capability'],handlers={'current_scope':handler},allowed_uids={0,10001,12001,12002},
        socket_mode=0o660,directory_mode=0o710,group_id=13000)


__all__=['build_worker_qualification','installed_consumer_qualification','installation_public_roots',
         'current_scope_handler','scope_server']
