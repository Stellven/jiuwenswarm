type Ref = { id: string; sha256: string };
type Status = { run_id: string; revision: number; stage: string; status: string; candidate_refs: Ref[]; accepted_refs: Ref[]; reasons: string[] };
type NamedFile = { path: string; artifact_ref: Ref; media_type: string };
type Readiness = { schema_version: string; client_contract_version: string; ready: boolean; instance_id: string; build_id: string; ext: { 'm0.intent': { profile_id: string; account_id: string; workspace_id: string; invalid_for_product: boolean } }; prerequisites: { name: string; status: string; reason: string }[] };
const translations: Record<string, Record<string, string>> = {
  en: { eyebrow: 'AI4Research · compiler', title: 'From request to research brief', intro: 'Inspect the interpretation, checks and released brief in one place.', language: 'Language', connection: 'Connection', token: 'Operator token', connect: 'Check readiness', tokenHelp: "The token stays in this tab’s memory.", smoke: 'Fixture smoke mode · invalid for product acceptance. These outputs do not establish semantic model quality.', requestHeading: 'Research request', request: 'Objective, expected result and boundaries', documents: 'Local reference documents · one path per line', resources: 'Resources · JSON list with path, role and required', requestId: 'Client request ID · keep this for reconnection', submit: 'Compile request', reconcile: 'Find existing request', disconnect: 'Closing this tab leaves server work running. Use Cancel to stop new work.', runHeading: 'Run and decisions', cancel: 'Cancel', download: 'Download evidence', candidates: 'Candidates · not released', accepted: 'Durably accepted outputs', inspection: 'Named evidence', inspectionHelp: 'Select a record to inspect its purpose, scope, constraints, defaults, uncertainty and gate findings.', manifest: 'Manifest and missing evidence', ready: 'Ready', blocked: 'Prerequisites unavailable', connectFirst: 'Check readiness first.', expired: 'Monitoring stopped after 10 minutes. Find the existing request to reconnect.', recordBinary: 'This binary record is available in the evidence download.', noRecords: 'No records yet.' },
  zh: { eyebrow: 'AI4Research · 意图编译器', title: '将研究请求转为研究简报', intro: '在同一页面检查解释、验证和已发布的研究简报。', language: '语言', connection: '连接', token: '操作员令牌', connect: '检查就绪状态', tokenHelp: '令牌仅保留在此标签页的内存中。', smoke: '模拟测试模式 · 不可用于产品验收。此输出不能证明模型的语义质量。', requestHeading: '研究请求', request: '目标、预期结果和边界', documents: '本地参考文档 · 每行一个路径', resources: '资源 · 包含 path、role 和 required 的 JSON 列表', requestId: '客户端请求 ID · 保留以便重新连接', submit: '编译请求', reconcile: '查找已有请求', disconnect: '关闭标签页不会停止服务器任务。使用取消按钮停止新的执行。', runHeading: '运行与决策', cancel: '取消', download: '下载证据', candidates: '候选输出 · 尚未发布', accepted: '持久化验收记录', inspection: '命名证据', inspectionHelp: '选择记录以查看目的、范围、约束、默认值、不确定项和门控结果。', manifest: '清单与缺失证据', ready: '已就绪', blocked: '执行前提不可用', connectFirst: '请先检查就绪状态。', expired: '监控已在十分钟后停止。查找已有请求即可重新连接。', recordBinary: '此二进制记录可在证据下载中查看。', noRecords: '尚无记录。' }
};
let language = 'en';
let token = '';
let ready: Readiness | null = null;
let active: Status | null = null;
let watch = 0;
const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const val = (id: string) => el<HTMLInputElement>(id).value;
const t = (key: string) => translations[language][key] || key;
const terminal = new Set(['completed', 'halted', 'cancelled', 'paused', 'blocked', 'rejected']);
function error(message: string) { el('error').textContent = message; el('error').dataset.variant = message ? 'error' : 'idle'; }
async function api(path: string, body?: unknown): Promise<any> {
  const response = await fetch('/api/v1' + path, { method: body === undefined ? 'GET' : 'POST', headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || response.statusText);
  return data;
}
function refs(id: string, values: Ref[]) {
  const list = el(id); list.replaceChildren();
  for (const ref of values) { const item = document.createElement('li'); item.textContent = ref.id + ' · ' + ref.sha256; item.dataset.testid = 'intent-trial-reference'; item.dataset.variant = ref.id; list.append(item); }
}
async function inspect(file: NamedFile) {
  if (!active) return;
  el('record-name').textContent = file.path;
  if (!file.media_type.includes('json') && !file.media_type.startsWith('text/')) { el('record').textContent = t('recordBinary'); return; }
  const response = await fetch('/api/v1/runs/' + active.run_id + '/artifacts/' + encodeURIComponent(file.artifact_ref.id), { headers: { Authorization: 'Bearer ' + token } });
  if (!response.ok) throw new Error((await response.json()).message);
  const text = await response.text();
  el('record').textContent = file.media_type.includes('json') ? JSON.stringify(JSON.parse(text), null, 2) : text;
}
async function refreshFiles() {
  if (!active) return;
  const manifest = await api('/runs/' + active.run_id + '/manifest');
  el('manifest').textContent = JSON.stringify(manifest, null, 2);
  const files = el('files'); files.replaceChildren();
  for (const file of manifest.files as NamedFile[]) { const item = document.createElement('li'); item.dataset.testid = 'intent-trial-file'; item.dataset.variant = file.artifact_ref.id; const button = document.createElement('button'); button.textContent = file.path; button.dataset.testid = 'intent-trial-file-open'; button.dataset.variant = file.artifact_ref.id; button.onclick = () => { inspect(file).catch(e => error(String(e))); }; item.append(button); files.append(item); }
}
function show(data: Status) {
  if (active && active.run_id === data.run_id && data.revision < active.revision) throw new Error('Stale status revision');
  active = data; el('run-id').textContent = data.run_id;
  el('status').textContent = data.stage + ' · ' + data.status; el('status').dataset.variant = data.status;
  el('reasons').textContent = data.reasons.join('\n'); refs('candidates', data.candidate_refs); refs('accepted', data.accepted_refs);
  el<HTMLButtonElement>('cancel').disabled = terminal.has(data.status); el<HTMLButtonElement>('download').disabled = false;
}
async function monitor(initial: Status) {
  const generation = ++watch; const deadline = Date.now() + 600000; show(initial); await refreshFiles();
  while (generation === watch && !terminal.has(active!.status)) {
    if (Date.now() > deadline) { error(t('expired')); break; }
    await new Promise(resolve => setTimeout(resolve, 1000));
    if (generation !== watch) break;
    show(await api('/runs/' + initial.run_id)); await refreshFiles();
  }
}
el<HTMLFormElement>('connect').onsubmit = async event => {
  event.preventDefault(); error(''); token = val('token'); el<HTMLInputElement>('token').value = '';
  try { ready = await api('/readiness'); if (ready!.schema_version !== '1.0.0' || ready!.client_contract_version !== '1.0.0') throw new Error('Unsupported client contract'); el('readiness').textContent = (ready!.ready ? t('ready') : t('blocked')) + '\n' + ready!.prerequisites.map(p => p.name + ': ' + p.status + ' — ' + p.reason).join('\n'); el('readiness').dataset.variant = ready!.ready ? 'ready' : 'blocked'; el('smoke').hidden = !ready!.ext['m0.intent'].invalid_for_product; el<HTMLButtonElement>('submit-button').disabled = !ready!.ready; } catch (e) { ready = null; error(String(e)); }
};
el<HTMLFormElement>('submit').onsubmit = async event => {
  event.preventDefault(); error(''); if (!ready) { error(t('connectFirst')); return; }
  const requestId = val('request-id');
  try { const submission = { schema_version: '1.0.0', id: 'submission-' + requestId, client_request_id: requestId, account_id: ready.ext['m0.intent'].account_id, workspace_id: ready.ext['m0.intent'].workspace_id, profile_id: ready.ext['m0.intent'].profile_id, expected_instance_id: ready.instance_id, expected_build_id: ready.build_id, client_contract_version: '1.0.0', request: val('request'), documents: val('documents').split('\n').map(p => p.trim()).filter(Boolean).map(path => ({ path, required: true })), resources: JSON.parse(val('resources')) }; const data = await api('/runs', submission); await monitor(data); } catch (e) { error(String(e)); }
};
el('reconcile').onclick = () => { error(''); monitorFromRequest().catch(e => error(String(e))); };
async function monitorFromRequest() { const data = await api('/requests/' + encodeURIComponent(val('request-id'))); await monitor(data); }
el('cancel').onclick = async () => { if (!active) return; try { const requestId = crypto.randomUUID(); await api('/runs/' + active.run_id + '/cancel', { schema_version: '1.0.0', id: 'cancel-' + requestId, request_id: requestId, run_id: active.run_id }); show(await api('/runs/' + active.run_id)); await refreshFiles(); } catch (e) { error(String(e)); } };
el('download').onclick = async () => { if (!active) return; try { const response = await fetch('/api/v1/runs/' + active.run_id + '/bundle', { headers: { Authorization: 'Bearer ' + token } }); if (!response.ok) throw new Error((await response.json()).message); const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = active.run_id + '.zip'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); } catch (e) { error(String(e)); } };
el<HTMLSelectElement>('language').onchange = () => { language = val('language'); document.documentElement.lang = language; document.querySelectorAll<HTMLElement>('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n!); }); };
el<HTMLInputElement>('request-id').value = crypto.randomUUID();
