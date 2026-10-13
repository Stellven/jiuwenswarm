# AI4Research 开发文档

本目录统一收纳开发指南与真实任务记录。实际工作位于 `Missions/项目阶段/`：阶段目录放 TASKS.md，每个任务目录并列放 TASK.md、spec.md、plan.md、tasks.md。按逐块、跨块连接、整个系统的顺序验证。

先读 [开发 SOP](Code_SOP.md) 和 [文档目录](CATALOG.md)，再从 [M1 任务登记表](Missions/M1/TASKS.md) 进入实际工作。任务与规格中的当前记录决定输入和进度。

## 内容在哪里

| 内容 | 位置 |
| --- | --- |
| 开发规范与操作指南 | 本目录；[Spec Kit 使用流程](SPEC_KIT_WORKFLOW.md)、[验证方法](VERIFICATION.md)、[Git 工作方式](GIT_WORKFLOW.md)、[迁移说明](MIGRATION.md) |
| 通用 Spec Kit 能力 | [Codex 插件](../../plugins/spec-kit/README.md)，统一持有 skills、脚本与基础模板 |
| 项目规则与本地设置 | [.specify 项目状态](../../.specify/README.md)；仅项目专属覆盖配置放在这里 |
| 项目记录模板 | [TASKS](../../plugins/spec-kit/templates/TASKS_TEMPLATE.md)、[TASK](../../plugins/spec-kit/templates/TASK_TEMPLATE.md)、[证据](../../plugins/spec-kit/templates/EVIDENCE_TEMPLATE.md)及 AGENTS 模板 |
| 真实任务与原生规格 | docs/code/Missions/；[M1](Missions/M1/TASKS.md)与[开发工具维护](Missions/DEVTOOLS/TASKS.md)各自组织实际任务，四个任务文件放在一起 |
| 历史浏览器 demo | [AI4R-001 的运行指南](Missions/AI4R-001/CODEX_DEMO.md)，与对应任务放在一起 |

当前指南和模板是可维护来源；旧交付快照保持历史原文。阅读和使用本流程不要求创建 commit。参见 [English entry](README.en.md)。
