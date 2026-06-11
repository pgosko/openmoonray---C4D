# Copyright 2024-2026 - Apache License 2.0
# MoonRay Cinema 4D Plugin - C++ Build Configuration
#
# Prerequisites:
#   - Cinema 4D C++ SDK (download from developers.maxon.net)
#   - MoonRay scene_rdl2 library (built from openmoonray)
#   - CMake 3.20+

cmake_minimum_required(VERSION 3.20)
project(MoonRayC4D VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# Configuration
# ============================================================

# Path to Cinema 4D SDK
set(C4D_SDK_PATH "" CACHE PATH "Path to Cinema 4D C++ SDK")

# Path to MoonRay installation
set(MOONRAY_ROOT "" CACHE PATH "Path to MoonRay installation (contains lib/ and include/)")

if(NOT C4D_SDK_PATH)
    message(FATAL_ERROR
        "C4D_SDK_PATH not set. Please specify the path to the Cinema 4D C++ SDK.\n"
        "Download from: https://developers.maxon.net/\n"
        "Usage: cmake -DC4D_SDK_PATH=/path/to/c4d_sdk ..")
endif()

if(NOT MOONRAY_ROOT)
    message(WARNING
        "MOONRAY_ROOT not set. The plugin will compile but will not link "
        "against MoonRay libraries. Set this to enable direct scene_rdl2 "
        "integration.")
endif()

# ============================================================
# Cinema 4D SDK
# ============================================================

# Include the C4D SDK project configuration
if(EXISTS "${C4D_SDK_PATH}/plugins/project/projectdefinition.txt")
    # Modern C4D SDK structure
    include_directories(
        "${C4D_SDK_PATH}/frameworks/cinema.framework/source"
        "${C4D_SDK_PATH}/frameworks/core.framework/source"
        "${C4D_SDK_PATH}/frameworks/maxon.framework/source"
    )
else()
    # Legacy SDK structure
    include_directories(
        "${C4D_SDK_PATH}/resource/_api"
        "${C4D_SDK_PATH}/resource/_api_lib"
    )
endif()

# ============================================================
# MoonRay Libraries
# ============================================================

if(MOONRAY_ROOT)
    include_directories("${MOONRAY_ROOT}/include")
    link_directories("${MOONRAY_ROOT}/lib")

    set(MOONRAY_LIBRARIES
        scene_rdl2
        rendering_rndr
        common_math
        common_platform
    )
endif()

# ============================================================
# Plugin Target
# ============================================================

set(PLUGIN_SOURCES
    source/main.cpp
    source/moonray_videopost.cpp
)

add_library(moonray_c4d SHARED ${PLUGIN_SOURCES})

target_include_directories(moonray_c4d PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/source"
    "${CMAKE_CURRENT_SOURCE_DIR}/res"
)

if(MOONRAY_ROOT)
    target_link_libraries(moonray_c4d PRIVATE ${MOONRAY_LIBRARIES})
    target_compile_definitions(moonray_c4d PRIVATE MOONRAY_AVAILABLE=1)
endif()

# Platform-specific settings
if(WIN32)
    set_target_properties(moonray_c4d PROPERTIES
        SUFFIX ".cdl64"
        PREFIX ""
    )
elseif(APPLE)
    set_target_properties(moonray_c4d PROPERTIES
        SUFFIX ".dylib"
        PREFIX ""
    )
else()
    set_target_properties(moonray_c4d PROPERTIES
        SUFFIX ".so"
        PREFIX ""
    )
endif()

# ============================================================
# Installation
# ============================================================

# Install to Cinema 4D plugins directory
set(C4D_PLUGINS_DIR "" CACHE PATH "Cinema 4D plugins installation directory")

if(C4D_PLUGINS_DIR)
    install(TARGETS moonray_c4d
        DESTINATION "${C4D_PLUGINS_DIR}/moonray_renderer"
    )
    install(DIRECTORY res/
        DESTINATION "${C4D_PLUGINS_DIR}/moonray_renderer/res"
    )
endif()
