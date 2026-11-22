# CMake toolchain: x86_64 host -> aarch64 Linux (DGX Spark / GB10, CUDA 13, sm_121).
#
# Inputs (environment variable, or -D cache variable of the same name; cache wins):
#   CROSS_TRIPLE        compiler triple prefix            (default aarch64-linux-gnu)
#   CROSS_TOOLCHAIN_BIN dir holding <triple>-gcc/g++       (default: search PATH)
#   CROSS_SYSROOT       sysroot for gcc/ld                 (default: none = Ubuntu's
#                       gcc-aarch64-linux-gnu layout under /usr/aarch64-linux-gnu)
#   CUDA_TOOLKIT_ROOT   CUDA 13 toolkit with an x86_64 nvcc in bin/ and the aarch64
#                       server target in targets/sbsa-linux (default /usr/local/cuda;
#                       the apt package cuda-cross-sbsa-13-0 provides that target)
#   CUDA_TARGET_NAME    target dir name under targets/     (default sbsa-linux)
#
# Use:  cmake -DCMAKE_TOOLCHAIN_FILE=.../aarch64-cuda13.toolchain.cmake ...

macro(_xopt name default)
  if(NOT DEFINED ${name})
    if(DEFINED ENV{${name}} AND NOT "$ENV{${name}}" STREQUAL "")
      set(${name} "$ENV{${name}}")
    else()
      set(${name} "${default}")
    endif()
  endif()
endmacro()
_xopt(CROSS_TRIPLE aarch64-linux-gnu)
_xopt(CROSS_TOOLCHAIN_BIN "")
_xopt(CROSS_SYSROOT "")
_xopt(CUDA_TOOLKIT_ROOT /usr/local/cuda)
_xopt(CUDA_TARGET_NAME sbsa-linux)
# try_compile sub-projects re-read this file: forward the inputs
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES
     CROSS_TRIPLE CROSS_TOOLCHAIN_BIN CROSS_SYSROOT CUDA_TOOLKIT_ROOT CUDA_TARGET_NAME)

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

if(CROSS_TOOLCHAIN_BIN)
  set(_xprefix "${CROSS_TOOLCHAIN_BIN}/${CROSS_TRIPLE}-")
else()
  set(_xprefix "${CROSS_TRIPLE}-")
endif()
set(CMAKE_C_COMPILER   "${_xprefix}gcc")
set(CMAKE_CXX_COMPILER "${_xprefix}g++")
set(CMAKE_AR      "${_xprefix}ar"      CACHE FILEPATH "")
set(CMAKE_RANLIB  "${_xprefix}ranlib"  CACHE FILEPATH "")
set(CMAKE_STRIP   "${_xprefix}strip"   CACHE FILEPATH "")

set(_xcuda_target "${CUDA_TOOLKIT_ROOT}/targets/${CUDA_TARGET_NAME}")
set(CMAKE_CUDA_COMPILER "${CUDA_TOOLKIT_ROOT}/bin/nvcc")
set(CMAKE_CUDA_HOST_COMPILER "${CMAKE_CXX_COMPILER}")
set(CUDAToolkit_ROOT "${CUDA_TOOLKIT_ROOT}")
# nvcc otherwise picks targets/x86_64-linux for headers and libs
set(CMAKE_CUDA_FLAGS_INIT "--target-directory=${CUDA_TARGET_NAME}")

set(_xld "")
if(CROSS_SYSROOT)
  set(CMAKE_SYSROOT "${CROSS_SYSROOT}")
  # CMake does not forward CMAKE_SYSROOT to nvcc's host compiler, nor to the host
  # compiler when it links CUDA executables/try_compile checks
  string(APPEND CMAKE_CUDA_FLAGS_INIT " -Xcompiler=--sysroot=${CROSS_SYSROOT}")
  set(_xld "--sysroot=${CROSS_SYSROOT}")
  # Debian/Ubuntu multiarch-cross layout keeps target libs in <sysroot>/usr/<triple>
  set(_xtarget_root "${CROSS_SYSROOT}" "${CROSS_SYSROOT}/usr/${CROSS_TRIPLE}")
else()
  set(_xtarget_root "/usr/${CROSS_TRIPLE}")
endif()

set(CMAKE_FIND_ROOT_PATH "${_xcuda_target}" ${_xtarget_root})
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# libggml-cuda.so needs libcuda.so.1 (the driver), which only exists on the GPU
# machine. Link against the toolkit stub: expose it under its soname for -rpath-link
# so that linking executables against libggml-cuda.so resolves the cu* symbols.
set(_xstubs "${_xcuda_target}/lib/stubs")
if(EXISTS "${_xstubs}/libcuda.so")
  set(_xstub_dir "${CMAKE_BINARY_DIR}/_cuda_stub_soname")
  if(NOT EXISTS "${_xstub_dir}/libcuda.so.1")
    file(MAKE_DIRECTORY "${_xstub_dir}")
    file(CREATE_LINK "${_xstubs}/libcuda.so" "${_xstub_dir}/libcuda.so.1" SYMBOLIC)
  endif()
  string(APPEND _xld " -Wl,-rpath-link,${_xstub_dir} -Wl,-rpath-link,${_xcuda_target}/lib")
endif()
# set (not append): this file is read once per (try_compile) project
set(CMAKE_EXE_LINKER_FLAGS_INIT "${_xld}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_xld}")
set(CMAKE_MODULE_LINKER_FLAGS_INIT "${_xld}")
