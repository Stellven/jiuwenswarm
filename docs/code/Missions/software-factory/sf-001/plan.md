# sf-001 plan
Revision 1; [TASK](TASK.md), [spec](spec.md), sf-if-001@r1.

| Block | Behavior | Paths |
| --- | --- | --- |
| B01 | Contract-backed stage pool and artifact validators; nested lineage; real process execution/evidence; dynamic graph recovery | jiuwenswarm/software_factory/ |
| B02 | Fixed STRATA acquisition, source-bound implementation patch, components, native backend entry, actual inference/comparison | software_factory/strata_* and retained source/patch artifacts |
| B03 | Existing host HTTP mounting and actual event UI; no production mock path | gateway/channel_manager/web/factory_http.py, frontend/src/features/workflowDemo/ |

| Check | Scope | Procedure / independent criterion |
| --- | --- | --- |
| V01 | Block/boundary | Backend tests: two different goals, real file validation, subprocess outcome and failure-triggered recovery, artifact custody/path rejection; no mocked inference pass |
| V02 | UI/system | Main frontend build, live backend catalog/run/events/artifact browser test via existing Sidebar; no outer scroll and real phase/error rendering |
| V03 | Connected real engineering | Execute factory on fixed STRATA revision, run component builds/tests and numerical references; inspect all subprocess logs, consumed artifact identities and graph revisions |
| V04 | Required target system | Build migrated code with actual Ascend SDK, load real device, execute real model/operator path, compare original results at same model/input/config. If unavailable, record exact missing prerequisite without passing any dependent layer |

Resource audit inspects only configured/authorized remote endpoints and model stores, never prints credentials or fabricates hosts. All independent implementation/tests continue while native resource prerequisites are blocked.
