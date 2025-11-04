cmake_minimum_required(VERSION 3.18 FATAL_ERROR)
if(POLICY CMP0177)
  cmake_policy(SET CMP0177 NEW)
endif()

project(SolarAnalysis LANGUAGES CXX CUDA)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set CUDA standard
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

# Enable CUDA separable compilation
set(CMAKE_CUDA_SEPARABLE_COMPILATION ON)

# Find required packages
find_package(CUDAToolkit REQUIRED)

# Set python and pybind paths
set(Python_EXECUTABLE "C:/Users/wTxT/miniconda3/envs/solar/python.exe")
set(Python_FIND_STRATEGY LOCATION)
find_package(Python 3.11.4 EXACT COMPONENTS Interpreter Development REQUIRED)

set(pybind11_DIR "C:/Users/wTxT/miniconda3/envs/solar/Lib/site-packages/pybind11/share/cmake/pybind11")
find_package(pybind11 REQUIRED)

# Find OptiX
set(OptiX_INSTALL_DIR "C:/ProgramData/NVIDIA Corporation/OptiX SDK 9.0.0" CACHE PATH "Path to OptiX installation")
find_path(OptiX_INCLUDE_DIR
    NAMES optix.h
    PATHS ${OptiX_INSTALL_DIR}/include
)

if(NOT OptiX_INCLUDE_DIR)
    message(FATAL_ERROR "OptiX not found. Please set OptiX_INSTALL_DIR to your OptiX installation directory")
endif()

# Set compiler flags
if(MSVC)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /W3")
    set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} -Xcompiler=/W3")
    set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} -diag-suppress=128")
endif()

# CUDA architecture settings
set(CMAKE_CUDA_ARCHITECTURES "75;86;89")

# ===== Python Module =====
pybind11_add_module(solar_engine_optix
    python_bindings.cpp
    optix_solar.cu
    ${HEADER_FILES}
)

target_include_directories(solar_engine_optix PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${OptiX_INCLUDE_DIR}
    ${CUDAToolkit_INCLUDE_DIRS}
)

target_link_libraries(solar_engine_optix PRIVATE
    CUDA::cudart
    CUDA::cuda_driver
)

target_compile_definitions(solar_engine_optix PRIVATE
    $<$<COMPILE_LANGUAGE:CUDA>:EPSILON=1e-6f>
)

set_target_properties(solar_engine_optix PROPERTIES
    CUDA_RESOLVE_DEVICE_SYMBOLS ON
    CUDA_RUNTIME_LIBRARY Shared
)

# ===== PTX Generation =====
# Generate PTX files for OptiX
add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/optix_programs.ptx
    COMMAND ${CMAKE_CUDA_COMPILER} 
        --ptx 
        -arch=sm_75
        -I"${CMAKE_CURRENT_SOURCE_DIR}" 
        -I"${OptiX_INCLUDE_DIR}"
        -I"${CUDAToolkit_INCLUDE_DIRS}"
        -DEPSILON=1e-6f
        --use_fast_math
        --relocatable-device-code=true
        "${CMAKE_CURRENT_SOURCE_DIR}/optix_programs.cu" 
        -o "${CMAKE_CURRENT_BINARY_DIR}/optix_programs.ptx"
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/optix_programs.cu
    COMMENT "Generating PTX files for OptiX"
    VERBATIM
)

# Create target for PTX generation
add_custom_target(generate_ptx ALL
    DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/optix_programs.ptx
)

# Copy PTX file to source directory
add_custom_command(TARGET generate_ptx POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy
        ${CMAKE_CURRENT_BINARY_DIR}/optix_programs.ptx
        ${CMAKE_CURRENT_SOURCE_DIR}/optix_programs.ptx
)

# Copy PTX to Python module output directory
add_custom_command(TARGET solar_engine_optix POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy
        ${CMAKE_CURRENT_BINARY_DIR}/optix_programs.ptx
        $<TARGET_FILE_DIR:solar_engine_optix>/optix_programs.ptx
)

# Make both targets depend on PTX generation
add_dependencies(solar_engine_optix generate_ptx)


# ===== Installation =====
install(TARGETS solar_engine_optix
    LIBRARY DESTINATION ${Python_SITELIB}
)

install(FILES ${CMAKE_CURRENT_BINARY_DIR}/optix_programs.ptx
    DESTINATION ${Python_SITELIB}
)

# ===== Configuration Info =====
message(STATUS "CUDA Toolkit Root: ${CUDAToolkit_ROOT}")
message(STATUS "CUDA Version: ${CUDAToolkit_VERSION}")
message(STATUS "OptiX Include Dir: ${OptiX_INCLUDE_DIR}")
message(STATUS "CUDA Architectures: ${CMAKE_CUDA_ARCHITECTURES}")
message(STATUS "CMAKE_CUDA_COMPILER: ${CMAKE_CUDA_COMPILER}")
message(STATUS "CMAKE_CUDA_HOST_COMPILER: ${CMAKE_CUDA_HOST_COMPILER}")
message(STATUS "pybind11 Found: ${pybind11_FOUND}")
message(STATUS "pybind11 Version: ${pybind11_VERSION}")
message(STATUS "Python Executable: ${Python_EXECUTABLE}")