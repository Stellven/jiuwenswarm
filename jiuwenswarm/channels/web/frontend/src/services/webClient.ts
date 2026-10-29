import { useCodexSubscription } from '../features/codexSubscription/state';
import {
  WebConnectOptions,
  WebConnectionState,
  WebError,
  WebMessage,
  WebRequestOptions,
  WsEvent,
  WsRequest,
  WsResponse,
  FileDownloadItem,
} from '../types';
import { getWsBase } from '../utils/env';
import { resolveUserId } from '../utils/userId';
import i18n from '../i18n';
import { GoalRecord } from '../types/goal';
import { createSessionEventGate } from './sessionEventGate';
import { requestSettingsModule } from '../features/settings/settingsNavigation';
import { bootstrapResearchSession, hasResearchSession, hasLocalChat, researchRequest, submitResearchIntake, captureResearchInputs, consumeResearchInputs, migrateResearchInputs, researchWorkspace, researchAccount, rememberResearchRun, type ResearchRef } from '../utils/researchClient';
import { projectResearchWorkflow, type ResearchStatus } from '../components/teamArea/researchWorkflow';
import { hasResearchConfiguration, researchInteraction, refreshResearchRuntime, researchRunRequest } from '../utils/researchClient';

type EventHandler = (event: WsEvent) => void;
type TypedEventHandler<TPayload> = (event: WsEvent & { payload: TPayload }) => void;
type StateHandler = (state: WebConnectionState) => void;

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
  timeoutId: number;
  awaitRuntimeAccepted: boolean;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const DEFAULT_TIMEOUT_MS = 15000;

const LEGACY_EVENT_MAP: Record<string, string> = {
  connection_ack: 'connection.ack',
  content_chunk: 'chat.delta',
  content: 'chat.final',
  media_content: 'chat.media',
  file_content: 'chat.file',
  tool_call: 'chat.tool_call',
  tool_update: 'chat.tool_update',
  tool_result: 'chat.tool_result',
  error: 'chat.error',
  interrupt_result: 'chat.interrupt_result',
  subtask_update: 'chat.subtask_update',
  ask_user_question: 'chat.ask_user_question',
  todo_update: 'todo.updated',
  session_update: 'session.updated',
  processing_status: 'chat.processing_status',
  heartbeat: 'connection.heartbeat',
  security_alert: 'security.alert',
  chat_retract: 'chat.retract',
};

interface DevWsLogEntry {
  direction: 'outgoing' | 'incoming' | 'lifecycle';
  messageType?: 'req' | 'res' | 'event';
  data: unknown;
}

function logDevWsTraffic(entry: DevWsLogEntry): void {
  if (!import.meta.env.DEV) {
    return;
  }

  const body = {
    direction: entry.direction,
    messageType: entry.messageType,
    // Payloads can contain short-lived login material or user content.
    data: undefined,
    at: new Date().toISOString(),
  };

  void fetch('/__dev/ws-log', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify(body),
    keepalive: true,
  }).catch(() => {
    // 仅用于本地调试日志，失败时不影响业务逻辑
  });
}

class WebClient {
  private ws: WebSocket | null = null;
  private state: WebConnectionState = 'idle';
  private handlers = new Map<string, Set<EventHandler>>();
  private stateHandlers = new Set<StateHandler>();
  private pending = new Map<string, PendingRequest>();
  private reconnectTimer: number | null = null;
  private reconnectAttempts = 0;
  private manualClose = false;
  private connectPromise: Promise<void> | null = null;
  private connectionGeneration = 0;
  private cancelConnect: (() => void) | null = null;
  private lastConnectOptions: WebConnectOptions = {};
  private requestSeq = 0;
  private researchPolls = new Map<string, number>();
  private researchRevisions = new Map<string, number>();
  private researchSubmissions = new Map<string, { sessionId: string; requestId: string; resolvedRunId?: string; updatedAt?: string }>();
  private researchRecoveries = new Map<string, Promise<void>>();
  private researchActivity = new Map<string, { sessionId: string; stage: string }>();
  private researchReplies = new Set<string>();
  private completedResearchReplies = new Set<string>();
  private codexRequests = new Map<string, string>();
  private readonly sessionEventGate = createSessionEventGate((event) => {
    this.dispatchEventNow(event);
  });

  getState(): WebConnectionState {
    return this.state;
  }

  onStateChange(handler: StateHandler): () => void {
    this.stateHandlers.add(handler);
    return () => {
      this.stateHandlers.delete(handler);
    };
  }

  on<TPayload = Record<string, unknown>>(
    eventName: string,
    handler: TypedEventHandler<TPayload>
  ): () => void {
    const set = this.handlers.get(eventName) ?? new Set<EventHandler>();
    const eventHandler = handler as EventHandler;
    set.add(eventHandler);
    this.handlers.set(eventName, set);

    return () => {
      const target = this.handlers.get(eventName);
      if (!target) {
        return;
      }
      target.delete(eventHandler);
      if (target.size === 0) {
        this.handlers.delete(eventName);
      }
    };
  }

  suspendSessionEvents(sessionId: string): () => void {
    return this.sessionEventGate.suspend(sessionId);
  }

  async connect(options: WebConnectOptions = {}): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }
    if (this.connectPromise) {
      return this.connectPromise;
    }

    this.lastConnectOptions = options;
    this.manualClose = false;
    this.clearReconnectTimer();
    const generation = ++this.connectionGeneration;
    let resolveAttempt!: () => void;
    let rejectAttempt!: (reason: unknown) => void;
    const attempt = new Promise<void>((resolve, reject) => {
      resolveAttempt = resolve;
      rejectAttempt = reject;
    });
    const clearAttempt = () => {
      if (this.connectPromise === attempt) {
        this.connectPromise = null;
        this.cancelConnect = null;
      }
    };
    // Publish ownership before the first await: reload may have several callers.
    this.connectPromise = attempt;
    this.cancelConnect = () => {
      clearAttempt();
      rejectAttempt(this.createWebError(i18n.t('network.connectionClosed'), 'WS_CLOSED', undefined, false));
    };

    void (async () => {
      try {
        await bootstrapResearchSession();
        if (generation !== this.connectionGeneration || this.manualClose) {
          return;
        }
        this.updateState(this.reconnectAttempts > 0 ? 'reconnecting' : 'connecting');
        const url = this.buildWsUrl(options);
        const previous = this.ws;
        const ws = new WebSocket(url);
        this.ws = ws;
        if (previous && previous.readyState !== WebSocket.CLOSED) {
          previous.close(1000, 'Superseded connection');
        }
        const ownsSocket = () => generation === this.connectionGeneration && this.ws === ws;

        ws.onopen = () => {
          if (!ownsSocket()) return;
          logDevWsTraffic({ direction: 'lifecycle', data: { event: 'open', url } });
          this.reconnectAttempts = 0;
          this.updateState('ready');
          clearAttempt();
          resolveAttempt();
        };
        ws.onmessage = (event) => {
          if (ownsSocket()) this.handleIncoming(event.data);
        };
        ws.onerror = () => {
          if (!ownsSocket()) return;
          logDevWsTraffic({ direction: 'lifecycle', data: { event: 'error' } });
          if (this.state !== 'ready') {
            clearAttempt();
            rejectAttempt(this.createWebError(i18n.t('network.wsError'), 'WS_ERROR', undefined, true));
          }
        };
        ws.onclose = (closeEvent) => {
          if (!ownsSocket()) return;
          logDevWsTraffic({
            direction: 'lifecycle',
            data: {
              event: 'close',
              code: closeEvent.code,
              reason: closeEvent.reason,
              wasClean: closeEvent.wasClean,
            },
          });
          this.ws = null;
          clearAttempt();
          const error = this.createWebError(
            i18n.t('network.connectionClosedWithCode', { code: closeEvent.code }),
            'WS_DISCONNECTED',
            undefined,
            true,
          );
          rejectAttempt(error);
          this.rejectAllPending(error);
          if (this.manualClose || closeEvent.code === 1000) {
            this.updateState('closed');
            return;
          }
          this.scheduleReconnect();
        };
      } catch (error) {
        clearAttempt();
        if (!this.manualClose && generation === this.connectionGeneration) this.scheduleReconnect();
        rejectAttempt(error);
      }
    })();
    return attempt;
  }

  /**
   * 断开后立刻用同一组参数重连。
   *
   * 登录态变化时必须调这个：登录会话 id 是 **WS 握手时**从 cookie / 请求头读的，
   * 之后这条连接就一直用那份值。而登录走的是 HTTP，发生在握手之后——不重连的话，
   * 连接上停留的还是登录前那份，服务端据此取凭据会取不到，
   * 表现为"选了免费模型却跑了配置的模型"。
   */
  async reconnect(reason = 'Auth changed'): Promise<void> {
    const options = this.lastConnectOptions;
    await this.disconnect(reason);
    await this.connect(options);
  }

  disconnect(reason = 'User disconnect'): Promise<void> {
    this.manualClose = true;
    this.connectionGeneration += 1;
    this.cancelConnect?.();
    this.cancelConnect = null;
    for (const timer of this.researchPolls.values()) window.clearTimeout(timer);
    this.researchPolls.clear();
    this.clearReconnectTimer();
    this.rejectAllPending(
      this.createWebError(i18n.t('network.connectionClosed'), 'WS_CLOSED', undefined, false)
    );
    const currentWs = this.ws;
    let closedPromise = Promise.resolve();
    if (currentWs) {
      closedPromise = new Promise<void>((resolve) => {
        let finished = false;
        const finish = () => {
          if (finished) {
            return;
          }
          finished = true;
          resolve();
        };
        const timeoutId = window.setTimeout(() => {
          finish();
        }, 800);
        currentWs.addEventListener(
          'close',
          () => {
            window.clearTimeout(timeoutId);
            finish();
          },
          { once: true }
        );
        currentWs.close(1000, reason);
      });
    }
    this.ws = null;
    this.connectPromise = null;
    this.updateState('closed');
    return closedPromise;
  }

  async request<T = unknown>(
    method: string,
    params?: Record<string, unknown>,
    options: WebRequestOptions = {}
  ): Promise<T> {
    const interactionSession = typeof params?.session_id === 'string' ? params.session_id : 'new';
    const explicitUploads = Array.isArray(params?.upload_refs)
      && params.upload_refs.every((value) => typeof value === 'string') ? [...params.upload_refs] as string[] : undefined;
    const capturedInputs = method === 'chat.send' || method === 'session.create'
      ? options.researchInputSnapshot ?? captureResearchInputs(interactionSession, explicitUploads)
      : undefined;
    const inputSnapshot = capturedInputs ? { ...capturedInputs,
      uploadRefs: [...capturedInputs.uploadRefs], selectionVersions: { ...capturedInputs.selectionVersions },
      files: capturedInputs.files?.map((file) => ({ ...file })) } : undefined;
    const uploadRefs = explicitUploads ?? inputSnapshot?.uploadRefs ?? [];
    await this.ensureReady();

    const research = hasResearchSession() && method === 'chat.send' && (!hasLocalChat() || (inputSnapshot?.interaction ?? researchInteraction(interactionSession)) === 'research');
    if (research) {
      const runtime = await refreshResearchRuntime();
      if (!hasResearchConfiguration()) {
        requestSettingsModule('agent');
        throw this.createWebError(i18n.t('researchWorkflow.setupRequired'), 'RESEARCH_NOT_CONFIGURED');
      }
      if (!runtime.ready) {
        requestSettingsModule('agent');
        throw this.createWebError(i18n.t('researchWorkflow.blocked'), 'RESEARCH_NOT_READY');
      }
    }
    const localChat = hasLocalChat() && method === 'chat.send' && !research;
    if (localChat) {
      if (['signed_out', 'subscription_required'].includes(useCodexSubscription.getState().state)) {
        requestSettingsModule('models');
        throw this.createWebError(i18n.t('codexSubscription.signInFirst'), 'SIGN_IN_REQUIRED');
      }
      const sessionId = typeof params?.session_id === 'string' ? params.session_id : 'new';
      method = 'codex.chat';
      params = { ...params, session_id: sessionId, upload_refs: uploadRefs, codex_model: useCodexSubscription.getState().model || undefined, capsule_id: useCodexSubscription.getState().capsule || undefined };
    }

    if (hasResearchSession() && method === 'command.workflows') {
      const sessionId = typeof params?.session_id === 'string' ? params.session_id : 'new';
      if (params?.action === 'list') {
        await this.recoverResearchConversation(sessionId);
        // Reconnect the real background requests without adding their backend
        // execution graph to the normal conversation's workflow panel.
        return { workflows: [], total: 0, has_more: false } as T;
      }
      const status = await researchRequest<ResearchStatus>(`/api/v1/runs/${encodeURIComponent(String(params?.workflow_id))}`);
      this.followResearchRun(status, sessionId);
      const workflow = projectResearchWorkflow(status);
      if (params?.action === 'get_workflow') return { workflow, has_more: false } as T;
      if (params?.action === 'get_phase') return { phase: workflow.phases?.find((phase) => phase.id === params?.phase_id), has_more: false } as T;
      if (params?.action === 'get_agent') return { agent: workflow.phases?.flatMap((phase) => phase.agents ?? []).find((agent) => agent.id === params?.agent_id) } as T;
      throw new Error('Research workflow inspection is read-only');
    }
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw this.createWebError(i18n.t('network.connectionUnavailable'), 'WS_NOT_READY', undefined, true);
    }

    const id = this.generateRequestId();
    const subscription = useCodexSubscription.getState();
    if (subscription.enabled && !hasResearchSession()) {
      const sid = String(params?.session_id || '');
      if (method === 'chat.send') {
        if (subscription.state !== 'ready') {
          throw this.createWebError(i18n.t('codexSubscription.signInFirst'), 'SIGN_IN_REQUIRED', id, false);
        }
        params = { ...params, codex_model: subscription.model || undefined };
        this.codexRequests.set(sid, id);
      } else if (method === 'chat.interrupt') {
        params = { ...params, target_request_id: this.codexRequests.get(sid) };
      }
    }
    const timeoutMs = localChat ? 250_000 : research ? Math.max(60_000, options.timeoutMs ?? 0)
      : options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    if (research) {
      params = { ...params, workspace_id: researchWorkspace(), upload_refs: uploadRefs };
    }
    const message: WsRequest = {
      type: 'req',
      id,
      method,
      params: params ?? {},
      ...(!localChat && options.isStream ? { is_stream: true } : {}),
    };

    const response = await new Promise<T>((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        this.pending.delete(id);
        const action = method === 'session.create' ? 'createConversation'
          : method === 'chat.send' ? 'submitResearch'
          : method === 'codex.chat' ? 'receiveReply'
          : method === 'document.persist' || method === 'media.persist' ? 'attachFiles'
          : /^(config\.|locale\.|research\.preferences\.|models\.)/.test(method) ? 'loadSettings'
          : 'request';
        const message = research ? i18n.t('network.researchSubmitTimeout')
          : i18n.t('network.requestTimeoutAction', { action: i18n.t(`network.requestActions.${action}`) });
        reject(this.createWebError(message, 'REQUEST_TIMEOUT', id, true));
      }, timeoutMs);

      const pending: PendingRequest = {
        resolve: (value) => resolve(value as T),
        reject,
        timeoutId,
        awaitRuntimeAccepted: options.awaitRuntimeAccepted === true && !hasResearchSession() && !localChat,
      };
      this.pending.set(id, pending);

      if (options.signal) {
        const onAbort = () => {
          if (!this.pending.has(id)) {
            return;
          }
          window.clearTimeout(timeoutId);
          this.pending.delete(id);
          reject(this.createWebError(i18n.t('network.requestAborted'), 'REQUEST_ABORTED', id, false));
        };
        if (options.signal.aborted) {
          onAbort();
          return;
        }
        options.signal.addEventListener('abort', onAbort, { once: true });
      }

      logDevWsTraffic({
        direction: 'outgoing',
        messageType: 'req',
        data: message,
      });
      try {
        options.onRequestId?.(id);
        this.ws!.send(JSON.stringify(message));
      } catch (error) {
        window.clearTimeout(timeoutId);
        this.pending.delete(id);
        reject(error);
      }
    });
    if ((hasLocalChat() || hasResearchSession()) && method === 'session.create' && inputSnapshot) {
      const created = response as { session_id?: string };
      if (created.session_id) {
        migrateResearchInputs(created.session_id, inputSnapshot);
      }
    }
    if (localChat) {
      const reply = response as { content?: string; session_id?: string; model?: string };
      if (typeof reply?.content !== 'string' || !reply.content) throw new Error('Codex returned no reply');
      const sessionId = String(params?.session_id || 'new');
      this.dispatchEventNow({ type: 'event', event: 'chat.final', payload: {
        session_id: sessionId, content: reply.content, request_id: id,
        final_mode: 'replace_turn', model: reply.model,
      } });
      this.dispatchEventNow({ type: 'event', event: 'chat.processing_status', payload: {
        session_id: sessionId, is_processing: false,
      } });
      if (inputSnapshot) consumeResearchInputs(sessionId, { ...inputSnapshot, uploadRefs });
      return response;
    }
    if (research) {
      const qualified = response as { intake_ref?: ResearchRef };
      if (!qualified?.intake_ref) throw new Error('Native research intake was not qualified');
      const submitted = await submitResearchIntake(qualified.intake_ref, id) as unknown as ResearchStatus;
      const sessionId = typeof params?.session_id === 'string' ? params.session_id : 'new';
      if (!submitted?.run_id) throw new Error('Native research delivery could not be reconciled');
      if (inputSnapshot) consumeResearchInputs(sessionId, { ...inputSnapshot, uploadRefs });
      this.researchSubmissions.set(submitted.run_id, { sessionId, requestId: id });
      this.followResearchRun(submitted, sessionId);
      return submitted as T;
    }
    return response;
  }

  async recoverResearchConversation(sessionId: string): Promise<void> {
    if (!hasResearchSession() || sessionId === 'new') return;
    const account = researchAccount();
    const workspace = researchWorkspace();
    const key = JSON.stringify([account, workspace, sessionId]);
    const prior = this.researchRecoveries.get(key);
    if (prior) return prior;
    const recovery = (async () => {
      const value = await researchRequest<{ schema: string; session_id: string; workspace_id: string; runs: {
        run_id: string; client_request_id: string; updated_at: string; resolved_run_id: string; resolved_updated_at: string;
        request: { content: string; timestamp: string; files: { id: string; filename: string }[] }; status: ResearchStatus;
      }[] }>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/research?workspace_id=${encodeURIComponent(workspace)}`);
      if (researchAccount() !== account || researchWorkspace() !== workspace
          || value.schema !== 'ai4r-native-session-research:1' || value.session_id !== sessionId
          || value.workspace_id !== workspace || !Array.isArray(value.runs)) throw new Error('Owned conversation history unavailable');
      for (const entry of value.runs) {
        if (!entry.run_id || !entry.client_request_id || entry.status?.run_id !== entry.run_id
            || entry.status.client_request_id !== entry.client_request_id || typeof entry.request?.content !== 'string'
            || !Number.isFinite(Date.parse(entry.request.timestamp)) || !Array.isArray(entry.request.files)
            || !entry.request.files.every((file) => typeof file.id === 'string' && typeof file.filename === 'string'))
          throw new Error('Original conversation request unavailable');
        this.sessionEventGate.dispatch({ type: 'event', event: 'chat.research_message', payload: {
          session_id: sessionId, request_id: entry.client_request_id, role: 'user',
          content: entry.request.content, timestamp: entry.request.timestamp, research_files: entry.request.files,
        } });
        this.researchSubmissions.set(entry.run_id, { sessionId, requestId: entry.client_request_id,
          resolvedRunId: entry.resolved_run_id, updatedAt: entry.resolved_updated_at });
        this.followResearchRun(entry.status, sessionId);
      }
    })();
    this.researchRecoveries.set(key, recovery);
    try { await recovery; } finally { if (this.researchRecoveries.get(key) === recovery) this.researchRecoveries.delete(key); }
  }

  private followResearchRun(value: ResearchStatus, sessionId: string): void {
    const pending = this.researchSubmissions.get(value.run_id) ?? researchRunRequest(value.run_id);
    if (pending && !this.completedResearchReplies.has(value.run_id)) this.researchSubmissions.set(value.run_id, pending);
    rememberResearchRun(sessionId, value.run_id, pending?.requestId);
    const publish = (status: ResearchStatus) => {
      if (status.revision < (this.researchRevisions.get(status.run_id) ?? -1)) return;
      this.researchRevisions.set(status.run_id, status.revision);
      if (status.status === 'in_progress') {
        const submission = this.researchSubmissions.get(status.run_id);
        if (submission?.updatedAt) this.researchSubmissions.set(status.run_id, { ...submission, updatedAt: undefined });
      }
      if (status.status === 'in_progress') this.researchActivity.set(status.run_id, { sessionId, stage: status.stage });
      else this.researchActivity.delete(status.run_id);
      const active = [...this.researchActivity.values()].find((entry) => entry.sessionId === sessionId);
      this.dispatchEventNow({ type: 'event', event: 'chat.processing_status',
        payload: { session_id: sessionId, is_processing: Boolean(active), research_stage: active?.stage ?? '' } });
      if (status.status !== 'in_progress' && status.status !== 'paused') void this.finishResearchReply(status);
    };
    publish(value);
    if (this.researchPolls.has(value.run_id) || value.status !== 'in_progress') return;
    const poll = async () => {
      if (this.manualClose) { this.researchPolls.delete(value.run_id); return; }
      try {
        const current = await researchRequest<ResearchStatus>(`/api/v1/runs/${encodeURIComponent(value.run_id)}`);
        publish(current);
        if (current.status !== 'in_progress') { this.researchPolls.delete(value.run_id); return; }
      } catch {
        // Inspection reconnects using GET only. A local network interruption
        // never cancels, replays or resubmits accepted work.
        if (!hasResearchSession()) { this.researchPolls.delete(value.run_id); return; }
      }
      if (!this.manualClose) this.researchPolls.set(value.run_id, window.setTimeout(() => { void poll(); }, 1500));
    };
    this.researchPolls.set(value.run_id, window.setTimeout(() => { void poll(); }, 0));
  }

  private async finishResearchReply(status: ResearchStatus): Promise<void> {
    const pending = this.researchSubmissions.get(status.run_id);
    if (!pending || this.researchReplies.has(status.run_id)) return;
    this.researchReplies.add(status.run_id);
    const needsConfigurationRepair = status.reasons.some((reason) =>
      reason === 'check_asset_unqualified' || reason.startsWith('check_asset_unqualified:'));
    let content = i18n.t(needsConfigurationRepair
      ? 'researchWorkflow.configurationRepair'
      : 'researchWorkflow.requestIncomplete');
    let hasAcceptedReport = false;
    if (status.status !== 'completed') {
      let noContinuation = false;
      try {
        const next = await researchRequest<{ run_id: string; continuation_run_id: string | null }>(`/api/v1/runs/${encodeURIComponent(status.run_id)}/continuation`);
        if (next.run_id !== status.run_id || next.continuation_run_id === status.run_id) throw new Error('Invalid continuation');
        if (next.continuation_run_id) {
          const child = await researchRequest<ResearchStatus>(`/api/v1/runs/${encodeURIComponent(next.continuation_run_id)}`);
          if (child.run_id !== next.continuation_run_id) throw new Error('Continuation identity differs');
          this.researchSubmissions.set(child.run_id, pending);
          this.researchSubmissions.delete(status.run_id);
          this.researchReplies.delete(status.run_id);
          this.completedResearchReplies.add(status.run_id);
          this.followResearchRun(child, pending.sessionId);
          return;
        }
        noContinuation = true;
      } catch {
        content += `\n\n${i18n.t('researchWorkflow.continuationUnavailable')}`;
      }
      if (noContinuation && status.reasons.some((reason) =>
        reason === 'plan_infeasible' || reason === 'compiler_did_not_release')) {
        try {
          const result = await researchRequest<{ run_id: string;
            plan_outcome?: { outcome: string; reasons: string[] };
            compiler_outcome?: { outcome: string; reasons: string[] } }>(`/api/v1/runs/${encodeURIComponent(status.run_id)}/result`);
          const compilerHalted = status.reasons.includes('compiler_did_not_release');
          const outcome = compilerHalted ? result.compiler_outcome : result.plan_outcome;
          if (result.run_id !== status.run_id || outcome?.outcome !== (compilerHalted ? 'compiler_halted' : 'plan_infeasible')
              || !Array.isArray(outcome.reasons) || outcome.reasons.length < 1 || outcome.reasons.length > 20
              || !outcome.reasons.every((reason) => typeof reason === 'string' && reason.trim() && reason.length <= 300))
            throw new Error('Public halt explanation unavailable');
          const prefix = i18n.t(compilerHalted ? 'researchWorkflow.compilerHalted' : 'researchWorkflow.planInfeasible');
          content = `${prefix}\n\n${outcome.reasons.join('\n\n')}\n\n${i18n.t('researchWorkflow.planFilesRetained')}`;
        } catch { /* Keep the truthful generic failure when the owned explanation is unavailable. */ }
      }
    }
    try {
      if (status.status === 'completed') {
        const result = await researchRequest<{ run_id: string; report: { content: string; redacted: boolean } | null }>(`/api/v1/runs/${encodeURIComponent(status.run_id)}/result`);
        if (result.run_id !== status.run_id || !result.report?.content) throw new Error('Accepted report unavailable');
        content = result.report.redacted ? `${i18n.t('researchWorkflow.redactedReport')}\n\n${result.report.content}` : result.report.content;
        hasAcceptedReport = true;
      }
    } catch {
      content = i18n.t('researchWorkflow.reportUnavailable');
    }
    const timestamp = pending.resolvedRunId === status.run_id && pending.updatedAt
      && Number.isFinite(Date.parse(pending.updatedAt)) ? pending.updatedAt : new Date().toISOString();
    const files: FileDownloadItem[] = [];
    if (hasAcceptedReport) {
      const exportPath = `/api/v1/runs/${encodeURIComponent(status.run_id)}/export?audience=researcher`;
      files.push({ name: 'run_export.zip', size: 0, mime_type: 'application/zip',
        download_url: exportPath, download_token: '', path: exportPath });
    }
    this.sessionEventGate.dispatch({ type: 'event', event: 'chat.research_message', payload: {
      session_id: pending.sessionId, request_id: pending.requestId, role: 'assistant',
      content, timestamp, accepted: hasAcceptedReport, files,
    } });
    this.researchSubmissions.delete(status.run_id);
    this.researchReplies.delete(status.run_id);
    this.completedResearchReplies.add(status.run_id);
  }

  /**
   * 发出去就不等了——给那些正常路径上压根不会有 res 的 is_stream 请求用（目前是 command.goal
   * 的 set/resume，见 backend-requests.md #4：process_stream/_chunk_to_message 对每个 chunk
   * 无条件 type="event"，没有能产出 res 的分支，连"需要用户确认"这类失败也是走
   * goal.confirm_required 事件）。跟 request() 共用同一套就绪检查（没连上照样立刻抛错，这个
   * 检查本身不依赖等 res），区别只是不注册 pending/不设超时——没有 res 要等，也就没有"超时"
   * 这回事，真实状态全靠调用方自己订阅事件拿。
   */
  async sendFireAndForget(
    method: string,
    params?: Record<string, unknown>,
    options: { isStream?: boolean } = {}
  ): Promise<void> {
    await this.ensureReady();

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw this.createWebError(i18n.t('network.connectionUnavailable'), 'WS_NOT_READY', undefined, true);
    }

    const message: WsRequest = {
      type: 'req',
      id: this.generateRequestId(),
      method,
      params: params ?? {},
      ...(options.isStream ? { is_stream: true } : {}),
    };

    logDevWsTraffic({
      direction: 'outgoing',
      messageType: 'req',
      data: message,
    });
    this.ws.send(JSON.stringify(message));
  }

  private async ensureReady(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN && this.state === 'ready') {
      return;
    }
    await this.connect(this.lastConnectOptions);
  }

  private handleIncoming(rawData: string): void {
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawData);
    } catch {
      logDevWsTraffic({
        direction: 'incoming',
        data: { rawData, parse: 'failed' },
      });
      return;
    }

    const message = this.normalizeIncoming(parsed);
    if (!message) {
      logDevWsTraffic({
        direction: 'incoming',
        data: { parsed, normalize: 'ignored' },
      });
      return;
    }

    logDevWsTraffic({
      direction: 'incoming',
      messageType: message.type,
      data: message,
    });

    if (message.type === 'res') {
      this.resolvePending(message);
      return;
    }

    this.resolveRuntimeAcceptedPending(message);
    this.dispatchEvent(message);
  }

  private normalizeIncoming(input: unknown): WsResponse | WsEvent | null {
    if (!input || typeof input !== 'object') {
      return null;
    }
    const msg = input as Record<string, unknown>;
    const rawType = msg.type;
    if (rawType === 'res') {
      if (typeof msg.id !== 'string') {
        return null;
      }
      return {
        type: 'res',
        id: msg.id,
        ok: Boolean(msg.ok),
        payload: msg.payload,
        error: typeof msg.error === 'string' ? msg.error : undefined,
        code: typeof msg.code === 'string' ? msg.code : undefined,
      };
    }

    if (rawType === 'event') {
      const eventName = typeof msg.event === 'string' ? msg.event : '';
      if (!eventName) {
        return null;
      }
      const payload = this.normalizePayload(msg.payload);
      return {
        type: 'event',
        // Older gateways wrap control ACKs in chat.final; an ACK must never close a turn.
        event: eventName === 'chat.final' && payload.event_type === 'runtime.accepted' ? 'runtime.accepted' : eventName,
        payload,
        seq: typeof msg.seq === 'number' ? msg.seq : undefined,
        stream_id: typeof msg.stream_id === 'string' ? msg.stream_id : undefined,
      };
    }

    if (typeof rawType === 'string') {
      const mappedEvent = LEGACY_EVENT_MAP[rawType];
      if (!mappedEvent) {
        return null;
      }
      const payload = this.normalizePayload(msg.payload);
      return {
        type: 'event',
        event: mappedEvent === 'chat.final' && payload.event_type === 'runtime.accepted' ? 'runtime.accepted' : mappedEvent,
        payload,
      };
    }

    return null;
  }

  private normalizePayload(payload: unknown): Record<string, unknown> {
    if (!payload || typeof payload !== 'object') {
      return {};
    }
    return payload as Record<string, unknown>;
  }

  private resolvePending(message: WsResponse): void {
    const pending = this.pending.get(message.id);
    if (!pending) {
      return;
    }
    if (message.ok && pending.awaitRuntimeAccepted) {
      return;
    }
    window.clearTimeout(pending.timeoutId);
    this.pending.delete(message.id);

    if (message.ok) {
      pending.resolve(message.payload);
      return;
    }

    pending.reject(
      this.createWebError(
        message.error ?? i18n.t('network.requestFailed'),
        message.code,
        message.id,
        this.isRetriableCode(message.code),
        message.payload
      )
    );
  }

  private resolveRuntimeAcceptedPending(message: WsEvent): void {
    if (message.event !== 'runtime.accepted' && message.event !== 'chat.error') {
      return;
    }
    const requestId = message.payload.request_id;
    if (typeof requestId !== 'string') {
      return;
    }
    const pending = this.pending.get(requestId);
    if (!pending?.awaitRuntimeAccepted) {
      return;
    }
    window.clearTimeout(pending.timeoutId);
    this.pending.delete(requestId);
    if (message.event === 'runtime.accepted') {
      pending.resolve(message.payload);
      return;
    }
    const error =
      typeof message.payload.error === 'string'
        ? message.payload.error
        : i18n.t('network.requestFailed');
    const code = typeof message.payload.code === 'string' ? message.payload.code : undefined;
    pending.reject(this.createWebError(error, code, requestId, true, message.payload));
  }

  private dispatchEvent(event: WsEvent): void {
    this.sessionEventGate.dispatch(event);
  }

  private dispatchEventNow(event: WsEvent): void {
    const handlers = this.handlers.get(event.event);
    if (!handlers || handlers.size === 0) {
      return;
    }
    handlers.forEach((handler) => {
      handler(event);
    });
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    this.reconnectAttempts += 1;
    this.updateState('reconnecting');

    // 前 N 次使用指数退避，超过后改为固定间隔持续重试，后端恢复后能自动检测并恢复连接
    const delay =
      this.reconnectAttempts <= MAX_RECONNECT_ATTEMPTS
        ? Math.min(1000 * 2 ** (this.reconnectAttempts - 1), 30000)
        : 2000; // 每 2 秒持续尝试

    this.reconnectTimer = window.setTimeout(() => {
      void this.connect(this.lastConnectOptions).catch(() => {
        // connect owns the next bounded retry, including bootstrap failures.
      });
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private rejectAllPending(error: WebError): void {
    this.pending.forEach((entry) => {
      window.clearTimeout(entry.timeoutId);
      entry.reject(error);
    });
    this.pending.clear();
  }

  private updateState(state: WebConnectionState): void {
    this.state = state;
    this.stateHandlers.forEach((handler) => {
      handler(state);
    });
  }

  private buildWsUrl(options: WebConnectOptions): string {
    const wsBase = getWsBase();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const base = wsBase || `${protocol}//${host}`;
    const path = base.endsWith('/ws') || base.endsWith('/ws/gateway') ? '' : '/ws';
    if (hasResearchSession()) {
      const sameOrigin = `${protocol}//${host}`;
      return `${sameOrigin}/ws`;
    }
    const params = new URLSearchParams();
    if (options.provider) params.set('provider', options.provider);
    if (options.apiKey) params.set('api_key', options.apiKey);
    if (options.apiBase) params.set('api_base', options.apiBase);
    if (options.model) params.set('model', options.model);
    if (options.projectDir) params.set('project_dir', options.projectDir);
    // user_id 来自 URL ?user_id= 或 localStorage（见 utils/userId.ts），
    // 供 gateway 为 faas 注入 X-Session-Context（CreateSandbox 绑定用户标识）。
    // 浏览器 new WebSocket 无法设置自定义 header，只能走 query string。
    const userId = resolveUserId();
    if (userId) params.set('user_id', userId);
    const query = params.toString();
    const target = `${base}${path}`;
    return query ? `${target}?${query}` : target;
  }

  private generateRequestId(): string {
    this.requestSeq += 1;
    const stamp = Date.now().toString(36);
    return `req_${stamp}_${this.requestSeq}`;
  }

  private createWebError(
    message: string,
    code?: string,
    requestId?: string,
    retriable = false,
    payload?: unknown
  ): WebError {
    const error = new Error(message) as WebError;
    error.code = code;
    error.requestId = requestId;
    error.retriable = retriable;
    error.payload = payload;
    return error;
  }

  private isRetriableCode(code?: string): boolean {
    return (
      code === 'REQUEST_TIMEOUT' ||
      code === 'WS_DISCONNECTED' ||
      code === 'WS_NOT_READY'
    );
  }
}

export const webClient = new WebClient();

export async function webRequest<T = unknown>(
  method: string,
  params?: Record<string, unknown>,
  options?: WebRequestOptions
): Promise<T> {
  return webClient.request<T>(method, params, options);
}

// ── SwarmFlow workflow 分页 RPC 封装（command.workflows） ─────────

export interface WorkflowListResponse {
  type?: string;
  workflows?: unknown[];
  session_id?: string;
  total?: number;
  has_more?: boolean;
}

export interface WorkflowDetailResponse {
  type?: string;
  workflow?: unknown;
  session_id?: string;
  phase_total?: number;
  has_more?: boolean;
}

export interface WorkflowPhaseResponse {
  type?: string;
  phase?: unknown;
  session_id?: string;
  agent_total?: number;
  has_more?: boolean;
  error?: unknown;
}

export interface WorkflowAgentResponse {
  type?: string;
  agent?: unknown;
  session_id?: string;
  error?: unknown;
}

export async function requestWorkflowList(
  sessionId: string,
  offset = 0,
  limit?: number,
): Promise<WorkflowListResponse> {
  return webRequest<WorkflowListResponse>('command.workflows', {
    session_id: sessionId,
    action: 'list',
    offset,
    ...(limit == null ? {} : { limit }),
  });
}

export async function requestWorkflowDetail(
  sessionId: string,
  workflowId: string,
  phaseOffset = 0,
  phaseLimit?: number,
): Promise<WorkflowDetailResponse> {
  return webRequest<WorkflowDetailResponse>('command.workflows', {
    session_id: sessionId,
    action: 'get_workflow',
    workflow_id: workflowId,
    phase_offset: phaseOffset,
    ...(phaseLimit == null ? {} : { phase_limit: phaseLimit }),
  });
}

export async function requestPhaseAgents(
  sessionId: string,
  workflowId: string,
  phaseId: string,
  agentOffset = 0,
  agentLimit?: number,
): Promise<WorkflowPhaseResponse> {
  return webRequest<WorkflowPhaseResponse>('command.workflows', {
    session_id: sessionId,
    action: 'get_phase',
    workflow_id: workflowId,
    phase_id: phaseId,
    agent_offset: agentOffset,
    ...(agentLimit == null ? {} : { agent_limit: agentLimit }),
  });
}

export async function requestAgentDetail(
  sessionId: string,
  workflowId: string,
  phaseId: string,
  agentId: string,
): Promise<WorkflowAgentResponse> {
  return webRequest<WorkflowAgentResponse>('command.workflows', {
    session_id: sessionId,
    action: 'get_agent',
    workflow_id: workflowId,
    phase_id: phaseId,
    agent_id: agentId,
  });
}

interface GoalCommandResponsePayload {
  action?: string;
  message?: string;
  goal?: GoalRecord | null;
  record?: GoalRecord | null;
  cleared_goal?: GoalRecord | null;
  existing_goal?: GoalRecord | null;
  requested_objective?: string | null;
  code?: string | null;
}

/**
 * Goal（持续目标）控制里"有真正 res"的三个一次性动作：get/pause/clear。这三个走的是非流式
 * 一次性响应（interface.py 的 process_message()），正常应该秒回，用默认超时兜底——这里超时
 * 是真的有问题，不是误判。见 cjh/goal/Goal持续目标Web前端对接.md §4。
 * clear 成功后 goal 应视为已清空，不用 cleared_goal 兜底出一个"已清除的目标"。
 */
export async function requestGoalAction(params: {
  sessionId: string;
  action: 'get' | 'pause' | 'clear';
  /** 当前会话模式（如 'agent'），协议文档 v2 §2.1 要求带上，不要写死 'code.normal' */
  mode?: string;
}): Promise<GoalRecord | null> {
  const { sessionId, action, mode } = params;
  const payload = await webRequest<GoalCommandResponsePayload>('command.goal', {
    session_id: sessionId,
    action,
    mode: mode ?? 'agent',
  });
  if (action === 'clear') {
    return null;
  }
  return payload?.goal ?? payload?.record ?? null;
}

/**
 * set/resume：is_stream:true，抢到监听席位后正常路径上永远不会有 res——`process_stream`/
 * `_chunk_to_message`（gateway/message_handler/message_handler.py）对每个 chunk 无条件
 * `type="event"`，没有能产出 res 的分支；连"目标已存在，需要 overwrite_confirmed 确认"这类
 * 失败，协议里对应的也是 `goal.confirm_required` 事件，不是 res（见 backend-requests.md #4）。
 * 所以这两个动作干脆不等 res：发出去就返回，真实状态全靠 goal.snapshot/goal.updated 事件驱动
 * （`useWebSocket.ts` 的 `applyGoalSnapshot`），不再需要一个"等不到就超时"的 Promise。
 */
export async function sendGoalStreamCommand(params: {
  sessionId: string;
  action: 'set' | 'resume';
  objective?: string;
  mode?: string;
  modelName?: string | null;
}): Promise<void> {
  const { sessionId, action, objective, mode, modelName } = params;
  await webClient.sendFireAndForget(
    'command.goal',
    {
      session_id: sessionId,
      action,
      mode: mode ?? 'agent',
      ...(action === 'set' ? { objective, overwrite_confirmed: true } : {}),
      ...(modelName ? { model_name: modelName } : {}),
    },
    { isStream: true }
  );
}

// Expose webClient to window for debugging in development
if (import.meta.env.DEV) {
  (window as any).webClient = webClient;
}

export type { WsEvent, WebMessage };
