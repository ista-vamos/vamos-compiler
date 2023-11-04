#include "vamos-buffers/core/arbiter.h"
#include "vamos-buffers/core/monitor.h"
#include <inttypes.h>
#include <stdatomic.h>
#include <threads.h>
//#include "gen/mmlib.h"

typedef struct ___vamos_streaminfo __vamos_streaminfo;
typedef struct ___vamos_bg_list_node __vamos_bg_list_node;
typedef struct ___vamos_buffer_group __vamos_buffer_group;

struct ___vamos_bg_list_node {
    __vamos_bg_list_node *next;
    __vamos_bg_list_node *prev;
    __vamos_bg_list_node *update_next;
    __vamos_bg_list_node *update_prev;
    __vamos_bg_list_node *member_next;
    __vamos_bg_list_node *member_prev;
    __vamos_bg_list_node * volatile insert_next;
    __vamos_buffer_group *group;
    __vamos_streaminfo * stream;
    uint64_t id;
};

struct ___vamos_buffer_group {
    __vamos_bg_list_node *head;
    __vamos_bg_list_node *updated;
    __vamos_bg_list_node * volatile inserted;
    size_t size;
    uint64_t idcounter;
    uint64_t lastfirst;
    mtx_t insert_lock;
    int (*order)(__vamos_buffer_group * bg, __vamos_bg_list_node *stream1, __vamos_bg_list_node *stream2);
} ;

struct ___vamos_streaminfo {
    vms_stream * stream;
    vms_arbiter_buffer * buffer;
    __vamos_bg_list_node * memberships;
    void* aggfields;
    uint64_t lastround;
    int status;
    int needed_aggfields;
    size_t available;
    void* data1;
    size_t size1;
    void* data2;
    size_t size2;
    uint64_t * limitvar;
    size_t drop_on_match;
    thrd_t thread;
};

void __vamos_init_buffer_group(__vamos_buffer_group *bg, int (*order)(__vamos_buffer_group * bg, __vamos_bg_list_node *stream1, __vamos_bg_list_node *stream2));
void __vamos_stream_mark_for_update(__vamos_streaminfo * stream);

void __vamos_bg_insert(__vamos_buffer_group *bg, __vamos_streaminfo *stream);
bool __vamos_bg_add(__vamos_buffer_group *bg, __vamos_streaminfo *stream);
bool __vamos_bg_remove(__vamos_buffer_group *bg, __vamos_streaminfo *stream);
bool __vamos_bg_adjust_pos(__vamos_buffer_group *bg, __vamos_bg_list_node * node);
bool __vamos_bg_insert_node(__vamos_buffer_group *bg, __vamos_bg_list_node * node);

void __vamos_bg_process_inserts(__vamos_buffer_group *bg);
void __vamos_bg_process_updates(__vamos_buffer_group *bg);

int __vamos_advance_permutation_forward(__vamos_bg_list_node** nodes, int permsize, __vamos_bg_list_node* first);
int __vamos_advance_permutation_backward(__vamos_bg_list_node** nodes, int permsize, __vamos_bg_list_node* last);

size_t __vamos_request_from_buffer(__vamos_streaminfo * stream, size_t count, uint64_t current_round);