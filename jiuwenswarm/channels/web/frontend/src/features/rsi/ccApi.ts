import { webRequest } from '../../services/webClient';
import type { CcActionReceipt, CcCandidateDetail, CcRunReceipt, CcSnapshot, CcSourceCatalog } from './ccTypes';

// Separate from legacy Harness selection/install. There is no demo fallback.
export const ccSourceTargets = () => webRequest<CcSourceCatalog>('rsi.cc.targets.list', {});
export const ccSnapshot = () => webRequest<CcSnapshot>('rsi.cc.snapshot', {});
export const ccCandidate = (nodeId: string, candidateHash: string) =>
  webRequest<CcCandidateDetail>('rsi.cc.candidate.get', { node_id: nodeId, candidate_hash: candidateHash });
export async function ccOperatorAction(action: 'admit' | 'activate', nodeId: string, candidateHash: string) {
  const receipt = await webRequest<CcActionReceipt>('rsi.cc.operator.action', {
    action,
    node_id: nodeId,
    candidate_hash: candidateHash,
  });
  if (
    receipt.action !== action ||
    receipt.node_id !== nodeId ||
    receipt.candidate_hash !== candidateHash ||
    !receipt.actor ||
    !receipt.receipt_ref?.id ||
    !/^[a-f0-9]{64}$/.test(receipt.receipt_ref.sha256)
  ) {
    throw new Error('The operator did not acknowledge this exact candidate. Refresh to reconcile.');
  }
  return receipt;
}
export async function ccStartRun(targetId: string, revision: string, clientRequestId: string) {
  const receipt = await webRequest<CcRunReceipt>('rsi.cc.run.start', {
    target_id: targetId,
    revision,
    client_request_id: clientRequestId,
  });
  const fields = ['client_request_id', 'target_id', 'revision', 'run_id', 'status', 'security_status', 'receipt_ref'];
  if (
    !receipt ||
    Object.keys(receipt).sort().join() !== fields.sort().join() ||
    receipt.client_request_id !== clientRequestId ||
    receipt.target_id !== targetId ||
    receipt.revision !== revision ||
    typeof receipt.run_id !== 'string' ||
    !receipt.run_id ||
    receipt.run_id.length > 256 ||
    receipt.status !== 'ACCEPTED_UNQUALIFIED' ||
    receipt.security_status !== 'SECURITY_DEFERRED' ||
    typeof receipt.receipt_ref?.id !== 'string' ||
    !receipt.receipt_ref.id ||
    Object.keys(receipt.receipt_ref).sort().join() !== 'id,sha256' ||
    typeof receipt.receipt_ref.sha256 !== 'string' ||
    !/^[a-f0-9]{64}$/.test(receipt.receipt_ref.sha256)
  ) {
    throw new Error(
      'The development broker did not acknowledge this exact request. Refresh to reconcile; do not repeat.',
    );
  }
  return receipt;
}
