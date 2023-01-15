cmake_minimum_required(VERSION 3.9)
project(vamos-compiler LANGUAGES C VERSION 0.1)

find_package(vamos-buffers REQUIRED)

if(NOT CMAKE_BUILD_TYPE)
	message(STATUS "Build type not set. Setting buffer's build type.")
	set(CMAKE_BUILD_TYPE ${vamos-buffers_BUILD_TYPE} CACHE STRING "" FORCE)
endif()

if (vamos-buffers_OPTION_ENABLE_IPO)
        set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

get_target_property(vamos-buffers_vamos-buffers-lib vamos-buffers-lib LOCATION)
get_target_property(vamos-buffers_vamos-buffers-ringbuf vamos-buffers-ringbuf LOCATION)
get_target_property(vamos-buffers_vamos-buffers-shmbuf vamos-buffers-shmbuf LOCATION)
get_target_property(vamos-buffers_vamos-buffers-streams vamos-buffers-streams LOCATION)
get_filename_component(vamos-buffers_LIBRARIES_DIRS_lib ${vamos-buffers_vamos-buffers-lib} DIRECTORY)
get_filename_component(vamos-buffers_LIBRARIES_DIRS_core ${vamos-buffers_vamos-buffers-ringbuf} DIRECTORY)
get_filename_component(vamos-buffers_LIBRARIES_DIRS_shmbuf ${vamos-buffers_vamos-buffers-shmbuf} DIRECTORY)
get_filename_component(vamos-buffers_LIBRARIES_DIRS_streams ${vamos-buffers_vamos-buffers-streams} DIRECTORY)

set(CMAKE_VERBOSE_MAKEFILE 1)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

get_filename_component(vamos-buffers_DIR ${vamos-buffers_DIR} ABSOLUTE)
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/config.py.in
	       ${CMAKE_CURRENT_SOURCE_DIR}/config.py)
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/config.sh.in
	       ${CMAKE_CURRENT_SOURCE_DIR}/config.sh)

if (NOT EXISTS compiler/tessla-rust.jar)
	message(STATUS "Downloading TeSSLa jar")
	file(DOWNLOAD "https://git.tessla.io/tessla/tessla/builds/artifacts/rust-compiler/raw/target/scala-2.13/tessla-assembly-1.2.3.jar?job=deploy" compiler/tessla-rust.jar
	SHOW_PROGRESS)
endif()
