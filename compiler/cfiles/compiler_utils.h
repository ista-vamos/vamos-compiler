#include "vamos-buffers/core/shamon.h"
//#include "gen/mmlib.h"

typedef struct ___vamos_bg_list_node {
    struct ___vamos_bg_list_node *next;
    struct ___vamos_bg_list_node *prev;
    struct ___vamos_bg_list_node *update_next;
    struct ___vamos_bg_list_node *update_prev;
    volatile struct ___vamos_bg_list_node *insert_next;
    shm_stream *stream;
    void *buffer;
    void *args;
    int was_used;
} __vamos_bg_list_node;

typedef struct ___vamos_buffer_group {
    __vamos_bg_list_node *head;
    __vamos_bg_list_node *updated;
    volatile __vamos_bg_list_node *inserted;
    int size;
    int was_used;
} __vamos_buffer_group;

typedef struct ___vamos_streaminfo {
    vms_stream * stream;
    vms_arbiter_buffer * buffer;
    void* aggfields;
    uint64_t lastround;
    int status;
    size_t available;
    void* data1;
    size_t size1;
    void* data2;
    size_t data2;
    uint64_t * limitvar;
    size_t drop_on_match;
} __vamos_streaminfo;

void init_buffer_group(__vamos_buffer_group *bg);

void destroy_buffer_group(__vamos_buffer_group *bg);

void bg_insert(buffer_group *bg, shm_stream *stream, void* buffer, void *args, bool (*order_exp)(void *args1, void *args2));

dll_node *find_stream(buffer_group *bg, shm_stream *stream);

bool bg_remove(buffer_group *bg, shm_stream *stream);

void bg_remove_first_n(buffer_group *bg, int n);

void bg_remove_last_n(buffer_group *bg, int n);

bool bg_get_first_n(buffer_group *bg, int at_least, dll_node ***result);

bool bg_get_last_n(buffer_group *bg, int at_least, dll_node ***result);

void swap_dll_node(dll_node *node1, dll_node *node2);

void bg_update(buffer_group *bg, bool (*order_exp)(void *args1, void *args2)); // checks that order is preserved

// int advance_permutation(int* arr, int permsize, int numoptions);

int __vamos_advance_permutation_forward(dll_node** nodes, int permsize, dll_node* first);
int __vamos_advance_permutation_backward(dll_node** nodes, int permsize, dll_node* last);

size_t __vamos_request_from_buffer(__vamos_streaminfo * stream, size_t count, uint64_t current_round);