


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
    vms_event head;
    union {
        EVENT_hole hole;
    }cases;
};

static void init_hole_hole(vms_event *hev) {
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    h->head.kind = vms_event_get_hole_kind();
    h->cases.hole.n = 0;
}

static void update_hole_hole(vms_event *hev, vms_event *ev) {
    (void)ev;
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    ++h->cases.hole.n;
}

// declares the structs of stream types needed for event sources
enum Events_kinds {
EVENTS_E = 2,
EVENTS_HOLE = 1,
};

// declare hole structs


// declare stream types structs
// event declarations for stream type Events
struct _EVENT_Events_E {
	long n;

};
typedef struct _EVENT_Events_E EVENT_Events_E;

// input stream for stream type Events
struct _STREAM_Events_in {
    vms_event head;
    union {
        EVENT_Events_E E;
    }cases;
};
typedef struct _STREAM_Events_in STREAM_Events_in;

// output stream for stream processor Events
struct _STREAM_Events_out {
    vms_event head;
    union {
        EVENT_hole hole;
        EVENT_Events_E E;
    }cases;
};
typedef struct _STREAM_Events_out STREAM_Events_out;
        

// functions that create a hole and update holes




// Declare structs that store the data of streams shared among events in the struct


// instantiate the structs that store the variables shared among events in the same struct


int arbiter_counter; // int used as id for the events that the arbiter generates, it increases for every event it generates

static bool ARBITER_MATCHED_ = false; // in each iteration we set this to true if it mathces
static bool ARBITER_DROPPED_ = false; // in each iteration we set this to true if it drops the event
static size_t match_and_no_drop_num = 0; // count of consecutive matches without dropping the event (we raise a warning when we reach a certain number of this)

// monitor buffer
vms_monitor_buffer *monitor_buffer; // where we store the events that the monitor needs to process

bool is_selection_successful;
dll_node **chosen_streams; // used in rule set for get_first/last_n
int current_size_chosen_stream = 0; // current number of elements in  chosen_streams

void update_size_chosen_streams(const int s) {
    if (s > current_size_chosen_stream) {
        // if s is greater then we need to increase the size of chosen_streams
        free(chosen_streams);
        chosen_streams = (dll_node **) calloc(s, sizeof(dll_node*)); // allocate more space
        current_size_chosen_stream = s; // set the new number of elements in chosen_streams
    }
}

// globals code
STREAM_Events_out *arbiter_outevent;

size_t processed = 0;
 size_t dropped = 0;
 size_t holes_num = 0;
 

// functions for streams that determine if an event should be forwarded to the monitor

bool SHOULD_KEEP_forward(vms_stream * s, vms_event * e) {
    return true;
}


atomic_int count_event_streams = 0; // number of active event sources

// declare event streams
vms_stream *EV_SOURCE_Src;


// event sources threads
thrd_t THREAD_Src;


// declare arbiter thread
thrd_t ARBITER_THREAD;

// we index rule sets
const int SWITCH_TO_RULE_SET_rules = 0;



static size_t RULE_SET_rules_nomatch_cnt = 0;
 // MAREK knows


int current_rule_set = SWITCH_TO_RULE_SET_rules; // initial arbiter rule set

// Arbiter buffer for event source Src
vms_arbiter_buffer *BUFFER_Src;




// buffer groups
// sorting streams functions




int PERF_LAYER_forward_Events (vms_arbiter_buffer *buffer) {
    // this function forwards everything
    atomic_fetch_add(&count_event_streams, 1); 
    vms_stream *stream = vms_arbiter_buffer_stream(buffer);   
    void *inevent;
    void *outevent;   

    // wait for active buffer
    while ((!vms_arbiter_buffer_active(buffer))){
        sleep_ns(10);
    }
    while(true) {
        inevent = stream_filter_fetch(stream, buffer, &SHOULD_KEEP_forward);

        if (inevent == NULL) {
            // no more events
            break;
        }
        outevent = vms_arbiter_buffer_write_ptr(buffer);

        memcpy(outevent, inevent, sizeof(STREAM_Events_in));
        vms_arbiter_buffer_write_finish(buffer);
        
        vms_stream_consume(stream, 1);
    }  
    atomic_fetch_add(&count_event_streams, -1);
    return 0;   
}
        

// variables used to debug arbiter
long unsigned no_consecutive_matches_limit = 1UL<<35;
int no_matches_count = 0;

bool are_there_events(vms_arbiter_buffer * b) {
  return vms_arbiter_buffer_is_done(b) > 0;
}


bool are_buffers_done() {
	if (!vms_arbiter_buffer_is_done(BUFFER_Src)) return 0;

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

static inline bool is_buffer_done(vms_arbiter_buffer *b) {
    return vms_arbiter_buffer_is_done(b);
}


static inline
bool check_at_least_n_events(size_t count, size_t n) {
    // count is the result after calling vms_arbiter_buffer_peek
	return count >= n;
}

static
bool are_events_in_head(char* e1, size_t i1, char* e2, size_t i2, int count, size_t ev_size, int event_kinds[], int n_events) {
    // this functions checks that a buffer have the same kind of event as the array event_kinds
    assert(n_events > 0);
	if (count < n_events) {
	    return false;
    }

	int i = 0;
	while (i < i1) {
	    vms_event * ev = (vms_event *) (e1);
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
	    vms_event * ev = (vms_event *) e2;
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
static inline dump_event_data(vms_event *ev, size_t ev_size) {
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
            return "E";
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
print_buffer_prefix(vms_arbiter_buffer *b, int src_idx, size_t n_events, int cnt, char* e1, size_t i1, char* e2, size_t i2) {
    if (cnt == 0) {
        fprintf(stderr, " empty\n");
        return;
    }
    const size_t ev_size = vms_arbiter_buffer_elem_size(b);
    int n = 0;
	int i = 0;
	while (i < i1) {
	    vms_event * ev = (vms_event *) (e1);
        fprintf(stderr, "  %d: {id: %5lu, kind: %3lu", ++n,
                vms_event_id(ev), vms_event_kind(ev));
        if (src_idx != -1)
            fprintf(stderr, " -> %-12s", get_event_name(src_idx, vms_event_kind(ev)));
        /*dump_event_data(ev, ev_size);*/
        fprintf(stderr, "}\n");
        if (--n_events == 0)
            return;
	    i+=1;
	    e1 += ev_size;
	}

	i = 0;
	while (i < i2) {
	    vms_event * ev = (vms_event *) e2;
        fprintf(stderr, "  %d: {id: %5lu, kind: %3lu", ++n,
                vms_event_id(ev), vms_event_kind(ev));
        if (src_idx != -1)
            fprintf(stderr, " -> %-12s", get_event_name(src_idx, vms_event_kind(ev)));
        /*dump_event_data(ev, ev_size);*/
        fprintf(stderr, "}\n");

        if (--n_events == 0)
            return;
	    i+=1;
	    e2 += ev_size;
	}
}



static inline
vms_event * get_event_at_index(char* e1, size_t i1, char* e2, size_t i2, size_t size_event, int element_index) {
	if (element_index < i1) {
		return (vms_event *) (e1 + (element_index*size_event));
	} else {
		element_index -=i1;
		return (vms_event *) (e2 + (element_index*size_event));
	}
}

//arbiter outevent (the monitor looks at this)
STREAM_Events_out *arbiter_outevent;

int RULE_SET_rules();


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
            printf("E\n");
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
    

int get_event_at_head(vms_arbiter_buffer *b) {
    void * e1; size_t i1;
    void * e2; size_t i2;

    int count = vms_arbiter_buffer_peek(b, 0, &e1, &i1, &e2, &i2);
    if (count == 0) {
        return -1;
    }
    vms_event * ev = (vms_event *) (e1);
    return ev->kind;
}
    

void print_buffers_state() {
    int event_index;
int count;
void *e1, *e2;
size_t i1, i2;

	fprintf(stderr, "Prefix of 'Src':\n");
	count = vms_arbiter_buffer_peek(BUFFER_Src, 10, (void**)&e1, &i1, (void**)&e2, &i2);
	print_buffer_prefix(BUFFER_Src, 0, i1 + i2, count, e1, i1, e2, i2);

}

static void print_buffer_state(vms_arbiter_buffer *buffer) {
    int count;
    void *e1, *e2;
    size_t i1, i2;
    count = vms_arbiter_buffer_peek(buffer, 10, (void**)&e1, &i1, (void**)&e2, &i2);
    print_buffer_prefix(buffer, -1, i1 + i2, count, e1, i1, e2, i2);
}


int RULE_SET_rules() {
char* e1_Src; size_t i1_Src; char* e2_Src; size_t i2_Src;
int count_Src = vms_arbiter_buffer_peek(BUFFER_Src, 1, (void**)&e1_Src, &i1_Src, (void**)&e2_Src, &i2_Src);

            int TEMPARR0[] = {EVENTS_E};

            
                if (are_events_in_head(e1_Src, i1_Src, e2_Src, i2_Src, 
                count_Src, sizeof(STREAM_Events_out), TEMPARR0, 1)) {
                    
            STREAM_Events_out * event_for_n = (STREAM_Events_out *) get_event_at_index(e1_Src, i1_Src, e2_Src, i2_Src, sizeof(STREAM_Events_out), 0);
long n = event_for_n->cases.E.n;


           
            if(true ) {
                bool local_continue_ = false;
                
        arbiter_outevent = (STREAM_Events_out *)vms_monitor_buffer_write_ptr(monitor_buffer);
         arbiter_outevent->head.kind = 2;
    arbiter_outevent->head.id = arbiter_counter++;
    ((STREAM_Events_out *) arbiter_outevent)->cases.E.n = n;

         vms_monitor_buffer_write_finish(monitor_buffer);
        
                	vms_arbiter_buffer_drop(BUFFER_Src, 1); ARBITER_DROPPED_ = true;


                if (!local_continue_) {
                    return 1;
                }
            }
            

                }
            
            int TEMPARR1[] = {EVENTS_HOLE};

            
                if (are_events_in_head(e1_Src, i1_Src, e2_Src, i2_Src, 
                count_Src, sizeof(STREAM_Events_out), TEMPARR1, 1)) {
                    
            STREAM_Events_out * event_for_n = (STREAM_Events_out *) get_event_at_index(e1_Src, i1_Src, e2_Src, i2_Src, sizeof(STREAM_Events_out), 0);
int n = event_for_n->cases.hole.n;


           
            if(true ) {
                bool local_continue_ = false;
                
        arbiter_outevent = (STREAM_Events_out *)vms_monitor_buffer_write_ptr(monitor_buffer);
         arbiter_outevent->head.kind = 1;
    arbiter_outevent->head.id = arbiter_counter++;
    ((STREAM_Events_out *) arbiter_outevent)->cases.hole.n = n;

         vms_monitor_buffer_write_finish(monitor_buffer);
        
                	vms_arbiter_buffer_drop(BUFFER_Src, 1); ARBITER_DROPPED_ = true;


                if (!local_continue_) {
                    return 1;
                }
            }
            

                }
            _Bool ok = 1;
if (count_Src >= 1) {	ok = 0;
}
if (ok == 0) {
	fprintf(stderr, "Prefix of 'Src':\n");
	count_Src = vms_arbiter_buffer_peek(BUFFER_Src, 5, (void**)&e1_Src, &i1_Src, (void**)&e2_Src, &i2_Src);
	print_buffer_prefix(BUFFER_Src, 0, i1_Src + i2_Src, count_Src, e1_Src, i1_Src, e2_Src, i2_Src);
fprintf(stderr, "No rule in rule set 'rules' matched even though there was enough events, CYCLING WITH NO PROGRESS (exiting)!\n");__work_done=1; abort();}
if (++RULE_SET_rules_nomatch_cnt >= 500000) {                if (RULE_SET_rules_nomatch_cnt == 500000)                    fprintf(stderr, "Rule set 'rules' cycles long time without progress...\n");                if (RULE_SET_rules_nomatch_cnt % 5000 == 0) _mm_pause();                if (RULE_SET_rules_nomatch_cnt > 650000) _mm_pause();                if (RULE_SET_rules_nomatch_cnt > 700000) _mm_pause();                if (RULE_SET_rules_nomatch_cnt > 750000) _mm_pause();                size_t sleep_time = 2;                if (RULE_SET_rules_nomatch_cnt > 800000) sleep_time += (10);                if (RULE_SET_rules_nomatch_cnt > 900000) sleep_time += (20);                if (RULE_SET_rules_nomatch_cnt > 950000) sleep_time += (40);                sleep_ns(sleep_time);                if (RULE_SET_rules_nomatch_cnt > 1000000) {                    RULE_SET_rules_nomatch_cnt = 0;	fprintf(stderr, "\033[31mRule set 'rules' cycles really long time without progress\033[0m\n");	fprintf(stderr, "Prefix of 'Src':\n");
	count_Src = vms_arbiter_buffer_peek(BUFFER_Src, 5, (void**)&e1_Src, &i1_Src, (void**)&e2_Src, &i2_Src);
	print_buffer_prefix(BUFFER_Src, 0, i1_Src + i2_Src, count_Src, e1_Src, i1_Src, e2_Src, i2_Src);
fprintf(stderr, "Seems all rules are waiting for some events that are not coming\n");}}
	return 0;
}
int arbiter() {

        while (!are_streams_done()) {
            ARBITER_MATCHED_ = false;
            ARBITER_DROPPED_ = false;

            		if (!ARBITER_MATCHED_ && current_rule_set == SWITCH_TO_RULE_SET_rules) { 
			if (RULE_SET_rules()) { ARBITER_MATCHED_= true; RULE_SET_rules_nomatch_cnt = 0; }
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
	fprintf(stderr, "Prefix of 'Src':\n");
	count_ = vms_arbiter_buffer_peek(BUFFER_Src, 5, (void**)&e1, &i1, (void**)&e2, &i2);
	print_buffer_prefix(BUFFER_Src, 0, i1 + i2, count_, e1, i1, e2, i2);

                        
                    }
                }
            }
        }
        vms_monitor_set_finished(monitor_buffer);
        return 0;
    }
        

static void sig_handler(int sig) {
	printf("signal %d caught...", sig);	vms_stream_detach(EV_SOURCE_Src);
	__work_done = 1;
} // MAREK knows

static void setup_signals() {
    // MAREK knows
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
    // startup code
	

    // init. event sources streams
    

    // connecting event sources
    	// connect to event source Src

                vms_stream_hole_handling hh_Src = {
                  .hole_event_size = sizeof(STREAM_Events_out),
                  .init = &init_hole_hole,
                  .update = &update_hole_hole
                };

                	EV_SOURCE_Src = vms_stream_create_from_argv("Src", argc, argv, &hh_Src);
	BUFFER_Src = vms_arbiter_buffer_create(EV_SOURCE_Src,  sizeof(STREAM_Events_out), 1024);

	// register events in Src
	if (vms_stream_register_event(EV_SOURCE_Src, "E", EVENTS_E) < 0) {
		fprintf(stderr, "Failed registering event E for stream Src : Events\n");
		fprintf(stderr, "Available events:\n");
		vms_stream_dump_events(EV_SOURCE_Src);
		abort();
	}


     // activate buffers
     printf("-- creating buffers\n");
    	vms_arbiter_buffer_set_active(BUFFER_Src, true);

 	monitor_buffer = vms_monitor_buffer_create(sizeof(STREAM_Events_out), 4);

 	 // init buffer groups
     printf("-- initializing buffer groups\n");
     

     // create source-events threads
     printf("-- creating performance threads\n");
     	thrd_create(&THREAD_Src, (void*)PERF_LAYER_forward_Events,BUFFER_Src);


     // create arbiter thread
     printf("-- creating arbiter thread\n");
     thrd_create(&ARBITER_THREAD, arbiter, 0);

     
        // monitor
        printf("-- starting monitor code \n");
        STREAM_Events_out * received_event;
        while(true) {
            received_event = fetch_arbiter_stream(monitor_buffer);
            if (received_event == NULL) {
                break;
            }

		if (received_event->head.kind == 2) {
			long n = received_event->cases.E.n;

		  if (true ) {
		      ++processed;
     
		  }
		}
        
		if (received_event->head.kind == 1) {
			int n = received_event->cases.hole.n;

		  if (true ) {
		      ++holes_num;
       dropped += n;
     
		  }
		}
        
        vms_monitor_buffer_consume(monitor_buffer, 1);
    }
    

     printf("-- cleaning up\n");
     	vms_stream_destroy(EV_SOURCE_Src);
	vms_arbiter_buffer_free(BUFFER_Src);
	free(monitor_buffer);
	free(chosen_streams);


    // BEGIN clean up code
printf("Processed %lu events, dropped %lu events in %lu holes\n",
         processed, dropped, holes_num);
 
}
