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
CPPFLAGS="-D_POSIX_C_SOURCE=200809L -I${GENDIR} -I$vamos_buffers_INCLUDE_DIR\
	   -I$vamos_buffers_INCLUDE_DIR/streams -I$vamos_buffers_INCLUDE_DIR/core\
	   -I$vamos_buffers_INCLUDE_DIR/shmbuf -I$GENDIR/.."
LTOFLAGS=""
if [ "$vamos_buffers_BUILD_TYPE" = "Debug" ]; then
	CFLAGS="-g -O0 -std=c11"
else
	CFLAGS="-g3 -O3 -std=c11"
	if [ -z "$NOLTO" ]; then
		LTOFLAGS="-flto -fno-fat-lto-objects"
	fi
        CPPFLAGS="$CPPFLAGS -DNDEBUG"
fi

LDFLAGS=-lpthread
LIBRARIES="$vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-arbiter.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-stream.a\
           $vamos_buffers_LIBRARIES_DIRS_shmbuf/libvamos-buffers-shmbuf.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-parallel-queue.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-ringbuf.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-event.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-source.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-signature.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-list.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-utils.a\
           $vamos_buffers_LIBRARIES_DIRS_core/libvamos-buffers-monitor-buffer.a\
           $vamos_buffers_LIBRARIES_DIRS_streams/libvamos-buffers-streams.a"

test -z $CC && CC=cc
${CC} $CFLAGS $LTOFLAGS $CPPFLAGS -o $CURDIR/monitor $MONITORSRC $@ $LIBRARIES $LDFLAGS #-DSHMBUF_ARBITER_BUFSIZE=$ARBITER_BUFSIZE
