cmake_minimum_required(VERSION 3.9)
project(vamos-compiler LANGUAGES C VERSION 0.1)

find_package(shamon)

SET (CMAKE_VERBOSE_MAKEFILE 1)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/paths.py.in
	       ${CMAKE_CURRENT_SOURCE_DIR}/paths.py)

