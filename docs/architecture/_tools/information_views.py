"""Project the canonical fixed frontend and planned/frozen DAG, with display filters."""
import re


def render(vault, *, observability=True, rsi=True):
    control = (vault / 'm1/control-flow.md').read_text(encoding='utf-8')
    graph = re.findall(r'```mermaid\s*\n(.*?)```', control, re.S)[0].rstrip()
    lines = [graph,
        '  HAR["Benchmark client: authenticated local API"] -->|"task, config and request identity"| IN',
        '  STORE["Canonical store: required capture and durable records"]',
        '  MODEL["Protected Codex bridge: private credential owner"]',
        '  EXPORT["Sealed export and authorized manifest retrieval"]',
        '  POLICY["Pinned configuration, budgets and policy"]',
        '  POLICY -->|"permitted planning limits"| PLAN',
        '  POLICY -->|"frozen enforcement inputs"| BIND',
        '  PLAN -->|"authorized bounded proposal request"| MODEL',
        '  RUN -->|"authorized work and verifier requests"| MODEL',
        '  MODEL -->|"captured proposal or typed failure"| PLAN',
        '  MODEL -->|"captured result or typed failure"| RUN',
        '  IC1 -->|"output and required capture via trusted writer"| STORE',
        '  RC -->|"requirements and required capture"| STORE',
        '  IG1 -->|"frontend Verification and release via supervisor"| STORE',
        '  RG -->|"requirement Verification and release"| STORE',
        '  SAVE -->|"immutable output and required raw capture"| STORE',
        '  COMMIT -->|"Verification then release: one trusted writer"| STORE',
        '  STORE -->|"only committed authority is replayed"| REC',
        '  PUB -->|"processed outputs and committed manifest"| STORE',
        '  STORE -->|"authorized sealed public evidence"| EXPORT',
        '  EXPORT -->|"manifest-scoped data"| VIEW',
        '  EXPORT -->|"correlated benchmark evidence"| HAR']
    if observability:
        lines += ['  VIEWS["Derived telemetry, UI progress and Data Foundation views"]',
                  '  STORE -.->|"derive views without changing authority"| VIEWS',
                  '  VIEWS -.->|"optional displays"| VIEW']
    if rsi:
        lines += ['  RSI["Offline RSI: eligible work capsules only"]',
                  '  ORACLE["Private fixture oracle"]',
                  '  ADMIT["Admission: integrity plus tested or Puppet policy"]',
                  '  ACT["Explicit human activation"]',
                  '  USER -.->|"separate offline session"| RSI',
                  '  LIB -->|"frozen parent and zero Gate mutation permission"| RSI',
                  '  RSI -->|"reserved private evaluation"| ORACLE',
                  '  ORACLE -->|"aggregate results, no hidden answers"| RSI',
                  '  RSI -->|"public Candidate without hidden fixtures"| ADMIT',
                  '  ADMIT -->|"admitted inactive candidate"| ACT',
                  '  USER -->|"explicit activation command"| ACT',
                  '  ACT -->|"future snapshots only"| LIB']
    return '```mermaid\n' + '\n'.join(lines) + '\n```'


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
