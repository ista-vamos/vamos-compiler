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
	CC=clang
	CFLAGS="-g3 -O3 -flto  -fno-fat-lto-objects -fPIC -std=c11"
        CPPFLAGS="$CPPFLAGS -DNDEBUG"
fi

LDFLAGS="-lpthread -ldl"
LIBRARIES="$SHAMONDIR/core/libshamon-arbiter.a\
           $SHAMONDIR/core/libshamon-monitor-buffer.a\
           $SHAMONDIR/core/libshamon-stream.a\
           $SHAMONDIR/shmbuf/libshamon-shmbuf.a\
           $SHAMONDIR/core/libshamon-parallel-queue.a\
           $SHAMONDIR/core/libshamon-ringbuf.a\
           $SHAMONDIR/core/libshamon-event.a\
           $SHAMONDIR/core/libshamon-source.a\
           $SHAMONDIR/core/libshamon-signature.a\
           $SHAMONDIR/core/libshamon-list.a\
           $SHAMONDIR/streams/libshamon-streams.a\
           $SHAMONDIR/core/libshamon-utils.a\
	   $SHAMONDIR/compiler/cfiles/compiler_utils.o\
	   $SHAMONDIR/compiler/cfiles/intmap.o"

test -z $CC && CC=cc
$CC $CFLAGS $CPPFLAGS -o $CURDIR/monitor $MONITORSRC $@ $LIBRARIES -lstdc++ $LDFLAGS
