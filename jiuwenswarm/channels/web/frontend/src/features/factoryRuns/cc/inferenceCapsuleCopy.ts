export const prefixReuseId = 'engine.kv_reuse_lab';
export const warmTolerance = "Same as AQB: within the checker's 10% tolerance on the same server (measured ratios 0.95 to 1.03).";
export const demoCapsuleIds: readonly string[] = ['weights.build_weight_pack_compiler', 'engine.size_prefill_batch', prefixReuseId];

export const inferenceCapsules: Record<string, { title: string; method: string; evidence: string }> = {
  'weights.build_weight_pack_compiler': {
    title: 'Quantization',
    method: 'Chooses a bit width per weight group from a sensitivity census and builds the pack.',
    evidence: 'The 267.2 GB mixed pack uses IQ2_XXS for gate and up projections and Q2_K for down projections. The original NVFP4 pack was 528.9 GB.',
  },
  'engine.size_prefill_batch': {
    title: 'Prefill plan',
    method: 'Sizes prefill batches to the target device budget using measured allocation and compute costs.',
    evidence: 'The mixed-pack microbatch grew from 512 to 2048 tokens. The NVFP4 arm used its defaults.',
  },
  [prefixReuseId]: {
    title: 'Prefix reuse',
    method: "Turns on the engine's built-in prompt cache for document follow-up workloads.",
    evidence: 'Cache on per request; the follow-up gain comes from that. AQBC kept --swa-full and --ctx-checkpoints 32 as measured, with 736 MiB more KV and 5,704 MiB of device headroom.',
  },
  'weights.build_muse_nvfp4_reader': {
    title: 'Checkpoint converter',
    method: 'Maps checkpoint tensors and scale metadata into the engine’s weight format and checks the mapping on a small fixture.',
    evidence: 'Run 1 converted stacked Muse NVFP4 experts and their scale planes into GGUF. The converter fixture matched the pinned weight values.',
  },
  'weights.build_expert_scale_wiring': {
    title: 'Expert scale wiring',
    method: 'Applies stored quantization scales at the engine operation that consumes the weights.',
    evidence: 'Run 1 wired the per-expert NVFP4 scales. The separate small-fixture check confirmed numerical agreement and matching scale-free output.',
  },
  'factory.source_workbench': {
    title: 'Source integration workbench',
    method: 'Edits a task-owned checkout and records the exact source revision used by the build.',
    evidence: 'Run 1 kept the converter and expert-scale wiring changes in the pinned engine checkout.',
  },
  'factory.capped_runner': {
    title: 'Capped run workbench',
    method: 'Runs declared jobs under host resource limits and retains their execution receipts.',
    evidence: 'Run 1 retained scoped build and pack evidence. Run 2 recorded a single 96 GiB, zero-swap target load for lab acceptance.',
  },
  'factory.lab_manager': {
    title: 'Lab manager',
    method: 'Seals the image and its test requirements in a package for delivery to the lab agent.',
    evidence: 'Run 1 recorded the verified engine handoff. Run 2 linked its test requirements to the factory-checked AQBC image in the lab mailbox.',
  },
  'factory.builder': {
    title: 'Image assembler',
    method: 'Packages a pinned executable and launch configuration as an identified image and records how it was built.',
    evidence: 'Run 1 packaged the built engine. Run 2 assembled the AQBC config-only image from AQB with the same executable and pack.',
  },
  'factory.node_check': {
    title: 'Node verifier',
    method: 'Checks a node’s output against the contract written by the scheduler.',
    evidence: 'Run 2 checked that the accepted lab verdict and factory checks referred to the same sealed delivery before release.',
  },
};

export function capsuleStage(output: string, node: string) {
  if (node === 'measure_engine' || (node === 'build_base_engine' && output === 'smoke')) return 'Runtime stage';
  if (node === 'size_prefill_batch' && output === 'batch_plan') return 'Factory stage · uses runtime evidence';
  return 'Factory stage';
}
