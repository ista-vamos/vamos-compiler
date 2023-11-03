#define __mm_consume(B, k) vms_arbiter_buffer_drop((B), (k))
#define __mm_stream_peek(S, k, ptr1, len1, ptr2, len2) \
    vms_arbiter_buffer_peek((S), (k), (ptr1), (ptr2), (len2))
