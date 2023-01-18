#!/usr/bin/env python3

import sys
import argparse
import os
import shutil
import subprocess
from pathlib import Path

from compiler.parser import parse_program
from compiler.type_checker import TypeChecker
from compiler.cfile_utils import get_c_program
from compiler.utils import *
from compiler.tessla_utils import get_rust_file, get_c_interface, update_toml

from config import (
    vamos_buffers_LIBRARIES_DIRS_core,
    vamos_buffers_LIBRARIES_DIRS_shmbuf,
    vamos_buffers_LIBRARIES_DIRS_streams,
    vamos_buffers_INCLUDE_DIR,
)

parser = argparse.ArgumentParser(prog="vamosc")
parser.add_argument("inputfile", type=str, help="VAMOS program to compile.")
parser.add_argument(
    "-lg",
    "--legacy-mode",
    action="store_true",
    help="Legacy mode: only generate C file with monitor code (plus TeSSLa interface where applicable).",
)
parser.add_argument(
    "-o",
    "--out",
    help="Output file for monitor C code.",
    default="/tmp/vamos_monitor.c",
)
parser.add_argument(
    "-e", "--executable", help="Path of the executable to generate.", default="monitor"
)
parser.add_argument(
    "-l",
    "--link",
    help="Describes list of external libraries that the C compiler should link against",
    nargs="*",
)
parser.add_argument(
    "-ll",
    "--link-lookup",
    help="Lists libraries to be linked against via -l parameters",
    nargs="*",
)
parser.add_argument(
    "-t",
    "--with-tessla",
    help="Tessla specification to be used as the higher-level monitor. Tessla input streams must match events of arbiter's output stream.",
)
parser.add_argument(
    "-d",
    "--dir",
    help="Directory where the library generated by Tessla is (not needed if --with-tessla flag is present).",
    default="vamos_tesslamon",
)
parser.add_argument(
    "-b",
    "--bufsize",
    help="Is the value used to replace @BUFSIZE in VAMOS specification",
)
parser.add_argument(
    "-s",
    "--compilescript",
    help="Path to the compile script that should be generated.",
    default="/tmp/vamos_compile.sh",
)
parser.add_argument("-v", "--verbose", action="store_true")
parser.add_argument("-g", "--debug", action="store_true")
parser.add_argument(
    "--crate-local-vendor",
    help="Path to local copies of Rust dependencies to prevent fetching them from online repositories",
)

args = parser.parse_args()
bufsize = args.bufsize

input_file = Path(args.inputfile).absolute()  # second argument should be input file
parsed_args_file = replace_cmd_args(open(input_file).readlines(), bufsize)
file = " ".join(parsed_args_file)


# Type checker initialization
TypeChecker.clean_checker()
TypeChecker.add_reserved_keywords()

# Parser
ast = parse_program(file)
assert ast[0] == "main_program"
components = dict()
get_components_dict(ast[1], components)

if "stream_type" in components.keys():
    TypeChecker.get_stream_types_data(components["stream_type"])

if "stream_processor" in components.keys():
    TypeChecker.get_stream_processors_data(components["stream_processor"])
for event_source in components["event_source"]:
    TypeChecker.insert_event_source_data(event_source)
TypeChecker.get_stream_events(components["stream_type"])

if "buff_group_def" in components.keys():
    for buff_group in components["buff_group_def"]:
        TypeChecker.add_buffer_group_data(buff_group)

if "match_fun_def" in components.keys():
    for match_fun in components["match_fun_def"]:
        TypeChecker.add_match_fun_data(match_fun)

# TypeChecker.check_arbiter(ast[-2])
# TypeChecker.check_monitor(ast[-1])
#
# Produce C file

#
streams_to_events_map = get_stream_to_events_mapping(
    components["stream_type"], TypeChecker.stream_processors_data
)

stream_types: Dict[str, Tuple[str, str]] = get_stream_types(components["event_source"])
arbiter_event_source = get_arbiter_event_source(ast[2])
existing_buffers = get_existing_buffers(TypeChecker)

TypeChecker.arbiter_output_type = arbiter_event_source

# if args.out is None:
# 	print("provide the path of the file where the C program must be written.")
# 	exit(1)
# else:
output_path = os.path.abspath(args.out)
cscript_path = args.compilescript
executable_path = os.path.abspath(args.executable)
# if

ownpath = str(Path(os.path.abspath(__file__)).absolute().parent.parent)

if args.with_tessla is not None:
    if args.dir is None:
        print("ERROR: Must provide the directory path where Tessla files are located")
        exit(1)
    if os.path.exists(args.dir):
        shutil.rmtree(args.dir)

    if args.legacy_mode is not True:
        subprocess.call(
            [
                "java",
                "-jar",
                f"{ownpath}/compiler/tessla-rust.jar",
                "compile-rust",
                "-p",
                args.dir,
                args.with_tessla,
            ]
        )

    update_toml(args.dir, args.crate_local_vendor)

    # BEGIN writing c-file interface
    c_interface = get_c_interface(
        components,
        ast,
        streams_to_events_map,
        stream_types,
        arbiter_event_source,
        existing_buffers,
    )
    file = open(output_path, "w")
    file.write(c_interface)
    file.close()

    file = open(f"{args.dir}/src/monitor.rs", "r")
    lines = file.readlines()
    file.close()
    # BEGIN writing rust file
    program = get_rust_file(streams_to_events_map, arbiter_event_source, lines)

    file = open(f"{args.dir}/src/monitor.rs", "w")
    extern_keyword_found = False
    is_there_prev_compilation = False
    for line in lines:
        if "#[no_mangle]" in line:
            print("Code from previous compilation found. Removing it...")
            is_there_prev_compilation = True
            break

    for line in lines:
        file.write(line)
        if (not is_there_prev_compilation) and ("extern crate tessla_stdlib;" in line):
            assert not extern_keyword_found
            extern_keyword_found = True
            file.write("use std::os::raw::c_int;\n")
            file.write("use std::os::raw::c_long;\n")
        if "#[no_mangle]" in line:
            break
    file.write(program)
    file.close()
    if args.legacy_mode is True:
        print(
            "DO NOT FORGET to add target/debug/libmonitor.a to the build file of your monitor"
        )
else:

    program = get_c_program(
        components,
        ast,
        streams_to_events_map,
        stream_types,
        arbiter_event_source,
        existing_buffers,
    )
    output_file = open(output_path, "w")
    output_file.write(program)
    output_file.close()

if args.legacy_mode is not True:
    output_file = open(cscript_path, "w")
    output_file.write("#!/usr/bin/env bash\n\n")
    if args.verbose:
        output_file.write("set -x\n\n")
    else:
        output_file.write("set +x\n\n")

    output_file.write(f'SELFDIR="{ownpath}"\n')
    output_file.write(f'SHAMON_INCLUDE_DIR="{vamos_buffers_INCLUDE_DIR}"\n')

    output_file.write("CC=clang\n")
    output_file.write(
        'CPPFLAGS="-D_POSIX_C_SOURCE=200809L -I$SELFDIR -I$SHAMON_INCLUDE_DIR\\\n'
    )
    output_file.write(
        '          -I$SHAMON_INCLUDE_DIR/streams -I$SHAMON_INCLUDE_DIR/core -I$SHAMON_INCLUDE_DIR/shmbuf"\n\n'
    )

    if args.debug:
        output_file.write('LTOFLAGS=""\n')
        output_file.write('CFLAGS="-g -O0"\n\n')
    else:
        output_file.write('CFLAGS="-g3 -O3 -fPIC -std=c11"\n')
        # output_file.write('LTOFLAGS="-fno-lto -fno-fat-lto-objects"\n')
        output_file.write('CPPFLAGS="$CPPFLAGS -DNDEBUG"\n\n')

    linklibraries = [
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-arbiter.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-stream.a",
        f"{vamos_buffers_LIBRARIES_DIRS_shmbuf}/libvamos-buffers-shmbuf.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-parallel-queue.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-ringbuf.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-event.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-source.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-signature.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-list.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-utils.a",
        f"{vamos_buffers_LIBRARIES_DIRS_core}/libvamos-buffers-monitor-buffer.a",
        f"{vamos_buffers_LIBRARIES_DIRS_streams}/libvamos-buffers-streams.a",
        "$SELFDIR/compiler/cfiles/compiler_utils.o",
    ]

    if args.link is not None:
        linklibraries = linklibraries + [os.path.abspath(p) for p in args.link]
    if args.link_lookup is not None:
        linklibraries = linklibraries + [f"-l{p}" for p in args.link_lookup]

    if args.with_tessla:
        linklibraries.append(f"{os.path.abspath(args.dir)}/target/release/libmonitor.a")

    output_file.write(f'LIBRARIES="{linklibraries[0]}')
    for llib in linklibraries[1:]:
        output_file.write(f"\\\n          {llib}")
    output_file.write('"\n\n')

    output_file.write(f'EXECUTABLEPATH="{executable_path}"\n')
    output_file.write(f'CFILEPATH="{output_path}"\n\n')

    if args.with_tessla is not None:
        output_file.write("CURPATH=${pwd}\n")
        output_file.write(f"cd {os.path.abspath(args.dir)}\n")
        output_file.write("cargo build --release\n")
        output_file.write(f"cd $CURPATH\n\n")

    output_file.write("test -z $CC && CC=cc\n")
    output_file.write(
        "${CC} -I$SHAMON_INCLUDE_DIR -c $CFLAGS $SELFDIR/compiler/cfiles/compiler_utils.c -o $SELFDIR/compiler/cfiles/compiler_utils.o\n"
    )
    output_file.write(
        "${CC} $CFLAGS $LTOFLAGS $CPPFLAGS -o $EXECUTABLEPATH $CFILEPATH $@ $LIBRARIES $LDFLAGS\n"
    )

    output_file.close()

    subprocess.call(["bash", cscript_path])
