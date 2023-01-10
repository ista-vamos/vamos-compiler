cmake_minimum_required(VERSION 3.9)
project(vamos-compiler LANGUAGES C VERSION 0.1)

find_package(shamon REQUIRED)

get_target_property(shamon_shamon-lib shamon-lib LOCATION)
get_target_property(shamon_shamon-ringbuf shamon-ringbuf LOCATION)
get_target_property(shamon_shamon-shmbuf shamon-shmbuf LOCATION)
get_target_property(shamon_shamon-streams shamon-streams LOCATION)
get_filename_component(shamon_LIBRARIES_DIRS_lib ${shamon_shamon-lib} DIRECTORY)
get_filename_component(shamon_LIBRARIES_DIRS_core ${shamon_shamon-ringbuf} DIRECTORY)
get_filename_component(shamon_LIBRARIES_DIRS_shmbuf ${shamon_shamon-shmbuf} DIRECTORY)
get_filename_component(shamon_LIBRARIES_DIRS_streams ${shamon_shamon-streams} DIRECTORY)

set(CMAKE_VERBOSE_MAKEFILE 1)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/config.py.in
	       ${CMAKE_CURRENT_SOURCE_DIR}/config.py)
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/config.sh.in
	       ${CMAKE_CURRENT_SOURCE_DIR}/config.sh)

