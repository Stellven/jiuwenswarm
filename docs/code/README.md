# AI4Research 开发文档入口 v2

本体系采用 **TASKS → TASK → 每个 TASK 一套 Spec Kit**，按“逐块验证 → 跨块连接验证 → 整个系统验证”推进开发。

建议先阅读 [开发 SOP](Code_SOP.md)，再查看 [完整文档目录](code_sop/README.md) 和 [M1 总任务入口](../tasks/M1/TASKS.md)。目前正在为完整 M1 提前铺设流程，最终 PRD 与架构仍待补齐；文档准备完成不代表 M1 已实现或通过验证。

## 常用入口

- [Spec Kit 使用流程](code_sop/SPEC_KIT_WORKFLOW.md)：从需求、设计到工作项及证据对照表。
- [验证体系](code_sop/VERIFICATION.md)：如何验证单个 block、跨模块连接和整个系统。
- [Git 工作方式](code_sop/GIT_WORKFLOW.md)：分支、集成版本与验证证据的关系。
- [完整示例](code_sop/WORKED_EXAMPLE.md)：查看 TASKS、TASK 与各自 Spec Kit 如何配合。
- [迁移与准备说明](code_sop/MIGRATION.md)：旧文档如何替换，以及未完成任务如何衔接。

本入口使用中文，其余流程文档、模板和示例保持英文。新体系已替换独立的开工授权、实施清单、审查和交接卡；历史任务证据仍然保留。旧的 CODEX_DEMO.md 属于历史功能文档，不属于本流程包。

完整 ZIP 包含流程指南、全部模板、示例、仓库指令、Spec Kit 模板覆盖文件、constitution 和 M1 骨架。文件清单记录各文件的内容哈希。阅读和使用这套文档不要求创建 commit。

## 完整交付

- [完整合订本（中文入口，其余英文）](AI4Research_Documentation_v2.md)
- [完整文档 ZIP](AI4Research_Documentation_v2.zip)
- [文件与哈希清单](DELIVERY_MANIFEST.json)
- [文档检查记录](DOCUMENTATION_CHECKS.md)
