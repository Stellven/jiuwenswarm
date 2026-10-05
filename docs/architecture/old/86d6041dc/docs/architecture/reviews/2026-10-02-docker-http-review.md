---
type: review
status: draft
version: 1
owner: muk
sources: [../system/deployment.md, ../system/environment.md, ../system/benchmark-export.md, ../contracts/services-v1.schema.json]
provides: [review.docker_http]
consumes: [system.deployment, system.benchmark_export]
depends_on: [../system/deployment.md, ../system/benchmark-export.md]
tags: [review, m1, security]
---

# Docker and benchmark transport source audit — October 2

This is a focused author-side feasibility and consistency audit, not an independent approval or executed security validation. Deployment and transport remain draft. A fresh reviewer must inspect the connected contracts and downstream tests must validate the actual image/kernel/profile.

| Finding | Consequence and disposition |
|---|---|
| Docker default seccomp denies mounts as well as namespace creation | Corrected deployment to include required mount/umount2/pivot_root setup calls in the pinned outer profile, followed by a stacked inner denial before untrusted exec. Seccomp cannot authorize by application process name; that limit is explicit. Kernel capability checks still govern operations outside nested namespaces. |
| no-new-privileges could be misread as forbidding the fixed identity helper | No incompatible privilege acquisition is required: bootstrap/helper starts with explicitly granted identity-drop capabilities; child exec cannot regain dropped capabilities. No setuid/file-capability executable is the fallback. Added release obligation: inspect each effective capability set and NoNewPrivs state. |
| Native macOS Seatbelt and Docker Linux profiles disagreed | Corrected environment, runner and black-box compatibility page to one Linux image/profile, Linux Engine/macOS Docker Desktop. Native Seatbelt is superseded; source originals and historical reviews remain intact. |
| HTTP body/deadline settings were referenced without closed configuration entries | Added cc.benchmark.max_body_bytes=1048576 and request_timeout_s=30, policy-bounded and independent of supervised research deadline. |
| New HTTP route shapes initially missing from canonical schema | Current services-v1 now contains readiness, benchmark_profiles, export_handle and abort_request alongside benchmark_request/run_handle/export_request/export. Route definitions reference these owners. No second body shape is introduced here. |
| Model reply hash did not describe authorized byte retrieval | Complete bridge response now requires committed reply Artifact ref and matching hash; broker validates run/obs/request membership before retrieval. Child direct store access remains forbidden. |
| Process-group termination could leave detached descendants | Deployment specifies owned PID namespace init termination and reaping, plus die-with-parent behavior; downstream probe must try detached grandchildren. |

Primary evidence: [Docker seccomp](https://docs.docker.com/engine/security/seccomp/) documents clone/unshare/mount/pivot_root denials and custom profiles; [Linux no-new-privileges](https://man7.org/linux/man-pages/man2/PR_SET_NO_NEW_PRIVS.2const.html) describes exec privilege suppression and inherited state; [Bubblewrap](https://github.com/containers/bubblewrap/blob/main/README.md) describes constructed namespaces/filesystem and application responsibility for a complete policy. These support a design pattern, not a claim that a particular Docker Desktop kernel permits it.

## Remaining implementation evidence

Validate exact image digest, architecture, kernel, Docker/LSM policy, custom seccomp, nested namespace/mount setup, capability drops and helper authentication. Prove named-volume custody and secret/fixture exclusion, namespace subtree termination and direct network denial. Probe both published endpoints against host-interface leakage, bad bearer tokens, unknown fields, conflicting IDs, workload disconnect, corrupt artifact bytes and failed Gate persistence. If nested user namespaces are denied, report UNSUPPORTED_SECURITY_PROFILE without privileged/unconfined fallback. No platform success or security pass is asserted by this audit.

The scoped git diff whitespace check passed after the repairs. Schema/compiler, seam, diagram and fresh review outcomes are recorded by the parent revision's validation report.
