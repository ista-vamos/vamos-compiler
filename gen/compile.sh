#!/bin/bash

set -x

CURDIR="$(pwd)"

set -e
if [ $# -eq 0 ]; then
	echo "Need the source file of the monitor"
	exit 1
fi

GENDIR=$(dirname $0)
SHAMONDIR=$(readlink -f "$GENDIR/..")

CC=clang
CPPFLAGS="-D_POSIX_C_SOURCE=200809L -I${GENDIR} -I$SHAMONDIR\
	   -I$SHAMONDIR/streams -I$SHAMONDIR/core -I$SHAMONDIR/shmbuf"
LTOFLAGS=""
if grep -q 'CMAKE_BUILD_TYPE.*=Debug' $GENDIR/../CMakeCache.txt; then
	CFLAGS="-g -O0"
	# CFLAGS="$CFLAGS -fsanitize=address,undefined"
else
	CFLAGS="-g3 -O3 -fPIC -std=c11"
	if [ -z "$NOLTO" ]; then
		LTOFLAGS="-flto -fno-fat-lto-objects"
	fi
        CPPFLAGS="$CPPFLAGS -DNDEBUG"
fi

LDFLAGS=-lpthread
LIBRARIES="$SHAMONDIR/core/libshamon-arbiter.a\
           $SHAMONDIR/core/libshamon-stream.a\
           $SHAMONDIR/shmbuf/libshamon-shmbuf.a\
           $SHAMONDIR/core/libshamon-parallel-queue.a\
           $SHAMONDIR/core/libshamon-ringbuf.a\
           $SHAMONDIR/core/libshamon-event.a\
           $SHAMONDIR/core/libshamon-source.a\
           $SHAMONDIR/core/libshamon-signature.a\
           $SHAMONDIR/core/libshamon-list.a\
           $SHAMONDIR/core/libshamon-utils.a\
           $SHAMONDIR/core/libshamon-monitor-buffer.a\
           $SHAMONDIR/streams/libshamon-streams.a"

test -z $CC && CC=cc
${CC} $CFLAGS $LTOFLAGS $CPPFLAGS -o $CURDIR/monitor $MONITORSRC $@ $LIBRARIES $LDFLAGS -DSHMBUF_ARBITER_BUFSIZE=$ARBITER_BUFSIZE
