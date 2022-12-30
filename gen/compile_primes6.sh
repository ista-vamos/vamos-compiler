#!/bin/bash

set -x

CURDIR="$(pwd)"
MONITORSRC="$1"
shift  # consume the first argument in case there are some additional ones
       # for the compilation

GENDIR=$(dirname $0)
SHAMONDIR="$GENDIR/.."

g++ -c $SHAMONDIR/compiler/cfiles/intmap.cpp

CPPFLAGS="-D_POSIX_C_SOURCE=200809L -I${GENDIR} -I$SHAMONDIR\
	   -I$SHAMONDIR/streams -I$SHAMONDIR/core -I$SHAMONDIR/shmbuf"
if grep -q 'CMAKE_BUILD_TYPE.*=Debug' $GENDIR/../CMakeCache.txt; then
	CFLAGS="-g -O0"
else
	CFLAGS="-g3 -O3 -flto  -fno-fat-lto-objects -fPIC -std=c11"
        CPPFLAGS="$CPPFLAGS -DNDEBUG"
fi

LDFLAGS="-lpthread -ldl"
LIBRARIES="$SHAMONDIR/core/libshamon-arbiter.a\
           $SHAMONDIR/core/libshamon-monitor.a\
           $SHAMONDIR/core/libshamon-utils.a\
           $SHAMONDIR/core/libshamon-stream.a\
           $SHAMONDIR/core/libshamon-parallel-queue.a\
           $SHAMONDIR/tessla/bankmon/target/debug/libmonitor.a\
           $SHAMONDIR/core/list.c\
           $SHAMONDIR/core/signatures.c\
           $SHAMONDIR/shmbuf/libshamon-shmbuf.a\
           $SHAMONDIR/streams/libshamon-streams.a\
	   $SHAMONDIR/compiler/cfiles/compiler_utils.c\
	   $SHAMONDIR/compiler/cfiles/intmap.o"

test -z $CC && CC=cc
${CC} $CFLAGS $CPPFLAGS -o $CURDIR/monitor $MONITORSRC -lstdc++ $@ $LIBRARIES $LDFLAGS
