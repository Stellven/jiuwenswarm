# AI4Research 完整开发文档合订本 v2（中文版）

完整中文译本，包含中文入口。更新日期：2026-09-30。

TASKS → TASK → 每个 TASK 一套 Spec Kit。

本合订本完整覆盖流程指南、模板、示例、仓库指令、未来 M1 骨架及文档检查记录。源文件仍是可编辑的权威记录；本文件为阅读译本。文件名、命令、代码、ID 和状态值保留原样，方便执行与对照。文档完备不代表 M1 已实现或通过运行验证。

[中文入口](README.md) | [英文合订本](AI4Research_Documentation_v2.md)

## 目录
1. [AI4Research 开发 SOP v2](#document-1)
2. [验证体系：block、连接边界与整个系统](#document-2)
3. [AI4Research 开发文档入口 v2](#document-3)
4. [TASKS：[PROGRAM-ID]](#document-4)
5. [TASK：[TASK-ID] — [标题]](#document-5)
6. [验证运行：[RUN-ID]](#document-6)
7. [功能规格：[TASK-ID - FEATURE NAME]](#document-7)
8. [实施方案：[TASK-ID - FEATURE]](#document-8)
9. [工作项：[TASK-ID - FEATURE]](#document-9)
10. [TASKS / TASK 的 Spec Kit 工作流程](#document-10)
11. [Git 与集成](#document-11)
12. [v2 提前准备与迁移](#document-12)
13. [SOP v2 仓库 AGENTS 模板](#document-13)
14. [模块/子目录 AGENTS 模板](#document-14)
15. [AI4Research 仓库指令](#document-15)
16. [AI4Research Constitution](#document-16)
17. [TASKS：M1](#document-17)
18. [完整示例：一个小项目、两个 TASK](#document-18)
19. [TASKS：DEMO](#document-19)
20. [TASK：DEMO-001 — 规范化执行者标签](#document-20)
21. [TASK：DEMO-SYSTEM — 验证完整标签链路](#document-21)
22. [功能规格：DEMO-001 — 标签规范化](#document-22)
23. [实施方案：DEMO-001](#document-23)
24. [工作项：DEMO-001](#document-24)
25. [功能规格：DEMO-SYSTEM](#document-25)
26. [实施方案：DEMO-SYSTEM](#document-26)
27. [工作项：DEMO-SYSTEM](#document-27)
28. [完整文档目录 — SOP v2](#document-28)
29. [文档验证记录](#document-29)

---

<a id="document-1"></a>

## 1. AI4Research 开发 SOP v2

对应源文件: [docs/code/Code_SOP.md](Code_SOP.md)

<a id="document-1-heading-0"></a>

### AI4Research 开发 SOP v2
修订日期：2026-09-29。在 M1 的 PRD 和架构仍在编写时，提前准备完整的开发流程。

<a id="document-1-heading-1"></a>

#### 1. 层级
**TASKS → TASK → 每个 TASK 一个 Spec Kit 功能目录。**

- TASKS 是项目总登记表：登记输入基线、需求分配、任务依赖图、接口索引和系统验证。
- TASK 是任务身份证和入口：登记执行者、范围、原生产物的准确路径、依赖，以及内嵌的跨模块约定。
- Spec Kit 是工作核心：spec.md 定义验收；plan.md 定义技术设计和验证步骤；tasks.md 保存有序工作项、进度和验收—证据对照表。
- 证据保存在该功能目录内，记录实际验证结果，不承担另一份任务清单的职责。

大写 TASKS.md 是项目总登记表。小写 tasks.md 是单个任务的原生工作清单。每个检出目录只安装一次 Spec Kit；每个 TASK 拥有独立的功能目录，无须分别安装工具。

TASK 是逻辑上的任务单元，TASK.md 是入口文件。功能规格 spec.md、实施方案 plan.md、工作项 tasks.md 和证据都归属于这个 TASK，但实体上是登记在其 Spec Kit 目录中的独立文件。TASK.md 链接到它们，不把这些文件的全文嵌入自身。

不再设置独立的开工授权卡、实施清单、测试报告卡、审查卡、交接卡、变更申请卡，也不保留手动 DESIGN/PLAN 流程分支。用户要求的工作范围直接记录在 TASK 中。本流程不增加审查人分配或审批阶段。实际执行外部操作时，仍须遵守平台权限和用户的明确指令。

<a id="document-1-heading-2"></a>

#### 2. 每类事实的唯一权威来源
| 信息 | 权威来源 |
| --- | --- |
| 产品意图和完整 M1 范围 | 已登记的主 PRD |
| 系统结构与架构节点 | 已登记的总体架构 |
| 输入基线、需求分配、任务依赖图 | TASKS.md |
| 任务身份、执行者、范围和产物路径 | TASK.md |
| 跨模块约定 | 定义该约定的 TASK 接口章节，带 IF ID 和修订版本 |
| 任务要求、AC 和可度量阈值 | 原生 spec.md |
| 技术设计、block 边界和验证步骤 | 原生 plan.md |
| 工作进度及 AC → block → 检查 → 证据对照表 | 原生 tasks.md |
| 实际执行中观察到的结果 | 功能目录中的 evidence/RUN-ID.md 及原始产物 |

PRD 与 spec.md 属于相互关联的层级。范围内每条 PRD 条款都必须通过 TASKS 对应到一个或多个有明确归属的 AC。每个 AC 只归属于一份 spec。一条条款拆给多个任务时，必须覆盖全部组成部分。spec 不得悄悄缩小已登记 PRD 的范围，也不得与之矛盾。

TASKS 引用任务进度，不复制工作项复选框。TASK 引用原生验收要求，不重复维护 AC 表。plan 引用 TASK 约定，不重新定义。生成的 schema 或 contracts/ 文件实现所属约定，并携带对应 IF ID 和修订版本。

<a id="document-1-heading-3"></a>

#### 3. 路径和标识
建议采用以下仓库布局：
```text
docs/tasks/M1/TASKS.md
docs/tasks/M1/M1-001/TASK.md
docs/tasks/M1/M1-SYSTEM/TASK.md
specs/M1-001-slug/{spec.md,plan.md,tasks.md,evidence/}
specs/M1-SYSTEM-slug/{spec.md,plan.md,tasks.md,evidence/}
```
使用带任务限定的 ID：M1-001/AC-001、M1-001/B01、M1-001/V01 和 M1-001/T001。接口 ID 在整个项目内唯一，例如 M1-IF-001@r1。废弃的 ID 不得重新用于其他含义。

每个 TASK 有一位负责的执行者，可以列出协作者；不建立单独的 role 分类。一个任务可以跨模块，一个模块也可以拆成多个任务。按边界明确、可验证的行为及其依赖拆分。

<a id="document-1-heading-4"></a>

#### 4. 最终输入到位前的准备
现在即可建立文档骨架。尚未提供的 PRD、架构、模型清单、预算或阈值标为 PENDING_SOURCE，并注明受影响工作及解决条件。这是正常的准备状态，不要求先完成队友手中的任务，也不要求先跑试点。

输入到位后：
1. 登记真实路径、版本、内容哈希和大小。
2. 为输入条款与架构节点赋予稳定 ID，或提供准确的章节定位。
3. 将范围内每条条款分配给 TASK 和 AC；记录被排除的内容及原因。
4. 建立依赖关系，把约定写入负责定义它的 TASK。
5. 在依赖这些定义的实施开始前，补全该任务的 spec、plan、工作项和证据对照表。
6. 通过系统 TASK，在集成候选版本上验证完整 M1。

不要在缺少需求时虚构正式任务拆分。完整示例仅供说明。现有任务记录保留为历史证据，不构成本次准备工作的前置门槛。

<a id="document-1-heading-5"></a>

#### 5. 工作循环
1. 从 TASKS 定位 TASK，读取其原生产物和依赖。
2. 定义可观察的 AC、失败行为及适用的非功能阈值。
3. 规划实施 block、受影响文件、接口约定、测试输入和验证方法。
4. 生成原生工作项及对照表。每个 AC 都要关联实施与验证；每项必需检查都要有独立定义的预期结果。
5. 逐块实现、逐块验证。保留证据、修复失败，并沿依赖图推进。某块受阻时，无关的独立 block 可以继续。
6. 连接 block，验证真实提供方与消费方之间的边界。
7. 通过系统 TASK 验证完整 M1 用户链路及系统约束。
8. 更新同一套原生记录，由这些记录推导项目进度。

这是开发循环，不是一串审批卡。AI 分析用于发现不一致；运行证据用于证明行为。

<a id="document-1-heading-6"></a>

#### 6. TASK 内的跨模块约定
每个接口定义由一个 TASK 持有。其接口章节明确提供方与消费方、输入输出结构及语义、校验规则、错误状态、超时/重试/取消、副作用与幂等性、兼容性和边界验证。使用 N/A 时解释原因。

消费方引用定义方及版本，不平行维护另一份定义。区分接口定义依赖与实现依赖，以便识别并解决循环依赖。

接口变更记入定义方 TASK 的变更表，更新受影响消费方，并使相关证据失效。未知细节只阻塞依赖它的工作。

<a id="document-1-heading-7"></a>

#### 7. 验证与完成
遵循[验证体系](#document-2)。
- 工作项打勾表示该工作已执行，不代表验收通过。
- AC 只有在全部必需检查均有有效 PASS 证据时才通过。
- TASK 完成要求必需工作、AC 和边界验证全部通过，且没有使结论失效的未解决依赖。
- M1 完成要求输入分配完整、必需任务对当前候选版本的验证有效，并且系统 TASK 在同一候选版本上通过。
- NOT_RUN、BLOCKED、FAIL、STALE 均不是 PASS。排除某项需要已记录的范围依据，不能借此抹去失败。

完成状态由证据决定，不另设审查与收口阶段。

<a id="document-1-heading-8"></a>

#### 8. 大型输入、变更与续接
保留完整的 100–200 KB 输入文件，但为每个功能目录提供其相关条款、架构节点、接口约定和周边约束。摘要不能替代源文件覆盖。TASKS 用于发现分片之间的遗漏。

使用稳定的定位标识和版本，使会话重启后仍可继续工作。维护总体架构视图和可读的模块/交互视图，并通过节点 ID 关联。一张图本身不能完整定义接口语义。

需求改变时，更新基线和分配、相关约定及原生产物。记录受影响的 AC/block/check ID，把对应证据标为 STALE。普通进度变化只更新 tasks.md。保留旧运行记录，并指明当前有效证据。

尽早集成相互依赖的 block。整体验收仍覆盖全部 M1；较小的实施单元不会缩减总范围。

<a id="document-1-heading-9"></a>

#### 9. 模板与工具
遵循[文档目录](#document-28)中的表格结构，保留必需字段，对 N/A 给出合理解释，并记录未解决条件。

项目原生模板放在 .specify/templates/overrides/，在本流程中覆盖上游“测试可选”的默认设定。阅读 [Spec Kit 工作流程](#document-10)和 [Git 工作方式](#document-11)。生成的命令不得覆盖用户明确的 no-commit 指令。

---

<a id="document-2"></a>

## 2. 验证体系：block、连接边界与整个系统

对应源文件: [docs/code/code_sop/VERIFICATION.md](code_sop/VERIFICATION.md)

<a id="document-2-heading-0"></a>

### 验证体系：block、连接边界与整个系统
版本 2，2026-09-29。本文件替换旧测试规范及测试报告/实施清单流程，定义未来 M1 的验证方式，不宣称应用已经就绪。

<a id="document-2-heading-1"></a>

#### 1. 定义 block
block 是一段边界明确的行为，具备已定义输入、可观察输出或状态变化、失败语义和可执行检查。它可以是函数、服务、流程步骤或小型连接组件。文件名本身不是 block 定义。

在 plan.md 中定义 block 并关联 spec.md 的 AC。实施和验证工作写入 tasks.md，实际结果附在 evidence/。不需要平行维护实施清单或报告。

<a id="document-2-heading-2"></a>

#### 2. 验证层级
| 层级 | 必须证明的结论 | 代表性检查 | 结论边界 |
| --- | --- | --- | --- |
| BLOCK | 单个 block 实现规定行为 | 正常、边界和非法输入；状态不变量；相关失败与恢复路径 | 桩实现可隔离依赖，不能证明真实连接 |
| BOUNDARY | 连接的 block 遵守 TASK 中的约定 | 真实序列化和字段语义、兼容性、超时/错误传播、重复调用 | 测试输入本身不能证明外部服务可用 |
| SYSTEM | 集成候选版本满足 M1 | 完整链路、适用的持久化/重启、恢复、质量、预算、成本和延迟 | 局部演示或全绿的 block 测试不能证明整个 M1 |

单元测试、集成测试、端到端测试、评估、静态检查和可复现的人工检查都是验证方法，不是新增流程阶段。文档任务需要相关的文档检查，不需要运行无关应用测试。

<a id="document-2-heading-3"></a>

#### 3. 执行前定义每项检查
对每个 V ID，plan.md 记录层级、block/IF ID、AC 引用、测试输入、依赖模式（桩/本地真实/外部真实）、预期结果、阈值来源、命令和工作目录或准确人工步骤、前置条件及保留产物。

选择适用的正常、边界、失败和恢复场景，说明省略原因。预期结果必须来自要求或独立定义的测试输入，不能照抄实现算法。修复缺陷时，优先提供能够复现缺陷的回归用例。

缺失的阈值、schema 或服务继续保留为未解决项。独立准备可以继续，依赖这些信息的验证不能通过。

<a id="document-2-heading-4"></a>

#### 4. block 工作循环
1. 阅读 block 的 AC 和接口依赖。
2. 以小步方式建立检查与实现。
3. 执行检查，保留运行记录和原始输出。
4. 在 tasks.md 中为每个 V/AC 行关联证据。
5. 保留失败、修复原因、重新运行。
6. 连接已验证 block，执行边界检查。

测试可以先于实现，也可以随实现编写。不必为每次文档编辑人为制造一个失败测试。检查必须真正执行并断言目标行为。

<a id="document-2-heading-5"></a>

#### 5. 证据
在功能目录 evidence/ 中使用[证据模板](#document-6)。一次运行可以覆盖多个检查，但每个检查必须有独立结果。

记录时间与运行 ID、候选版本身份、输入/spec/plan/IF 版本、准确命令或步骤和工作目录、环境、依赖模式、测试输入版本、预期与实际结果、退出码、通过/失败/跳过数量、原始产物路径及局限。

未提交代码仅记录 HEAD 不够：还要记录 HEAD、diff 摘要哈希及相关已修改/未跟踪执行输入的哈希，或不可变快照引用。包括测试、配置和依赖输入。保留可复现性，但不捕获秘密，也不为获取证据 ID 而创建 commit。

<a id="document-2-heading-6"></a>

#### 6. 结果含义
| 结果 | 含义 |
| --- | --- |
| PASS | 必需断言在已标识候选版本上真实执行并满足预期 |
| FAIL | 某项要求被违反 |
| BLOCKED | 前置条件或未解决定义阻止验证 |
| NOT_RUN | 尚未执行该检查 |
| STALE | 旧证据不再覆盖当前候选版本或要求 |
| N/A | 根据范围给出理由后判定不适用；不得代替失败的必需检查 |

没有收集到用例、全部跳过、错误被抑制或仅使用桩实现，不能证明需要真实运行或真实服务的行为。跳过项必须单独记录。必需断言被跳过时，对应检查不是 PASS。

映射到某个 AC 的全部必需 V ID 都要有有效 PASS 证据。不能用平均通过结果掩盖混合结果。

<a id="document-2-heading-7"></a>

#### 7. 系统 TASK
TASKS 指定一个普通 TASK 承担系统验证。它有自己的 spec/plan/tasks/evidence，持有系统 AC 和完整链路，引用子任务覆盖结果，不复制子任务要求。

其 plan 固定候选版本配置和组件版本、依赖要求、完整链路、数据集及可测量约束。对照表映射：系统 AC → 参与的 TASK/block/IF ID → 系统 V → 证据。

最终验收前，必需 block 和接口必须就绪，证据对该候选版本必须有效。早期系统运行有价值，但不证明最终完成。

运行组装后的产品，包括适用的跨模块失败与恢复。缺少真实账号或服务时仍为 BLOCKED，mock 结果不能补足这一缺口。

<a id="document-2-heading-8"></a>

#### 8. 模型与研究
允许的模型取自已登记 PRD。不得虚构模型标识、基于 role 的选择方式、提供商或评估阈值。

记录提供商/模型标识及可获得版本、执行者输入、提示词/配置、数据集和划分、样本数、重复次数、可控随机种子、评分标准、质量指标和原始结果。成本/延迟证据还包括测量边界、重试、并发、缓存和计费依据。

比较运行时使用冻结的评估输入，并在最终测量前定义阈值。单次响应不能证明可靠性。桩实现可证明路由规则，但真实调用 AC 需要独立的真实服务证据。说明不可控波动。

<a id="document-2-heading-9"></a>

#### 9. 重新验证
行为、schema、测试、配置、依赖、验收标准和候选版本变化都会触发影响评估。利用 TASKS 依赖和 TASK 约定识别受影响 block 及下游消费方。将相关对照表行标为 STALE，重新执行其检查及相关系统链路。

只有记录了比较依据，证明相关行为、输入和依赖等价，才可复用未受影响的证据。仅记录证据的文字编辑不必然要求重跑。复用依据与证据引用放在一起。

系统完成结论指向一个准确候选版本。候选版本变化后，先重新评估证据并执行受影响检查，再保留完成声明。

<a id="document-2-heading-10"></a>

#### 10. 完成条件
TASK 完成要求必需工作完成、每项必需 AC/检查都有有效 PASS 证据，且没有使结论失效的未解决依赖。

M1 完成要求范围内所有输入条款均已分配、全部必需 TASK 对当前候选版本验证有效、接口一致，并且系统 TASK 在该候选版本上通过。

准备这套框架不要求尚未完成的队友任务先完成。

---

<a id="document-3"></a>

## 3. AI4Research 开发文档入口 v2

对应源文件: [docs/code/README.md](README.md)

<a id="document-3-heading-0"></a>

### AI4Research 开发文档入口 v2

本体系采用 **TASKS → TASK → 每个 TASK 一套 Spec Kit**，按“逐块验证 → 跨块连接验证 → 整个系统验证”推进开发。

建议先阅读 [开发 SOP](#document-1)，再查看 [完整文档目录](#document-28) 和 [M1 总任务入口](#document-17)。目前正在为完整 M1 提前铺设流程，最终 PRD 与架构仍待补齐；文档准备完成不代表 M1 已实现或通过验证。

<a id="document-3-heading-1"></a>

#### 常用入口

- [Spec Kit 使用流程](#document-10)：从需求、设计到工作项及证据对照表。
- [验证体系](#document-2)：如何验证单个 block、跨模块连接和整个系统。
- [Git 工作方式](#document-11)：分支、集成版本与验证证据的关系。
- [完整示例](#document-18)：查看 TASKS、TASK 与各自 Spec Kit 如何配合。
- [迁移与准备说明](#document-12)：旧文档如何替换，以及未完成任务如何衔接。

本入口使用中文，并提供完整中文合订本。可编辑的流程、模板和示例源文件保持英文；英文版使用独立的英文入口。新体系已替换独立的开工授权、实施清单、审查和交接卡；历史任务证据仍然保留。旧的 CODEX_DEMO.md 属于历史功能文档，不属于本流程包。

完整 ZIP 包含流程指南、全部模板、示例、仓库指令、Spec Kit 模板覆盖文件、constitution 和 M1 骨架。文件清单记录各文件的内容哈希。阅读和使用这套文档不要求创建 commit。

<a id="document-3-heading-2"></a>

#### 完整交付

- [完整中文合订本](AI4Research_Documentation_v2.zh-CN.md)
- [完整英文合订本](AI4Research_Documentation_v2.md)
- [英文入口](#document-3)
- [完整文档 ZIP](AI4Research_Documentation_v2.zip)
- [文件与哈希清单](DELIVERY_MANIFEST.json)
- [文档检查记录](#document-29)

---

<a id="document-4"></a>

## 4. TASKS：[PROGRAM-ID]

对应源文件: [docs/code/code_sop/templates/TASKS_TEMPLATE.md](code_sop/templates/TASKS_TEMPLATE.md)

<a id="document-4-heading-0"></a>

### TASKS：[PROGRAM-ID]
复制到 docs/tasks/[PROGRAM-ID]/TASKS.md。这是项目总登记表，不是第二份实施清单。

<a id="document-4-heading-1"></a>

#### 1. 身份与输入基线
| 字段 | 内容 |
| --- | --- |
| 项目 ID 和目标 | [填写] |
| 登记表修订版本/日期 | [填写] |
| 项目协调者 | [姓名或 UNASSIGNED；负责登记，不是审批门槛] |
| 完整 PRD 路径 / 修订版本 / SHA256 / 字节数 | [填写或 PENDING_SOURCE] |
| 架构源文件及渲染视图 / 修订版本 / SHA256 | [填写或 PENDING_SOURCE] |
| 范围内和排除的内容 | [输入引用和原因] |
| 系统验证 TASK | [准确 TASK 链接或 PENDING_SOURCE] |
| 集成候选版本 | [commit，以及必要时未提交文件树的身份；或 NOT_BUILT] |

<a id="document-4-heading-2"></a>

#### 2. 任务登记表与依赖图
| TASK ID / 入口链接 | 边界明确的结果 | 执行者 | 项目必需？ | 前置 TASK/block/IF ID | 原生功能目录 | 进度/证据来源 |
| --- | --- | --- | --- | --- | --- | --- |
| [填写] | [填写] | [填写] | [是/否，并给出范围依据] | [填写或 None] | [准确路径] | [原生 tasks.md 链接] |

描述依赖顺序或添加图示。解释并解决循环依赖。进度从链接的原生记录读取，不复制复选框，也不维护第二张任务状态表。

<a id="document-4-heading-3"></a>

#### 3. 输入覆盖分配
| 输入条款 ID / 准确定位 | 架构节点/边 ID | 所属 TASK / AC 引用 | 分配决定与完整性 |
| --- | --- | --- | --- |
| [填写] | [填写，或 N/A 并说明原因] | [一个或多个带任务限定的 AC ID] | [Allocated / PENDING_SOURCE / Unallocated / Excluded，并说明原因] |

覆盖功能、非功能和系统级条款。一条条款对应多个 AC 时，说明其组成部分如何被覆盖。每个 AC 只有一份所属 spec。宣称项目完整前，所有范围内条款必须已分配。

<a id="document-4-heading-4"></a>

#### 4. 接口索引
| IF ID / 修订版本 | 权威定义所在 TASK 章节 | 提供方 TASK | 消费方 TASK | 边界验证位置 |
| --- | --- | --- | --- | --- |
| [填写] | [准确链接] | [填写] | [填写] | [限定 V ID / 原生证据对照表] |

这里仅提供索引。语义由定义方 TASK 持有，不在此重复 schema。

<a id="document-4-heading-5"></a>

#### 5. 系统验证入口
- 系统 TASK 及原生 spec/plan/tasks：[链接]。
- 完整链路和横跨模块的要求：[引用系统 AC，不复制内容]。
- 候选组件/版本清单：[位置]。
- 最终系统运行证据：[链接或 NOT_RUN]。
- 对候选版本所需的子任务证据：[原生链接；适用时附复用依据]。
- 项目结论：[NOT_READY / VERIFYING / VERIFIED；从覆盖和原生证据推导]。
- 未验证范围及原因：[填写或 None]。

VERIFIED 要求输入分配完整、全部必需任务/block/边界证据对候选版本有效，且系统 TASK 在该版本上通过。

<a id="document-4-heading-6"></a>

#### 6. 输入变更与未解决输入
| 变更/问题 ID | 输入或 IF 修订版本 / 问题 | 受影响 TASK/AC/block/check ID | 行动及证据失效处理 | 执行者 / 解决条件 |
| --- | --- | --- | --- | --- |
| [填写] | [填写] | [填写] | [填写] | [填写] |

在此记录重要范围决定及其来源。未来输入尚不明确属于正常准备状态，不另建变更申请卡。

---

<a id="document-5"></a>

## 5. TASK：[TASK-ID] — [标题]

对应源文件: [docs/code/code_sop/templates/TASK_TEMPLATE.md](code_sop/templates/TASK_TEMPLATE.md)

<a id="document-5-heading-0"></a>

### TASK：[TASK-ID] — [标题]
复制到 docs/tasks/[PROGRAM-ID]/[TASK-ID]/TASK.md。TASK 是身份和入口。验收、设计、进度和结果保存在已登记的 Spec Kit 产物中。

逻辑上的 TASK 包含其 Spec Kit 产物。实体上 spec.md、plan.md 和 tasks.md 是独立的链接文件，不是复制进 TASK.md 的章节。

<a id="document-5-heading-1"></a>

#### 1. 身份
| 字段 | 内容 |
| --- | --- |
| TASK ID / 修订版本 / 日期 | [填写] |
| 上级 TASKS | [准确链接] |
| 执行者 / 协作者 | [填写或 UNASSIGNED] |
| 要求的结果及指令/来源 | [边界明确的目标及来源引用] |
| 范围内内容 / 排除内容 | [填写] |
| PRD 条款与架构节点引用 | [ID/定位及版本] |
| 工作检出目录 / 分支 / 基线 | [填写或 NOT_STARTED] |
| 受影响代码/文档路径 | [真实路径或 PENDING_DESIGN] |

不要求独立授权卡或审查人分配。遵循已请求的范围，重要范围变化记在下文。

<a id="document-5-heading-2"></a>

#### 2. Spec Kit 登记表
| 产物 | 准确路径 | 权威职责 |
| --- | --- | --- |
| 功能目录 | [specs/TASK-ID-slug/] | 此 TASK 的唯一目录 |
| spec.md | [链接] | 要求、AC、阈值 |
| plan.md | [链接] | 技术/block 设计与验证步骤 |
| tasks.md | [链接] | 工作/进度与证据对照 |
| evidence/ | [路径] | 实际验证运行及原始产物 |
| 辅助产物 | [路径或 None] | 研究、schema、数据模型；从属于已登记权威来源 |

不要在此重复验收表、工作清单或运行结果。

<a id="document-5-heading-3"></a>

#### 3. 依赖
| 依赖 TASK/block/IF ID 及版本 | 所需行为或产物 | 依赖工作开始前的必要条件 | 受影响 block/工作项引用 |
| --- | --- | --- | --- |
| [填写或 None] | [填写] | [填写] | [填写] |

区分定义阶段依赖与运行/实现依赖。一项依赖未解决时，无关独立工作可以继续。

<a id="document-5-heading-4"></a>

#### 4. 内嵌跨模块约定
每个本任务持有的 IF 使用一个以下子章节。消费的 IF 只引用权威定义及版本。没有跨模块边界时写 None 并说明原因。

<a id="document-5-heading-5"></a>

##### [IF-ID]，版本 [revision]
| 属性 | 定义 |
| --- | --- |
| 提供方和消费方 TASK ID | [填写] |
| 目的 / 输入要求 | [填写] |
| 输入：字段、类型、单位、必需/可选、校验 | [填写] |
| 输出：字段、类型、单位、语义、保证 | [填写] |
| 状态与不变量 | [填写] |
| 错误、超时、重试、取消 | [填写或合理说明 N/A] |
| 副作用与幂等性 | [填写或合理说明 N/A] |
| 兼容性和迁移 | [版本关系及受影响消费方] |
| 机器可读 schema / 源文件路径 | [链接或 None；用于实现此约定] |
| 提供方/消费方验证职责 | [限定 V ID 及定义位置] |
| 未解决约定问题 | [填写或 None] |

消费的约定：[权威 TASK 章节链接及准确 IF 版本；不复制定义]。

<a id="document-5-heading-6"></a>

#### 5. 变更与未解决决定
| ID / 日期 | 变更或问题及来源 | 受影响 spec/plan/work/IF 引用 | 依赖工作及需失效的证据 | 执行者 / 解决条件 |
| --- | --- | --- | --- | --- |
| [填写或 None] | [填写] | [填写] | [填写] | [填写] |

进度仍保存在 tasks.md。重要输入或接口变更需要更新上级 TASKS 的分配/索引，以及全部受影响的原生引用。

---

<a id="document-6"></a>

## 6. 验证运行：[RUN-ID]

对应源文件: [docs/code/code_sop/templates/EVIDENCE_TEMPLATE.md](code_sop/templates/EVIDENCE_TEMPLATE.md)

<a id="document-6-heading-0"></a>

### 验证运行：[RUN-ID]
保存在所选功能目录的 evidence/RUN-ID.md。这是实际观察证据，不是实施清单。一次运行可以覆盖多项检查。

<a id="document-6-heading-1"></a>

#### 1. 执行身份
| 字段 | 实际值 |
| --- | --- |
| TASK ID / 运行 ID / UTC 时间 | [填写] |
| 层级和 V ID | [BLOCK / BOUNDARY / SYSTEM；使用限定 ID] |
| 候选版本身份 | [commit；有未提交内容时附 diff 摘要及相关变更/未跟踪文件哈希，或不可变快照] |
| 基线 / 组件版本 | [填写] |
| PRD、spec、plan 和 IF 版本 | [填写] |
| 工作目录 / 平台 / 运行时 / 依赖版本 | [填写] |
| 输入/测试输入/数据集/模型/提示词/配置版本 | [填写，或说明 N/A] |
| 依赖模式和实际服务 | [桩 / 本地真实 / 外部真实；附详情] |
| 命令或可复现人工步骤 | [准确调用/步骤；不记录秘密值] |

<a id="document-6-heading-2"></a>

#### 2. 每项检查的观察
| V ID / AC 引用 | 预期结果 / 阈值来源 | 实际结果 | 退出码 / 含跳过项的数量 | 结果状态 | 原始产物位置 |
| --- | --- | --- | --- | --- | --- |
| [填写] | [填写] | [真实观察，不能填计划结果] | [填写；人工检查可为 N/A] | [PASS / FAIL / BLOCKED / NOT_RUN / STALE / N/A] | [准确路径/哈希] |

只有全部必需断言实际通过，该检查才是 PASS。未收集到用例、必需项被跳过、缺少真实依赖或错误被抑制均不满足条件。

<a id="document-6-heading-3"></a>

#### 3. 范围与有效性
- 已被证明的行为：[填写]。
- 尚未证明的行为 / 失败 / 阻塞：[填写或 None]。
- 模型/评估运行的可复现信息：[样本数、重复次数、随机性、评分标准、波动、成本/延迟边界，或 N/A]。
- 复用的旧证据及比较依据：[填写或 None]。
- 被取代的运行 ID / 原因：[填写或 None]。
- 后续 V/工作项引用：[填写或 None]。
- 本次运行后的候选版本/输入变化：[无已知变化，或影响和 STALE 引用]。

更新原生 tasks.md 对照表，指向本次运行。保留旧运行，不重写其观察结果。

---

<a id="document-7"></a>

## 7. 功能规格：[TASK-ID - FEATURE NAME]

对应源文件: [.specify/templates/overrides/spec-template.md](../../.specify/templates/overrides/spec-template.md)

<a id="document-7-heading-0"></a>

### 功能规格：[TASK-ID - FEATURE NAME]
**TASK**：[准确的 TASK.md 链接]
**上级 TASKS**：[准确的 TASKS.md 链接]
**修订版本 / 日期**：[填写]
**功能分支**：[实际分支或 NOT_STARTED；功能目录不代表分支]
**输入**：[已登记的 PRD 条款和架构节点，带版本与准确定位]
**状态**：[Preparing / Specified；不表示运行结果]

<a id="document-7-heading-1"></a>

#### 用户场景与测试
<a id="document-7-heading-2"></a>

##### 用户故事 1 — [可观察结果]（优先级：P1）
[用文字描述用户或执行者链路。]
**独立测试**：[输入、观察对象和预期行为。]
**验收场景**：
1. 给定[状态]，执行[动作]，应得到[可观察结果]。
[按需增加故事。基础设施或系统验证任务应描述可观察的消费方/系统行为。]

<a id="document-7-heading-3"></a>

##### 边缘情况
[适用的非法/边界输入、失败、取消、恢复和兼容性场景。说明省略原因。]

<a id="document-7-heading-4"></a>

#### 要求
<a id="document-7-heading-5"></a>

##### 功能要求
- **FR-001**：[与输入条款关联的必需行为。]

<a id="document-7-heading-6"></a>

##### 关键实体
[实体及含义，或 N/A。接口语义由定义方 TASK 持有，在此引用。]

<a id="document-7-heading-7"></a>

#### 成功标准
<a id="document-7-heading-8"></a>

##### 可度量结果
| AC ID | 输入条款 / FR / 用户故事 | 可观察标准和阈值 | 必需验证层级 |
| --- | --- | --- | --- |
| AC-001 | [填写] | [准确行为/指标；未知时为 PENDING_SOURCE] | [BLOCK / BOUNDARY / SYSTEM] |

全部必需行为、失败场景和非功能约束都要有 AC 覆盖。行为变化必须进行运行验证；文档变化使用相关文档检查。生成测试工作项时必须保留这些要求。

<a id="document-7-heading-9"></a>

#### 范围与假设
- 包含 / 排除范围：[有输入依据的边界]。
- 消费的 TASK 约定：[IF ID、版本和权威链接]。
- 允许的模型：[适用时采用 PRD 定义的标识；尚未获得时为 PENDING_SOURCE，不虚构名单]。
- 假设和未解决输入：[问题、受影响 AC 和解决条件，或 None]。
- 系统任务：[参与任务/AC 引用；仅持有系统级 AC，不复制 block 标准]。

本文件是 AC 权威来源。实施细节在 plan.md，进度和证据链接在 tasks.md。

---

<a id="document-8"></a>

## 8. 实施方案：[TASK-ID - FEATURE]

对应源文件: [.specify/templates/overrides/plan-template.md](../../.specify/templates/overrides/plan-template.md)

<a id="document-8-heading-0"></a>

### 实施方案：[TASK-ID - FEATURE]
**TASK**：[准确链接] | **Spec**：[准确链接 / 版本]
**修订版本 / 日期**：[填写] | **分支**：[实际分支]
**输入来源**：[PRD/架构版本及相关定位]

<a id="document-8-heading-1"></a>

#### 概述
[方案、范围及关键技术决定，引用 AC。]

<a id="document-8-heading-2"></a>

#### 技术上下文
- 语言/运行时、依赖、平台、存储：[已确认值或未解决项]。
- 相关模型/提供商配置：[PRD 定义的选择]。
- 环境及实际命令入口：[路径；标记未确认命令]。
- 性能/质量/资源约束：[AC 引用；不重新定义阈值]。

<a id="document-8-heading-3"></a>

#### Constitution 一致性检查
确认 TASKS/TASK/功能目录关联、唯一权威来源、内嵌约定引用、完整 AC/block/check 映射及范围和证据真实性。记录未解决项及受影响工作。这是一致性检查，不是人工审批阶段。

<a id="document-8-heading-4"></a>

#### 项目结构
[真实受影响代码/测试/配置路径和原生辅助产物。不能从模块名称虚构实现目录。]

<a id="document-8-heading-5"></a>

#### Block 与依赖
| Block ID | 职责 / AC 引用 | 输入、输出、状态不变量 | 依赖 block/TASK/IF 引用 | 受影响实现路径 |
| --- | --- | --- | --- | --- |
| B01 | [填写] | [填写] | [填写或 None] | [填写] |

[依赖顺序或图，标识共享文件。定义阶段依赖和运行依赖可能不同。]

<a id="document-8-heading-6"></a>

#### 接口与技术决定
- 持有/消费的 IF 版本及权威 TASK 章节链接：[填写]。
- 数据模型、存储、失败处理和恢复：[填写或合理说明 N/A]。
- 替代方案和重要决定：[决定、原因及影响]。
- 生成的 schema/contracts：[实现所属 TASK 约定，不建立平行规范定义]。

<a id="document-8-heading-7"></a>

#### 验证设计
| V ID | 层级 | Block / IF / AC 引用 | 测试输入和依赖模式 | 预期断言 / 标准来源 | 命令及工作目录，或人工步骤 | 必需前置条件 / 产物 |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | [BLOCK/BOUNDARY/SYSTEM] | [带任务限定的引用] | [填写] | [AC 链接] | [准确入口或 PENDING_DESIGN] | [填写] |

定义相关正常、边界、失败和恢复检查，区分真实连接与桩实现。模型相关工作定义数据集版本、指标、重复次数和测量方法；阈值仍放在 spec.md。

<a id="document-8-heading-8"></a>

#### 系统候选版本与链路
[系统 TASK：组件版本/配置清单、完整链路步骤、参与 block/接口、真实服务要求和证据有效性规则。其他任务：引用系统 TASK 并说明贡献。]

<a id="document-8-heading-9"></a>

#### 未解决决定与影响
[问题、受影响 block/check、解决条件。范围/IF 变更链接到 TASK 变更记录。沿依赖图重新验证。]

---

<a id="document-9"></a>

## 9. 工作项：[TASK-ID - FEATURE]

对应源文件: [.specify/templates/overrides/tasks-template.md](../../.specify/templates/overrides/tasks-template.md)

---
description: "TASK 原生工作项与验收/证据对照"
---
<a id="document-9-heading-0"></a>

### 工作项：[TASK-ID - FEATURE]
**TASK**：[准确链接] | **Spec / Plan 版本**：[填写]
**功能目录**：[准确登记路径]

必须包含 spec.md 和 plan.md 定义的验证工作。本文件是唯一实施工作清单，不再生成独立实施清单、授权卡、审查卡或交接卡。

<a id="document-9-heading-1"></a>

#### 工作项
格式：`- [ ] T001 [P?] [US1] 描述；block/AC/V 引用；真实路径`。
[P] 表示变更互不干扰且依赖已满足，不表示可以自行启动代理或发布。

<a id="document-9-heading-2"></a>

##### 基础准备 / 共享定义
- [ ] T001 [US1] [准备必需测试输入/接口/环境；注明引用和路径]

<a id="document-9-heading-3"></a>

##### Block B01 — [名称]
- [ ] T002 [US1] [实现边界明确的行为；B01、AC-001；实际代码路径]
- [ ] T003 [US1] [执行 block 验证 V01 并保留运行证据；实际检查路径]

<a id="document-9-heading-4"></a>

##### 连接边界
- [ ] T004 [US1] [对真实连接的 block 执行 V02；IF 引用和检查路径]

<a id="document-9-heading-5"></a>

##### 系统贡献
- [ ] T005 [US1] [集成并执行本任务必需的系统贡献，或引用系统 TASK 工作；实际路径]

用真实依赖顺序替换示例项。系统 TASK 在此定义候选版本准备和完整链路检查。工作项打勾仅表示已执行操作，不代表对应 AC 通过。

<a id="document-9-heading-6"></a>

#### 验收与证据对照表
| AC ID / spec 链接 | Block / IF 引用 | 实施工作 ID | 必需 V ID / 验证工作 ID | 当前结果 | 当前运行证据 / 候选版本 | 复用或失效依据 |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | B01 | T002 | V01 / T003 | NOT_RUN | None | 初始状态 |

按需添加行，使每个必需 V 的结果明确。每个 AC 必须被覆盖，每个 V 必须能追溯到 AC。只要有一个必需检查是 FAIL、BLOCKED、NOT_RUN 或 STALE，就不能把 AC 标为通过。

<a id="document-9-heading-7"></a>

#### 依赖顺序与执行说明
[顺序、未解决前置条件、共享文件约束、可恢复的下一步。不要复制工作清单。]

<a id="document-9-heading-8"></a>

#### 当前验证结论
- 候选版本身份：[准确身份或 NOT_BUILT]。
- 必需工作是否完成：[从工作项推导]。
- 必需 AC/check 覆盖：[从对照表推导的摘要]。
- 结论：[NOT_READY / IN_PROGRESS / BLOCKED / VERIFIED]。
- 剩余局限及下一步工作 ID：[填写或 None]。

VERIFIED 要求必需工作完成、全部必需检查有对候选版本有效的 PASS 证据，且不存在使结论失效的依赖。仅系统 TASK 完成还不够，项目完整性还需 TASKS 的输入覆盖。

<a id="document-9-heading-9"></a>

#### 证据失效
[变化的输入/IF/代码/配置/测试/依赖 ID、受影响行、新运行要求，或明确的未变证据复用依据。保留旧运行记录。]

---

<a id="document-10"></a>

## 10. TASKS / TASK 的 Spec Kit 工作流程

对应源文件: [docs/code/code_sop/SPEC_KIT_WORKFLOW.md](code_sop/SPEC_KIT_WORKFLOW.md)

<a id="document-10-heading-0"></a>

### TASKS / TASK 的 Spec Kit 工作流程
<a id="document-10-heading-1"></a>

#### 1. 工具与任务身份
仓库已安装 Spec Kit 1.0.12。安装细节位于 docs/governance/ENVIRONMENT.md；这些是历史环境事实，不是未来 M1 的准备门槛。

一个检出目录拥有一套安装和多个功能目录。每个 TASK 持有一个功能目录。从 TASKS → TASK 进入，不凭猜测的分支名选择任务。

执行原生命令前，选择准确登记的目录：
```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'specs/M1-001-example'
git status --short --branch
```
将示例替换为实际 TASK 路径。环境变量优先于本地 .specify/feature.json 指针。选择功能不等于切换分支。不要在同一检出目录并发运行两个生成会话；并行任务使用隔离的检出目录。

<a id="document-10-heading-2"></a>

#### 2. 项目模板
本地解析器优先选择 .specify/templates/overrides/，再考虑已安装模板。本包在该目录提供 spec-template.md、plan-template.md、tasks-template.md。

使用这些覆盖模板，不复制旧 DESIGN/PLAN 模板。上游核心模板和技能保持原状；升级工具时要保留并重新检查项目覆盖模板。

从仓库根目录执行只读解析检查：
```powershell
& .\.specify\scripts\powershell\resolve-template.ps1 spec-template -Json
& .\.specify\scripts\powershell\resolve-template.ps1 plan-template -Json
& .\.specify\scripts\powershell\resolve-template.ps1 tasks-template -Json
```

<a id="document-10-heading-3"></a>

#### 3. 原生命令顺序
| 命令 | 输入与输出 | 项目要求 |
| --- | --- | --- |
| $speckit-specify | 已分配 PRD 条款 → 原生 spec.md | 保留输入定位、AC ID 和必需验证 |
| $speckit-clarify | 未解决输入 → 澄清后的 spec | 只询问真正缺失的信息，独立准备可以继续 |
| $speckit-plan | spec 与 TASK 约定 → 原生 plan.md | 定义 block、依赖和验证步骤 |
| $speckit-tasks | spec 与 plan → 原生 tasks.md | 包含验证工作和 AC/block/check/evidence 对照表 |
| $speckit-analyze | 跨产物一致性问题 | 仅用于诊断，在权威产物内修复 |
| $speckit-implement | 有序工作 → 代码、检查与证据 | 遵循 block 依赖，更新同一套原生记录 |
| $speckit-converge | 可选的进一步缺口检测 | 新问题成为 TASK 范围内的原生工作项 |

上述 $speckit 名称是调用名称，不是 PowerShell 可执行文件。通过已安装的代理集成调用。

Spec Kit 内置的 requirements checklist 是生成的规格质量诊断，不是已删除的实施清单。不要增加自定义清单流程、审查人分配、独立授权卡或人工审查门槛。问题在 spec/plan/tasks 中修复；缺失定义只限制依赖工作，不限制无关准备。

上游实施技能可能建议因清单标记暂停或提交代码。用户的 v2 指令明确移除了这套平行门槛。调用原生技能时附带下方项目指令。这是项目流程指令，并不表示已重写上游技能代码。

<a id="document-10-heading-4"></a>

#### 4. 可复用调用上下文
```text
Work under Code SOP v2. TASK: <exact path>; parent TASKS: <exact path>;
feature directory: <exact registered path>. Read its registered source clauses,
TASK interface agreements and project native overrides.
Use spec.md for ACs, plan.md for blocks/procedures and tasks.md for all work
and AC-to-evidence mapping. Required block/boundary/system verification is
explicitly requested. Generated quality findings are diagnostic: resolve
them in those files; do not add an implementation checklist, reviewer gate,
write_code card, test-report card or handoff card.
Respect the user's current action scope and no-commit/no-push instructions.
```
上方可复制英文指令的含义是：按 SOP v2 工作，定位准确 TASK、上级 TASKS 与功能目录；读取输入条款、接口约定和项目模板；用 spec 管 AC、plan 管 block/步骤、tasks 管工作和证据对照；明确要求 block/边界/系统验证；把质量问题当作诊断在原文件修复；不增加实施清单、审查门槛、授权卡、报告卡或交接卡；遵守当前范围与 no-commit/no-push 指令。

<a id="document-10-heading-5"></a>

#### 5. 大型 PRD 和生成的辅助文件
TASKS 覆盖完整输入。每个任务获得已分配条款、相关全局约束、架构视图及提供方/消费方约定。仅给摘要不够。确认每个 AC 有来源，每条已分配条款有 AC 覆盖。

research、data-model、quickstart 和生成的 schema 是可选辅助材料。跨模块规范行为仍在定义方 TASK。生成的 contracts/ 文件携带其实现的 IF 版本。

生成后检查必需章节和对照表列。重新生成 tasks.md 时保留已完成工作和证据，或明确迁移，不能覆盖运行历史。

<a id="document-10-heading-6"></a>

#### 6. 续接与输入阻塞
从 TASKS → TASK → 所选功能 → 原生 tasks.md 的下一步恢复工作。阅读对照表与未解决依赖，不创建第二份状态报告。

未来 PRD/架构编写期间允许 PENDING_SOURCE。不得为填完模板而虚构模型、约定或阈值。仅阻塞正确性依赖该信息的工作。

<a id="document-10-heading-7"></a>

#### 7. Hooks 与外部操作
执行前检查实际 hooks。本流程不会启用自动分支/commit/PR 扩展。生成的 hook 或建议不能覆盖用户指令。commit、push、merge、消息发送和部署遵循用户授权范围，不以清单结果代替。

---

<a id="document-11"></a>

## 11. Git 与集成

对应源文件: [docs/code/code_sop/GIT_WORKFLOW.md](code_sop/GIT_WORKFLOW.md)

<a id="document-11-heading-0"></a>

### Git 与集成
本指南说明代码传递与集成方式，不是审查或授权流程。

<a id="document-11-heading-1"></a>

#### 分支
团队集成分支为 ai4r_main_branch。长期个人分支为 ai4r_xiaoyang、ai4r_saurav、ai4r_ramika、ai4r_muk。在 TASK 中记录实际检出目录、分支和基线。

保持无关任务变更可分离。并行任务可以使用任务分支和隔离检出目录。功能目录名称不会改变 Git 分支。切换、同步或解决冲突前保留已有工作。

<a id="document-11-heading-2"></a>

#### 只读检查
在实际检出目录运行：
```powershell
git status --short --branch
git diff --stat
git diff --check
git rev-parse HEAD
```
本包使用的本地仓库是 D:\research\ai_for_research\jiuwenswarm。模板不能证明工作树干净或远程已同步。

<a id="document-11-heading-3"></a>

#### 集成与证据
遵循已登记的 TASK 范围和 Spec Kit 工作清单。将相互依赖的 block 集成为可标识的候选版本，执行必需边界/系统检查。

用户要求 commit 或 PR 时，引用 TASK、说明行为并链接原生 tasks.md 的证据，不另建具有权威性的 PR 模板/清单。团队 PR 预期合入 ai4r_main_branch，必须检查实际目标。

解决冲突和基线变化可能使证据失效。评估受影响 block 及下游链路，再按 VERIFICATION.md 重跑。功能分支通过不代表组合后的候选版本通过。

<a id="document-11-heading-4"></a>

#### 不自动提交
命令、生成工作项和 hooks 不要求 commit。遵守 no-commit 指令，包括可能产生 merge commit 的同步步骤。按证据规则记录未提交候选版本身份。

不要为了简化集成丢弃本地变更、强推共享分支或改写历史。恢复数据或外部副作用可能不止是回退代码；所需恢复工作也纳入同一套 TASK/Spec Kit 体系。

---

<a id="document-12"></a>

## 12. v2 提前准备与迁移

对应源文件: [docs/code/code_sop/MIGRATION.md](code_sop/MIGRATION.md)

<a id="document-12-heading-0"></a>

### v2 提前准备与迁移
<a id="document-12-heading-1"></a>

#### 目标状态
在完整 M1 PRD 和架构到位前准备流程。队友现有实现尚未完成，并不代表本次文档准备需要修复这一状态。采用本结构不要求试点或配置审查人。

<a id="document-12-heading-2"></a>

#### 替换关系
| 原产物/流程 | v2 中的位置 |
| --- | --- |
| TASK 卡及独立授权 | TASK 身份、请求范围和来源 |
| 手动 DESIGN、PLAN | 原生 plan.md |
| 独立 contract / ADR / 架构任务记录 | TASK 内嵌约定和原生 plan 的决定；总体架构仍作为输入 |
| 实施清单 | 删除；原生 tasks.md 是唯一工作清单 |
| TESTING 规范和 TEST_REPORT 卡 | 重建的 VERIFICATION.md、plan 步骤、原生证据对照表及功能 evidence/ |
| AI/人工审查卡及收口门槛 | 从任务生命周期删除 |
| HANDOFF 和 CURRENT_STATUS 任务副本 | TASK 入口和可续接的原生工作/证据 |
| CHANGE_REQUEST | TASK 变更和 TASKS 输入影响记录 |
| 每任务 ownership、file-map、environment 卡 | TASK 执行者/范围及 plan 技术上下文 |
| 采用清单与启动包 | 当前文档目录及未来 M1 骨架 |

已从活动 docs/code 包删除旧模板和协议。docs/tasks/AI4R-001 历史记录及现有应用测试代码保留，其旧流程文字不是新 v2 任务的要求。

<a id="document-12-heading-3"></a>

#### 当前已准备
- 项目/任务/证据模板。
- 原生 spec/plan/tasks 覆盖模板。
- block、边界和系统验证方法。
- 已更新的根指令和 constitution。
- 明确标为虚构的完整文档示例。
- 输入待补齐的未来 M1 TASKS 骨架。
- 完整英文交付包与清单。

<a id="document-12-heading-4"></a>

#### 最终输入到位后
将准确 PRD/架构路径和基线登记到 M1 TASKS。分配真实条款，建立正式 TASK 及功能目录，指定系统 TASK。从 PRD 提取模型清单，不能把示例名称当需求。

命令和阈值绑定实际代码与要求。未知值显式保留到需要解决时。不要为了填满空登记表而创建推测性实施任务。

<a id="document-12-heading-5"></a>

#### 现有工作
继续现有任务不需要追溯复制记录。迁到 v2 时保留原生工作 ID 和证据，把任务登记到 TASKS，将仍相关的边界定义纳入 TASK，并将旧产物列作历史引用。不得把未完成测试改标通过，也不得重写过去执行历史。

当前旧状态/环境文件可以作为历史背景保留。新 M1 进度通过 TASKS 进入各任务原生记录。

<a id="document-12-heading-6"></a>

#### 工具维护
项目覆盖模板与上游模板/技能分开保存。根指令和调用上下文确立用户要求的 v2 行为。本包不负责应用实现、应用测试套件替换或远程仓库配置。

产品输入尚未到位时，本包也可以使用。未来 M1 实现是否完整，是另外一个基于证据的判断。

---

<a id="document-13"></a>

## 13. SOP v2 仓库 AGENTS 模板

对应源文件: [docs/code/AGENTS_global.md](AGENTS_global.md)

<a id="document-13-heading-0"></a>

### SOP v2 仓库 AGENTS 模板
整合到仓库根目录时，保留适用的实现约束。

<a id="document-13-heading-1"></a>

#### 入口
- 规范：docs/code/Code_SOP.md。
- 项目入口：docs/tasks/<PROGRAM-ID>/TASKS.md。
- 任务入口：docs/tasks/<PROGRAM-ID>/<TASK-ID>/TASK.md。
- Spec Kit 流程：docs/code/code_sop/SPEC_KIT_WORKFLOW.md。
- 验证：docs/code/code_sop/VERIFICATION.md。
- Constitution：.specify/memory/constitution.md。

<a id="document-13-heading-2"></a>

#### 长期规则
1. 从 TASKS → TASK → 准确登记的功能目录开始。实施前阅读适用子目录 AGENTS 和已有调用方/测试。
2. TASKS 持有输入分配与依赖，TASK 持有身份/范围/接口约定。原生 spec、plan、tasks 分别持有验收、设计、工作与证据对照。
3. 每个 TASK 有执行者及一个 Spec Kit 目录，不另建授权、实施清单、审查、交接或测试报告卡。
4. 跨模块定义保存在唯一所属 TASK，消费方引用 IF ID/版本，生成的 schema 实现该约定。
5. 逐块实现验证，再验证连接边界，最后通过系统 TASK 验证完整候选版本。
6. 保留证据，区分 PASS、FAIL、BLOCKED、NOT_RUN、STALE、N/A。复选框本身不能证明验收。
7. 缺失未来 PRD/架构输入不阻塞无关准备；不得虚构模型、阈值或 schema。
8. 显式选择功能，隔离并发生成。使用原生技能时读取项目覆盖模板并附 v2 调用上下文。
9. 生成的需求质量清单用于诊断，不得恢复已删除的审批/审查人流程。在原生产物中解决其发现的问题。
10. 重要变更后更新输入映射、IF 引用和证据；普通进度只更新原生 tasks.md。
11. 保留无关工作和凭据。外部操作遵循用户授权；不自动提交，不绕过 no-commit 指令。
12. 阅读相应模板，保留必需字段和对照表，说明 N/A 及未解决条件。

---

<a id="document-14"></a>

## 14. 模块/子目录 AGENTS 模板

对应源文件: [docs/code/AGENTS_local.md](AGENTS_local.md)

<a id="document-14-heading-0"></a>

### 模块/子目录 AGENTS 模板
确认实际代码路径后再部署，并保留已有子目录约束。

<a id="document-14-heading-1"></a>

#### 上下文
- 范围及排除项：[实际路径与职责]。
- 上级 AGENTS：[实际路径]。
- 项目 TASKS 和当前 TASK：[链接]。
- 执行者：[姓名或任务引用]。
- 原生功能目录：[TASK 中的准确路径]。
- 相关架构节点：[引用]。
- 持有/消费的约定：[所属 TASK 链接及 IF 版本]。

<a id="document-14-heading-2"></a>

#### 局部不变量
[行为、状态、持久化、兼容性和资源约束。不能从模块名称虚构接口。]

<a id="document-14-heading-3"></a>

#### 工作与验证
阅读已有代码、调用方和测试。在原生 plan.md 规划可观察 block，在原生 tasks.md 跟踪全部实施/验证工作。验证正常、边界和相关失败路径，再验证真实连接边界和系统贡献。

命令、工作目录、测试输入及阈值登记在当前原生 plan/spec。真实输出存放在功能 evidence/，由原生对照表引用。不需要独立审查、清单、授权或交接记录。

任务进度不写入 AGENTS；只有长期局部约束和入口改变时才更新本文件。遵守用户范围，保留凭据/无关工作，不自动提交。

---

<a id="document-15"></a>

## 15. AI4Research 仓库指令

对应源文件: [AGENTS.md](../../AGENTS.md)

<a id="document-15-heading-0"></a>

### AI4Research 仓库指令
维护者：Xiaoyang。以下长期指令适用于整个仓库，代码子目录已有指令仍适用。

<a id="document-15-heading-1"></a>

#### 入口
- [开发 SOP v2](#document-1)
- [未来 M1 TASKS](#document-17)
- [Spec Kit 流程](#document-10)
- [验证方法](#document-2)
- [Constitution](#document-16)
- 历史环境事实：docs/governance/ENVIRONMENT.md。
- 历史任务：docs/tasks/AI4R-001/TASK.md；它不是未来 M1 的总登记表。

<a id="document-15-heading-2"></a>

#### 工作规则
1. 遵循 TASKS → TASK → 每 TASK 唯一登记的 Spec Kit 目录。实施前阅读适用 AGENTS、准确输入条款、约定、原生 spec/plan/tasks，以及已有调用方/测试。
2. TASKS 持有输入分配与任务依赖。TASK 持有身份、执行者、范围和跨模块约定。spec.md 持有 AC；plan.md 持有技术/block 设计和验证步骤；tasks.md 持有工作/进度和 AC—证据对照。
3. 不创建独立 write_code、实施清单、测试报告、审查、交接或变更申请卡。用户请求范围记录在 TASK；v2 没有审查人分配或审批门槛。
4. 跨模块约定有唯一所属 TASK 和稳定 IF ID/版本。消费方和生成的 schema 引用该定义。
5. 实现并验证 block，再验证连接边界，最后验证完整集成系统。用当前证据声明验收，不能用清单勾选或生成的分析替代。
6. 记录准确候选版本、命令、环境、测试输入、预期/实际结果和局限。必需项被跳过、服务缺失、证据失效和未运行都不是通过。
7. 未来 PRD/架构/模型/阈值允许为 PENDING_SOURCE。继续独立准备，仅限制受影响工作；不虚构产品要求。
8. 原生命令前选择准确功能目录，隔离并发生成；本地功能指针不是任务锁。
9. 阅读 .specify/templates/overrides/ 并使用 v2 调用上下文。已安装技能关于可选测试、审查人持有的清单或自动 commit 的建议，不得重新引入用户已明确删除的流程。在原生产物内解决质量问题，保留真实诊断。
10. 重要输入/接口变化更新 TASKS/TASK 及相关原生记录，使受影响证据失效。普通进度只改 tasks.md。
11. 保留无关工作、已有实现约束和凭据。外部操作遵循用户授权，不能仅因生成工作项或 hook 建议就 commit/push/merge/deploy。明确 no-commit 时也不能执行会生成 commit 的 merge。
12. 阅读并遵循相关模板，保留必需字段和对照表，用未解决条件和有理由的 N/A 替代虚构事实。

<a id="document-15-heading-3"></a>

#### 已有代码子目录指令
修改 web 时读取 jiuwenswarm/channels/web/AGENTS.md 和 frontend AGENTS.md。修改 trajectory 时还要读取该子目录指令。保留前端测试标识、共享设置布局、支持的浏览器兼容性、本地化和适用的视觉/构建验证。

功能请求允许必要功能变更；旧 test-ID-only 指令只适用于仅修改测试 ID 的任务，不取消明确要求的功能工作。对触及的控件继续使用其命名规则。

<a id="document-15-heading-4"></a>

#### 历史证据
现有任务历史与应用测试保留。新 v2 任务不要求旧授权/审查卡，也不要求未完成旧任务先结束。引用旧结果时不能重写过去运行记录。

---

<a id="document-16"></a>

## 16. AI4Research Constitution

对应源文件: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)

<a id="document-16-heading-0"></a>

### AI4Research Constitution
版本 2.0.0 | 更新于 2026-09-29 | 来源：用户要求的 TASKS/TASK/Spec Kit 重设计。

<a id="document-16-heading-1"></a>

#### I. 一个层级
TASKS 描述整个项目；TASK 是身份和入口；每个 TASK 恰好有一个 Spec Kit 功能目录。执行者承担任务责任，不设独立 role 分类。

<a id="document-16-heading-2"></a>

#### II. 每类事实一个权威来源
TASKS 持有输入/分配/依赖；TASK 持有身份/范围/接口；原生 spec.md 持有验收，plan.md 持有设计/步骤，tasks.md 持有工作/进度/证据对照；证据记录实际运行。

不要求独立开工授权、实施清单、测试报告、审查、交接或变更申请卡。

<a id="document-16-heading-3"></a>

#### III. 内嵌约定
跨模块约定有唯一权威 TASK 章节、IF ID 和版本。消费方引用，生成的 contracts 和 schema 实现它。

<a id="document-16-heading-4"></a>

#### IV. 从 block 到系统的验证
实现并验证边界明确的 block，验证真实连接边界，再通过系统 TASK 验证完整集成候选版本。全部必需 AC 均有对应检查及有效证据。生成的工作清单必须明确包含必需验证。

<a id="document-16-heading-5"></a>

#### V. 真实且有效的证据
复选框和分析不能证明行为。保留失败和局限，区分 PASS、FAIL、BLOCKED、NOT_RUN、STALE、N/A。标识准确受测文件树，包括相关未提交输入；不为获取证据身份而 commit。

<a id="document-16-heading-6"></a>

#### VI. 准备与变更
缺少未来产品输入时保持 PENDING_SOURCE，仅限制依赖工作。范围/接口变化更新其权威来源并使受影响证据失效。准备本框架不以前期任务完成或试点为条件。

<a id="document-16-heading-7"></a>

#### VII. 用户范围与工具
阅读适用 AGENTS 和项目覆盖模板。生成的诊断清单不能构成人工审查或授权门槛。用户明确范围及 no-commit 指令适用于命令和 hooks。保留无关工作和秘密。

<a id="document-16-heading-8"></a>

#### 治理
本 constitution 实现 SOP v2，替换旧的以审查/授权为中心的版本。原生产物保留这些原则；上游模板/技能是工具，不得覆盖用户要求的流程。文档修订不代表应用就绪或远程强制规则已配置。

---

<a id="document-17"></a>

## 17. TASKS：M1

对应源文件: [docs/tasks/M1/TASKS.md](../tasks/M1/TASKS.md)

<a id="document-17-heading-0"></a>

### TASKS：M1
于 2026-09-29 按 SOP v2 准备。这是未来完整产品 M1 的总登记表，与历史 AI4R-001 中的里程碑命名区分。

<a id="document-17-heading-1"></a>

#### 1. 身份与输入基线
| 字段 | 内容 |
| --- | --- |
| 项目 ID 和目标 | M1：实现即将提供的主 PRD 与架构定义的完整里程碑 |
| 登记表版本/日期 | r1 / 2026-09-29 |
| 项目协调者 | UNASSIGNED；不阻塞文档准备 |
| 完整 PRD 路径 / 版本 / SHA256 / 字节数 | PENDING_SOURCE；预期 100–200 KB，尚未登记 |
| 架构源文件及渲染视图 / 版本 / SHA256 | PENDING_SOURCE |
| 包含和排除范围 | PENDING_SOURCE；不虚构排除项 |
| 系统验证 TASK | PENDING_SOURCE；实际任务拆分后指定 |
| 集成候选版本 | 本未来项目为 NOT_BUILT |

<a id="document-17-heading-2"></a>

#### 2. 任务登记与依赖图
| TASK ID / 入口链接 | 边界明确的结果 | 执行者 | 项目必需？ | 前置 TASK/block/IF ID | 原生功能目录 | 进度/证据来源 |
| --- | --- | --- | --- | --- | --- | --- |

尚未登记真实子 TASK。按主输入填写，每 TASK 对应一个功能目录。进度由原生 tasks.md 持有。本包 DEMO 示例不是正式 M1 任务。

依赖图：PENDING_SOURCE。Model Router 是预期整体范围的一部分，其详细拆分必须依据最终输入。

<a id="document-17-heading-3"></a>

#### 3. 输入覆盖分配
| 输入条款 ID / 准确定位 | 架构节点/边 ID | 所属 TASK / AC 引用 | 分配决定与完整性 |
| --- | --- | --- | --- |
| 主 PRD 尚未提供 | 总体架构尚未提供 | 尚未分配 | PENDING_SOURCE |

输入到位后必须分配范围内每条条款。大型 PRD 可以分片阅读，但本表必须覆盖完整范围。

<a id="document-17-heading-4"></a>

#### 4. 接口索引
| IF ID / 版本 | 权威定义所属 TASK 章节 | 提供方 TASK | 消费方 TASK | 边界验证位置 |
| --- | --- | --- | --- | --- |

PENDING_SOURCE。约定放在定义方 TASK 内，不放在独立合同卡。

<a id="document-17-heading-5"></a>

#### 5. 系统验证入口
- 系统 TASK 及原生 spec/plan/tasks：PENDING_SOURCE。
- 链路与系统要求：PENDING_SOURCE。
- 候选组件/版本清单：NOT_BUILT。
- 最终系统运行证据：NOT_RUN。
- 对候选版本有效的子任务证据：尚无。
- 项目结论：实现验收为 NOT_READY；文档准备已可使用。
- 未验证范围：整个未来 M1。

<a id="document-17-heading-6"></a>

#### 6. 输入变更与未解决输入
| 变更/问题 ID | 输入或 IF 版本 / 问题 | 受影响 TASK/AC/block/check ID | 行动与证据失效处理 | 执行者 / 解决条件 |
| --- | --- | --- | --- | --- |
| INPUT-001 | 完整主 PRD | 待分配 | 登记真实文件/版本/哈希，再映射全部条款 | 未分配；主 PRD 提供后解决 |
| INPUT-002 | 总体架构及节点 ID | 待分配 | 登记源文件/视图；确定任务边界与依赖 | 未分配；架构提供后解决 |
| INPUT-003 | 允许的模型标识与仅包含执行者的路由输入 | 未来 Router TASK | 从 PRD 提取准确名单；保留用户取消 role 的方向 | 未来 Router 执行者；从已登记 PRD 解决 |
| INPUT-004 | 系统链路及可测量阈值 | 未来系统 TASK | 从 PRD 推导；最终测量前定义检查 | 未来系统执行者；从已登记 PRD 解决 |

使用本骨架不要求队友现有任务先完成。本表不要求试点、审查人分配或 commit。

---

<a id="document-18"></a>

## 18. 完整示例：一个小项目、两个 TASK

对应源文件: [docs/code/code_sop/WORKED_EXAMPLE.md](code_sop/WORKED_EXAMPLE.md)

<a id="document-18-heading-0"></a>

### 完整示例：一个小项目、两个 TASK
这是虚构且未执行的文档示例，不是 M1 PRD、Router 设计、模型清单或测试通过报告。

打开 [DEMO TASKS](#document-19)。它将一个小型输入分配为：
- [DEMO-001](#document-20)：校验并规范化执行者标签。
- [DEMO-SYSTEM](#document-21)：连接消费方，验证从请求到显示的完整链路。

两者各有独立 spec/plan/tasks 目录。提供方持有一个内嵌 IF 约定，消费方引用它。DEMO-001 原生对照表覆盖两个 block 和连接检查；系统 TASK 对照表覆盖完整链路结果。

预期值只演示测试设计。全部运行检查仍为 NOT_RUN。本示例不创建任何应用代码或测试文件。

<a id="document-18-heading-1"></a>

#### 步骤演示
1. TASKS 将每条 SOURCE 分配给唯一所属 spec/AC。
2. TASK 绑定执行者、输入、功能路径，并持有或消费 IF-001@r1。
3. spec.md 定义行为，包括拒绝的输入。
4. plan.md 定义 B01 校验、B02 规范化、连接检查和准确预期值。
5. tasks.md 保存实施/验证工作及证据对照表。
6. 将来执行时用共享证据模板创建真实证据，再更新对照表。
7. 仅 block 通过不能完成 DEMO；候选版本上的边界和系统检查也必须通过。

示例没有 write_code、实施清单、测试报告、审查或交接文件。

---

<a id="document-19"></a>

## 19. TASKS：DEMO

对应源文件: [docs/code/code_sop/examples/DEMO/TASKS.md](code_sop/examples/DEMO/TASKS.md)

<a id="document-19-heading-0"></a>

### TASKS：DEMO
仅供说明，尚未发生运行执行。

<a id="document-19-heading-1"></a>

#### 1. 身份与输入基线
| 字段 | 内容 |
| --- | --- |
| 项目 ID 和目标 | DEMO：规范化执行者标签并展示给消费方 |
| 登记表版本/日期 | r1 / 2026-09-29 |
| 项目协调者 | 示例未分配 |
| 完整 PRD 路径 / 版本 / SHA256 / 字节数 | 下方内嵌的三条 SOURCE，r1；内嵌虚构输入的哈希/大小为 N/A |
| 架构源文件及渲染视图 / 版本 / SHA256 | 内嵌 r1：请求 → 校验 → 规范化 → 消费方显示；哈希 N/A |
| 包含及排除范围 | 三条 SOURCE；排除外部服务、存储、模型路由及性能声明 |
| 系统验证 TASK | [DEMO-SYSTEM](#document-21) |
| 集成候选版本 | NOT_BUILT |

虚构输入：
- SOURCE-01：标签必须是字符串，且至少包含一个非空白字符；其他值产生 INVALID_LABEL。
- SOURCE-02：返回去掉首尾空白并转成小写的标签。
- SOURCE-03：完整请求成功时显示规范化标签，输入非法时显示 INVALID_LABEL，不得保留旧成功值。

<a id="document-19-heading-2"></a>

#### 2. 任务登记与依赖图
| TASK ID / 入口链接 | 边界明确的结果 | 执行者 | 项目必需？ | 前置 TASK/block/IF ID | 原生功能目录 | 进度/证据来源 |
| --- | --- | --- | --- | --- | --- | --- |
| [DEMO-001](#document-20) | 校验并规范化标签 | 示例未分配 | 是 | block 工作无前置；边界 V03 需要消费方 | 本示例内 specs/DEMO-001-label/ | [工作项](#document-24) |
| [DEMO-SYSTEM](#document-21) | 消费方连接和系统验证 | 示例未分配 | 是 | DEMO-001 block 及 IF-001@r1 | 本示例内 specs/DEMO-SYSTEM-journey/ | [工作项](#document-27) |

顺序：定义 IF → 提供方 block → 消费方连接 → 边界检查 → 最终系统检查。提供方边界检查依赖消费方连接完成，不依赖整个系统 TASK 完成，避免形成完成状态循环。

<a id="document-19-heading-3"></a>

#### 3. 输入覆盖分配
| 输入条款 ID / 准确定位 | 架构节点/边 ID | 所属 TASK / AC 引用 | 分配决定与完整性 |
| --- | --- | --- | --- |
| SOURCE-01 | 校验 | DEMO-001/AC-001 | 已分配：有效性及错误结果 |
| SOURCE-02 | 规范化 | DEMO-001/AC-002 | 已分配：输出变换 |
| SOURCE-03 | 提供方 → 消费方显示 | DEMO-SYSTEM/AC-001、AC-002 | 已分配：成功和非法输入链路 |

<a id="document-19-heading-4"></a>

#### 4. 接口索引
| IF ID / 版本 | 权威定义所属 TASK 章节 | 提供方 TASK | 消费方 TASK | 边界验证位置 |
| --- | --- | --- | --- | --- |
| IF-001@r1 | [定义方 TASK](#document-20-heading-4) | DEMO-001 | DEMO-SYSTEM | DEMO-001/V03 |

<a id="document-19-heading-5"></a>

#### 5. 系统验证入口
- 原生 spec/plan/tasks：[系统 TASK 登记表](#document-21-heading-2)。
- 完整链路：DEMO-SYSTEM/AC-001 和 AC-002。
- 候选清单：NOT_BUILT；未来运行记录提供方与消费方源码哈希。
- 最终运行证据：NOT_RUN。
- 必需子任务证据：DEMO-001/V01、V02、V03 对候选版本有效。
- 项目结论：NOT_READY。
- 未验证范围：全部运行行为。

<a id="document-19-heading-6"></a>

#### 6. 输入变更与未解决输入
| 变更/问题 ID | 输入或 IF 版本 / 问题 | 受影响 TASK/AC/block/check ID | 行动与证据失效处理 | 执行者 / 解决条件 |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 | 尚无实现 | 全部 | 保持 NOT_RUN；实例化时绑定真实路径 | 未分配；仅在明确选择实现此小示例时解决 |

---

<a id="document-20"></a>

## 20. TASK：DEMO-001 — 规范化执行者标签

对应源文件: [docs/code/code_sop/examples/DEMO/DEMO-001/TASK.md](code_sop/examples/DEMO/DEMO-001/TASK.md)

<a id="document-20-heading-0"></a>

### TASK：DEMO-001 — 规范化执行者标签
虚构示例；当前没有请求实施。

<a id="document-20-heading-1"></a>

#### 1. 身份
| 字段 | 内容 |
| --- | --- |
| TASK ID / 修订版本 / 日期 | DEMO-001 / r1 / 2026-09-29 |
| 上级 TASKS | [DEMO](#document-19) |
| 执行者 / 协作者 | 示例未分配 |
| 请求结果及指令/来源 | 使用 SOURCE-01 和 SOURCE-02 演示文档结构 |
| 包含范围 / 排除内容 | 标签校验与规范化；不包含模型、role、存储或外部服务 |
| PRD 条款与架构引用 | 内嵌 DEMO SOURCE-01/02 r1；校验和规范化节点 |
| 工作检出目录 / 分支 / 基线 | NOT_STARTED |
| 受影响路径 | 假设的提供方和测试路径；实例化前为 PENDING_DESIGN |

<a id="document-20-heading-2"></a>

#### 2. Spec Kit 登记表
| 产物 | 准确路径 | 权威职责 |
| --- | --- | --- |
| 功能目录 | 相对本文件的 ../specs/DEMO-001-label/ | 仅本任务使用 |
| spec.md | [规格](#document-22) | AC |
| plan.md | [方案](#document-23) | Block/检查 |
| tasks.md | [工作项](#document-24) | 工作/证据 |
| evidence/ | 执行时使用 ../specs/DEMO-001-label/evidence/ | 实际运行 |
| 辅助产物 | None | N/A |

<a id="document-20-heading-3"></a>

#### 3. 依赖
| 依赖 TASK/block/IF ID 及版本 | 所需行为或产物 | 依赖工作开始前的必要条件 | 受影响 block/工作项引用 |
| --- | --- | --- | --- |
| DEMO-SYSTEM/T001 | 真实消费方连接 | 提供方—消费方边界执行需要它；block 实现不需要 | DEMO-001/V03 和 T004 |

<a id="document-20-heading-4"></a>

#### 4. 内嵌跨模块约定
<a id="document-20-heading-5"></a>

##### IF-001，版本 r1
| 属性 | 定义 |
| --- | --- |
| 提供方和消费方 TASK ID | DEMO-001 → DEMO-SYSTEM |
| 目的 / 输入要求 | SOURCE-01/02 结果被 SOURCE-03 显示功能消费 |
| 输入 | label：未知类型的值；只有去掉首尾空白后非空的字符串才有效 |
| 输出 | 成功：status=ok，包含 normalized_label 字符串；非法：status=error、code=INVALID_LABEL，且不含 normalized_label |
| 状态与不变量 | 无状态；非法输入不产生局部成功 |
| 错误、超时、重试、取消 | INVALID_LABEL 是普通错误结果；不重试；同步进程内示例的超时/取消为 N/A |
| 副作用与幂等性 | 无副作用；相同输入得到相同结果 |
| 兼容性和迁移 | r1 为初始约定；字段/语义变化需更新消费方，使 V03/系统证据失效 |
| 机器可读 schema / 源文件路径 | None；假设实现尚未创建 |
| 提供方/消费方验证职责 | DEMO-001/V01、V02 验证提供方；V03 连接真实消费方；DEMO-SYSTEM/V01、V02 验证完整链路 |
| 未解决约定问题 | 虚构范围内无 |

消费的约定：None。

<a id="document-20-heading-6"></a>

#### 5. 变更与未解决决定
| ID / 日期 | 变更或问题及来源 | 受影响引用 | 依赖工作及需失效的证据 | 执行者 / 解决条件 |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 / 2026-09-29 | 实现路径未绑定 | Plan/工作项 | 全部执行为 NOT_RUN | 未分配；仅实现示例时绑定 |

---

<a id="document-21"></a>

## 21. TASK：DEMO-SYSTEM — 验证完整标签链路

对应源文件: [docs/code/code_sop/examples/DEMO/DEMO-SYSTEM/TASK.md](code_sop/examples/DEMO/DEMO-SYSTEM/TASK.md)

<a id="document-21-heading-0"></a>

### TASK：DEMO-SYSTEM — 验证完整标签链路
虚构示例，尚未执行任何系统。

<a id="document-21-heading-1"></a>

#### 1. 身份
| 字段 | 内容 |
| --- | --- |
| TASK ID / 修订版本 / 日期 | DEMO-SYSTEM / r1 / 2026-09-29 |
| 上级 TASKS | [DEMO](#document-19) |
| 执行者 / 协作者 | 示例未分配 |
| 请求结果及指令/来源 | 演示消费方集成和 SOURCE-03 系统验证 |
| 包含范围 / 排除内容 | 从请求到显示的链路；不含模型服务或持久化 |
| PRD 条款与架构引用 | 内嵌 DEMO SOURCE-03 r1；提供方到显示的边 |
| 工作检出目录 / 分支 / 基线 | NOT_STARTED |
| 受影响路径 | 假设的消费方/入口/系统测试；PENDING_DESIGN |

<a id="document-21-heading-2"></a>

#### 2. Spec Kit 登记表
| 产物 | 准确路径 | 权威职责 |
| --- | --- | --- |
| 功能目录 | 相对本文件的 ../specs/DEMO-SYSTEM-journey/ | 仅本任务使用 |
| spec.md | [规格](#document-25) | 系统 AC |
| plan.md | [方案](#document-26) | 候选版本/链路 |
| tasks.md | [工作项](#document-27) | 工作/证据 |
| evidence/ | 执行时使用 ../specs/DEMO-SYSTEM-journey/evidence/ | 实际运行 |
| 辅助产物 | None | N/A |

<a id="document-21-heading-3"></a>

#### 3. 依赖
| 依赖 TASK/block/IF ID 及版本 | 所需行为或产物 | 依赖工作开始前的必要条件 | 受影响 block/工作项引用 |
| --- | --- | --- | --- |
| DEMO-001/B01、B02 和 IF-001@r1 | 提供方及接口定义 | 连接需要定义；集成需要可工作的 block | T001、T002 |
| DEMO-001/V03 | 连接边界证据 | 最终系统验收需要；不阻塞初始连接 | T003、T004 |

<a id="document-21-heading-4"></a>

#### 4. 内嵌跨模块约定
持有：None；消费现有边界，不新增跨任务接口。
消费：[DEMO-001 IF-001@r1](#document-20-heading-4)。不在此复制字段。

<a id="document-21-heading-5"></a>

#### 5. 变更与未解决决定
| ID / 日期 | 变更或问题及来源 | 受影响引用 | 依赖工作及需失效的证据 | 执行者 / 解决条件 |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 / 2026-09-29 | 没有可执行系统候选版本 | 全部 | 所有结果 NOT_RUN | 未分配；执行前绑定实际实现 |

---

<a id="document-22"></a>

## 22. 功能规格：DEMO-001 — 标签规范化

对应源文件: [docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/spec.md](code_sop/examples/DEMO/specs/DEMO-001-label/spec.md)

<a id="document-22-heading-0"></a>

### 功能规格：DEMO-001 — 标签规范化
**TASK**：[DEMO-001](#document-20)
**上级 TASKS**：[DEMO](#document-19)
**修订版本 / 日期**：r1 / 2026-09-29
**功能分支**：NOT_STARTED
**输入**：DEMO 内嵌 SOURCE-01/02 r1
**状态**：仅为演示定义规格

<a id="document-22-heading-1"></a>

#### 用户场景与测试
<a id="document-22-heading-2"></a>

##### 用户故事 1 — 规范化执行者标签（优先级：P1）
执行者提供标签，提供方返回规范化文本或已定义的非法输入结果。
**独立测试**：输入 "  ALPHA  "，预期规范化文本为 "alpha"；输入空白或数字，预期 INVALID_LABEL。
**验收场景**：
1. 有效字符串经处理后，去掉首尾空白并将内容转为小写。
2. 非法输入经处理后，返回定义的错误，且不包含成功字段。

<a id="document-22-heading-3"></a>

##### 边缘情况
空字符串、全空白字符串、非字符串输入均非法。已规范化文本保持原样。持久化、并发和外部网络恢复对于无状态虚构范围为 N/A。

<a id="document-22-heading-4"></a>

#### 要求
<a id="document-22-heading-5"></a>

##### 功能要求
- FR-001：按 SOURCE-01 校验。
- FR-002：按 SOURCE-02 转换有效字符串。
<a id="document-22-heading-6"></a>

##### 关键实体
执行者标签；接口语义见 TASK IF-001@r1。

<a id="document-22-heading-7"></a>

#### 成功标准
<a id="document-22-heading-8"></a>

##### 可度量结果
| AC ID | 输入条款 / FR / 用户故事 | 可观察标准和阈值 | 必需验证层级 |
| --- | --- | --- | --- |
| AC-001 | SOURCE-01 / FR-001 / US1 | 非法输入返回 INVALID_LABEL，且不含 normalized_label | BLOCK、BOUNDARY |
| AC-002 | SOURCE-02 / FR-002 / US1 | 有效字符串准确返回去掉首尾空白后的小写内容 | BLOCK、BOUNDARY |

<a id="document-22-heading-9"></a>

#### 范围与假设
本示例仅以虚构输入为依据，不涉及模型或基于 role 的输入。系统显示行为由 DEMO-SYSTEM 持有，不在此复制。尚无实现，全部运行结论未验证。

---

<a id="document-23"></a>

## 23. 实施方案：DEMO-001

对应源文件: [docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/plan.md](code_sop/examples/DEMO/specs/DEMO-001-label/plan.md)

<a id="document-23-heading-0"></a>

### 实施方案：DEMO-001
**TASK**：[DEMO-001](#document-20) | **Spec**：[r1](#document-22)
**修订版本 / 日期**：r1 / 2026-09-29 | **分支**：NOT_STARTED
**输入来源**：DEMO 内嵌输入/架构 r1

<a id="document-23-heading-1"></a>

#### 概述
校验值、规范化有效文本，并返回 TASK 规定的结果。这是方案示例，不是实际实现。

<a id="document-23-heading-2"></a>

#### 技术上下文
若选定实现本示例，运行时和真实代码/测试路径仍为 PENDING_DESIGN。不需要外部服务、存储或模型。下方人工步骤描述可观察行为，不假设具体测试运行器。

<a id="document-23-heading-3"></a>

#### Constitution 一致性检查
一个 TASK 对应一个功能目录；AC 在 spec；IF 在 TASK；工作和证据在 tasks。运行证据为 NOT_RUN，不使用审批卡。

<a id="document-23-heading-4"></a>

#### 项目结构
假设的提供方入口和测试尚未创建。执行 T001 前应绑定真实路径。原生文档位于本示例目录。

<a id="document-23-heading-5"></a>

#### Block 与依赖
| Block ID | 职责 / AC 引用 | 输入、输出、状态不变量 | 依赖 block/TASK/IF 引用 | 受影响实现路径 |
| --- | --- | --- | --- | --- |
| B01 | 校验 / AC-001 | 未知输入 → 有效文本或错误；无副作用 | IF-001@r1 | PENDING_DESIGN 提供方 |
| B02 | 规范化 / AC-002 | 有效文本 → 规范化结果 | B01 和 IF-001@r1 | PENDING_DESIGN 提供方 |

顺序：B01 → B02。V03 还需要 DEMO-SYSTEM 消费方连接，但不需要系统验收已完成。

<a id="document-23-heading-6"></a>

#### 接口与技术决定
[IF-001@r1](#document-20-heading-4) 是权威定义。无状态同步函数足以实现此虚构行为，不需要存储或重试机制。

<a id="document-23-heading-7"></a>

#### 验证设计
| V ID | 层级 | Block / IF / AC 引用 | 测试输入和依赖模式 | 预期断言 / 标准来源 | 命令及工作目录，或人工步骤 | 必需前置条件 / 产物 |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BLOCK | B01 / AC-001 | ""、"   "、42；本地真实提供方 | 按 AC-001 返回错误且没有成功字段 | 逐个调用提供方，捕获完整返回字段 | 可执行提供方；原始输入/输出记录 |
| V02 | BLOCK | B02 / AC-002 | "  ALPHA  "、"alpha"；本地真实提供方 | 按 AC-002 准确返回 "alpha" | 对两个值调用提供方，比较准确输出 | 可执行提供方；原始记录 |
| V03 | BOUNDARY | IF-001@r1 / AC-001、AC-002 | "  ALPHA  "，随后 " "；真实提供方和消费方 | 消费方正确读取成功/错误字段，不残留旧成功值 | 两个值经过真实边界；捕获结果对象和消费方状态 | DEMO-SYSTEM/T001；边界跟踪和源码哈希 |

<a id="document-23-heading-8"></a>

#### 系统候选版本与链路
DEMO-SYSTEM 记录提供方/消费方组合候选版本，验证从请求到显示的行为。只有候选版本比较证明相关输入未变，才复用 block 证据。

<a id="document-23-heading-9"></a>

#### 未解决决定与影响
尚未绑定可执行路径/运行时。全部运行检查为 NOT_RUN。IF 或提供方变更使 V03 和相关系统检查失效。

---

<a id="document-24"></a>

## 24. 工作项：DEMO-001

对应源文件: [docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/tasks.md](code_sop/examples/DEMO/specs/DEMO-001-label/tasks.md)

<a id="document-24-heading-0"></a>

### 工作项：DEMO-001
**TASK**：[DEMO-001](#document-20) | **Spec / Plan 版本**：r1 / r1
**功能目录**：docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/

<a id="document-24-heading-1"></a>

#### 工作项
<a id="document-24-heading-2"></a>

##### 基础准备 / 共享定义
- [ ] T001 [US1] 若请求实施，在 plan.md 绑定真实提供方、测试路径及运行时。
<a id="document-24-heading-3"></a>

##### Block B01 和 B02
- [ ] T002 [US1] 在 T001 确定的路径按 AC-001/002 实现 B01/B02。
- [ ] T003 [US1] 执行 V01/V02，把实际运行记录保存在 evidence/。
<a id="document-24-heading-4"></a>

##### 连接边界
- [ ] T004 [US1] DEMO-SYSTEM/T001 完成后执行 V03，把真实边界证据保存在 evidence/。
<a id="document-24-heading-5"></a>

##### 系统贡献
- [ ] T005 [US1] 向 DEMO-SYSTEM 原生对照表提供提供方候选版本身份和当前证据。

<a id="document-24-heading-6"></a>

#### 验收与证据对照表
| AC ID / spec 链接 | Block / IF 引用 | 实施工作 ID | 必需 V ID / 验证工作 ID | 当前结果 | 当前运行证据 / 候选版本 | 复用或失效依据 |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](#document-22) | B01 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | 虚构示例 |
| [AC-001](#document-22) | IF-001@r1 | T002 | V03 / T004 | NOT_RUN | None / NOT_BUILT | 需要消费方连接 |
| [AC-002](#document-22) | B02 | T002 | V02 / T003 | NOT_RUN | None / NOT_BUILT | 虚构示例 |
| [AC-002](#document-22) | IF-001@r1 | T002 | V03 / T004 | NOT_RUN | None / NOT_BUILT | 需要消费方连接 |

<a id="document-24-heading-7"></a>

#### 依赖顺序与执行说明
T001 → T002 → T003；V03 需要消费方连接；最终系统验收在边界验证之后。没有实施请求时，不执行此示例范围。

<a id="document-24-heading-8"></a>

#### 当前验证结论
- 候选版本身份：NOT_BUILT。
- 必需工作完成：否。
- 必需 AC/check 覆盖：2 个 AC、3 个 V ID，全部 NOT_RUN。
- 结论：NOT_READY。
- 剩余局限：没有可执行实现。

<a id="document-24-heading-9"></a>

#### 证据失效
尚无运行证据。未来接口变更必须使边界和下游系统结果失效。

---

<a id="document-25"></a>

## 25. 功能规格：DEMO-SYSTEM

对应源文件: [docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/spec.md](code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/spec.md)

<a id="document-25-heading-0"></a>

### 功能规格：DEMO-SYSTEM
**TASK**：[DEMO-SYSTEM](#document-21)
**上级 TASKS**：[DEMO](#document-19)
**修订版本 / 日期**：r1 / 2026-09-29
**功能分支**：NOT_STARTED
**输入**：DEMO SOURCE-03 r1
**状态**：为演示定义规格

<a id="document-25-heading-1"></a>

#### 用户场景与测试
<a id="document-25-heading-2"></a>

##### 用户故事 1 — 查看完整请求结果（优先级：P1）
请求经过真实提供方和消费方，显示最终结果。
**独立测试**：提交 "  ALPHA  "，再提交非法空白；观察两次可见结果。
**验收场景**：
1. 有效请求显示 "alpha"。
2. 非法请求显示 INVALID_LABEL，并清除之前成功值。

<a id="document-25-heading-3"></a>

##### 边缘情况
先成功后失败时，不得残留旧成功值。本示例输入排除持久化及外部服务中断。

<a id="document-25-heading-4"></a>

#### 要求
<a id="document-25-heading-5"></a>

##### 功能要求
- FR-001：显示提供方成功返回的规范化值。
- FR-002：输入非法时显示已定义错误，清除旧成功值。
<a id="document-25-heading-6"></a>

##### 关键实体
请求、提供方结果和消费方显示状态；消费 IF-001@r1。

<a id="document-25-heading-7"></a>

#### 成功标准
<a id="document-25-heading-8"></a>

##### 可度量结果
| AC ID | 输入条款 / FR / 用户故事 | 可观察标准和阈值 | 必需验证层级 |
| --- | --- | --- | --- |
| AC-001 | SOURCE-03 / FR-001 / US1 | 真实完整链路对 "  ALPHA  " 显示 "alpha" | SYSTEM |
| AC-002 | SOURCE-03 / FR-002 / US1 | 后续空白请求显示 INVALID_LABEL，且无之前成功值 | SYSTEM |

<a id="document-25-heading-9"></a>

#### 范围与假设
参与行为：DEMO-001/AC-001 和 AC-002。不复制其 block 标准。不涉及模型服务。以上结果均为预期，不是已观察到的通过。

---

<a id="document-26"></a>

## 26. 实施方案：DEMO-SYSTEM

对应源文件: [docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/plan.md](code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/plan.md)

<a id="document-26-heading-0"></a>

### 实施方案：DEMO-SYSTEM
**TASK**：[DEMO-SYSTEM](#document-21) | **Spec**：[r1](#document-25)
**修订版本 / 日期**：r1 / 2026-09-29 | **分支**：NOT_STARTED
**输入来源**：DEMO SOURCE-03 与架构 r1

<a id="document-26-heading-1"></a>

#### 概述
把真实消费方连接到提供方，建立候选版本，验证完整请求到显示行为。

<a id="document-26-heading-2"></a>

#### 技术上下文
运行时和可执行路径为 PENDING_DESIGN。全部连接采用本地真实实现；桩实现不能证明最终系统验收。

<a id="document-26-heading-3"></a>

#### Constitution 一致性检查
仅持有系统 AC。引用提供方约定/证据，维护自己的原生工作对照表，不另建审查或收口卡。

<a id="document-26-heading-4"></a>

#### 项目结构
消费方入口、显示和系统检查都是尚未创建的假设。T001 执行前绑定路径。

<a id="document-26-heading-5"></a>

#### Block 与依赖
| Block ID | 职责 / AC 引用 | 输入、输出、状态不变量 | 依赖 block/TASK/IF 引用 | 受影响实现路径 |
| --- | --- | --- | --- | --- |
| B01 | 消费方/显示 / AC-001、AC-002 | 请求 → 可见结果；无旧成功值残留 | DEMO-001/B01、B02 和 IF-001@r1 | PENDING_DESIGN 消费方 |
| B02 | 完整链路验证 / AC-001、AC-002 | 准确候选版本和请求 → 观察到的链路证据 | B01、提供方 block 证据和 DEMO-001/V03 | PENDING_DESIGN 系统检查 |

<a id="document-26-heading-6"></a>

#### 接口与技术决定
消费 [IF-001@r1](#document-20-heading-4)。出错时重置显示状态，不另存接口 schema 副本。

<a id="document-26-heading-7"></a>

#### 验证设计
| V ID | 层级 | Block / IF / AC 引用 | 测试输入和依赖模式 | 预期断言 / 标准来源 | 命令及工作目录，或人工步骤 | 必需前置条件 / 产物 |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | SYSTEM | B01、B02 / AC-001 / DEMO-001 block / IF-001 | "  ALPHA  "；全部本地真实组件 | 按 AC-001 准确显示 "alpha" | 启动候选入口，提交输入，捕获请求、提供方结果和显示 | 候选哈希、有效 block/边界证据、跟踪记录 |
| V02 | SYSTEM | B01、B02 / AC-002 / IF-001 | V01 后同一会话，再提交 " " | 按 AC-002 显示 INVALID_LABEL，无旧 "alpha" | 提交非法输入，捕获错误及最终显示状态 | 同一候选版本和会话；跟踪记录 |

<a id="document-26-heading-8"></a>

#### 系统候选版本与链路
运行记录必须包含真实提供方、消费方、检查和配置哈希，以及运行时和初始状态。候选版本目前为 NOT_BUILT。最终运行要求 DEMO-001/V01、V02、V03 对该版本有效。较早的探索运行不能证明最终完成。

<a id="document-26-heading-9"></a>

#### 未解决决定与影响
真实运行时/路径尚不存在。提供方、消费方或接口变化都需要影响评估及相关系统重跑。

---

<a id="document-27"></a>

## 27. 工作项：DEMO-SYSTEM

对应源文件: [docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/tasks.md](code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/tasks.md)

<a id="document-27-heading-0"></a>

### 工作项：DEMO-SYSTEM
**TASK**：[DEMO-SYSTEM](#document-21) | **Spec / Plan 版本**：r1 / r1
**功能目录**：docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/

<a id="document-27-heading-1"></a>

#### 工作项
<a id="document-27-heading-2"></a>

##### 消费方 block 与集成
- [ ] T001 [US1] 绑定路径并实现 B01 真实消费方连接，在 plan.md 更新可执行入口。
- [ ] T002 [US1] 组装提供方/消费方/检查/配置候选版本，记录其身份，取得 DEMO-001/V03 边界证据。
<a id="document-27-heading-3"></a>

##### 整个系统验证
- [ ] T003 [US1] 在候选版本执行 V01，把实际运行保存在 evidence/。
- [ ] T004 [US1] 在同一候选版本会话执行 V02，把实际运行保存在 evidence/。

<a id="document-27-heading-4"></a>

#### 验收与证据对照表
| AC ID / spec 链接 | Block / IF 引用 | 实施工作 ID | 必需 V ID / 验证工作 ID | 当前结果 | 当前运行证据 / 候选版本 | 复用或失效依据 |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](#document-25) | B01、B02；DEMO-001/B01、B02；IF-001@r1 | T001、T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | 虚构示例 |
| [AC-002](#document-25) | B01、B02；IF-001@r1 | T001、T002 | V02 / T004 | NOT_RUN | None / NOT_BUILT | 需要同一候选版本/会话 |

<a id="document-27-heading-5"></a>

#### 依赖顺序与执行说明
消费方连接可在 IF 定义完成后开始。最终系统检查需要有效提供方 block 和边界证据。V02 在同一会话中接在 V01 后面，以暴露旧状态残留缺陷。

<a id="document-27-heading-6"></a>

#### 当前验证结论
- 候选版本身份：NOT_BUILT。
- 必需工作完成：否。
- 必需 AC/check 覆盖：2 个系统 AC、2 个系统 V ID，全部 NOT_RUN。
- 结论：NOT_READY。
- 剩余局限：尚无实现或运行证据。

<a id="document-27-heading-7"></a>

#### 证据失效
尚无证据。候选版本变化使相关系统结论失效，直到完成影响评估与必需重跑。

---

<a id="document-28"></a>

## 28. 完整文档目录 — SOP v2

对应源文件: [docs/code/code_sop/README.md](code_sop/README.md)

<a id="document-28-heading-0"></a>

### 完整文档目录 — SOP v2
本包提供中英文入口。可编辑的规范、模板和示例源文件保持英文，同时提供完整中文合订本。先阅读[开发 SOP](#document-1)。本目录覆盖整套流程；可选研究/schema 产物不是额外必需卡片。

<a id="document-28-heading-1"></a>

#### 阅读顺序
1. [文档入口](#document-3)
2. [开发 SOP](#document-1)
3. [Spec Kit 流程](#document-10)
4. [从 block 到系统的验证](#document-2)
5. [完整示例](#document-18)
6. [未来 M1 登记表](#document-17)

<a id="document-28-heading-2"></a>

#### 指南与指令
| 文档 | 用途 |
| --- | --- |
| [Git 工作方式](#document-11) | 分支/候选版本处理，不自动 commit |
| [迁移与准备](#document-12) | 替换关系及未完成历史工作的处理 |
| [根 AGENTS 模板](#document-13) | 可复用仓库长期指令 |
| [局部 AGENTS 模板](#document-14) | 可复用子目录上下文 |
| [当前仓库 AGENTS](#document-15) | 已部署 v2 仓库入口和规则 |
| [当前 constitution](#document-16) | Spec Kit 的 v2 原则 |

<a id="document-28-heading-3"></a>

#### 必需记录模板
| 模板 | 目标位置 / 权威职责 |
| --- | --- |
| [TASKS](#document-4) | docs/tasks/PROGRAM-ID/TASKS.md；整体输入/覆盖/依赖 |
| [TASK](#document-5) | docs/tasks/PROGRAM-ID/TASK-ID/TASK.md；身份与内嵌约定 |
| [证据](#document-6) | 所选功能 evidence/RUN-ID.md；实际运行观察 |

活动包只有这三种记录模板。证据是输出附件，不是额外任务卡。

<a id="document-28-heading-4"></a>

#### Spec Kit 原生模板
| 原生模板 | 目标位置 / 权威职责 |
| --- | --- |
| [Spec 覆盖模板](#document-7) | 功能 spec.md；要求与 AC |
| [Plan 覆盖模板](#document-8) | 功能 plan.md；设计、block 和检查 |
| [Tasks 覆盖模板](#document-9) | 功能 tasks.md；工作和 AC—证据对照表 |

覆盖文件是模板权威来源，不在本目录的 templates 下维护重复副本。

<a id="document-28-heading-5"></a>

#### 完整虚构示例
| 文档 | 链接 |
| --- | --- |
| 项目登记表和内嵌输入 | [DEMO TASKS](#document-19) |
| 提供方 TASK | [DEMO-001](#document-20) |
| 提供方原生产物 | [规格](#document-22)、[方案](#document-23)、[工作项](#document-24) |
| 系统 TASK | [DEMO-SYSTEM](#document-21) |
| 系统原生产物 | [规格](#document-25)、[方案](#document-26)、[工作项](#document-27) |

没有任何示例运行结果被报告为通过。未来实际运行使用证据模板。

<a id="document-28-heading-6"></a>

#### 交付
完整包由本流程包、活动根指令、constitution、原生覆盖模板及未来 M1 登记表生成，并包含文件清单和文档检查记录。仓库旧 CODEX_DEMO.md 描述历史功能工作，不属于本流程包。

旧启动 ZIP 及授权/审查/清单/测试模板已删除，避免误用。

下载[完整 ZIP](AI4Research_Documentation_v2.zip)，阅读[英文合订本](AI4Research_Documentation_v2.md)或[中文合订本](AI4Research_Documentation_v2.zh-CN.md)，也可查看[文件清单](DELIVERY_MANIFEST.json)和[文档检查](#document-29)。交付文件是生成快照；编辑时使用上方源文件。

---

<a id="document-29"></a>

## 29. 文档验证记录

对应源文件: [docs/code/DOCUMENTATION_CHECKS.md](DOCUMENTATION_CHECKS.md)

<a id="document-29-heading-0"></a>

### 文档验证记录
日期：2026-09-29。范围为 SOP v2 文档，不是应用/运行验收。

<a id="document-29-heading-1"></a>

#### 已执行检查
| 检查 | 观察结果 |
| --- | --- |
| 初始源文档扫描 | 32 份英文源文档；无空文件或中日韩文字 |
| 初始本地链接/锚点扫描 | 增加交付链接前检查了 99 个引用，零失败 |
| TASK 与原生工作清单章节 | 示例必需章节齐全；没有已勾选示例工作项 |
| 示例 AC/检查对应关系 | DEMO-001：2 个 AC、3 项检查、5 个工作项；DEMO-SYSTEM：2 个 AC、2 项检查、4 个工作项；全部有映射 |
| 活动记录模板清单 | 恰好为 TASKS、TASK、EVIDENCE |
| 原生解析器 | spec-template、plan-template、tasks-template 都解析到项目覆盖文件 |
| 已删除流程引用扫描 | 活动文件中无被删除模板文件名或原独立审查要求的引用 |
| 空白/错误检查 | git diff --check 通过 |
| 变更范围 | 仅 docs/code、未来 M1 骨架、根 AGENTS、constitution 和原生覆盖模板变化 |
| 最终源文件/合订本链接扫描 | 34 个 Markdown 文件，247 个本地链接/锚点，零失败 |
| 交付压缩包 | 35 个条目；压缩包完整性和清单 SHA256 检查通过 |
| Commit 状态 | HEAD 保持 918df5e4081ed35d53257dfccd33119a7b639c57；未执行 commit |

<a id="document-29-heading-2"></a>

#### 方法与环境
从 D:\research\ai_for_research\jiuwenswarm 使用 Python 3.13.1、PowerShell 和 Git 执行检查。
- Python 检查 UTF-8 内容、相对 Markdown 链接/标题锚点、示例 AC/V/工作项集合、预期模板名和变更路径。
- PowerShell 加载 .specify/scripts/powershell/common.ps1，为每个原生模板调用 Resolve-Template 和 Resolve-TemplateContent，确认覆盖路径和非空内容。
- Git 提供空白诊断、变更路径清单和候选 HEAD。

生成后还检查压缩包完整性、清单与内容一致性以及交付链接。交付清单记录源文件和快照内容哈希。

<a id="document-29-heading-3"></a>

#### 范围边界
没有运行 M1 运行时套件、真实外部模型调用、工具升级、commit、push 或部署。虚构示例运行检查仍为 NOT_RUN，未来主 PRD 和架构仍为 PENDING_SOURCE。没有重写历史任务或应用测试。

<a id="document-29-heading-4"></a>

#### 入口本地化
按用户要求，docs/code/README.md 改为中文，其他指南、模板和示例仍为英文，并重新生成合订本、清单和 ZIP。之前“仅英文”扫描结果描述的是本地化之前的初始交付。

<a id="document-29-heading-5"></a>

#### 中英文完整交付
2026-09-30：新增全英文 README.en.md，英文合订本使用该入口；中文 README.md 对应完整中文合订本。以上文件数量与链接数量属于先前交付的历史记录，本次重新执行内容覆盖、章节/表格、工作项 ID、链接、语言和压缩包哈希检查。中文译文按源路径保存在 translations.zh-CN.json，便于重新生成和对应查阅。未创建 commit。

本次交付检查结果：33 个中英文部分完整对应，章节数量、表格结构、工作项 ID 和代码块一致；英文合订本未检测到中文正文；两份合订本各 172 个链接有效；ZIP 共 38 个条目，清单哈希与包内内容一致。

<a id="document-29-heading-6"></a>

#### 删除模块指南与澄清任务文件
2026-09-30：按用户要求删除旧 RSI、Router、Capsule、Verifier 四份模块指南，移除目录条目和译文，重新生成两份合订本与 ZIP。明确逻辑 TASK 持有 spec.md、plan.md、tasks.md，而 TASK.md 是其入口和链接登记表。当前每份合订本有 29 个部分；上方旧数量描述此前交付。本次没有执行 commit。
