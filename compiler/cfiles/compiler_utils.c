#include "compiler_utils.h"
#include "../../core/shamon.h"
#include "../../gen/mmlib.h"
#include <stdio.h>

void init_buffer_group(buffer_group *bg) {
    //bg = malloc(sizeof(buffer_group));
    bg->size = 0;
    bg->head = NULL;
    bg->tail = NULL;
    bg->waiting_list_head = NULL;
    bg->waiting_list_tail = NULL;
}

void destroy_buffer_group(buffer_group *bg) {
    dll_node * curr = bg->head;
    dll_node *next;
     while (curr != NULL) {
        next = curr->next;
        free(curr);
        curr = next;
     }
    //free(bg);
}

void bg_merge_waiting_list(buffer_group *bg, bool (*order_exp)(void *args1, void *args2)) {
    dll_node * current = bg->waiting_list_head;
    while(current != NULL) {
        shm_stream *s = current->stream;
        void *b = current->buffer;
        void *args = current->args;
        
        dll_node *next = current->next; 
        bg_insert(bg, current, order_exp);
        current = next;
    }

    bg->waiting_list_head = NULL;
    bg->waiting_list_tail = NULL;
}

void bg_add_to_waiting_list(buffer_group *bg, shm_stream *stream, void* buffer, void *args) {
    dll_node *new_node =  (dll_node *) malloc(sizeof(dll_node));
    new_node->stream = stream;
    new_node->buffer = buffer;
    new_node->args = args;
    new_node->next = NULL;
    new_node->prev = NULL;
    if(bg->waiting_list_head == NULL) {
        bg->head = new_node;
        bg->tail = new_node;
    } else {
        bg->tail->next = new_node;
        bg->tail = new_node;
    }
}

void bg_insert(buffer_group *bg, dll_node *new_node, bool (*order_exp)(void *args1, void *args2)) {
    new_node->next = NULL;
    new_node->prev = NULL;
    if(bg->size == 0) {
        bg->head = new_node;
        bg->tail = new_node;
    } else {
        // check if it goes on the tail
        if (bg->tail->stream == new_node->stream) return;
        if (bg->head->stream == new_node->stream) return;
        if (order_exp(new_node->args, bg->tail->args)) {
            bg->tail->next = new_node;
            new_node->next = NULL;
            new_node->prev = bg->tail;
            bg->tail = new_node;            
        }
        // check if it goes on head
        
        else if(!order_exp(new_node->args, bg->head->args)) {
            new_node->next = bg->head;
            new_node->prev = NULL;
            bg->head->prev = new_node;
            bg->head = new_node;
        }else {
            // new node goes somewhere in the middle
            dll_node *curr = bg->head;
            while (order_exp(new_node->args, curr->args)) {
                // curr should never be NULL at this point
                curr = curr->next;
            }

            dll_node *prev_node = curr->prev;
            if(curr->stream == new_node->stream || prev_node->stream == new_node->stream) return;
            new_node->prev = prev_node;
            new_node->next = curr;

            prev_node->next = new_node;
            curr->prev = new_node;
        }
    }

    bg->size +=1;
}


bool bg_remove(buffer_group *bg, shm_stream *stream) {
    // returns true only when the element was found and therefore, removed.
    dll_node * curr = bg->head;

    while(curr != NULL) {
        if (curr->stream == stream) {
            dll_node *after_curr = curr->next;
            dll_node *before_curr = curr->prev;
            if(before_curr != NULL){
                before_curr->next = after_curr;
            }
            
            if(after_curr != NULL){
                after_curr->prev = before_curr;
            }
            if(curr == bg->head) {
                bg->head = after_curr;
            }
            if(curr == bg->tail) {
                bg->tail = before_curr;
            }
            free(curr);
            bg->size -=1;
            return true;
        } 
        curr = curr->next;
    }
    return false;

}

void bg_remove_first_n(buffer_group *bg, int n) {
    dll_node * curr = bg->head;
    dll_node * next;
    while(n > 0 && bg->size > 0) {
        next = curr->next;
        bg_remove(bg, curr->stream);
        n--;
        curr = next;
    }
}

void bg_remove_last_n(buffer_group *bg, int n) {
    dll_node * curr = bg->tail;
    dll_node * next;
    while(n > 0 && bg->size > 0) {
        next = curr->prev;
        bg_remove(bg, curr->stream);
        n--;
        curr = next;
    }
}

bool bg_get_first_n(buffer_group *bg, int at_least, dll_node ***result) {
    if (bg->size < at_least) {
        return false;
    }
    dll_node * curr = bg->head;
    for (int i = 0; curr!=NULL; i++){
        (*result)[i] = curr;
        curr = curr->next;
    }
    return true;
}

bool bg_get_last_n(buffer_group *bg, int at_least, dll_node ***result) {
    if (bg->size < at_least) {
        return false;
    }
    dll_node * curr = bg->tail;
    for (int i = 0; curr!=NULL; i++){
        (*result)[i] = curr;
        curr = curr->prev;
    }
    return true;
}

void swap_dll_node(dll_node *node1, dll_node *node2) {
    dll_node * node1_prev = node1->prev;
    dll_node * node1_next = node1->next;

    dll_node *node2_prev = node2->prev;
    dll_node *node2_next = node2->next;
    if (node1_prev){
        node1_prev->next = node2;
    }

    assert(node1_next == node2);
    node1->prev = node2;
    node1->next = node2_next;

    assert(node2_prev == node1);
    node2->prev = node1_prev;
    node2->next = node1;
    if(node2_next){
        node2_next->prev = node1;
    }
    

}

void bg_update(buffer_group *bg, bool (*order_exp)(void *args1, void *args2)) {

    bool change = true;

    while(change) {
        dll_node *prev = bg->head;
        dll_node * current;
        dll_node * temp_after;
        change = false;
        while(prev && prev->next){
            current = prev->next;
            // at this point prev and current are NOT NULL
            if(order_exp(prev->args, current->args)){
                if(prev == bg->head){
                    bg->head = current;
                }
                if(current == bg->tail){
                    bg->tail = prev;
                }
                change = true;
                

                swap_dll_node(prev, current);
                prev = prev->next;
            } else {
                prev = current;
            }

        }


    }

}

