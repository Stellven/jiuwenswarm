"""Reproducible, opt-in source change to the pinned STRATA inference expert path."""
from __future__ import annotations
import hashlib
from pathlib import Path
import shutil

PIN = '13eedf552417a6a791a7d13c6597e24300ee3a09'
ROOT = Path(__file__).with_name('strata_port')

def apply_port(checkout: Path) -> dict:
    """Apply to a separate implementation checkout; never modify the acquired baseline."""
    changes = []
    for source in ROOT.rglob('*'):
        if source.is_file():
            relative = source.relative_to(ROOT)
            target = checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            changes.append(str(relative))
    path = checkout / 'src/kernels/cpu/pool.cpp'
    content = path.read_text()
    anchor = '#include "strata/kernels/cpu/expert_layout.hpp"'
    if 'strata/kernels/ascend/expert_adapter.hpp' not in content:
        if anchor not in content: raise ValueError('pinned ExpertPool include anchor missing')
        content = content.replace(anchor, anchor+'\n#include "strata/kernels/ascend/expert_adapter.hpp"', 1)
        content = content.replace('void ExpertPool::run_split(ExpertJob* jobs, int n) {', 'void ExpertPool::run_split(ExpertJob* jobs, int n) {\n    if (strata::kernels::ascend::requested()) { run(jobs, n); return; }', 1)
        content = content.replace('if (n > kMaxSplitMulti || expert_oracle_q8_0_enabled()) {', 'if (n > kMaxSplitMulti || expert_oracle_q8_0_enabled() || strata::kernels::ascend::requested()) {', 1)
        content = content.replace('void ExpertPool::run_split_multi_native(const NativeFmt& f, ExpertJobMulti* jobs, int n, NativeArithmetic arithmetic) {', 'void ExpertPool::run_split_multi_native(const NativeFmt& f, ExpertJobMulti* jobs, int n, NativeArithmetic arithmetic) {\n    if (strata::kernels::ascend::requested()) throw std::runtime_error("Ascend expert port supports canonical Q2_0 only; native IQ/K-quant/Hadamard packs require implemented conversion, not field aliases");', 1)
        content = content.replace('void ExpertPool::run(ExpertJob* jobs, int n) {', 'void ExpertPool::run(ExpertJob* jobs, int n) {\n    if (strata::kernels::ascend::requested()) {\n        for (int i = 0; i < n; ++i) strata::kernels::ascend::run_expert(jobs[i].blob, *jobs[i].act, jobs[i].out);\n        return;\n    }', 1)
        path.write_text(content)
    changes.append(str(path.relative_to(checkout)))
    path = checkout/'cmake/backends/cpu.cmake'
    content = path.read_text()
    marker = '# Software Factory: opt-in Ascend canonical expert projections.'
    if marker not in content:
        anchor='target_include_directories(strata_kernels_cpu PUBLIC include)'
        if anchor not in content: raise ValueError('pinned CPU library anchor missing')
        addition = '''
# Software Factory: opt-in Ascend canonical expert projections.
# This is NOT an Ascend full-model backend; attention/SSM/cache migration is separate.
target_sources(strata_kernels_cpu PRIVATE src/kernels/ascend/expert.cpp)
option(STRATA_ENABLE_ASCEND_EXPERTS "Compile CANN execution of canonical Q2_0 expert projections (not full-model inference)" OFF)
if(STRATA_ENABLE_ASCEND_EXPERTS)
  set(ASCEND_HOME_PATH "$ENV{ASCEND_HOME_PATH}" CACHE PATH "CANN toolkit root")
  find_path(STRATA_CANN_INCLUDE acl/acl.h PATHS "${ASCEND_HOME_PATH}/include" REQUIRED NO_DEFAULT_PATH)
  find_library(STRATA_ASCENDCL ascendcl PATHS "${ASCEND_HOME_PATH}/lib64" REQUIRED NO_DEFAULT_PATH)
  find_library(STRATA_OPAPI opapi PATHS "${ASCEND_HOME_PATH}/lib64" REQUIRED NO_DEFAULT_PATH)
  target_include_directories(strata_kernels_cpu PRIVATE ${STRATA_CANN_INCLUDE})
  target_compile_definitions(strata_kernels_cpu PRIVATE STRATA_ENABLE_ASCEND_EXPERTS=1)
  target_link_libraries(strata_kernels_cpu PUBLIC ${STRATA_ASCENDCL} ${STRATA_OPAPI})
endif()
if(STRATA_BUILD_TESTS)
  add_executable(strata_ascend_adapter_test src/kernels/ascend/expert_adapter_test.cpp)
  target_link_libraries(strata_ascend_adapter_test PRIVATE strata_kernels_cpu)
  add_test(NAME strata_ascend_adapter_test COMMAND strata_ascend_adapter_test)
  set_tests_properties(strata_ascend_adapter_test PROPERTIES SKIP_RETURN_CODE 77)
endif()
'''
        path.write_text(content.replace(anchor, anchor+addition, 1))
    changes.append(str(path.relative_to(checkout)))
    return {'patch_scope':'canonical Q2_0 ExpertPool path', 'files':[{'path':p,'sha256':hashlib.sha256((checkout/p).read_bytes()).hexdigest()} for p in changes],
            'full_ascend_backend_implemented':False,
            'unimplemented_full_model_operations':['embedding and dense projections','router top-k on Ascend','QSA/GDN attention and recurrent state','KV/cache/device graph management','sampler and output token loop'],
            'source_pin':PIN}
