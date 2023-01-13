#include "vamos-buffers/core/shamon.h"
//#include "gen/mmlib.h"

typedef struct _dll_node {
    struct _dll_node *next;
    struct _dll_node *prev;
    shm_stream *stream;
    void *buffer;
    void *args;
} dll_node;

typedef struct _buffer_group {
    dll_node *head; 
    dll_node *tail;
    int size;
} buffer_group;

void init_buffer_group(buffer_group *bg);

void destroy_buffer_group(buffer_group *bg);

void bg_insert(buffer_group *bg, shm_stream *stream, void* buffer, void *args, bool (*order_exp)(void *args1, void *args2));

dll_node *find_stream(buffer_group *bg, shm_stream *stream);

bool bg_remove(buffer_group *bg, shm_stream *stream);

void bg_remove_first_n(buffer_group *bg, int n);

void bg_remove_last_n(buffer_group *bg, int n);

bool bg_get_first_n(buffer_group *bg, int at_least, dll_node ***result);

bool bg_get_last_n(buffer_group *bg, int at_least, dll_node ***result);

void swap_dll_node(dll_node *node1, dll_node *node2);

void bg_update(buffer_group *bg, bool (*order_exp)(void *args1, void *args2)); // checks that order is preserved


