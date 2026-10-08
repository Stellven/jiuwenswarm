# AI4Research 开发文档入口 v2

M1 product/design inputs are maintained in [design package](../architecture/design-package/README.md). Use the live SOP and [M1 coding registration entrypoint](../tasks/M1/TASKS.md) with that package. 旧合订本、ZIP 与交付哈希已从当前目录移除；现行工作使用下面的流程源文档。

本体系采用 **TASKS → TASK → 每个 TASK 一套 Spec Kit**，按“逐块验证 → 跨块连接验证 → 整个系统验证”推进开发。

建议先阅读 [开发 SOP](Code_SOP.md)，再查看 [完整文档目录](code_sop/README.md) 和 [M1 总任务入口](../tasks/M1/TASKS.md)。目前正在为完整 M1 提前铺设流程，当前 PRD 与架构已纳入 build-package，编码记录仍需按现行流程生成或协调；文档准备完成不代表 M1 已实现或通过验证。

## 常用入口

- [Spec Kit 使用流程](code_sop/SPEC_KIT_WORKFLOW.md)：从需求、设计到工作项及证据对照表。
- [验证体系](code_sop/VERIFICATION.md)：如何验证单个 block、跨模块连接和整个系统。
- [Git 工作方式](code_sop/GIT_WORKFLOW.md)：分支、集成版本与验证证据的关系。
- [完整示例](code_sop/WORKED_EXAMPLE.md)：查看 TASKS、TASK 与各自 Spec Kit 如何配合。
- [迁移与准备说明](code_sop/MIGRATION.md)：旧文档如何替换，以及未完成任务如何衔接。

本入口使用中文，其余流程文档、模板和示例保持英文。新体系已替换独立的开工授权、实施清单、审查和交接卡；历史任务证据仍然保留。旧的 CODEX_DEMO.md 属于历史功能文档，不属于本流程包。

## 历史交付

旧合订本、ZIP 与哈希清单可从 [固定 Git 历史](../architecture/design-package/history.md#final-branch-cleanup--october-7-2026) 查看，不是当前流程或设计输入。[历史文档检查记录](DOCUMENTATION_CHECKS.md) 保留当时结果，不代表现行 M1 验证。
