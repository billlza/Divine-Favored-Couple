cmake_minimum_required(VERSION 3.20)
project(DivineFavoredCouple VERSION 1.0.0 LANGUAGES CXX)

# Platform requirements
set(CMAKE_OSX_ARCHITECTURES "arm64" CACHE STRING "Build for Apple Silicon only")
set(CMAKE_OSX_DEPLOYMENT_TARGET "15.0" CACHE STRING "Minimum macOS version")

# C++ settings
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Note: Swift code is built via Swift Package Manager (swift build)
# CMake is used for C++ engine library only

# Output directories
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# Options
option(BUILD_SHARED_LIBS "Build shared libraries" OFF)
option(ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)

# Sanitizers
if(ENABLE_ASAN)
    add_compile_options(-fsanitize=address -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address)
endif()

if(ENABLE_UBSAN)
    add_compile_options(-fsanitize=undefined)
    add_link_options(-fsanitize=undefined)
endif()

# Engine library (C++ placeholder for future Metal/ECS integration)
add_library(GameEngine STATIC
    Engine/src/placeholder.cpp
)

target_include_directories(GameEngine PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/Engine/include
)

target_compile_options(GameEngine PRIVATE
    -Wall -Wextra -Wpedantic
    $<$<CONFIG:Release>:-O3>
    $<$<CONFIG:Debug>:-O0 -g>
)

# Install rules
install(TARGETS GameEngine
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

install(DIRECTORY Engine/include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
)

# Testing
enable_testing()

add_test(NAME SwiftTests
    COMMAND swift test --package-path ${CMAKE_SOURCE_DIR}
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)

# Custom targets
add_custom_target(format
    COMMAND clang-format -i Engine/src/*.cpp Engine/include/*.h Engine/include/*.hpp 2>/dev/null || true
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Formatting C++ code"
)

add_custom_target(lint
    COMMAND clang-tidy Engine/src/*.cpp -- -I${CMAKE_SOURCE_DIR}/Engine/include 2>/dev/null || true
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Linting C++ code"
)

message(STATUS "DivineFavoredCouple CMake Configuration:")
message(STATUS "  Architecture: ${CMAKE_OSX_ARCHITECTURES}")
message(STATUS "  Deployment Target: ${CMAKE_OSX_DEPLOYMENT_TARGET}")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  ASan: ${ENABLE_ASAN}")
message(STATUS "  UBSan: ${ENABLE_UBSAN}")
