# 独立复审 Cycle 2：真实动态业务工作流与 STRATA 源码生产

结论：**本轮已经从“静态模板调度”推进到真实的、受限能力范围内的源码驱动微阶段组合；实际生成/构建/运行链成立。但完整 Software Factory / STRATA Native 验收仍未完成，且本轮仍检出需要下一轮修复的软件边界。**不能把本轮核心工程通过扩大为完整模型通过。

## 候选与证据范围

- 核心工程实际运行：`e20cd5bb89a34dcba385a696596119e7`，COMPLETED。
- normalization 实际运行：`475135502cfe45d4972f8d6da1b1f4d5`，COMPLETED。
- 完整 Native 目标实际运行：`7e34d3a870374b4ca3bdcbdcdfc32229`，BLOCKED。
- 上游仍为 `niko1221/strata @ 13eedf552417a6a791a7d13c6597e24300ee3a09`。
- 运行均有 write-once recipe：源码快照、请求、目录、阶段声明、Python/包信息、命令级代码/可执行文件身份。
- 宿主分支仍为 AI4Research-Main，HEAD `141c1c401138f916af0a41aca791adf226d814c7`，实现仍有未提交修改。本报告用运行 recipe 的23个源码文件作为已执行候选，而不是把后来工作区内容追认到旧运行。
- 复审过程中父线程又修复了 dynamic-input receipt，contracts.py/engine.py/source_planning.py 与上述运行快照已不同。旧运行没有被回填；这些新修改必须由下一候选运行复审。本报告不自动背书。
- 本次只读，未重新克隆、编译或运行工厂任务；使用已有二进制和已记录输入作只读重执行。完整原始记录与带行号的 recipe 源码见 `raw-cycle2.txt`。

## 仍需整改的软件发现

### C2-1：新发现的任意 scalar 算法仍缺可提交的独立语义 oracle，公开工厂交付路径无法完成

`cuda_lowering.py:63–85` 已能识别通用 elementwise 签名；`:190–253` 确实保留实际函数算术/控制流并生成 C++。但 `core_codegen.py:291–321` 的数值测试只给 router、SwiGLU、aggregation、RMSNorm 提供固定独立参考，elementwise-only 没有比较项。`construction.execute` 拒绝 outputs_compared<=0，source ZIP 又依赖此验证。README 明确要求 task-provided semantic oracle，但 `task_contract.py:20–34` 的任务字段没有 oracle；stage 契约也没有 oracle 输入。

因此，“新增 kernel 名称/数学变动可直接生成并手工检验”的 compiler 单元测试，不等于“公开工厂任务能够生成、验证并交付任意已支持新算法”。未知计算可以正确失败，但缺项要形成明确需求，不能把 R3 整体标完成。

更严重的是：混合已知操作和 elementwise 时，总 outputs_compared 可由已知操作贡献，未验证的新操作仍可随整个工程打包；CLI validation_operation 也只选第一个操作。总比较数大于零不能证明每一个 selected operation 均已通过语义验证。现有核心/normalization A/B 均是已知有参考操作，不能覆盖此漏洞。

整改/验收：新增受限、可检查的数值 oracle 契约（真实输入、expected、类型/shape、容差及来源），由实际 stage 读取并校验。至少一个超出既有四类固定参考的真实生产 kernel，经同一 factory/API 目标执行源码发现→lowering→构建→oracle→ZIP；错误 expected 必须阻止交付，无 oracle 明确 blocked；混合已验证/未验证操作时也必须逐项阻断，不能借用其他操作的比较数。每个 selected operation 应有独立验证覆盖账本。不得用生成器自身输出作为期望值。

### C2-2：通用多端口组合仍丢失输出 port 身份

本轮 `add_node` 已按输入绑定/参数/recipe 区分实例，修复了旧全局 stage_id 去重。但 `engine.import_workflow` 将 ExpandedGraph 的内部 binding 降为 node_id/kind，丢掉 source port；`inputs_for` 也以 producer+kind 匹配，不使用 artifact.metadata.output_port。一个合法阶段同时输出两个同 kind 的不同端口时，下游会得到 missing_artifact，或者无法选择该端口对应 validator。当前 STRATA 主要输出 kind 唯一，所以 A/B 没有覆盖此缺陷。

整改/验收：保留 source port 到 node.input_bindings，产物消费按 producer+output_port（或 exact artifact_id）解析并使用正确输出 validator；增加真实文件回归：一个生产阶段两个相同 kind 输出，两个消费者分别读不同内容并生成不同实际结果。相同绑定可复用，不同 port 不能合并。

### C2-3：新动态消费统一账本修复尚未由新运行验证

上述核心运行的 compose 阶段实际读取了3个 lower.core 产物，但 attempt.inputs 只有 source.operations/task.requirements；源码旧版 `product.read_json()` 真实读取，却没把动态输入加入统一 attempt 记录。新 UI 以实际 inputs 判定，所以旧运行3条 lower→compose 边仍 pending；Value Report 同样漏计。

父线程已新增 Stage.dynamic_inputs/Context.consume_json 与 artifact.consumed 事件，这是正确修复方向，但代码发生在这些运行后。需要新候选证明每个实际读入的 lowered artifact 都有 SHA 校验、消费事件和 attempt.inputs 对应，不能补写旧证据。

整改/验收：新运行的所有 compose dynamic inputs 与实际 consumed_lowerings 一一对应，UI/Value Report 使用同一绑定账本；篡改产物或 producer/port 不符应在读取前失败。只声明边或 ledger 通过 schema 不构成消费。

### C2-4：公开父 workflow / 内部路径入口尚缺实际系统运行证据

`workflow_definitions.py` 本轮确有可执行 Workflow/Subworkflow/StageRef、typed binding、expand/import，`--workflow`/API workflow_path 已接入，不再只是分组标签。现有真实核心业务路径使用 invoke_stage 并记录所属路径；但给出的 A/B/native 运行没有 workflow_path，公开选择父 workflow 或内部 stage 的完整 API/CLI 入口尚未由本轮实际任务证明。

整改/验收：至少通过公开入口执行一次父 workflow，再执行其内部阶段路径，确认内部阶段不会无故重放整个父 workflow、输入真实读取、产物可下载；保留请求、展开图、命令和实际输出。孤立测试可支持实现正确性，不能替代这项系统验收。

## 原 R1–R9 的复审判定

| 原要求 | 本轮判定 | 独立观察 |
| --- | --- | --- |
| R1 生成源码接入完整候选 | 软件断链已修；完整运行未验收 | candidate.integrate_generated 真复制已校验源码，改真实调用点/CMake，编译并执行 host bridge；完整 CUDA/native 模型仍未运行 |
| R2 任务/源码驱动阶段选择 | 受限能力范围内 PASS | 新 Task/Acceptance 编译，真实 discovery 后选择并运行 lowerer；A/B最终目标相同但实际插入不同阶段 |
| R3 从固定函数模板转为源算法生成 | 明显修复，仍 PARTIAL | 无旧函数名/hash白名单；真实 kernel 正文经 CUDA primitive lowering 进入 C++，支持新函数/结构变更；通用新算法 factory oracle 仍缺 |
| R4 候选/原版后端分离 | 软件路径 PASS，真实对照 BLOCKED | original 默认 CUDA、candidate 使用目标后端；Native请求的baseline现在因缺nvcc受阻，不再因目标Ascend被误拒 |
| R5 多实例/真实层次 | PARTIAL | 按绑定/参数/recipe 生成实例；真正父定义/阶段展开；仍有同kind多输出port及公开入口系统验证缺口 |
| R6 真消费驱动画布边 | 规则修复；新动态账本待验 | 无inputs的blocked节点边不再因来源成功变绿；旧A/B动态lower产物账本未记录，新代码还需新run |
| R7 固定执行器代码/配方 | 已执行候选的源码 pin PASS | 23文件快照、hash、catalog/request、命令recipe存在且匹配；后续修改清楚显示为新候选 |
| R8 Native完整图/模型/对照 | 未完成，不能归因于硬件一项 | Native计算图仍缺embedding/dense、attention/cache、调度/token loop等；同时缺SDK/设备/模型 |
| R9 真实AI Value评述 | 未完成且诚实标记 | 确定性报告实际生成；model_assessment unavailable、invoked=false，不构成AI模型执行 |

## 已确认改善的真实业务生成链

### A/B不是目标裁剪的旧证明

两个实际请求最终 goals 相同：value.report、construction.package、construction.portability。核心任务要求 routing/activation/aggregation；另一任务在真实 elementwise.cu 中要求 normalization。

- 核心任务在源码 discovery 后新增3个 source.bind_operation 实例、1个 lower.cooperative 和2个 lower.scalar，总19节点。
- normalization 新增1个绑定与1个 lower.cooperative，总15节点。
- 实际 implementation.selected 事件记录源码 descriptor/features、输入 SHA 与所选执行 stage。
- 每个 lowered_cpp 都能在实际生成的 src/strata_core.cpp 中逐字找到。

这确实证明源码内容/显式能力需求参与实现阶段选择，已经超出原版固定 artifact DAG 的单纯截断。当前仍是受支持的 CUDA 语法与 tensor-contract 范围，不是任意仓库/算法的自动建设器。

### 算术不再来自旧路由模板

新 `cuda_lowering` 保存真实 source body，替换 thread/block 索引、shared memory、barrier、shuffle 等执行原语为 C++20 cooperative CPU runtime；原有算术/比较/循环/选择写入保留。旧固定 router whole-body SHA 与固定三个文件名单已移除。ABI wrapper、运行时库与测试参考仍然是预写工程能力，这本身合理；不能把它们描述为全部自动推导。

### 源码到候选连接确有实际工程工作

完整请求中的 candidate.integrate_generated 实际消费 source.checkout 和 construction.source。校验后的 generated files 被复制到 checkout/factory_generated_core；原 router/SwiGLU/MoE combine 的实际函数/launch 调用点和 CMake 被修改。真实 c++ 命令编译复制的 strata_core.cpp、bridge.cpp、host_bridge_test.cpp，host binary exit0，调用计数各1。

这解除旧版完全独立 demo 分支的软件断链。当前 transport 策略显式为 cuda+host_generated_cores，不能称作 Ascend native；实际 CUDA编译、设备graph capture、完整模型仍未验证，相关flags保持false。

### 文件/运行真实性

两组实际 source/build/test/ZIP/rebuild/artifact 哈希均匹配；原有二进制用记录的外部输入再次运行 exit0、stdout与原记录完全相同。核心数值测试比较215项，max_abs_error1.49012e-08；normalization比较99项，误差0。这些都是 CPU reference 范围，不代表设备或原始模型正确性。

完整候选6209个记录源文件重哈希通过，生成manifest身份匹配真实construction.source。Native/fullmodel/baseline/comparison仍被准确阻断；未发现把CPU结果标成Ascend通过。

## 下一轮复审必须检查

1. 新候选执行 recipe 与当前修复源码一致；旧运行不回填。
2. C2-1 oracle输入和C2-2多端口修复有真实文件/进程验证。
3. C2-3动态产物读入凭据与UI/Value Report一致。
4. C2-4公开workflow选择入口真实跑通。
5. 所有失败与资源阻断保留；R8/R9不因上述软件修复被提前标完成。

本报告是中间复审，不是完整交付证书。原始快照、请求、运行图、命令、产物 hash 与事件保存在同目录raw-cycle2.txt。
