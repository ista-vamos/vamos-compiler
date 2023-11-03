#ifndef VAMOS_GEN_H_
#define VAMOS_GEN_H_

#include <stdbool.h>
#include <unistd.h>

#include "vamos-buffers/core/event.h"
#include "vamos-buffers/core/arbiter.h"
#include "vamos-buffers/core/monitor.h"
#include "vamos-buffers/core/source.h"
#include "vamos-buffers/core/stream.h"
#include "vamos-buffers/core/utils.h" /* sleeping */

#include "vamos-buffers/streams/streams.h"

/*
 * The high-level workflow is as follows:
 *
 *  // create a stream -- stream specific
 *  vms_stream *stream = vms_stream_XXX_create(...);
 *
 *  // create the arbiter's buffer
 *  vms_arbiter_buffer buffer.
 *  vms_arbiter_buffer_init(&buffer, stream,
 *                          ... output event size...,
 *                          ... buffer's capacity...);
 *
 *  // create thread that buffers events (code for it is below)
 *  thrd_t thread_id;
 *  thrd_create(&thread_id, buffer_manager_thrd, &buffer);
 *
 *  // let the thread know that the buffer is ready (optional,
 *  // depends on the thread's code)
 *  vms_arbiter_buffer_set_active(buffer, true);
 *
 *  // the main loop
 *  while (true) {
 *    avail_events_num = vms_arbiter_buffer_size(buffer);
 *    if (avail_events_num > 0) {
 *        if (avail_events_num > ... some threshold ...) {
 *            // summarize half of the buffer
 *            vms_eventid id = vms_event_id(vms_arbiter_buffer_top(buffer));
 *            void *data1, *data2;
 *            size_t size1, size2, n;
 *            n = vms_arbiter_buffer_peek(&buffer, c/2,
 *                                        &data1, &size1,
 *                                        &data2, &size2);
 *            summary_event_type summary;
 *            size_t element_size = vms_arbiter_buffer_elem_size(buffer);
 *            for (size_t i = 0; i < size1; ++i) {
 *               if (vms_event_is_hole((vms_event*)data1) {
 *                   ... update summary ...
 *               } else {
 *                   right_event_type *ev = (right_event_type*)data1;
 *                   ... update summary ...
 *               }
 *               data1 += element_size;
 *            }
 *            if (n > size1) {
 *                ... process data2 too ...
 *            }
 *
 *            vms_arbiter_buffer_drop(buffer, n);
 *            __monitor_send(&summary, ...);
 *        }
 *
 *        __monitor_send(vms_arbiter_buffer_top(buffer), ...);
 *        vms_arbiter_buffer_drop(buffer, 1);
 *    } else {
 *      ... sleep for a while? ...
 *  }
 *
 *
 * ///////////////////////////////////////////////////////////////////
 * // The code for the thread that buffers events can look like this:
 *
 * int buffer_manager_thrd(void *data) {
 *  vms_arbiter_buffer *buffer = (vms_arbiter_buffer*) data;
 *  vms_stream *stream = vms_arbiter_buffer_stream(buffer);
 *
 *  // wait until the buffer is active
 *  while (!vms_arbiter_buffer_active(buffer))
 *      _mm_pause();
 *
 *  void *ev, *out;
 *  while (true) {
 *      ev = stream_fetch(stream, buffer);
 *      if (!ev) {
 *          break;  // stream ended
 *      }
 *      if (filter && !filter(stream, ev)) {
 *          vms_stream_consume(stream, 1);
 *          continue;
 *      }
 *
 *      out = vms_arbiter_buffer_write_ptr(buffer);
 *      copy_and_maybe_alter(stream, ev, out);
 *      vms_arbiter_buffer_write_finish(buffer);
 *      vms_stream_consume(stream, 1);
 *  }
 *
 *  thrd_exit(EXIT_SUCCESS);
 * }
 */


#endif  // VAMOS_GEN_H_
