"""Reconcile ambiguous delivery before any possible resubmission."""
import httpx
from .client import ClientError


async def _reconcile_once(client,identity):
    try:return await client.reconcile(identity)
    except ClientError as exc:
        if exc.status_code!=404:raise
        return {'delivery':'unknown','launched':True,'reconciliation':'not_found'}
    except (httpx.TransportError,TimeoutError):return {'delivery':'unknown','launched':True}


async def submit_once(client,payload,ledger,attempt_id):
    if not ledger.claim(attempt_id,payload):
        return await _reconcile_once(client,payload['client_request_id'])
    ledger.event(attempt_id,'submitting',{'client_request_id':payload['client_request_id']})
    try:
        value=await client.submit(payload)
        ledger.event(attempt_id,'acknowledged',{'response':value});return value
    except ClientError as exc:
        ledger.event(attempt_id,'refused',{'http_status':exc.status_code,'client_error':exc.response_record})
        raise
    except (httpx.TransportError,TimeoutError):
        ledger.event(attempt_id,'delivery_ambiguous',{'launched':True})
        # Exactly one read-only reconciliation. Unknown is retained, never resent.
        value=await _reconcile_once(client,payload['client_request_id'])
        ledger.event(attempt_id,'reconciled',{'response':value});return value


async def _evaluation_reconcile(client,identity):
    try:
        value=await client.evaluation_request(identity)
        return value['result'] if value['status']=='completed' and value['result'] is not None else {
            'delivery':'unknown','launched':True,'reconciliation':value['status'],'failure_ref':value['failure_ref']}
    except ClientError as error:
        if error.status_code not in {200,404}:
            error.evaluation_delivery_unknown=True
            raise
        return {'delivery':'unknown','launched':True,'reconciliation':'not_found_or_untrusted'}
    except (httpx.TransportError,TimeoutError):return {'delivery':'unknown','launched':True}


async def evaluation_once(client,entry_mode,payload,ledger,attempt_id):
    identity=payload['request_id']
    if not ledger.claim(attempt_id,{'entry_mode':entry_mode,'request':payload}):
        value=await _evaluation_reconcile(client,identity)
        ledger.event(attempt_id,'evaluation_reconciled',{'request_id':identity,'response':value});return value
    ledger.event(attempt_id,'evaluation_submitting',{'request_id':identity,'entry_mode':entry_mode})
    try:
        value=await client.evaluate(entry_mode,payload)
        ledger.event(attempt_id,'evaluation_acknowledged',{'response':value});return value
    except ClientError as error:
        if error.status_code is not None and 400<=error.status_code<500:
            ledger.event(attempt_id,'evaluation_refused',{'http_status':error.status_code,'client_error':error.response_record});raise
        # A gateway/server error can follow successful upstream dispatch and
        # even completion. Preserve the reply, reconcile the same request ID,
        # and never infer refusal or issue another POST from this response.
        ledger.event(attempt_id,'evaluation_response_ambiguous',
            {'http_status':error.status_code,'client_error':error.response_record})
    except (httpx.TransportError,TimeoutError):pass
    ledger.event(attempt_id,'evaluation_delivery_ambiguous',{'request_id':identity,'launched':True})
    value=await _evaluation_reconcile(client,identity)
    ledger.event(attempt_id,'evaluation_reconciled',{'request_id':identity,'response':value});return value
