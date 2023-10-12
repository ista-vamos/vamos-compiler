#ifndef SHAMON_SINGLE_H_
#define SHAMON_SINGLE_H_

#include <stdbool.h>
#include <unistd.h>

#include "vamos-buffers/core/arbiter.h"
#include "vamos-buffers/core/monitor.h"
#include "vamos-buffers/core/source.h"
#include "vamos-buffers/core/stream.h"
#include "vamos-buffers/core/utils.h" /* sleeping */

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

typedef uint64_t vms_kind;
typedef uint64_t vms_eventid;
typedef struct _vms_event vms_event;
typedef struct _vms_stream vms_stream;
typedef struct _vms_arbiter_buffer vms_arbiter_buffer;

/************************************************************************
 * EVENTS
 ************************************************************************/

/* Must be called before using event API.
 * It is called from shamon_create */
void initialize_events(void);
/* called from shamon_destroy */
void deinitialize_events(void);

vms_kind vms_mk_event_kind(const char *name, size_t event_size,
                           const char *signature);
const char *vms_event_kind_name(vms_kind kind);

vms_eventid vms_event_id(vms_event *event);
size_t vms_event_size(vms_event *event);
vms_kind vms_event_kind(vms_event *event);
size_t vms_event_size_for_kind(vms_kind kind);

bool vms_event_is_hole(const vms_event *);
vms_kind vms_event_get_hole_kind(void);

/************************************************************************
 * STREAMS
 ************************************************************************/

typedef bool (*vms_stream_filter_fn)(vms_stream *, vms_event *);
typedef void (*vms_stream_alter_fn)(vms_stream *, vms_event *, vms_event *);

const char *vms_stream_get_name(vms_stream *);
bool vms_stream_consume(vms_stream *stream, size_t num);
const char *vms_stream_get_str(vms_stream *stream, uint64_t elem);

vms_stream *vms_stream_create_from_argv(
    const char *name, int argc, char *argv[],
    vms_stream_hole_handling *hole_handling);

vms_stream *vms_stream_create(const char *name, const char *spec);

int vms_stream_register_event(vms_stream *, const char *name, vms_kind);

/************************************************************************
 * ARBITER BUFFER
 ************************************************************************/

/* the important function -- get the pointer to the next event in the stream
 * (or NULL if the event was dropped or there is none). \param buffer
 * is taken only to handle dropping events, the next event on the stream
 * is not queued there by this function */
void *stream_fetch(vms_stream *stream, vms_arbiter_buffer *buffer);

void vms_arbiter_buffer_init(vms_arbiter_buffer *buffer, vms_stream *stream,
                             size_t out_event_size, size_t capacity);
vms_arbiter_buffer *vms_arbiter_buffer_create(vms_stream *stream,
                                              size_t out_event_size,
                                              size_t capacity);
void vms_arbiter_buffer_free(vms_arbiter_buffer *buffer);
void vms_arbiter_buffer_destroy(vms_arbiter_buffer *buffer);
void vms_arbiter_buffer_set_active(vms_arbiter_buffer *buffer, bool val);
size_t vms_arbiter_buffer_elem_size(vms_arbiter_buffer *q);
vms_stream *vms_arbiter_buffer_stream(vms_arbiter_buffer *buffer);
bool vms_arbiter_buffer_active(vms_arbiter_buffer *buffer);
size_t vms_arbiter_buffer_size(vms_arbiter_buffer *buffer);
size_t vms_arbiter_buffer_capacity(vms_arbiter_buffer *buffer);
size_t vms_arbiter_buffer_free_space(vms_arbiter_buffer *buffer);

/* writer's API */
void vms_arbiter_buffer_push(vms_arbiter_buffer *q, const void *elem,
                             size_t size);

void *vms_arbiter_buffer_write_ptr(vms_arbiter_buffer *q);
void vms_arbiter_buffer_write_finish(vms_arbiter_buffer *q);
void vms_arbiter_buffer_get_str(vms_arbiter_buffer *q, size_t elem);

/* reader's API */
/* multiple threads can use top and peek if none of them uses drop/pop
 * at possibly the same time */
vms_event *vms_arbiter_buffer_top(vms_arbiter_buffer *buffer);
size_t vms_arbiter_buffer_peek(vms_arbiter_buffer *buffer, size_t n,
                               void **data1, size_t *size1, void **data2,
                               size_t *size2);
size_t vms_arbiter_buffer_drop(vms_arbiter_buffer *buffer, size_t n);
bool vms_arbiter_buffer_pop(vms_arbiter_buffer *q, void *buff);

#endif  // SHAMON_H_
