


#include <threads.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdatomic.h>
#include <assert.h>
#include <limits.h>
#include <immintrin.h> /* _mm_pause */

#include "vamos-buffers/core/arbiter.h"
#include "vamos-buffers/core/monitor.h"
#include "vamos-buffers/core/utils.h"
#include "vamos-buffers/streams/streams.h"

#include "compiler/cfiles/compiler_utils.h"




#define __vamos_min(a, b) ((a < b) ? (a) : (b))
#define __vamos_max(a, b) ((a > b) ? (a) : (b))

#ifdef NDEBUG
#define vamos_check(cond)
#define vamos_assert(cond)
#else
#define vamos_check(cond) do { if (!cond) {fprintf(stderr, "[31m%s:%s:%d: check '" #cond "' failed![0m\n", __FILE__, __func__, __LINE__); print_buffers_state(); } } while(0)
#define vamos_assert(cond) do{ if (!cond) {fprintf(stderr, "[31m%s:%s:%d: assert '" #cond "' failed![0m\n", __FILE__, __func__, __LINE__); print_buffers_state(); __work_done = 1; } } while(0)
#endif

#define vamos_hard_assert(cond) do{ if (!cond) {fprintf(stderr, "[31m%s:%s:%d: assert '" #cond "' failed![0m\n", __FILE__, __func__, __LINE__); print_buffers_state(); __work_done = 1; abort();} } while(0)

struct _EVENT_hole
{
  uint64_t n;
};
typedef struct _EVENT_hole EVENT_hole;

struct _EVENT_hole_wrapper {
    shm_event head;
    union {
        EVENT_hole hole;
    }cases;
};

static void init_hole_hole(shm_event *hev) {
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    h->head.kind = shm_get_hole_kind();
    h->cases.hole.n = 0;
}

static void update_hole_hole(shm_event *hev, shm_event *ev) {
    (void)ev;
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    ++h->cases.hole.n;
}
enum Primes_kinds {
PRIMES_PRIME = 2,
PRIMES_HOLE = 1,
};

// event declarations for stream type Primes
struct _EVENT_Primes_Prime {
	int n;
	int p;

};
typedef struct _EVENT_Primes_Prime EVENT_Primes_Prime;

// input stream for stream type Primes
struct _STREAM_Primes_in {
    shm_event head;
    union {
        EVENT_Primes_Prime Prime;
    }cases;
};
typedef struct _STREAM_Primes_in STREAM_Primes_in;

// output stream for stream processor Primes
struct _STREAM_Primes_out {
    shm_event head;
    union {
        EVENT_hole hole;
        EVENT_Primes_Prime Prime;
    }cases;
};
typedef struct _STREAM_Primes_out STREAM_Primes_out;
        // event declarations for stream type NumberPairs
struct _EVENT_NumberPairs_NumberPair {
	int i;
	int n;
	int m;

};
typedef struct _EVENT_NumberPairs_NumberPair EVENT_NumberPairs_NumberPair;

// input stream for stream type NumberPairs
struct _STREAM_NumberPairs_in {
    shm_event head;
    union {
        EVENT_NumberPairs_NumberPair NumberPair;
    }cases;
};
typedef struct _STREAM_NumberPairs_in STREAM_NumberPairs_in;

// output stream for stream processor NumberPairs
struct _STREAM_NumberPairs_out {
    shm_event head;
    union {
        EVENT_hole hole;
        EVENT_NumberPairs_NumberPair NumberPair;
    }cases;
};
typedef struct _STREAM_NumberPairs_out STREAM_NumberPairs_out;
        





    typedef struct _STREAM_Primes_ARGS {
    	int pos;

    } STREAM_Primes_ARGS;
            


STREAM_Primes_ARGS *stream_args_P_0;
STREAM_Primes_ARGS *stream_args_P_1;

int arbiter_counter;
static bool ARBITER_MATCHED_ = false;
static bool ARBITER_DROPPED_ = false;
static size_t match_and_no_drop_num = 0;

// monitor buffer
shm_monitor_buffer *monitor_buffer;

bool is_selection_successful;
dll_node **chosen_streams; // used in rule set for get_first/last_n
int current_size_chosen_stream = 0;

void update_size_chosen_streams(const int s) {
    if (s > current_size_chosen_stream) {
        free(chosen_streams);
        chosen_streams = (dll_node **) calloc(s, sizeof(dll_node*));
        current_size_chosen_stream = s;
    }
}

// globals code


bool SHOULD_KEEP_forward(shm_stream * s, shm_event * e) {
    return true;
}


atomic_int count_event_streams = 0;

// declare event streams
shm_stream *EV_SOURCE_P_0;
shm_stream *EV_SOURCE_P_1;


// event sources threads
thrd_t THREAD_P_0;
thrd_t THREAD_P_1;


// declare arbiter thread
thrd_t ARBITER_THREAD;
const int SWITCH_TO_RULE_SET_rs = 0;

static size_t RULE_SET_rs_nomatch_cnt = 0;

int current_rule_set = SWITCH_TO_RULE_SET_rs;

// Arbiter buffer for event source P (0)
shm_arbiter_buffer *BUFFER_P0;

// Arbiter buffer for event source P (1)
shm_arbiter_buffer *BUFFER_P1;




// buffer groups

bool Ps_ORDER_EXP (void *args1, void *args2) {
    return ((STREAM_Primes_ARGS *) args1)->pos > ((STREAM_Primes_ARGS *) args2)->pos;
}        


buffer_group BG_Ps;
mtx_t LOCK_Ps;
        


int PERF_LAYER_forward_Primes (shm_arbiter_buffer *buffer) {
    atomic_fetch_add(&count_event_streams, 1); 
    shm_stream *stream = shm_arbiter_buffer_stream(buffer);   
    void *inevent;
    void *outevent;   

    // wait for active buffer
    while ((!shm_arbiter_buffer_active(buffer))){
        sleep_ns(10);
    }
    while(true) {
        inevent = stream_filter_fetch(stream, buffer, &SHOULD_KEEP_forward);

        if (inevent == NULL) {
            // no more events
            break;
        }
        outevent = shm_arbiter_buffer_write_ptr(buffer);

        memcpy(outevent, inevent, sizeof(STREAM_Primes_in));
        shm_arbiter_buffer_write_finish(buffer);
        
        shm_stream_consume(stream, 1);
    }  
    atomic_fetch_add(&count_event_streams, -1);
    return 0;   
}
        
int PERF_LAYER_forward_NumberPairs (shm_arbiter_buffer *buffer) {
    atomic_fetch_add(&count_event_streams, 1); 
    shm_stream *stream = shm_arbiter_buffer_stream(buffer);   
    void *inevent;
    void *outevent;   

    // wait for active buffer
    while ((!shm_arbiter_buffer_active(buffer))){
        sleep_ns(10);
    }
    while(true) {
        inevent = stream_filter_fetch(stream, buffer, &SHOULD_KEEP_forward);

        if (inevent == NULL) {
            // no more events
            break;
        }
        outevent = shm_arbiter_buffer_write_ptr(buffer);

        memcpy(outevent, inevent, sizeof(STREAM_NumberPairs_in));
        shm_arbiter_buffer_write_finish(buffer);
        
        shm_stream_consume(stream, 1);
    }  
    atomic_fetch_add(&count_event_streams, -1);
    return 0;   
}
        

// variables used to debug arbiter
long unsigned no_consecutive_matches_limit = 1UL<<35;
int no_matches_count = 0;

bool are_there_events(shm_arbiter_buffer * b) {
  return shm_arbiter_buffer_is_done(b) > 0;
}


bool are_buffers_done() {
	if (!shm_arbiter_buffer_is_done(BUFFER_P0)) return 0;
	if (!shm_arbiter_buffer_is_done(BUFFER_P1)) return 0;

    mtx_lock(&LOCK_Ps);
    int BG_Ps_size = BG_Ps.size;
    update_size_chosen_streams(BG_Ps_size);
    is_selection_successful = bg_get_first_n(&BG_Ps, 1, &chosen_streams);
    mtx_unlock(&LOCK_Ps);
    for (int i = 0; i < BG_Ps_size; i++) {
        if (!shm_arbiter_buffer_is_done(chosen_streams[i]->buffer)) return 0;
    }

    return 1;
}
    

static int __work_done = 0;
/* TODO: make a keywork from this */
void done() {
    __work_done = 1;
}

static inline bool are_streams_done() {
    assert(count_event_streams >=0);
    return (count_event_streams == 0 && are_buffers_done() && !ARBITER_MATCHED_) || __work_done;
}

static inline bool is_buffer_done(shm_arbiter_buffer *b) {
    return shm_arbiter_buffer_is_done(b);
}


static inline
bool check_at_least_n_events(size_t count, size_t n) {
    // count is the result after calling shm_arbiter_buffer_peek
	return count >= n;
}

static
bool are_events_in_head(char* e1, size_t i1, char* e2, size_t i2, int count, size_t ev_size, int event_kinds[], int n_events) {
    assert(n_events > 0);
	if (count < n_events) {
	    return false;
    }

	int i = 0;
	while (i < i1) {
	    shm_event * ev = (shm_event *) (e1);
	     if (ev->kind != event_kinds[i]) {
	        return false;
	    }
        if (--n_events == 0)
            return true;
	    i+=1;
	    e1 += ev_size;
	}

	i = 0;
	while (i < i2) {
	    shm_event * ev = (shm_event *) e2;
	     if (ev->kind != event_kinds[i1+i]) {
	        return false;
	    }
        if (--n_events == 0)
            return true;
	    i+=1;
	    e2 += ev_size;
	}

	return true;
}

/*
static inline dump_event_data(shm_event *ev, size_t ev_size) {
    unsigned char *data = ev;
    fprintf(stderr, "[");
    for (unsigned i = sizeof(*ev); i < ev_size; ++i) {
        fprintf(stderr, "0x%x ", data[i]);
    }
    fprintf(stderr, "]");
}
*/


const char *get_event_name(int ev_src_index, int event_index) {
    if (event_index == -1) {
        return "<none>";
    }
    
    if (event_index == 1) {
        return "hole";
    }
    
    
    if(ev_src_index == 0) {
        
        if (event_index == 2 ) {
            return "Prime";
        }
            
        if (event_index == 1 ) {
            return "hole";
        }
            
        fprintf(stderr, "No event matched! this should not happen, please report!\n");
        return "";
    }
        
    if(ev_src_index == 1) {
        
        if (event_index == 2 ) {
            return "NumberPair";
        }
            
        if (event_index == 1 ) {
            return "hole";
        }
            
        fprintf(stderr, "No event matched! this should not happen, please report!\n");
        return "";
    }
        
    printf("Invalid event source! this should not happen, please report!\n");
    return 0;
}
    

/* src_idx = -1 if unknown */
static void
print_buffer_prefix(shm_arbiter_buffer *b, int src_idx, size_t n_events, int cnt, char* e1, size_t i1, char* e2, size_t i2) {
    if (cnt == 0) {
        fprintf(stderr, " empty\n");
        return;
    }
    const size_t ev_size = shm_arbiter_buffer_elem_size(b);
    int n = 0;
	int i = 0;
	while (i < i1) {
	    shm_event * ev = (shm_event *) (e1);
        fprintf(stderr, "  %d: {id: %5lu, kind: %3lu", ++n,
                shm_event_id(ev), shm_event_kind(ev));
        if (src_idx != -1)
            fprintf(stderr, " -> %-12s", get_event_name(src_idx, shm_event_kind(ev)));
        /*dump_event_data(ev, ev_size);*/
        fprintf(stderr, "}\n");
        if (--n_events == 0)
            return;
	    i+=1;
	    e1 += ev_size;
	}

	i = 0;
	while (i < i2) {
	    shm_event * ev = (shm_event *) e2;
        fprintf(stderr, "  %d: {id: %5lu, kind: %3lu", ++n,
                shm_event_id(ev), shm_event_kind(ev));
        if (src_idx != -1)
            fprintf(stderr, " -> %-12s", get_event_name(src_idx, shm_event_kind(ev)));
        /*dump_event_data(ev, ev_size);*/
        fprintf(stderr, "}\n");

        if (--n_events == 0)
            return;
	    i+=1;
	    e2 += ev_size;
	}
}



static inline
shm_event * get_event_at_index(char* e1, size_t i1, char* e2, size_t i2, size_t size_event, int element_index) {
	if (element_index < i1) {
		return (shm_event *) (e1 + (element_index*size_event));
	} else {
		element_index -=i1;
		return (shm_event *) (e2 + (element_index*size_event));
	}
}

//arbiter outevent
STREAM_NumberPairs_out *arbiter_outevent;
int RULE_SET_rs();


void print_event_name(int ev_src_index, int event_index) {
    if (event_index == -1) {
        printf("None\n");
        return;
    }

    if (event_index == 1) {
        printf("hole\n");
        return;
    }

    
    if(ev_src_index == 0) {
        
        if (event_index == 2 ) {
            printf("Prime\n");
            return;
        }
            
        if (event_index == 1 ) {
            printf("hole\n");
            return;
        }
            
        printf("No event matched! this should not happen, please report!\n");
        return;
    }
        
    printf("Invalid event source! this should not happen, please report!\n");
}
    

int get_event_at_head(shm_arbiter_buffer *b) {
    void * e1; size_t i1;
    void * e2; size_t i2;

    int count = shm_arbiter_buffer_peek(b, 0, &e1, &i1, &e2, &i2);
    if (count == 0) {
        return -1;
    }
    shm_event * ev = (shm_event *) (e1);
    return ev->kind;
}
    

void print_buffers_state() {
    int event_index;
int count;
void *e1, *e2;
size_t i1, i2;

	fprintf(stderr, "Prefix of 'P0':\n");
	count = shm_arbiter_buffer_peek(BUFFER_P0, 10, &e1, &i1, &e2, &i2);
	print_buffer_prefix(BUFFER_P0, 0, i1 + i2, count, e1, i1, e2, i2);
	fprintf(stderr, "Prefix of 'P1':\n");
	count = shm_arbiter_buffer_peek(BUFFER_P1, 10, &e1, &i1, &e2, &i2);
	print_buffer_prefix(BUFFER_P1, 0, i1 + i2, count, e1, i1, e2, i2);

}

static void print_buffer_state(shm_arbiter_buffer *buffer) {
    int count;
    void *e1, *e2;
    size_t i1, i2;
    count = shm_arbiter_buffer_peek(buffer, 10, (void**)&e1, &i1, (void**)&e2, &i2);
    print_buffer_prefix(buffer, -1, i1 + i2, count, e1, i1, e2, i2);
}


int RULE_SET_rs() {
char* e1_P0; size_t i1_P0; char* e2_P0; size_t i2_P0;
int count_P0 = shm_arbiter_buffer_peek(BUFFER_P0, 1, (void**)&e1_P0, &i1_P0, (void**)&e2_P0, &i2_P0);
char* e1_P1; size_t i1_P1; char* e2_P1; size_t i2_P1;
int count_P1 = shm_arbiter_buffer_peek(BUFFER_P1, 1, (void**)&e1_P1, &i1_P1, (void**)&e2_P1, &i2_P1);

            int TEMPARR0[] = {PRIMES_PRIME};
int TEMPARR1[] = {PRIMES_PRIME};

            
                if (are_events_in_head(e1_P0, i1_P0, e2_P0, i2_P0, 
                count_P0, sizeof(STREAM_Primes_out), TEMPARR0, 1)) {
                    
                if (are_events_in_head(e1_P1, i1_P1, e2_P1, i2_P1, 
                count_P1, sizeof(STREAM_Primes_out), TEMPARR1, 1)) {
                    
            STREAM_Primes_out * event_for_ln = (STREAM_Primes_out *) get_event_at_index(e1_P0, i1_P0, e2_P0, i2_P0, sizeof(STREAM_Primes_out), 0);
int ln = event_for_ln->cases.Prime.n;

STREAM_Primes_out * event_for_lp = (STREAM_Primes_out *) get_event_at_index(e1_P0, i1_P0, e2_P0, i2_P0, sizeof(STREAM_Primes_out), 0);
int lp = event_for_lp->cases.Prime.p;

STREAM_Primes_out * event_for_rn = (STREAM_Primes_out *) get_event_at_index(e1_P1, i1_P1, e2_P1, i2_P1, sizeof(STREAM_Primes_out), 0);
int rn = event_for_rn->cases.Prime.n;

STREAM_Primes_out * event_for_rp = (STREAM_Primes_out *) get_event_at_index(e1_P1, i1_P1, e2_P1, i2_P1, sizeof(STREAM_Primes_out), 0);
int rp = event_for_rp->cases.Prime.p;


           
            if(count < 0 || stream_args_F->pos< stream_args_L->pos) {
                bool local_continue_ = false;
                fdasd 
                

                if (!local_continue_) {
                    return 1;
                }
            }
            

                }

                }
            _Bool ok = 1;
if (count_P0 >= 1) {if (count_P1 >= 1) {	ok = 0;
}}
if (ok == 0) {
	fprintf(stderr, "Prefix of 'P0':\n");
	count_P0 = shm_arbiter_buffer_peek(BUFFER_P0, 5, (void**)&e1_P0, &i1_P0, (void**)&e2_P0, &i2_P0);
	print_buffer_prefix(BUFFER_P0, 0, i1_P0 + i2_P0, count_P0, e1_P0, i1_P0, e2_P0, i2_P0);
	fprintf(stderr, "Prefix of 'P1':\n");
	count_P1 = shm_arbiter_buffer_peek(BUFFER_P1, 5, (void**)&e1_P1, &i1_P1, (void**)&e2_P1, &i2_P1);
	print_buffer_prefix(BUFFER_P1, 0, i1_P1 + i2_P1, count_P1, e1_P1, i1_P1, e2_P1, i2_P1);
fprintf(stderr, "No rule in rule set 'rs' matched even though there was enough events, CYCLING WITH NO PROGRESS (exiting)!\n");__work_done=1; abort();}
if (++RULE_SET_rs_nomatch_cnt >= 500000) {                if (RULE_SET_rs_nomatch_cnt == 500000)                    fprintf(stderr, "Rule set 'rs' cycles long time without progress...\n");                if (RULE_SET_rs_nomatch_cnt % 5000 == 0) _mm_pause();                if (RULE_SET_rs_nomatch_cnt > 650000) _mm_pause();                if (RULE_SET_rs_nomatch_cnt > 700000) _mm_pause();                if (RULE_SET_rs_nomatch_cnt > 750000) _mm_pause();                size_t sleep_time = 2;                if (RULE_SET_rs_nomatch_cnt > 800000) sleep_time += (10);                if (RULE_SET_rs_nomatch_cnt > 900000) sleep_time += (20);                if (RULE_SET_rs_nomatch_cnt > 950000) sleep_time += (40);                sleep_ns(sleep_time);                if (RULE_SET_rs_nomatch_cnt > 1000000) {                    RULE_SET_rs_nomatch_cnt = 0;	fprintf(stderr, "\033[31mRule set 'rs' cycles really long time without progress\033[0m\n");	fprintf(stderr, "Prefix of 'P0':\n");
	count_P0 = shm_arbiter_buffer_peek(BUFFER_P0, 5, (void**)&e1_P0, &i1_P0, (void**)&e2_P0, &i2_P0);
	print_buffer_prefix(BUFFER_P0, 0, i1_P0 + i2_P0, count_P0, e1_P0, i1_P0, e2_P0, i2_P0);
	fprintf(stderr, "Prefix of 'P1':\n");
	count_P1 = shm_arbiter_buffer_peek(BUFFER_P1, 5, (void**)&e1_P1, &i1_P1, (void**)&e2_P1, &i2_P1);
	print_buffer_prefix(BUFFER_P1, 0, i1_P1 + i2_P1, count_P1, e1_P1, i1_P1, e2_P1, i2_P1);
printf("***** BUFFER GROUPS *****\n");
printf("***** Ps *****\n");
dll_node *current = BG_Ps.head;
{int i = 0; 
 while (current){ 
    printf("Ps[%d].ARGS{", i);
	printf("pos = %d\n", ((STREAM_Primes_ARGS *) current->args)->pos);

    printf("}\n");
    char* e1_BG; size_t i1_BG; char* e2_BG; size_t i2_BG;
    int COUNT_BG_TEMP_ = shm_arbiter_buffer_peek(current->buffer, 5, (void**)&e1_BG, &i1_BG, (void**)&e2_BG, &i2_BG);
    printf("Ps[%d].buffer{\n", i);
    print_buffer_prefix(current->buffer, 0, i1_BG + i2_BG, COUNT_BG_TEMP_, e1_BG, i1_BG, e2_BG, i2_BG);
    printf("}\n");
 current = current->next;
 i+=1;
}
}fprintf(stderr, "Seems all rules are waiting for some events that are not coming\n");}}
	return 0;
}
int arbiter() {

        while (!are_streams_done()) {
            ARBITER_MATCHED_ = false;
            ARBITER_DROPPED_ = false;

            		if (!ARBITER_MATCHED_ && current_rule_set == SWITCH_TO_RULE_SET_rs) { 
			if (RULE_SET_rs()) { ARBITER_MATCHED_= true; RULE_SET_rs_nomatch_cnt = 0; }
		}


            if (!ARBITER_DROPPED_ && ARBITER_MATCHED_) {
                if (++match_and_no_drop_num >= 1000000) {
                    if (match_and_no_drop_num == 1000000) {
                        fprintf(stderr, "WARNING: arbiter matched 1000000 times without consuming an event, that might suggest a problem\n");
                    }

                    /* do not burn CPU as we might expect another void iteration */
                    sleep_ns(20);

                    if (++match_and_no_drop_num > 1500000) {
                        fprintf(stderr, "\033[31mWARNING: arbiter matched 1500000 times without consuming an event!\033[0m\n");
                        match_and_no_drop_num = 0;
                        void *e1, *e2;
size_t i1, i2;
int count_;
	fprintf(stderr, "Prefix of 'P0':\n");
	count_ = shm_arbiter_buffer_peek(BUFFER_P0, 5, (void**)&e1, &i1, (void**)&e2, &i2);
	print_buffer_prefix(BUFFER_P0, 0, i1 + i2, count_, e1, i1, e2, i2);
	fprintf(stderr, "Prefix of 'P1':\n");
	count_ = shm_arbiter_buffer_peek(BUFFER_P1, 5, (void**)&e1, &i1, (void**)&e2, &i2);
	print_buffer_prefix(BUFFER_P1, 0, i1 + i2, count_, e1, i1, e2, i2);
printf("***** BUFFER GROUPS *****\n");
printf("***** Ps *****\n");
dll_node *current = BG_Ps.head;
{int i = 0; 
 while (current){ 
    printf("Ps[%d].ARGS{", i);
	printf("pos = %d\n", ((STREAM_Primes_ARGS *) current->args)->pos);

    printf("}\n");
    char* e1_BG; size_t i1_BG; char* e2_BG; size_t i2_BG;
    int COUNT_BG_TEMP_ = shm_arbiter_buffer_peek(current->buffer, 5, (void**)&e1_BG, &i1_BG, (void**)&e2_BG, &i2_BG);
    printf("Ps[%d].buffer{\n", i);
    print_buffer_prefix(current->buffer, 0, i1_BG + i2_BG, COUNT_BG_TEMP_, e1_BG, i1_BG, e2_BG, i2_BG);
    printf("}\n");
 current = current->next;
 i+=1;
}
}
                        
                    }
                }
            }
        }
        shm_monitor_set_finished(monitor_buffer);
        return 0;
    }
        

static void sig_handler(int sig) {
	printf("signal %d caught...", sig);	shm_stream_detach(EV_SOURCE_P_0);
	shm_stream_detach(EV_SOURCE_P_1);
	__work_done = 1;
}

static void setup_signals() {
    if (signal(SIGINT, sig_handler) == SIG_ERR) {
	perror("failed setting SIGINT handler");
    }

    if (signal(SIGABRT, sig_handler) == SIG_ERR) {
	perror("failed setting SIGINT handler");
    }

    if (signal(SIGIOT, sig_handler) == SIG_ERR) {
	perror("failed setting SIGINT handler");
    }

    if (signal(SIGSEGV, sig_handler) == SIG_ERR) {
	perror("failed setting SIGINT handler");
    }
}
    
int main(int argc, char **argv) {
    setup_signals();

    arbiter_counter = 10;
	
    stream_args_P_0 = malloc(sizeof(STREAM_Primes_ARGS));
stream_args_P_1 = malloc(sizeof(STREAM_Primes_ARGS));
	stream_args_P_0->pos = 0;
	stream_args_P_1->pos = 0;


    	// connect to event source P_0

                shm_stream_hole_handling hh_P_0 = {
                  .hole_event_size = sizeof(STREAM_Primes_out),
                  .init = &init_hole_hole,
                  .update = &update_hole_hole
                };

                	EV_SOURCE_P_0 = shm_stream_create_from_argv("P_0", argc, argv, &hh_P_0);
	if (!EV_SOURCE_P_0) {
		fprintf(stderr, "Failed creating stream P_0\n");	abort();}
	BUFFER_P0 = shm_arbiter_buffer_create(EV_SOURCE_P_0,  sizeof(STREAM_Primes_out), 8);

	// register events in P_0
	if (shm_stream_register_event(EV_SOURCE_P_0, "Prime", PRIMES_PRIME) < 0) {
		fprintf(stderr, "Failed registering event Prime for stream P_0 : Primes\n");
		fprintf(stderr, "Available events:\n");
		shm_stream_dump_events(EV_SOURCE_P_0);
		abort();
	}
	// connect to event source P_1

                shm_stream_hole_handling hh_P_1 = {
                  .hole_event_size = sizeof(STREAM_Primes_out),
                  .init = &init_hole_hole,
                  .update = &update_hole_hole
                };

                	EV_SOURCE_P_1 = shm_stream_create_from_argv("P_1", argc, argv, &hh_P_1);
	if (!EV_SOURCE_P_1) {
		fprintf(stderr, "Failed creating stream P_1\n");	abort();}
	BUFFER_P1 = shm_arbiter_buffer_create(EV_SOURCE_P_1,  sizeof(STREAM_Primes_out), 8);

	// register events in P_1
	if (shm_stream_register_event(EV_SOURCE_P_1, "Prime", PRIMES_PRIME) < 0) {
		fprintf(stderr, "Failed registering event Prime for stream P_1 : Primes\n");
		fprintf(stderr, "Available events:\n");
		shm_stream_dump_events(EV_SOURCE_P_1);
		abort();
	}

     // activate buffers
     printf("-- creating buffers\n");
    	shm_arbiter_buffer_set_active(BUFFER_P0, true);
	shm_arbiter_buffer_set_active(BUFFER_P1, true);

 	monitor_buffer = shm_monitor_buffer_create(sizeof(STREAM_NumberPairs_out), 4);

 	 // init buffer groups
     printf("-- initializing buffer groups\n");
     init_buffer_group(&BG_Ps);
        if (mtx_init(&LOCK_Ps, mtx_plain) != 0) {
        printf("mutex init has failed for Ps lock\n");
        return 1;
    }
    	bg_insert(&BG_Ps, EV_SOURCE_P_0, BUFFER_P0,stream_args_P_0,Ps_ORDER_EXP);
	bg_insert(&BG_Ps, EV_SOURCE_P_1, BUFFER_P1,stream_args_P_1,Ps_ORDER_EXP);
        
    

     // create source-events threads
     printf("-- creating performance threads\n");
     	thrd_create(&THREAD_P_0, (void*)PERF_LAYER_forward_Primes,BUFFER_P0);
	thrd_create(&THREAD_P_1, (void*)PERF_LAYER_forward_Primes,BUFFER_P1);


     // create arbiter thread
     printf("-- creating arbiter thread\n");
     thrd_create(&ARBITER_THREAD, arbiter, 0);

     
        // monitor
        printf("-- starting monitor code \n");
        STREAM_NumberPairs_out * received_event;
        while(true) {
            received_event = fetch_arbiter_stream(monitor_buffer);
            if (received_event == NULL) {
                break;
            }

		if (received_event->head.kind == 2) {
			int i = received_event->cases.NumberPair.i;
			int n = received_event->cases.NumberPair.n;
			int m = received_event->cases.NumberPair.m;

		  if (true ) {
		      if(n!=m)
         {
           printf("Error at index %i: %i is not equal to %i\n", i, n, m);
         }
     
		  }
		}
        
        shm_monitor_buffer_consume(monitor_buffer, 1);
    }
    

     printf("-- cleaning up\n");
     	destroy_buffer_group(&BG_Ps);
	mtx_destroy(&LOCK_Ps);
	shm_stream_destroy(EV_SOURCE_P_0);
	shm_stream_destroy(EV_SOURCE_P_1);
	shm_arbiter_buffer_free(BUFFER_P0);
	shm_arbiter_buffer_free(BUFFER_P1);
	free(monitor_buffer);
	free(chosen_streams);
	free(stream_args_P_0);
	free(stream_args_P_1);



}
