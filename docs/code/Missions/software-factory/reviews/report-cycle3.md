# 独立复审 Cycle 3：动态流程生成业务源码

**核心结论：对于本轮已支持的 CPU 核心工程，业务源码确实由运行中的源码驱动动态微阶段流程生成、构建和验证。本轮 Cycle 2 的四项软件整改均有修复证据。完整 STRATA / Huawei Native 交付仍为 NOT_COMPLETE；完整 native 计算图、模型推理和真实 AI Value 评述尚未通过。**

审计为只读；未修改产品代码，未自行创建工厂任务、克隆或构建。核对了源码、冻结 recipe、真实请求/图/命令/日志、全部产物哈希、ZIP成员、正负例，并用已有 CPU 二进制读取原始输入作重执行。没有把测试数量、JSON布尔值或界面颜色单独作为通过依据。

## 仍未完成的交付项

1. **R8仍有软件实现缺口和资源阻断。**完整native embedding/dense、专家执行、attention/KV/cache、调度与token loop尚未完成，SDK/设备/模型也缺失。真实Native case已准确BLOCKED；没有Native模型推理或原版数值对照结果。不能把下一步概括为“只等硬件”。
2. **R9真实AI模型评述尚未执行。**Value Agent的事实报告真实生成；模型运行依赖/配置不可用，记录invoked=false。当前不是AI模型评述通过。
3. **最终发布必须指向新候选。**先前稳定路径 `/workspace/strata_native/` 以及 `/workspace/software-factory-delivery/huawei_native_strata.zip` 在本次检查时仍是Cycle1历史版本。新Cycle3产物在下列真实run目录；后续应发布新的带版本交付包或准确引用run产物，不得把旧链接描述为新实现。此项属于发布指向问题，不否定新run产物真实性。

本轮审查范围内未再发现与C2-1～4同等级、阻断这些CPU构建案例的软件问题。该结论不证明任意CUDA程序、任意仓库或完整Native模型已经受支持。

## 固定审计候选

8个实际运行使用相同执行器源码recipe digest：

```text
29da76161cef3dd019d2b2d3c06fdc3650d6170b986017827b4711dc9fbe4cea
```

每个recipe保留24个执行器代码文件、请求、catalog、解释器/包信息与命令身份；manifest、source snapshots及当前working文件哈希匹配。本轮修改没有回填旧Cycle1/2运行。

宿主分支仍为AI4Research-Main，HEAD `141c1c401138f916af0a41aca791adf226d814c7`；新实现位于未提交工作区，由上述源码recipe固定。STRATA唯一目标仍为 `niko1221/strata @ 13eedf552417a6a791a7d13c6597e24300ee3a09`。

| 案例 | 实际run | 结果 |
| --- | --- | --- |
| routing/activation/aggregation | 6db7a2b968c8434eaa9a508a6d16a7cf | COMPLETED |
| normalization | 02446be989844a3fb7e43dc9bd6a8e0a | COMPLETED |
| routing + scale独立oracle | b152d434c8e14b01adc8c4aa40ad83f2 | COMPLETED |
| 完整Native/原版对照目标 | baf3d77a8301423180ccda45fb11c66b | BLOCKED |
| 公开父workflow | 9e4d7d2016844066b504d87bc712b06c | COMPLETED |
| 缺oracle负例 | 68c1f757248741c6b14d0bcf7a3fc978 | BLOCKED |
| 错oracle负例 | 0121a742659c402eb9efc66265502573 | FAILED |
| 公开内部阶段 | cab4cb9235184b8d9b45c1ef40825589 | COMPLETED |

完整原始内容保存于 `raw-cycle3.txt`。未把BLOCKED/FAILED当作成功。

## C2-1：逐算子语义验证与真实oracle——已修复并验证

源码证据：

- `task_contract.py:20–40` 接受受限task.oracle数据。
- `oracle_validation.py:46–101` 只允许有界的数值输入、数值期望、容差、精确操作身份；不接受任意代码、命令或外部路径。
- `core_codegen.py:293–389` 为每一个具体source_id产生operation_checks，未知操作明确unverified，不借用其他操作的比较数。
- `oracle_validation.py:171–196` 按每个source_id合并内建/外部验证账本；`:281–324` 逐项判定，任何未覆盖操作阻断交付。
- `construction_pipeline.py:175–198` 真执行self-test和用户oracle，缺oracle为blocked，错oracle为failed。ZIP依赖这一实际结果。

本轮实际验证记录：

```text
core:
  router_top10_kernel      284 built-in comparisons, passed
  swiglu_kernel            51 built-in comparisons, passed
  moe_combine_kernel       17 built-in comparisons, passed
normalization:
  rms_norm_weighted_kernel 99 built-in comparisons, passed
mixed:
  router_top10_kernel      284 built-in comparisons, passed
  scale_kernel              4 external comparisons, passed
```

mixed case实际调用精确source ID：

```text
--operation src/kernels/cuda/elementwise.cu:scale_kernel
input: 4 2 1 -2 0 3.5
actual output: [2,-4,0,7]
```

该算术来自真实STRATA生产kernel，实际lowering进入编译的C++。任务期望数据独立提供，不是用同次程序输出伪造期望。

负例1：已有router284次比较通过，scale没有oracle仍触发numerical_oracle_missing；未发布package。

负例2：期望首项999，实际2，真实误差997，触发oracle_numerical_mismatch；未发布package。

mixed ZIP在独立目录重新构建，真实CTest包含并通过source_lowered_core_numerical和task_oracle_acceptance。由此验证了交付包保留所需验收入口。有限输入的数值通过不等于对任意输入的数学证明，也不等于完整模型正确性。

## C2-2：相同kind多输出端口与多实例——修复已核对

`engine.py:249–268` 的direct invocation保留artifact output_port并按端口取输出；`:270–308` 的父workflow导入保留source port；`:323–348` 的消费端按producer、exact artifact ID和port选择并执行对应validator。

同一个stage的实例身份包含输入绑定、参数和recipe，两个不同输入不会再因stage_id相同而合并。`tests/software_factory/test_port_bindings.py` 包含真实文件/进程回归，分别覆盖两个相同kind端口的不同内容、正确validator、父workflow/内部阶段和每个绑定的安全复用。本轮81项总测试中相关三项通过。

当前真实STRATA案例的主要端口kind仍唯一；多端口回归属于明确隔离的机制测试，其结果不冒充模型或设备验证。

## C2-3：动态读取账本、画布和报告——已由新运行验证

`Context.consume_json`（engine.py:61–75）先检查动态输入声明、published身份、producer verified、当前文件SHA并真实解析，再记录attempt.inputs、边和artifact.consumed事件。

实际compose阶段：

- core：3个core.lowered输入，3条消费事件；
- normalization：1个输入/事件；
- mixed：2个输入/事件。

每项ID/producer/kind/path/SHA均对应实际published文件，重新计算SHA一致。`source_planning.py:124` 使用此入口读取lowerer输出；源码生成消费相应合并IR。

前端 `graphLayout.ts:32–50` 使用下游实际attempt和published输入身份，不再以来源verified直接将未执行边染绿。旧Cycle2未记录receipt的运行没有被回填；本次证据来自新运行。

## C2-4：公开父workflow与内部阶段入口——两种实际运行均通过

公开父workflow请求：

```text
workflow_path=source_acquisition
```

实际运行workflow.execute、source.fetch、source.cuda_ast、source.discover，执行真实git和Python分析，导出source/inventory/discovery三个实际typed artifacts。

公开内部阶段请求：

```text
workflow_path=source_acquisition/cuda_analysis/scan
```

实际节点严格为：

```text
workflow.execute
source.fetch
source.cuda_ast
```

没有重放source.discover兄弟。source.fetch是该内部阶段真实source.checkout依赖；扫描实际读取该checkout并写出inventory。原始请求、展开图、进程记录及输出artifact均已核对。

因此，当前层次结构已经具有真实定义、typed ports、展开/导入和可执行选择，不能继续按旧版“只有分组标签”评价。

## 本轮业务生成链的独立结论

两个CPU任务的最终产物目标相同，源码与能力需求不同；discovery之后实际插入不同函数提取实例及scalar/cooperative lowerer。运行中每个选择都有descriptor/features与输入SHA。不同路径不再只是旧版不同goal截断同一条链。

生成器将真实CUDA函数的算术、比较、循环和选择语句保留，转换执行原语到明确的C++20 cooperative CPU runtime。固定三函数身份及整段路由哈希白名单已经移除。ABI wrapper、执行运行时、受限语法支持和独立测试参考是预写能力边界；未知helper/类型/collective仍明确拒绝。

每个lowered_cpp片段在实际生成src中出现；源manifest、构建消费路径、测试、ZIP成员和独立重建逐个哈希匹配。已有core/normalization/mixed二进制使用记录的输入重执行，exit0且stdout与原记录相同。本轮范围内没有发现预制成功状态替代计算或计时器模拟执行。

## 原R1–R9当前状态

| 要求 | 当前判定 |
| --- | --- |
| R1 生成源码进入完整候选 | 接线与host bridge真实验证；完整CUDA/Native模型消费仍NOT_RUN |
| R2 任务/源码驱动实现阶段选择 | 本轮受支持CPU能力范围PASS |
| R3 真实算法生成与逐项验证 | 支持的CUDA语法/数值oracle范围PASS；非任意算法/Native编译器 |
| R4 原版/候选backend分离 | 软件角色合同已修；真实双后端模型对照BLOCKED |
| R5 父/子/内部阶段与实例 | 定义/多实例/端口回归及公开父/内部实际入口PASS |
| R6 实际消费状态 | 新实际receipt与严格UI判定PASS |
| R7 运行时源码版本 | 本轮24文件recipe与请求/命令身份PASS；非完全封闭的系统环境快照 |
| R8 全部Native计算/设备/模型/对照 | 未完成，既有软件缺项又缺资源 |
| R9 真实AI Value评述 | 未完成；确定性证据报告真实，AI invoked=false |

完整候选本轮确实消费当前construction.source，复制生成源码，修改实际router/SwiGLU/combine调用点及CMake，编译并执行host bridge。该验证使用明确隔离的host transport测试，只证明接线与真实CPU生成数学，没有验证CUDA transport、graph capture、设备或模型。策略明确为cuda+host_generated_cores，不是Ascend回退。

## 后续不能降低的验收

- 继续实现R8中缺失的真实Native计算图和执行能力；不能只等待设备。
- 资源就绪后实际target编译、设备加载、算子执行、真实模型权重推理、原版对照，分别记录。
- 有真实可用模型/provider后执行R9并保存模型调用provenance；当前不得称AI评述通过。
- 新发布源码/工厂代码包必须标识本轮recipe，旧包作为历史保留；发布后应核对下载字节与本轮生成src。
- 新软件修改应产生新recipe/实际运行并独立复审，不改写本轮或旧轮结果。

本报告是受限CPU构建能力的独立验收及完整目标的未完成声明，不是完整STRATA/Huawei Native交付证书。
