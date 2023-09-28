#pragma once
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define _MM_EVACCESS(n, ilen, istrt, bstrt) \
    (ilen > n ? istrt + n : bstrt + (n - ilen))
#define __MM_BUFDROP(buf, n, tlen, flen, ilen, istrt, blen, bstrt) \
    do {                                                           \
        vms_arbiter_buffer_drop(buf, n);                           \
        tlen -= n;                                                 \
        flen -= n;                                                 \
        if (ilen >= n) {                                           \
            ilen -= n;                                             \
            istrt += n;                                            \
        } else {                                                   \
            ilen = blen - (n - ilen);                              \
            istrt = bstrt + (n - ilen);                            \
        }                                                          \
    } while (0)

typedef int _mm_type_int;
typedef struct __mm_gco {
    size_t refcount;
    char data[];
} * _mm_gco;

static inline _mm_gco _mm_decref(_mm_gco o) {
    o->refcount -= 1;
    if (o->refcount == 0) {
        free(o);
        return NULL;
    }
    return o;
}
static inline _mm_gco _mm_incref(_mm_gco o) {
    o->refcount += 1;
    return o;
}
static inline _mm_gco _mm_alloc(size_t size) {
    _mm_gco ret = (_mm_gco)malloc(size + sizeof(struct __mm_gco));
    assert(ret && "Could not allocate new object!");
    ret->refcount = 1;
    return ret;
}

#define _MM_NUMBUFSIZE 128

static char _MM_NUMBUF[_MM_NUMBUFSIZE];
static inline _mm_gco _mm_lib_int_to_string(_mm_type_int n) {
    int len = snprintf(_MM_NUMBUF, _MM_NUMBUFSIZE, "%i", n);
    _mm_gco ret = _mm_alloc(len + 1);
    if (len >= _MM_NUMBUFSIZE) {
        snprintf(ret->data, len + 1, "%i", n);
    } else {
        memcpy(ret->data, _MM_NUMBUF, len + 1);
    }
    return ret;
}

static inline _mm_gco _mm_lib_string_concat(_mm_gco left, _mm_gco right) {
    size_t leftlen = strlen(left->data);
    size_t rightlen = strlen(right->data);
    size_t newlen = leftlen + rightlen + 1;
    assert(((newlen > leftlen) && (newlen > rightlen)) &&
           "Not enough space for new strings!");
    _mm_gco ret = _mm_alloc(newlen);
    memcpy(ret->data, left->data, leftlen);
    memcpy(ret->data + leftlen, right->data, rightlen);
    ret->data[newlen - 1] = 0;
    _mm_decref(left);
    _mm_decref(right);
    return ret;
}

static inline _mm_type_int _mm_lib_string_length(_mm_gco str) {
    _mm_type_int len = (_mm_type_int)strlen(str->data);
    _mm_decref(str);
    return len;
}

static inline _mm_type_int _mm_lib_string_to_int(_mm_gco str) {
    _mm_type_int ret = atoi(str->data);
    _mm_decref(str);
    return ret;
}

static inline int _mm_lib_string_equals(_mm_gco left, _mm_gco right) {
    int ret = strcmp(left->data, right->data) == 0;
    _mm_decref(left);
    _mm_decref(right);
    return ret;
}
static inline _mm_type_int _mm_lib_string_compare(_mm_gco left, _mm_gco right) {
    _mm_type_int ret = (_mm_type_int)strcmp(left->data, right->data);
    _mm_decref(left);
    _mm_decref(right);
    return ret;
}

static inline _mm_gco _mm_lib_substring(_mm_gco str, _mm_type_int start,
                                        _mm_type_int len) {
    size_t slen = strlen(str->data);
    size_t newlen = (size_t)len;

    if (start < 0) {
        start = slen - start;
        if (start < 0) {
            start = 0;
        }
    }
    if (start > slen) {
        start = slen;
    }
    if (newlen < 0) {
        newlen = slen - newlen;
        if (len < 0) {
            newlen = slen - start;
        }
    } else if (newlen + start > slen) {
        newlen = slen - start;
    }
    _mm_gco ret = _mm_alloc(newlen + 1);
    memcpy(ret->data, str->data + start, newlen);
    ret->data[newlen] = 0;
    _mm_decref(str);
    return ret;
}

static inline _mm_gco _mm_lib_make_string(const char *str) {
    size_t len = strlen(str) + 1;
    _mm_gco ret = _mm_alloc(len);
    memcpy(ret->data, str, len);
    return ret;
}