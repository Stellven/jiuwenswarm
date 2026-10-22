// Headless frontend contract prototype. No React/browser integration is claimed.
export const scopeFields = ['session_id', 'execution_id', 'thread_id', 'turn_id', 'generation'];
export const ticketFields = [...scopeFields, 'request_id', 'call_id', 'ticket'];

function validTicket(value) {
  return value && typeof value === 'object' &&
    ticketFields.every((key) => key === 'generation'
      ? Number.isSafeInteger(value[key]) && value[key] >= 0
      : typeof value[key] === 'string' && value[key].length > 0);
}

export class ApprovalController {
  constructor(scope) {
    this.scope = { ...scope };
    this.ready = true;
    this.state = 'idle';
    this.notice = null;
    this.revision = 0;
    this.seen = new Set();
  }

  get buttonsEnabled() { return this.ready && this.state === 'pending'; }

  receive(notice) {
    if (!this.ready || !validTicket(notice) || notice.kind !== 'tool_approval' ||
        typeof notice.tool_name !== 'string' || !notice.tool_name ||
        scopeFields.some((key) => notice[key] !== this.scope[key]) || this.seen.has(notice.ticket)) {
      return false;
    }
    // A second request must not silently replace an unresolved displayed one.
    if (['pending', 'sending', 'delivery_unknown'].includes(this.state)) return false;
    this.notice = Object.fromEntries([...ticketFields, 'tool_name', 'kind'].map((key) => [key, notice[key]]));
    this.seen.add(notice.ticket);
    this.revision += 1;
    this.state = 'pending';
    return true;
  }

  changeContext(scope, ready) {
    this.revision += 1;
    this.scope = { ...scope };
    this.ready = ready === true;
    this.notice = null;
    this.state = this.ready ? 'expired' : 'signed_out';
  }

  async decide(approved, send) {
    if (typeof approved !== 'boolean' || !this.buttonsEnabled) return false;
    const payload = Object.fromEntries(ticketFields.map((key) => [key, this.notice[key]]));
    payload.approved = approved;
    const revision = this.revision;
    this.state = 'sending'; // Disable both buttons before awaiting the transport.
    try {
      const result = await send(payload);
      if (revision !== this.revision) return false;
      if (result?.accepted === true && result.ticket === payload.ticket) {
        this.state = 'resolved';
        return true;
      }
      this.state = ['STALE_OPERATION', 'CLOSED'].includes(result?.code) ? 'expired' : 'delivery_unknown';
    } catch {
      if (revision === this.revision) this.state = 'delivery_unknown';
    }
    return false; // No automatic retry when delivery is uncertain.
  }
}
