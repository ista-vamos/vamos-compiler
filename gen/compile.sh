#!/bin/bash

set -x
set -e

CURDIR="$(pwd)"

if [ $# -eq 0 ]; then
	echo "Need the source file of the monitor"
	exit 1
fi

GENDIR=$(dirname $0)
source $GENDIR/../config.sh

CC=clang
CPPFLAGS="-D_POSIX_C_SOURCE=200809L -I${GENDIR} -I$shamon_INCLUDE_DIR\
	   -I$shamon_INCLUDE_DIR/streams -I$shamon_INCLUDE_DIR/core\
	   -I$shamon_INCLUDE_DIR/shmbuf -I$GENDIR/.."
LTOFLAGS=""
if [ "$shamon_BUILD_TYPE" = "Debug" ]; then
	CFLAGS="-g -O0"
else
	CFLAGS="-g3 -O3 -fPIC -std=c11"
	if [ -z "$NOLTO" ]; then
		LTOFLAGS="-flto -fno-fat-lto-objects"
	fi
        CPPFLAGS="$CPPFLAGS -DNDEBUG"
fi

LDFLAGS=-lpthread
LIBRARIES="$shamon_LIBRARIES_DIRS_core/libshamon-arbiter.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-stream.a\
           $shamon_LIBRARIES_DIRS_shmbuf/libshamon-shmbuf.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-parallel-queue.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-ringbuf.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-event.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-source.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-signature.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-list.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-utils.a\
           $shamon_LIBRARIES_DIRS_core/libshamon-monitor-buffer.a\
           $shamon_LIBRARIES_DIRS_streams/libshamon-streams.a"

test -z $CC && CC=cc
${CC} $CFLAGS $LTOFLAGS $CPPFLAGS -o $CURDIR/monitor $MONITORSRC $@ $LIBRARIES $LDFLAGS -DSHMBUF_ARBITER_BUFSIZE=$ARBITER_BUFSIZE
