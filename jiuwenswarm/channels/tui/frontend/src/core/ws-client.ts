import WebSocket from "ws";
import type { Frame, ReqFrame, ResFrame } from "./protocol.js";
import { isResFrame } from "./protocol.js";
import { ResearchClient, projectResearchWorkflow, type ResearchStatus } from "./researchClient.js";

export type FrameHandler = (frame: Frame) => void;
export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "auth_failed"
  | "message_too_big";

interface PendingRequest {
  resolve: (frame: ResFrame) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

export class WsClient {
  private ws: WebSocket | null = null;
  private readonly url: string;
  private readonly token: string;
  private readonly userId: string;
  private handlers: FrameHandler[] = [];
  private pending = new Map<string, PendingRequest>();
  private retryCount = 0;
  private readonly maxBackoffRetries = 5;
  private readonly baseDelay = 1000;
  /**
   * 权威认证过期回调；由 index.ts 注入 ReauthenticationPort。
   * 仅在收到 close code 1008（auth_failed）时调用，表示服务端权威拒绝当前 token。
   * 非 1008 的断线、1006、5xx、普通超时不触发该回调。
   */
  onAuthExpired?: () => void;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _status: ConnectionStatus = "idle";
  private statusListeners: Array<(status: ConnectionStatus) => void> = [];
  private closeCode = 0;
  private closeReason = "";
  private researchRuns = new Map<string, { sessionId: string; status: ResearchStatus }>();
  private researchPolls = new Map<string, ReturnType<typeof setTimeout>>();

  constructor(url: string, token = "", userId = "", private readonly research: ResearchClient | null = null) {
    this.url = url;
    this.token = token;
    this.userId = userId;
  }

  get status(): ConnectionStatus {
    return this._status;
  }

  get lastCloseCode(): number {
    return this.closeCode;
  }

  get lastCloseReason(): string {
    return this.closeReason;
  }

  onStatusChange(fn: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.push(fn);
    return () => {
      this.statusListeners = this.statusListeners.filter((item) => item !== fn);
    };
  }

  onFrame(handler: FrameHandler): () => void {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter((item) => item !== handler);
    };
  }

  connect(): void {
    this.setStatus("connecting");
    this.doConnect();
  }

  disconnect(): void {
    this.clearReconnectTimer();
    for (const timer of this.researchPolls.values()) clearTimeout(timer);
    this.researchPolls.clear();
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      ws.removeAllListeners();
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    }
    this.rejectAllPending(new Error("disconnected"));
    this.setStatus("idle");
  }

  send(frame: Frame): void {
    if (this.research && frame.type === "req" && frame.method === "chat.send") {
      void this.request(frame.id, frame.method, frame.params).catch(() => {
        this.dispatchFrame({ type: "event", event: "chat.error", payload: { session_id: frame.params.session_id,
          error: "Research delivery is unavailable; inspect readiness and reconcile the request before submitting new work." } });
      });
      return;
    }
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(frame));
    }
  }

  request(
    id: string,
    method: string,
    params: Record<string, unknown>,
    timeoutMs = 30000,
    isStream = false,
  ): Promise<ResFrame> {
    if (this.research) return this.requestResearch(id, method, params, timeoutMs, isStream);
    return this.requestNative(id, method, params, timeoutMs, isStream);
  }

  private async requestResearch(id: string, method: string, params: Record<string, unknown>, timeoutMs: number, isStream: boolean): Promise<ResFrame> {
    const client = this.research!;
    let payload: unknown;
    if (method === "chat.send") {
      const qualified = await this.requestNative(id, method, { ...params, workspace_id: client.defaults.workspace_id }, timeoutMs, isStream);
      const ref = qualified.payload.intake_ref as { id: string; sha256: string } | undefined;
      if (!ref) throw new Error("Native research intake was not qualified");
      const status = await client.submit(ref, id);
      this.followResearch(status, typeof params.session_id === "string" ? params.session_id : "");
      payload = status;
    } else if (method === "research.readiness") payload = await client.readiness();
    else if (method === "research.status") payload = await client.status(String(params.run_id));
    else if (method === "research.export") payload = typeof params.output === "string" && params.output
      ? await client.download(String(params.run_id), params.output) : await client.export(String(params.run_id));
    else if (method === "research.cancel") payload = await client.cancel(String(params.run_id), String(params.request_id));
    else if (method === "command.workflows") {
      if (params.action === "list") {
        const runs = [...this.researchRuns.values()].filter((item) => item.sessionId === params.session_id);
        payload = { type: "workflow_run_list", workflows: runs.map((item) => projectResearchWorkflow(item.status)), total: runs.length, has_more: false };
      } else {
        const status = await client.status(String(params.workflow_id));
        const workflow = projectResearchWorkflow(status);
        if (params.action === "get_workflow") payload = { type: "workflow_run_detail", workflow, has_more: false };
        else if (params.action === "get_phase") payload = { phase: workflow.phases?.find((phase) => phase.id === params.phase_id), has_more: false };
        else if (params.action === "get_agent") payload = { agent: workflow.phases?.flatMap((phase) => phase.agents ?? []).find((agent) => agent.id === params.agent_id) };
        else throw new Error("Research workflow inspection is read-only");
      }
    } else return this.requestNative(id, method, params, timeoutMs, isStream);
    return { type: "res", id, ok: true, payload: payload as Record<string, unknown> };
  }

  private followResearch(value: ResearchStatus, sessionId: string): void {
    const publish = (status: ResearchStatus) => {
      if (status.revision < (this.researchRuns.get(status.run_id)?.status.revision ?? -1)) return;
      this.researchRuns.set(status.run_id, { sessionId, status });
      this.dispatchFrame({ type: "event", event: "workflow.updated", payload: { session_id: sessionId, workflow: projectResearchWorkflow(status) } });
      this.dispatchFrame({ type: "event", event: "chat.processing_status", payload: { session_id: sessionId, is_processing: status.status === "in_progress", current_task: status.stage } });
    };
    publish(value);
    if (value.status !== "in_progress" || this.researchPolls.has(value.run_id)) return;
    const poll = async () => {
      if (this._status === "idle" || this._status === "auth_failed") { this.researchPolls.delete(value.run_id); return; }
      try {
        const current = await this.research!.status(value.run_id); publish(current);
        if (current.status !== "in_progress") { this.researchPolls.delete(value.run_id); return; }
      } catch { /* Inspection retry is GET-only; never resend or cancel work. */ }
      this.researchPolls.set(value.run_id, setTimeout(() => { void poll(); }, 1500));
    };
    this.researchPolls.set(value.run_id, setTimeout(() => { void poll(); }, 0));
  }

  private requestNative(id: string, method: string, params: Record<string, unknown>, timeoutMs = 30000, isStream = false): Promise<ResFrame> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState !== WebSocket.OPEN) {
        reject(new Error(`socket not connected: ${method}`));
        return;
      }
      const frame: ReqFrame = {
        type: "req",
        id,
        method,
        timeout_ms: timeoutMs,
        params,
        ...(isStream ? { is_stream: true } : {}),
      };
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`request timeout: ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify(frame));
    });
  }

  private setStatus(status: ConnectionStatus): void {
    this._status = status;
    for (const listener of this.statusListeners) {
      listener(status);
    }
  }

  private doConnect(): void {
    const headers: Record<string, string> = {};
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }
    if (this.userId) {
      headers["X-User-Id"] = this.userId;
    }

    this.ws = new WebSocket(this.url, { headers });

    this.ws.on("open", () => {
      this.retryCount = 0;
      this.setStatus("connected");
      if (this.research) for (const run of this.researchRuns.values()) this.followResearch(run.status, run.sessionId);
    });

    this.ws.on("message", (data: WebSocket.Data) => {
      try {
        const frame = JSON.parse(data.toString()) as Frame;
        this.dispatchFrame(frame);
      } catch {
        // Ignore malformed frames.
      }
    });

    this.ws.on("close", (code: number, reason: Buffer) => {
      this.closeCode = code;
      this.closeReason = reason.toString();
      this.ws = null;

      if (code === 1008) {
        this.setStatus("auth_failed");
        this.rejectAllPending(new Error(`auth failed: ${this.closeReason}`));
        // 权威认证过期：通知 ReauthenticationPort 以 89 动作码退出（仅托管模式）。
        // 非托管模式下该回调为 undefined，状态变更为 auth_failed 后由 UI 显示错误。
        this.onAuthExpired?.();
        return;
      }

      if (code === 1009) {
        this.setStatus("message_too_big");
        this.rejectAllPending(new Error("消息过大，服务器拒绝了连接。请缩短输入内容后重试。"));
        return;
      }

      if (code === 1013) {
        this.setStatus("idle");
        this.rejectAllPending(new Error("cli channel busy"));
        return;
      }

      this.handleReconnect();
    });

    this.ws.on("error", () => {
      // The close handler runs afterwards.
    });
  }

  private dispatchFrame(frame: Frame): void {
    if (isResFrame(frame)) {
      const pending = this.pending.get(frame.id);
      if (pending) {
        clearTimeout(pending.timer);
        this.pending.delete(frame.id);
        if (frame.ok) {
          setTimeout(() => pending.resolve(frame), 0);
        } else {
          setTimeout(
            () =>
              pending.reject(
                new Error(frame.error ?? `request failed: ${frame.code ?? "unknown"}`),
              ),
            0,
          );
        }
        return;
      }
    }

    for (const handler of this.handlers) {
      try {
        handler(frame);
      } catch {
        // Ignore handler errors.
      }
    }
  }

  private handleReconnect(): void {
    this.setStatus("reconnecting");
    // Keep behavior aligned with web client:
    // use exponential backoff for the first retries, then keep retrying
    // at a fixed interval so long-running tasks can recover automatically.
    const delay =
      this.retryCount < this.maxBackoffRetries
        ? Math.min(this.baseDelay * 2 ** this.retryCount, 30000)
        : 2000;
    this.retryCount += 1;
    this.reconnectTimer = setTimeout(() => this.doConnect(), delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Cancel a specific pending request by ID.
   * Clears the timeout timer, removes the entry, and rejects the Promise.
   * Used when a command is interrupted (Ctrl+C) to clean up the WS request
   * immediately instead of waiting for timeout.
   */
  cancelRequest(id: string, reason = "cancelled"): void {
    const pending = this.pending.get(id);
    if (pending) {
      clearTimeout(pending.timer);
      this.pending.delete(id);
      pending.reject(new Error(reason));
    }
  }

  private rejectAllPending(error: Error): void {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}
