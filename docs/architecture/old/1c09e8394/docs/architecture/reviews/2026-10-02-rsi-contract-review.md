# RSI contract review and corrections — 2026-10-02

This review inspected frozen master PRD4.4.9–4.4.10, frozen RSI owner §3.Y.5 and §3.Y.11, and the current RSI controller/oracle/system-record owners. These are documentation corrections; no runtime security, improvement or platform acceptance is claimed.

| Finding | Correction | Source obligation |
|---|---|---|
| Oracle evaluation required a public Candidate before its acceptance, contrary to the received gate-before-Candidate sequence | Private immutable rsi_trial and TrialRef carry exact implementation/visible-parent-suite pins; public Candidate publication follows promotable final evidence | RSI owner §3.Y.5; master PRD4.4.3 parent tests before hidden evaluation |
| Controller states closing/closed/no_candidate had no durable closed record representation | Extended rsi_session and authored private oracle_session, oracle_closure and oracle_result payloads with exact pins/evidence | Master PRD4.4.9 attributable lineage, evaluation and replay |
| Close required ablations but supplied no operation that committed closed state | close_session freezes incumbent/lineage and zero-to-five ablation schedule; finish_close verifies complete exact results and permanently seals closed state before custodian final reservation | Master PRD4.4.9 terminal-only final evaluation; RSI owner §3.Y.5 final once |
| Security blocking could be bypassed through restart/new session and had no attributable human clearance | Private target-wide incident latch; terminal rsi_security_clearance plus custodian clear_security verification; explicit resume preserves phase/pins/quota and cannot reopen uncertain/final calls | Master PRD4.4.10 security violations halt and require explicit human clearance before autonomous optimization continues |

Independent production consumer derivations were written outside the repository under `.architecture-canary-2026-10-02/consumers/` before comparison with the production plan. All eight stage required input sets matched the recorded plan; optional IntentIR remains optional and Report's StageContext is a separately scoped broker context. The benchmark-to-Evaluation and RSI-to-Admission declaration canaries agreed with other required inputs declared explicitly. These checks establish documented interface agreement only.

Downstream coding must demonstrate trial hash/coverage refusal, parent-suite hard gate, private-reference separation, forged lineage refusal, zero/partial/duplicate ablation closure, final reservation interruption, target-wide security latch persistence, unauthenticated/self-authored clearance denial and verified explicit human continuation. Architectural reason codes must remain synchronized with the owning registry when these contracts are released.
