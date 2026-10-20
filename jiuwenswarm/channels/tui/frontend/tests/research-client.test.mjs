import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ResearchClient, projectResearchWorkflow } from "../dist/core/researchClient.js";

const defaults = { account_id: "owner", workspace_id: "work", configuration_ref: { id: "config", sha256: "a".repeat(64) }, plan_source: "static", profile_id: null };
const status = { run_id: "run:1", client_request_id: "request:1", revision: 1, status: "in_progress", stage: "screening",
  candidate_refs: [{ id: "candidate", sha256: "b".repeat(64) }], accepted_refs: [], reasons: [],
  node_statuses: [{ node_id: "screening", attempt_id: "attempt:1", lifecycle_status: "Evaluating", skipped_because: null }] };

test("TUI uses Bearer at one native origin and exact source submission", async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(url.pathname.endsWith("readiness")
      ? { ready: true, client_contract_version: "1.0.0", instance_id: "instance" } : status), { status: 200 });
  };
  const client = new ResearchClient("http://private:5173", "opaque-app-token", defaults, fetcher);
  await client.submit({ id: "intake", sha256: "c".repeat(64) }, "request:1");
  assert.equal(client.wsUrl, "ws://private:5173/ws");
  assert.equal(calls.length, 2);
  assert.equal(calls[1].options.headers.get("authorization"), "Bearer opaque-app-token");
  assert.ok(!calls[1].url.href.includes("opaque-app-token"));
  const body = JSON.parse(calls[1].options.body);
  assert.equal(body.workspace_id, "work");
  assert.equal(body.interaction_mode, "interactive");
  assert.ok(!("prompt" in body));
  await assert.rejects(client.request("http://foreign.invalid/api/v1/runs"));
});

test("lost delivery reconciles by stable ID without a second POST", async () => {
  const methods = [];
  const fetcher = async (url, options) => {
    methods.push(options.method ?? "GET");
    if (url.pathname.endsWith("readiness")) return new Response(JSON.stringify({ ready: true, client_contract_version: "1.0.0", instance_id: "instance" }));
    if (options.method === "POST") throw new TypeError("Controlled lost response");
    assert.equal(url.searchParams.get("client_request_id"), "request:1");
    return new Response(JSON.stringify(status));
  };
  const client = new ResearchClient("http://private:5173", "opaque-app-token", defaults, fetcher);
  assert.equal((await client.submit({ id: "intake", sha256: "c".repeat(64) }, "request:1")).run_id, "run:1");
  assert.deepEqual(methods, ["GET", "POST", "GET"]);
});

test("candidate projection preserves Evaluating and no accepted refs", () => {
  const workflow = projectResearchWorkflow(status);
  assert.equal(workflow.completed_agent_count, 0);
  assert.equal(workflow.phases[0].description, "Evaluating");
  assert.ok(workflow.logs[0].includes('"accepted_refs":[]'));
});

for (const current of ["in_progress", "halted"]) {
  test(`finite ${current} before a node preserves empty stage and no manufactured phases`, () => {
    const reasons = current === "halted" ? ["finite_fixture"] : [];
    const workflow = projectResearchWorkflow({
      ...status, status: current, stage: "", candidate_refs: [], accepted_refs: [], reasons, node_statuses: [],
    });
    assert.equal(workflow.summary, "");
    assert.equal(workflow.status, current === "in_progress" ? "running" : "failed");
    assert.deepEqual(workflow.phases, []);
    assert.equal(workflow.agent_count, 0);
    assert.equal(workflow.completed_agent_count, 0);
    assert.deepEqual(JSON.parse(workflow.logs[0]).reasons, reasons);
    assert.ok(!JSON.stringify(workflow).includes("intention_compiler"));
  });
}

test("original-byte export uses the same authenticated route and refuses overwrite", async () => {
  const directory = await mkdtemp(join(tmpdir(), "ai4r-tui-export-"));
  const raw = new Uint8Array([80, 75, 3, 4, 0, 255, 10]);
  const fetcher = async (url, options) => {
    assert.equal(url.pathname, "/api/v1/runs/run%3A1/export");
    assert.equal(options.headers.get("authorization"), "Bearer opaque");
    assert.equal(options.headers.get("accept"), "application/zip");
    return new Response(raw, { headers: { "content-type": "application/zip" } });
  };
  try {
    const client = new ResearchClient("http://private:5173", "opaque", defaults, fetcher);
    const destination = join(directory, "original.zip");
    await client.download("run:1", destination);
    assert.deepEqual(new Uint8Array(await readFile(destination)), raw);
    await assert.rejects(client.download("run:1", destination), { code: "EEXIST" });
    await assert.rejects(client.request("/api/v1/../../foreign"));
  } finally { await rm(directory, { recursive: true, force: true }); }
});
