"""Generate logical information-flow variants from the canonical production bindings."""
import json
import re


def render(vault, *, observability=True, rsi=True):
    pipeline = (vault / 'm1/pipeline.md').read_text(encoding='utf-8')
    plan = json.loads(re.search(r'```json\s*\n(.*?)```', pipeline, re.S).group(1))
    nodes = {step['step_id']: f'P{i}' for i, step in enumerate(plan['steps'])}
    lines = ['```mermaid', 'flowchart TB',
             '    USER["Researcher: question and declared local resources"]',
             '    HAR["External harness: intake proposal and config_ref"]',
             '    IN["Entry: validate, snapshot, extract source_text"]',
             '    POLICY["Configuration, policy, schemas and admitted library pins"]',
             '    VALID["Validate fixed production plan, then freeze Bindings"]',
             '    CTRL["Supervisor and runner: dispatch, resolve refs, enforce quotas"]',
             '    GATE["Gate host and CC: research.verifier"]',
             '    STORE["Canonical store: required evidence and committed records"]',
             '    MODEL["Protected bridge and Codex: authorized prompt and reply captures"]',
             '    LOCAL["CC: op.local_search"]',
             '    SCHOLAR["CC: op.scholarly_search"]',
             '    CODE["CC: op.codesearch"]',
             '    WEB["arXiv and Semantic Scholar: bounded retrieval"]',
             '    MEASURE["Confined baseline/treatment and trusted measurement"]',
             '    CONTEXT["Authorized StageContext: committed evidence references"]',
             '    PUB["Publisher: validate report and commit directory manifest"]',
             '    EXPORT["Export/retrieval: sealed manifest members and correlated evidence"]',
             '    HALT["Halt: retained evidence and explicit human recovery"]',
             '    subgraph WORK["Eight fixed production work CCs: logical input bindings"]']
    for step in plan['steps']:
        lines.append(f'        {nodes[step["step_id"]]}["CC: {step["capsule_name"]}"]')
    lines += ['    end', '    USER -->|"question and provisioned resource locators"| IN',
              '    HAR -->|"authenticated task, config, seed and request identity"| IN',
              '    IN -->|"committed intake identity"| VALID',
              '    POLICY -->|"exact versions, policy and permitted config"| VALID',
              '    VALID -->|"committed valid plan and frozen Bindings"| CTRL',
              '    CTRL -->|"reserved invocation through admitted ports"| WORK']
    for step in plan['steps']:
        for port, binding in step['inputs'].items():
            producer, payload = binding.split('.', 1)
            source = 'IN' if producer == 'launcher' else nodes[producer]
            lines.append(f'    {source} -->|"{payload} to {port}"| {nodes[step["step_id"]]}')
    lines += ['    IN -.->|"optional deterministic intent_ir hints"| P0',
              '    P1 -->|"query, documents and top_k: each query"| LOCAL',
              '    LOCAL -->|"search_hits: verbatim passages"| P1',
              '    P1 -->|"query and top_k: each query"| SCHOLAR',
              '    SCHOLAR -->|"search_hits: paper abstracts"| P1',
              '    SCHOLAR -->|"approved broker requests"| WEB',
              '    WEB -->|"paper metadata and abstracts"| SCHOLAR',
              '    P4 -->|"query, repository snapshot and top_k"| CODE',
              '    CODE -->|"code_hits: verified source ranges"| P4',
              '    P5 -->|"frozen protocol, POC bundle and resource pins"| MEASURE',
              '    MEASURE -->|"trusted samples, logs and raw evidence refs"| P5',
              '    CONTEXT -->|"authorized StageContext, not a capsule port"| P7',
              '    STORE -->|"committed permitted evidence only"| CONTEXT',
              '    CTRL -->|"authorized model requests: work or verifier"| MODEL',
              '    MODEL -->|"captured result or typed failure"| CTRL',
              '    CTRL -->|"work output and required capture publication"| STORE',
              '    CTRL -->|"committed evidence_bundle and pinned gate profile"| GATE',
              '    GATE -->|"Verification publication via supervisor writer"| STORE',
              '    STORE -->|"committed Verification and release replay"| CTRL',
              '    CTRL -->|"persist release before successor dispatch"| STORE',
              '    CTRL -->|"failure, nonpass or uncertain effect"| HALT',
              '    HALT -.->|"explicit recovery reuses committed results or records new attempt"| CTRL',
              '    P7 -->|"research_report after committed acceptance"| PUB',
              '    P4 -->|"poc_bundle_ref"| PUB',
              '    P5 -->|"benchmark_payload_ref"| PUB',
              '    CONTEXT -->|"stage_context_ref"| PUB',
              '    CTRL -->|"report release, authorized destination_ref and request_id"| PUB',
              '    PUB -->|"atomic manifest publication through store"| STORE',
              '    STORE -->|"sealed public evidence snapshot"| EXPORT',
              '    EXPORT -->|"report and authorized artifact retrieval"| USER',
              '    EXPORT -->|"benchmark_export and manifest-scoped downloads"| HAR']
    if observability:
        lines += ['    VIEWS["Derived Data Foundation, telemetry and local progress views"]',
                  '    STORE -.->|"lossless committed evidence: assemble, never rewrite"| VIEWS',
                  '    CTRL -.->|"progress notifications: not release authority"| VIEWS',
                  '    VIEWS -.->|"display and diagnostics"| USER']
    if rsi:
        lines += ['    RSI["CONDITIONAL session: required offline RSI"]',
                  '    ORACLE["Private fixture oracle: inputs/answers stay protected"]',
                  '    ADMIT["Admission: integrity plus tested or Puppet provider"]',
                  '    ACT["Explicit human activation for future snapshots"]',
                  '    USER -.->|"offline target/session request"| RSI',
                  '    POLICY -->|"frozen parent, suites and mutation policy"| RSI',
                  '    RSI -->|"private trial refs and reserved query"| ORACLE',
                  '    RSI -->|"authorized private proposal prompt"| MODEL',
                  '    MODEL -->|"private captured proposal, no hidden cases"| RSI',
                  '    ORACLE -->|"aggregate comparison and final evidence only"| RSI',
                  '    RSI -->|"eligible public Candidate, no hidden cases"| ADMIT',
                  '    USER -->|"developer-authored Candidate or allowlist"| ADMIT',
                  '    ADMIT -->|"admitted inactive RSI version"| ACT',
                  '    USER -->|"explicit activation command"| ACT',
                  '    ACT -->|"new future library snapshot, never active Binding"| POLICY']
    lines += ['    classDef cc fill:#E4F2F5,stroke:#087E8B,color:#172D45;',
              '    classDef optional fill:#FFF4DC,stroke:#A87B24,stroke-dasharray:5 4,color:#172D45;',
              '    class ' + ','.join(nodes.values()) + ',LOCAL,SCHOLAR,CODE,GATE cc;']
    if rsi:
        lines.append('    class RSI optional;')
    lines.append('```')
    return '\n'.join(lines)


def refresh(vault, check=False):
    path = vault / 'system/information-flow.md'
    text = path.read_text(encoding='utf-8')
    updated = text
    for name, obs, rsi in [('full', True, True), ('no-observability', False, True),
                            ('no-rsi', True, False), ('core', False, False)]:
        marker = f'information-{name}'
        block = f'<!-- generated:{marker} -->\n{render(vault, observability=obs, rsi=rsi)}\n<!-- /generated:{marker} -->'
        pattern = rf'<!-- generated:{marker} -->.*?<!-- /generated:{marker} -->'
        if not re.search(pattern, updated, re.S):
            raise ValueError('Missing projection marker: ' + marker)
        updated = re.sub(pattern, lambda _: block, updated, flags=re.S)
    if updated == text:
        return True
    if check:
        return False
    path.write_text(updated, encoding='utf-8', newline='\n')
    return True
