import { readFileSync, lstatSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import type { WorkflowRun, WorkflowStatus } from "./workflows.js";

export interface ResearchRef { id: string; sha256: string }
export interface ResearchDefaults {
  account_id: string; workspace_id: string; configuration_ref: ResearchRef;
  plan_source?: "static" | "planned"; profile_id?: string | null;
}
export interface ResearchStatus {
  run_id: string; client_request_id: string; revision: number; status: string; stage: string;
  candidate_refs: ResearchRef[]; accepted_refs: ResearchRef[]; reasons: string[];
  node_statuses: { node_id: string; attempt_id: string | null; lifecycle_status: string; skipped_because: string | null }[];
}

export function projectResearchWorkflow(value: ResearchStatus): WorkflowRun {
  const lifecycle: Record<string, WorkflowStatus> = { Pending: "pending", Running: "running", Evaluating: "running", Completed: "completed", Failed: "failed" };
  return { id: value.run_id, name: value.run_id, summary: value.stage,
    status: value.status === "in_progress" ? "running" : value.status === "completed" ? "completed" : value.status === "paused" ? "paused" : value.status === "cancelled" ? "stopped" : "failed",
    agent_count: value.node_statuses.length,
    completed_agent_count: value.node_statuses.filter((node) => node.lifecycle_status === "Completed").length,
    phases: value.node_statuses.map((node) => ({ id: node.node_id, name: node.node_id, description: node.lifecycle_status,
      status: lifecycle[node.lifecycle_status] ?? "failed", agents: [{ id: node.attempt_id ?? node.node_id, name: node.node_id,
        status: lifecycle[node.lifecycle_status] ?? "failed", outcome: node.lifecycle_status,
        ...(node.skipped_because ? { error: node.skipped_because } : {}) }] })),
    logs: [JSON.stringify({ candidate_refs: value.candidate_refs, accepted_refs: value.accepted_refs, reasons: value.reasons })],
  };
}

function protectedFile(path: string): string {
  const info = lstatSync(path);
  if (!info.isFile() || info.isSymbolicLink() || (process.platform !== "win32" && ((info.mode & 0o077) !== 0 || info.uid !== process.getuid?.()))) {
    throw new Error("Protected native client file is unavailable");
  }
  return readFileSync(path, "utf8").trim();
}

export class ResearchClient {
  private instanceId: string | null = null;
  constructor(readonly origin: string, readonly token: string, readonly defaults: ResearchDefaults,
    private readonly fetcher: typeof fetch = fetch) {
    const url = new URL(origin);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
      throw new Error("One protected native origin is required");
    }
    if (!token || !defaults.account_id || !defaults.workspace_id || !defaults.configuration_ref?.id
      || !/^[a-f0-9]{64}$/.test(defaults.configuration_ref.sha256)) throw new Error("Protected client defaults are incomplete");
  }

  static fromEnvironment(): ResearchClient | null {
    if (process.env.JIUWENSWARM_M1_PROFILE !== "1") return null;
    const origin = process.env.JIUWENSWARM_M1_ORIGIN;
    const tokenPath = process.env.JIUWENSWARM_M1_TOKEN_FILE;
    const defaultsPath = process.env.JIUWENSWARM_M1_CLIENT_CONFIG;
    if (!origin || !tokenPath || !defaultsPath) throw new Error("Protected research client configuration is unavailable");
    return new ResearchClient(origin, protectedFile(tokenPath), JSON.parse(protectedFile(defaultsPath)) as ResearchDefaults);
  }

  get wsUrl(): string {
    const value = new URL("/ws", this.origin); value.protocol = value.protocol === "https:" ? "wss:" : "ws:";
    return value.href;
  }

  private async response(path: string, options: RequestInit = {}): Promise<Response> {
    if (!path.startsWith("/api/v1/") || path.includes("\\")) throw new Error("Unsupported research operation");
    const url = new URL(path, this.origin);
    if (url.origin !== new URL(this.origin).origin || !url.pathname.startsWith("/api/v1/")) throw new Error("Foreign research origin refused");
    const headers = new Headers(options.headers); headers.set("Authorization", `Bearer ${this.token}`);
    if (typeof options.body === "string") headers.set("Content-Type", "application/json");
    const response = await this.fetcher(url, { ...options, headers, redirect: "error", signal: AbortSignal.timeout(30000) });
    if (!response.ok) {
      const error = new Error(`Research operation failed (${response.status})`) as Error & { status: number };
      error.status = response.status; throw error;
    }
    return response;
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    return await (await this.response(path, options)).json() as T;
  }

  async readiness() {
    const value = await this.request<{ ready: boolean; instance_id: string; client_contract_version: string }>("/api/v1/readiness");
    if (value.client_contract_version !== "1.0.0" || (this.instanceId !== null && value.instance_id !== this.instanceId)) {
      throw new Error("Research target or contract changed");
    }
    this.instanceId = value.instance_id; return value;
  }

  async submit(intakeRef: ResearchRef, clientRequestId: string): Promise<ResearchStatus> {
    if (!(await this.readiness()).ready) throw new Error("Research execution is not ready");
    const value = { schema_version: "1.0.0", id: clientRequestId, client_request_id: clientRequestId,
      ...this.defaults, intake_ref: intakeRef, plan_source: this.defaults.plan_source ?? "static", interaction_mode: "interactive" };
    try { return await this.request<ResearchStatus>("/api/v1/runs", { method: "POST", body: JSON.stringify(value) }); }
    catch (original) {
      const status = (original as { status?: number }).status;
      if (status && status >= 400 && status < 500) throw original;
      const found = await this.request<ResearchStatus>(`/api/v1/runs?client_request_id=${encodeURIComponent(clientRequestId)}`);
      if (!found || Array.isArray(found) || !found.run_id || found.client_request_id !== clientRequestId) throw original;
      return found;
    }
  }

  status(runId: string) { return this.request<ResearchStatus>(`/api/v1/runs/${encodeURIComponent(runId)}`); }
  cancel(runId: string, requestId: string) {
    return this.request(`/api/v1/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST", body: JSON.stringify({ request_id: requestId }) });
  }
  export(runId: string) { return this.request(`/api/v1/runs/${encodeURIComponent(runId)}/export`); }
  async download(runId: string, destination: string) {
    const response = await this.response(`/api/v1/runs/${encodeURIComponent(runId)}/export`, { headers: { Accept: "application/zip" } });
    if (!(response.headers.get("content-type") ?? "").includes("application/zip")) throw new Error("Original-byte export is unavailable");
    const data = new Uint8Array(await response.arrayBuffer());
    await writeFile(destination, data, { flag: "wx", mode: 0o600 });
    return { run_id: runId, destination, bytes: data.length };
  }
}
