# Copyright 2024 DreamWorks Animation LLC
# SPDX-License-Identifier: Apache-2.0

# These ExternalProject targets can be used to download, build and
# install many of the MoonRay dependencies on Windows.
# Run from a Visual Studio 2022 x64 Developer Command Prompt or
# a terminal where vcvars64.bat has already been sourced, with
# Ninja and CMake 3.23.1+ on PATH.
#
# Usage:
#   cmake -G Ninja -DCMAKE_BUILD_TYPE=Release \
#         -DInstallRoot=C:/MoonRay/installs \
#         C:/MoonRay/source/openmoonray/building/windows
#   cmake --build . -- -j <nproc>
#
# Pass -DNO_USD=1 to skip building USD (e.g. when using Houdini's USD).
# Pass -DNO_QT=1  to skip building Qt 5 (no GUI tools).
# Pass -DNO_CUDA=1 to skip OptiX headers (no GPU support).

cmake_minimum_required(VERSION 3.23.1)
project(openmoonray_third_party_windows)

include(ExternalProject)
cmake_policy(SET CMP0135 NEW)

include(ProcessorCount)
ProcessorCount(N)
if(NOT N EQUAL 0)
    set(JOBS_ARG -j${N})
endif()

# ---------------------------------------------------------------------------
# User-configurable paths
# ---------------------------------------------------------------------------
set(InstallRoot "C:/MoonRay/installs" CACHE FILEPATH "Install root for dependencies")
set(PythonRoot  "C:/Python39"         CACHE FILEPATH "Root of Python 3.9 installation")
set(PythonVer   "3.9"                 CACHE STRING   "Python version (major.minor), e.g. 3.9")

# Derive the python executable and library paths from PythonRoot
set(PYTHON_EXE       "${PythonRoot}/python.exe")
set(PYTHON_INCLUDE   "${PythonRoot}/include")
set(PYTHON_LIB       "${PythonRoot}/libs/python${PythonVer_nodot}.lib")
string(REPLACE "." "" PythonVer_nodot "${PythonVer}")
set(PYTHON_LIB       "${PythonRoot}/libs/python${PythonVer_nodot}.lib")

# Common CMake args used by most dependencies
set(COMMON_CMAKE_ARGS
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_INSTALL_PREFIX:PATH=${InstallRoot}
    -DCMAKE_PREFIX_PATH:PATH=${InstallRoot}
    -DBUILD_SHARED_LIBS=ON
)

# ---------------------------------------------------------------------------
# zlib  (needed by many deps; use vcpkg-provided if available, else build)
# ---------------------------------------------------------------------------
ExternalProject_Add(zlib
    GIT_REPOSITORY https://github.com/madler/zlib.git
    GIT_TAG        cacf7f1d4e3d44d871b605da3b647f07d718623f # v1.2.13
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DZLIB_BUILD_EXAMPLES=OFF
)
set(CHAIN zlib)

# ---------------------------------------------------------------------------
# JsonCpp
# ---------------------------------------------------------------------------
ExternalProject_Add(JsonCpp
    GIT_REPOSITORY https://github.com/open-source-parsers/jsoncpp.git
    GIT_TAG        5defb4ed1a4293b8e2bf641e16b156fb9de498cc # 1.9.5
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DJSONCPP_LIB_BUILD_SHARED:BOOL=ON
        -DJSONCPP_WITH_PKGCONFIG_SUPPORT=OFF
        -DPYTHON_EXECUTABLE=${PYTHON_EXE}
    DEPENDS ${CHAIN}
)
set(CHAIN JsonCpp)

# ---------------------------------------------------------------------------
# OpenSubdiv  (headers + minimal library; no GL, no CUDA, no tests)
# ---------------------------------------------------------------------------
ExternalProject_Add(OpenSubdiv
    GIT_REPOSITORY https://github.com/PixarAnimationStudios/OpenSubdiv
    GIT_TAG        8ffa2b6566be10209529d7a0d1db02a0796b160c # v3_5_0
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DCMAKE_BUILD_TYPE=Release
        -DPYTHON_EXECUTABLE=${PYTHON_EXE}
        -DNO_PTEX=1 -DNO_OMP=1 -DNO_TBB=1 -DNO_CUDA=1 -DNO_GLFW=1 -DNO_DOC=1
        -DNO_OPENCL=1 -DNO_CLEW=1 -DNO_REGRESSION=1 -DNO_EXAMPLES=1 -DNO_TUTORIALS=1 -DNO_GLTESTS=1
        -DNO_MACOS_FRAMEWORK=1 -DNO_METAL=1 -DNO_TESTS=1
    DEPENDS ${CHAIN}
)
set(CHAIN OpenSubdiv)

# ---------------------------------------------------------------------------
# OpenEXR / Imath  (static build to avoid DLL collisions)
# ---------------------------------------------------------------------------
ExternalProject_Add(OpenEXR
    GIT_REPOSITORY https://github.com/AcademySoftwareFoundation/openexr
    GIT_TAG        68d9e1e17620cef00e59b43fa42c97fbcf90e72b # v3.1.8
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DBUILD_SHARED_LIBS=OFF
        -DOPENEXR_BUILD_TOOLS=OFF
        -DOPENEXR_INSTALL_EXAMPLES=OFF
    DEPENDS ${CHAIN}
)
set(CHAIN OpenEXR)

# ---------------------------------------------------------------------------
# Random123  (headers-only; copy the include dir)
# ---------------------------------------------------------------------------
ExternalProject_Add(Random123
    GIT_REPOSITORY https://github.com/DEShawResearch/random123
    GIT_TAG        726a093cd9a73f3ec3c8d7a70ff10ed8efec8d13 # v1.14.0
    BUILD_IN_SOURCE 1
    CONFIGURE_COMMAND ""
    BUILD_COMMAND     ""
    INSTALL_COMMAND   ${CMAKE_COMMAND} -E copy_directory
                          <SOURCE_DIR>/include/Random123
                          ${InstallRoot}/include/Random123
    DEPENDS ${CHAIN}
)
set(CHAIN Random123)

# ---------------------------------------------------------------------------
# ISPC  (pre-built Windows binary from ispc.github.io)
# ---------------------------------------------------------------------------
ExternalProject_Add(ISPC
    URL             https://github.com/ispc/ispc/releases/download/v1.21.0/ispc-v1.21.0-windows.zip
    BUILD_IN_SOURCE 1
    CONFIGURE_COMMAND ""
    BUILD_COMMAND     ""
    INSTALL_COMMAND   ${CMAKE_COMMAND} -E copy
                          <SOURCE_DIR>/bin/ispc.exe
                          ${InstallRoot}/bin/ispc.exe
    DEPENDS ${CHAIN}
)
set(CHAIN ISPC)

# ---------------------------------------------------------------------------
# Intel oneTBB
# ---------------------------------------------------------------------------
ExternalProject_Add(TBB
    URL https://github.com/oneapi-src/oneTBB/archive/refs/tags/v2020.3.3.tar.gz
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DTBB_TEST=OFF
        -DTBB_EXAMPLES=OFF
    DEPENDS ${CHAIN}
)
set(CHAIN TBB)

# ---------------------------------------------------------------------------
# Embree  (uses ISPC, TBB)
# ---------------------------------------------------------------------------
ExternalProject_Add(embree
    GIT_REPOSITORY https://github.com/embree/embree
    GIT_TAG        341ef8c45d1ae072ead1ab65cd76e88b03d9302c # v4.2.0
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DEMBREE_ISPC_EXECUTABLE=${InstallRoot}/bin/ispc.exe
        -DEMBREE_ISPC_SUPPORT=ON
        -DEMBREE_IGNORE_INVALID_RAYS=ON
        -DEMBREE_RAY_MASK=ON
        -DEMBREE_MAX_ISA=AVX512
        -DEMBREE_TUTORIALS=OFF
        -DTBB_ROOT=${InstallRoot}
    DEPENDS ${CHAIN}
)
set(CHAIN embree)

# ---------------------------------------------------------------------------
# OpenColorIO  v2
# ---------------------------------------------------------------------------
ExternalProject_Add(OpenColorIO
    GIT_REPOSITORY https://github.com/AcademySoftwareFoundation/OpenColorIO
    GIT_TAG        d1ef24cbf8021f642e42f45f50c2cd4cc77141ce # v2.2.1
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DOCIO_BUILD_APPS=OFF
        -DOCIO_BUILD_TESTS=OFF
        -DOCIO_BUILD_GPU_TESTS=OFF
        -DOCIO_USE_SSE=OFF
        -DOCIO_BUILD_PYTHON=OFF
        -DOCIO_BUILD_STATIC=OFF
        -DCMAKE_CXX_STANDARD=17
    DEPENDS ${CHAIN}
)
set(CHAIN OpenColorIO)

# ---------------------------------------------------------------------------
# libjpeg-turbo
# ---------------------------------------------------------------------------
ExternalProject_Add(JPEGTurbo
    GIT_REPOSITORY https://github.com/libjpeg-turbo/libjpeg-turbo
    GIT_TAG        bb3d325624526c91646bb9af9578d7198c082d51 # 2.0.1
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DWITH_SIMD=FALSE
    DEPENDS ${CHAIN}
)
set(CHAIN JPEGTurbo)

# ---------------------------------------------------------------------------
# LibTIFF
# ---------------------------------------------------------------------------
ExternalProject_Add(TIFF
    URL https://gitlab.com/libtiff/libtiff/-/archive/v4.0.7/libtiff-v4.0.7.tar.gz
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
    DEPENDS ${CHAIN}
)
set(CHAIN TIFF)

# ---------------------------------------------------------------------------
# OpenImageIO  (OIIO 2.4.x)
# ---------------------------------------------------------------------------
ExternalProject_Add(OpenImageIO
    GIT_REPOSITORY https://github.com/OpenImageIO/oiio
    GIT_TAG        4991ac482e09bd8feff9ad7d984271cfdc315bff # 2.4.8.0
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DOpenEXR_ROOT=${InstallRoot}
        -DUSE_QT=OFF
        -DUSE_PYTHON=ON
        -DPYTHON_EXECUTABLE=${PYTHON_EXE}
    DEPENDS ${CHAIN}
)
set(CHAIN OpenImageIO)

# ---------------------------------------------------------------------------
# OpenImageDenoise  (pre-built Windows binary from OIDN releases)
# ---------------------------------------------------------------------------
ExternalProject_Add(OpenImageDenoise
    URL             https://github.com/OpenImageDenoise/oidn/releases/download/v2.3.3/oidn-2.3.3.x64.windows.zip
    BUILD_IN_SOURCE 1
    CONFIGURE_COMMAND ""
    BUILD_COMMAND     ""
    INSTALL_COMMAND   ${CMAKE_COMMAND} -E copy_directory
                          <SOURCE_DIR>
                          ${InstallRoot}
    DEPENDS ${CHAIN}
)
set(CHAIN OpenImageDenoise)

# ---------------------------------------------------------------------------
# Log4cplus  (Windows-friendly CMake build)
# ---------------------------------------------------------------------------
ExternalProject_Add(Log4CPlus
    GIT_REPOSITORY https://github.com/log4cplus/log4cplus
    GIT_TAG        REL_2_0_5
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DLOG4CPLUS_BUILD_TESTING=OFF
        -DLOG4CPLUS_BUILD_LOGGINGSERVER=OFF
        -DUNICODE=OFF
    DEPENDS ${CHAIN}
)
set(CHAIN Log4CPlus)

# ---------------------------------------------------------------------------
# Lua 5.4  (CMake build; upstream lua only ships a Makefile, use luarocks fork)
# ---------------------------------------------------------------------------
ExternalProject_Add(Lua
    GIT_REPOSITORY https://github.com/walterschell/Lua
    GIT_TAG        v5.4.5
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DLUA_BUILD_COMPILER=ON
    DEPENDS ${CHAIN}
)
set(CHAIN Lua)

# ---------------------------------------------------------------------------
# Blosc  (needed by OpenVDB)
# ---------------------------------------------------------------------------
ExternalProject_Add(Blosc
    GIT_REPOSITORY https://github.com/Blosc/c-blosc
    GIT_TAG        v1.21.5
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DBUILD_TESTS=OFF
        -DBUILD_BENCHMARKS=OFF
        -DPREFER_EXTERNAL_ZLIB=ON
    DEPENDS ${CHAIN}
)
set(CHAIN Blosc)

# ---------------------------------------------------------------------------
# OpenVDB  (9.1)
# ---------------------------------------------------------------------------
ExternalProject_Add(OpenVDB
    GIT_REPOSITORY https://github.com/AcademySoftwareFoundation/openvdb
    GIT_TAG        ab935574cdb25c3df66b068fce2a3b0a74281c54 # v9.1.0
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DBlosc_ROOT=${InstallRoot}
        -DTBB_ROOT=${InstallRoot}
        -DOPENVDB_BUILD_BINARIES=OFF
        -DOPENVDB_BUILD_PYTHON_MODULE=OFF
        -DUSE_BLOSC=ON
    DEPENDS ${CHAIN}
)
set(CHAIN OpenVDB)

# ---------------------------------------------------------------------------
# libcurl  (with OpenSSL backend bundled via schannel on Windows)
# ---------------------------------------------------------------------------
ExternalProject_Add(libcurl
    URL  https://curl.se/download/curl-7.88.1.tar.gz
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DCURL_USE_SCHANNEL=ON
        -DBUILD_CURL_EXE=OFF
        -DBUILD_TESTING=OFF
        -DCMAKE_USE_OPENSSL=OFF
    DEPENDS ${CHAIN}
)
set(CHAIN libcurl)

# ---------------------------------------------------------------------------
# pybind11  (headers + cmake integration)
# ---------------------------------------------------------------------------
ExternalProject_Add(pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11
    GIT_TAG        a2e59f0e7065404b44dfe92a28aca47ba1378dc4 # v2.13.6
    CMAKE_ARGS
        -DCMAKE_INSTALL_PREFIX:PATH=${InstallRoot}
        -DPYBIND11_TEST=NO
    DEPENDS ${CHAIN}
)
set(CHAIN pybind11)

# ---------------------------------------------------------------------------
# CppUnit  (test framework; optional but listed in presets)
# ---------------------------------------------------------------------------
ExternalProject_Add(CppUnit
    URL  http://dev-www.libreoffice.org/src/cppunit-1.15.1.tar.gz
    CMAKE_ARGS
        ${COMMON_CMAKE_ARGS}
        -DCPPUNIT_BUILD_TESTS=OFF
    DEPENDS ${CHAIN}
)
set(CHAIN CppUnit)

# ---------------------------------------------------------------------------
# USD  (OpenUSD v23.08 — skip with -DNO_USD=1)
# ---------------------------------------------------------------------------
if(NOT NO_USD)
    ExternalProject_Add(USD
        GIT_REPOSITORY https://github.com/PixarAnimationStudios/USD
        GIT_TAG        10b62439e9242a55101cf8b200f2c7e02420e1b0 # v23.08
        CMAKE_ARGS
            ${COMMON_CMAKE_ARGS}
            -DPXR_ENABLE_PYTHON_SUPPORT=ON
            -DPXR_USE_PYTHON_3=ON
            -DPYTHON_EXECUTABLE=${PYTHON_EXE}
            -DPYTHON_INCLUDE_DIR=${PYTHON_INCLUDE}
            -DPYTHON_LIBRARY=${PYTHON_LIB}
            -DTBB_ROOT_DIR=${InstallRoot}
            -DTBB_USE_DEBUG_BUILD=OFF
            -DPXR_BUILD_TESTS=OFF
            -DPXR_BUILD_EXAMPLES=OFF
            -DPXR_BUILD_TUTORIALS=OFF
            -DPXR_BUILD_USD_TOOLS=OFF
            -DPXR_ENABLE_PTEX_SUPPORT=OFF
            -DPXR_ENABLE_OPENVDB_SUPPORT=OFF
            -DPXR_BUILD_USDVIEW=OFF
            -DBoost_NO_BOOST_CMAKE=ON
            -DBoost_NO_SYSTEM_PATHS=ON
            -DTBB_SUPPRESS_DEPRECATED_MESSAGES=1
        DEPENDS ${CHAIN}
    )
    set(CHAIN USD)
endif()

# ---------------------------------------------------------------------------
# OptiX headers  (no CUDA binaries, just the headers needed at compile time;
#                 skip with -DNO_CUDA=1)
# ---------------------------------------------------------------------------
if(NOT NO_CUDA)
    ExternalProject_Add(OptiXHeaders
        GIT_REPOSITORY https://github.com/NVIDIA/optix-dev
        GIT_TAG        v7.6.0
        CONFIGURE_COMMAND ""
        BUILD_COMMAND     ""
        INSTALL_COMMAND   ${CMAKE_COMMAND} -E copy_directory
                              <SOURCE_DIR>/include
                              ${InstallRoot}/include
        DEPENDS ${CHAIN}
    )
    set(CHAIN OptiXHeaders)
endif()
