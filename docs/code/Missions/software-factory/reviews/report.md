# 独立审计：STRATA 业务源码是否由真实动态业务流程生成

审计结论：**PARTIAL。真实阶段执行、源码写出、CPU 编译、计算、打包及独立重建成立；“依据工程任务、真实源码与结果自主组合实现阶段并生产完整 STRATA”的标准尚未满足。**当前准确定位是：可执行的产物契约依赖调度器，连接一个只支持已审阅 STRATA 核心函数的有限源码转译器。

本结论针对本次审计固定的代码哈希与历史运行，不代表随后修复候选已被重新验收。未修改产品代码，未重新克隆、编译或运行工厂任务。审计只读检查真实代码/运行/产物，并执行已有 CPU 二进制一次，使用其原先记录的输入。

## 发现：按交付影响排序

### 1. 阻断：新生成的业务 src 没有进入完整模型候选构建/推理链

证据：

- `construction_pipeline.py:91–118` 写出 generated source；`:153–172` 构建它。该分支产物进入 core test、ZIP、independent rebuild 和 Value Report。
- `catalog.py:355–358` 的完整模型构建输入是 `implementation.checkout` 和 `environment.report`，不是 `construction.source`、`construction.cpp` 或其构建产物。
- `strata_stages.py:49–55` 单独克隆 upstream，再调用 `apply_port()`；`strata_patch.py:13–18` 把预写 `strata_port` 文件复制进去。
- 真实运行 `99ecb9591942439aa85683565ca4152f` 中，n14/full build 的输入只有 a60（来自 n12/static patch checkout）和 a61（environment）。不存在 n5/generated src 到 n14/full build 的路径。

影响：即使补齐设备和 SDK，完整模型分支也不会消费这份工厂新生成的 src。此项是软件连接缺口，不能归因于硬件。

### 2. 阻断：编排由预先声明的产物目标展开，未依据源码内容选择实现阶段

证据：

- `api.py:44–51` 请求只有 goals/repository/revision/model/backend/options，没有工程 Task/Acceptance 或编译后的能力需求契约。
- `engine.py:165–183` 的选择条件只有输出 kind、repairs 标记、backend、cost/id；没有读取源码分析、算法类型、当前计算产物内容或验收要求。
- `engine.py:341–354` 先为全部 goals 构图，再开始执行源码获取。真实 events 第2条就已给出18个节点，而 source.fetch 第4条才 started。
- `core_algorithms` 来自显式请求参数（`construction_pipeline.py:84–85`），不是源码分析结果。
- 第二实际请求 `e56a3f31070a46348619fe539419ecc0` 把 goal 改成 construction.cpp，并显式传 router；它执行的5个阶段恰好等于完整请求的前5个。这证明目标裁剪和参数分支，不证明按源码选择不同实现流程。

影响：当前存在真实 contract dependency planning，但尚没有用户所说的“理解工程任务和源码，再选择相应实现能力”的业务编排决策。

### 3. 阻断：核心生成器大量结构预置，只能处理固定已审阅函数

证据：

- `core_codegen.py:17–22` 固定 router_top10_kernel、swiglu_kernel、moe_combine_kernel 三个源码位置/函数。
- `:119` 只允许 `[router]` 或完整三件套。
- `:68–97` 要求路由完整规范化函数体 SHA 等于固定常量；唯一允许变化的数值是 clamp。未知算法改动直接拒绝，未触发实现能力检索或新实现生成。
- `:171–206` 的路由实现主体是预先写好的 C++ 字符串，用4个表达式占位符替换；在函数体白名单约束下，实际可变的算法参数主要是 clamp。
- `:100–113`、`:207–226` 的 SwiGLU/aggregation 是真实提取 scalar body 后替换 CUDA 索引为 CPU 循环。这部分确实有源码转译，不能称作空壳或假输出。
- `:302–343` 的 Ascend activation 实现也是预写常量源码；不是运行时根据任意 CUDA 算法产生的 native backend。

影响：这是一套有限的、源文件绑定且可校验的转译规则。真实 C++ 有数学计算、输入也真实消费，但不能把“阶段执行了预写生成器”扩大为已经具备通用业务代码生成工厂。新增 attention、不同路由或未知算子，目前仍需先手工实现新的规则/模板。

### 4. 阻断：Ascend 候选与 CUDA 原版无法在当前一次任务中进行对照

证据：

- `strata_inference.py:171–175` baseline build 读取同一个 target_backend；只接受 cuda。
- `:131–134` 候选和原版共享 `_run_inference()`，均要求 compiled backend == 请求 target_backend。
- 真实 n16 返回 `original_backend_unavailable`，details.target_backend=ascend，尚未进入 CUDA SDK 编译检查。

影响：即使两种设备/SDK均到位，Ascend target 请求的 CUDA 原版 baseline 仍会被软件拒绝。原版 backend 与候选 backend 需要分别建模并保留角色，不能把合法的跨后端对照误当回退。

### 5. 高：父 workflow 层次主要是分组标签，阶段实例复用条件不够

证据：

- `contracts.py:45–52` 只有 Stage callable 与 workflow_id/subworkflow_id 字符串。
- `engine.py:394–402` 从扁平 Stage 列表按字符串生成父分组；未发现 executable parent workflow 定义被运行时拆解的实现。
- `engine.py:167–169` 任意现有节点只要能输出该 kind 就复用；`:189–192` 全局按 stage_id 去重。
- `Execution.__init__` 每个运行从空 artifacts 字典开始，未发现跨运行按输入身份/产物兼容性复用已验证工程产物的机制。

影响：从不同逻辑父组选择微阶段、同一运行共享依赖确实成立。但不同输入下多次调用同一能力（例如不同模块的多次 codegen/build）目前会被合并成一个节点，尚不能支撑一般的多实例工程组合。不能仅以跨分组计数证明完整 workflow→subworkflow→subsubworkflow 组合能力。

### 6. 中：画布绿色边不证明实际产物已被下游接收

证据：`WorkflowDemo.tsx:343–345` 在 target 没有 failed 时直接使用 source.status。实际 environment→inference 等边中，下游 blocked、0 attempts、没有 input binding，来源 verified 仍能使边变绿。

影响：节点/日志来源是真后端，工厂模块未发现计时器伪造进度；但画布边的绿色语义有误，不能作为已交付/已消费的证据。Value Report 已正确区分 planned19、recorded-delivered14、planned-only5，画布尚未采用同一判定。

### 7. 中：历史运行没有固定执行器/生成器源码版本

证据：`engine.py:68–87` 的命令记录保存 argv/cwd/PID；产物有 SHA，但没有当时执行器 Python 源码快照/哈希。宿主 HEAD 是 `141c1c401138f916af0a41aca791adf226d814c7`，software_factory 与 workflowDemo 实现都在未提交工作区。

影响：现有源/产物/日志彼此一致，足以支持有限执行事实；不能严格证明现在看到的每一行生成器源码就是当时运行版本。本审计将当前代码哈希与完整源文保存在 raw-evidence.txt，可作为后续候选审计基线，但不是追补历史执行证明。

### 8. 尚未完成：完整模型、native 推理与 AI Value 评述

证据：

- `catalog.py:171–182` Ascend full build 无条件加入“full attention/cache/decode migration”缺项并抛出 blocked；`:183–184` CPU full engine 也直接 blocked。
- `strata_patch.py:62–64` 明列 embedding/dense、native router、QSA/GDN、KV/cache、token loop 等未实现。
- 交付 CLI（`/workspace/strata_native/src/main.cpp:18–24`）读取 logits/gate/up/shared 数值数组，计算路由、activation 与加权聚合；没有读取原始模型权重并执行完整推理。
- 真实 n15/inference、n17/baseline inference、n18/compare 均为 blocked、0 attempts。没有模型结果可供对照。
- source 构建和 ZIP 独立构建都明确使用 `STRATA_CORE_BACKEND=CPU`；可选 Ascend 源码未被本次编译执行。
- Value evidence 的 model_assessment=unavailable、invoked=false，缺 openjiuwen/ruamel；当前报告是真实证据驱动的确定性报告，没有发生 AI 模型评述。

影响：资源缺失必须保留；但生成完整模型实现与打通候选/原版链路的软件缺口也必须保留。补齐硬件不能直接使当前系统达到全量验收。

## 已独立确认的真实链路

运行根目录：`/workspace/factory-runs/99ecb9591942439aa85683565ca4152f/`。

| 阶段 | 实际证据 |
| --- | --- |
| 真实获取 | n1 git clone PID15348/exit0；SHA `13eedf552417a6a791a7d13c6597e24300ee3a09`，获取时 clean |
| 真实解析 | n3 Python adapter PID15865；IR 原始函数正文与固定源码逐字匹配 |
| 真实生成 | n5 `python -m ...core_codegen` PID15874，写出 src/header/CMake |
| 构建消费生成源码 | n6 Make 日志与 `.o.d` 明确指向 n5 的 src/strata_core.cpp |
| 真实数值测试 | n7 actual test executable，3424个比较，max abs error5.96046e-08，CPU scope |
| 真实打包 | ZIP15个成员均与生成 manifest 逐个哈希一致 |
| 独立重建/执行 | n9 CMake/Make/test/CLI真实进程；原始输入重执行 exit0、stdout一致 |
| 实际图调整 | missing CMake 的真实exit127触发新增 toolchain.install；19节点相对初始18节点；failed/verified两次attempt保留 |

核心源码 SHA：`de367ef101d6c617594088522675ff3858a7ceea9bde78a8c17ef3be75c58c58`。

ZIP SHA：`53873dac016b824f06332625f012575c5689ca01d308bf14ddc18f49c9a3749b`。

现有二进制用其记录的输入重新运行：

```text
exit_code=0
{"backend":"CPU","ids":[1,3],"weights":[0.880797088,0.119202919],"output":[2.11319304,0.132360563,0.141698241]}
```

此结果只证明当前已有 CPU 核心程序真实计算，与完整模型推理无关。

## 按用户标准逐项判定

| 标准 | 判定 | 范围/缺口 |
| --- | --- | --- |
| 真实STRATA固定版本获取 | PASS | clone/fetch/checkout、SHA、源文件存在 |
| 用户Task/Acceptance→能力需求→执行计划 | FAIL | 当前直接人工提交artifact goals，无任务编译与验收驱动选择 |
| 跨父组选择可执行内部stage | PARTIAL | flat Stage pool真实可执行；父workflow本身主要是标签 |
| 根据源码/算法/当前产物选择不同实现路径 | FAIL | 计划在fetch前形成，固定kind依赖，没有源码语义选择 |
| 真实结果触发执行图变化 | PASS（限域） | 实际missing_toolchain；没有新算法生成路径证据 |
| 真实产物传递与检查 | PASS（核心链范围） | 实际文件/哈希/源码消费/数值数据都核实；非通用语义契约体系 |
| 运行中的流程生成src | PASS（限域） | 真执行器调用真生成器写出并编译，未发现纯UI伪造 |
| 按新算法自动构造业务代码 | PARTIAL | 已审阅模式/预写router与native模板，scalar bodies真提取；未知模式拒绝 |
| 可独立构建运行的C++源码包 | PASS（CPU核心） | 15成员、独立build与external numeric input实算 |
| 生成src进入完整模型推理链 | FAIL | 两个独立分支，完整构建消费预写patch checkout |
| Ascend候选/CUDA原版对照软件路径 | FAIL | 单一target_backend耦合拒绝跨后端baseline |
| Ascend设备执行/模型推理 | BLOCKED + 实现未完成 | 无SDK/设备/模型，同时软件计算图未完成 |
| 前端真实事件/源码/下载 | PARTIAL | SSE/源码/下载真实；绿色边把未消费的planned边也显示成功 |
| Value Agent | PARTIAL | 实际证据报告成立；AI模型调用未执行 |
| 可复跑和历史代码归属 | PARTIAL | 上游/产物固定，factory executor源码版本未随run固定 |

## 必须自动进入整改的具体要求与复审验收

1. **R1：打通生成源码到完整候选工程。**候选构建必须实际消费 generated source/patch manifest，并把其SHA写入build/inference链。验收：真实构建的编译依赖/链接清单引用工厂产物；修改源驱动生成结果能改变候选计算；不存在另一个未接通的demo分支。模型与native验收仍需真实执行。
2. **R2：任务与源码驱动的阶段选择。**加入明确Task/Acceptance输入与能力需求编译；source analysis输出真实特征，planner依据特征、实际可用产物和能力契约选择实现stage。验收：同一artifact最终目标，两个真实不同源码/算法任务选择不同的实际实现阶段；差异不能只来自人工core_algorithms或goal裁剪。
3. **R3：把实现生成能力从固定三函数规则提升到可组合实现阶段。**保留已经正确的有限lowering为能力，明确其适用契约；新增算法需求必须选择/构造实际实现并验证，不能把拒绝未知哈希称为已经自动生成。验收：至少一个超出clamp参数变化的真实算法改动，产出正确的新C++计算并通过独立数值oracle；不支持的需求明确失败并形成未完成实现要求。
4. **R4：分离candidate/backend与baseline/backend。**原版CUDA基线和Ascend候选各自有显式角色/设备/SDK契约，禁止静默fallback。验收：软件合同测试证明Ascend任务选择CUDA baseline且候选仍为Ascend；资源到位后真实双后端推理和同模型/输入/配置数值对照。
5. **R5：支持阶段实例身份和安全复用。**同一个stage允许不同输入创建不同node；仅在输入身份、产物契约和版本一致时复用。验收：两个不同模块同时调用同一构建/生成能力得到两套真实产物，相同绑定才共享；父workflow/subworkflow/内部stage定义和拆取关系可检查。
6. **R6：画布边以真实绑定/验证事件表达交付。**blocked且没有attempt/input的下游边保持pending，不能因来源成功就绿。验收：最终运行19个planned cross edges中，仅14个有真实交付绑定；5个planned-only不得展示为已消费成功；contract失败有独立错误证据。
7. **R7：运行固定factory代码与配方。**每run记录执行器、adapter、codegen及stage catalog版本/哈希或可复跑快照。验收：给定run能定位当时源码并从同样输入重建；当前未提交修改不会重写旧版本归属。
8. **R8：完成剩余计算图与分层native验收。**分别记录源码实现、CPU测试、target编译、设备加载、算子、模型、原版对照。设备不可用不得打勾；软件缺口继续实现，不归因于资源。验收仍为真实模型权重端到端计算和原版对照。
9. **R9：Value AI评述真实调用与证据边界。**保留确定性事实账本；AI评述只有实际provider调用/输出/引用校验后才能标完成。验收：真实调用provenance/usage/调用ID（可用时）及报告引用；无provider时继续明确unavailable。

整改完成后应以新候选重新独立审计。本审计不自动为任何后续修改背书，也不降低原始完整STRATA/native验收。

## 审计版本与限制

宿主分支 AI4Research-Main，HEAD `141c1c401138f916af0a41aca791adf226d814c7`；factory/frontend实现存在未提交/未追踪修改。当前已审源码哈希、带行号源码、真实请求/图/命令/日志、全部产物哈希、ZIP成员、二进制重执行结果都在同目录 `raw-evidence.txt`。其中factory源码快照在已交付code ZIP或当前文件中与审计初始哈希匹配后保存，避免整改并发混淆。

未运行新build、新网络获取、模型或设备调用；未声称重演历史全过程。证据证明现有文件/日志的一致性及当前二进制计算，不能提供缺失的历史执行器签名或硬件正确性证明。
