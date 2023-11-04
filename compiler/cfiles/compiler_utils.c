#include <stdio.h>
#include <stdlib.h>
#include <assert.h>

#include "compiler_utils.h"
#include "vamos-buffers/core/shamon.h"


void __vamos_init_buffer_group(__vamos_buffer_group *bg, int (*order)(__vamos_buffer_group * bg, __vamos_bg_list_node *stream1, __vamos_bg_list_node *stream2))
{
    bg->head=0;
    bg->idcounter=1;
    bg->inserted=0;
    bg->lastfirst=0;
    bg->order=order;
    bg->size=0;
    bg->updated=0;
    mtx_init(&bg->insert_lock, mtx_plain);
}

void __vamos_bg_insert(__vamos_buffer_group *bg, __vamos_streaminfo *stream)
{
    __vamos_bg_list_node* node=(__vamos_bg_list_node*)malloc(sizeof(__vamos_bg_list_node));
    if(node==0)
    {
        printf("Could not allocate buffer group member list node!");
        abort();
    }
    node->group=bg;
    node->stream=stream;
    node->id=bg->idcounter++;
    node->insert_next=0;
    node->member_next=0;
    node->member_prev=0;
    node->next=0;
    node->prev=0;
    node->update_next=0;
    node->update_prev=0;
    int done=0;
    __vamos_bg_list_node * volatile * insert_pos = &bg->inserted;
    mtx_lock(&bg->insert_lock);
    __vamos_bg_list_node * insert=*insert_pos;
    while(insert!=0)
    {
        insert_pos=&insert->insert_next;
        insert=*insert_pos;
    }
    *insert_pos=node;
    mtx_unlock(&bg->insert_lock);
}
void __vamos_bg_process_inserts(__vamos_buffer_group *bg)
{
    __vamos_bg_list_node * volatile * insert_pos = &bg->inserted;
    mtx_lock(&bg->insert_lock);
    __vamos_bg_list_node * insert=*insert_pos;
    while(insert!=0)
    {
        __vamos_bg_insert_node(bg, insert);
        insert_pos=&insert->insert_next;
        insert=*insert_pos;
    }
    bg->inserted=0;
    mtx_unlock(&bg->insert_lock);
}
void __vamos_bg_process_updates(__vamos_buffer_group *bg)
{
    if(bg->updated!=0)
    {
        __vamos_bg_list_node * cur=bg->updated;
        __vamos_bg_list_node * final = cur->prev;
        __vamos_bg_list_node * lastcur=0;
        do
        {
            __vamos_bg_adjust_pos(bg, cur);
            lastcur=cur;
            cur=cur->update_next;
            if(!lastcur->stream->needed_aggfields)
            {
                lastcur->update_next->update_prev=lastcur->update_prev;
                lastcur->update_prev->update_next=lastcur->update_next;
                if(bg->updated==lastcur)
                {
                    if(lastcur->update_next==lastcur)
                    {
                        bg->updated=0;
                    }
                    else
                    {
                        bg->updated=lastcur->update_next;
                    }
                }
            }
        } while (lastcur!=final);
    }
}
bool __vamos_bg_add(__vamos_buffer_group *bg, __vamos_streaminfo *stream)
{
    if(stream->memberships!=0)
    {
        __vamos_bg_list_node* cur=stream->memberships;
        do
        {
            if(cur->group==bg)
            {
                return false;
            }
            cur=cur->member_next;
        } while (cur!=stream->memberships);
        
    }
    __vamos_bg_list_node* node=(__vamos_bg_list_node*)malloc(sizeof(__vamos_bg_list_node));
    if(node==0)
    {
        printf("Could not allocate buffer group member list node!");
        abort();
    }
    node->group=bg;
    node->stream=stream;
    node->id=bg->idcounter++;
    node->insert_next=0;
    node->member_next=0;
    node->member_prev=0;
    node->next=0;
    node->prev=0;
    node->update_next=0;
    node->update_prev=0;
    return __vamos_bg_insert_node(bg, node);
}
bool __vamos_bg_insert_node(__vamos_buffer_group *bg, __vamos_bg_list_node * node)
{
    if(bg->head==0)
    {
        bg->head=node;
        node->next=node;
        node->prev=node;
    }
    else
    {
        node->next=bg->head;
        node->prev=bg->head->prev;
        node->next->prev=node;
        node->prev->next=node;
        __vamos_bg_adjust_pos(bg, node);
    }
    if(node->stream->memberships==0)
    {
        node->stream->memberships=node;
        node->member_next=node;
        node->member_prev=node;
    }
    else
    {
        node->member_next=node->stream->memberships;
        node->member_prev=node->stream->memberships->member_prev;
        node->member_next->member_prev=node;
        node->member_prev->member_next=node;
    }
    return true;
}
bool __vamos_bg_adjust_pos(__vamos_buffer_group *bg, __vamos_bg_list_node * node)
{
    __vamos_bg_list_node * curcomp=node->prev;
    int swap=false;
    int direction=0;
    while(true)
    {
        while(curcomp->update_next!=0&&curcomp!=node&&curcomp!=bg->head)
        {
            curcomp=curcomp->prev;
        }
        if(order(node, curcomp)<0)
        {
            swap=true;
            if(curcomp==bg->head)
            {
                break;
            }
        }
        curcomp=node->prev;
    }
    if(swap)
    {
        node->prev->next=node->next;
        node->next->prev=node->prev;

        node->prev=curcomp->prev;
        node->prev->next=node;
        curcomp->prev=node;
        node->next=curcomp;

        if(curcomp==bg->head)
        {
            bg->head=node;
        }
    }
    else
    {
        curcomp=bg->head->prev;
        while(true)
        {
            while(curcomp->update_next!=0&&curcomp!=node)
            {
                curcomp=curcomp->prev;
            }
            if(curcomp==node)
            {
                break;
            }
            if(order(curcomp, node)<0)
            {
                node->prev->next=node->next;
                node->next->prev=node->prev;

                node->next=curcomp->next;
                node->next->prev=node;
                curcomp->next=node;
                node->prev=curcomp;
                break;
            }
            curcomp=node->prev;
        }
    }
    return true;
}
bool __vamos_bg_remove(__vamos_buffer_group *bg, __vamos_streaminfo *stream)
{
    if(stream->memberships!=0)
    {
        __vamos_bg_list_node* cur=stream->memberships;
        do
        {
            if(cur->group==bg)
            {
                if(stream->memberships==cur)
                {
                    if(cur->member_next==cur)
                    {
                        stream->memberships=0;
                    }
                    else
                    {
                        stream->memberships=cur->member_next;
                    }
                }
                if(bg->head==cur)
                {
                    if(cur->next==cur)
                    {
                        bg->head=0;
                    }
                    else
                    {
                        bg->head=cur->next;
                    }
                }
                if(bg->updated==cur)
                {
                    if(cur->update_next==cur)
                    {
                        bg->updated=0;
                    }
                    else
                    {
                        bg->updated=cur->update_next;
                    }
                }
                cur->next->prev=cur->prev;
                cur->prev->next=cur->next;
                if(cur->update_next!=0)
                {
                    cur->update_next->update_prev=cur->update_prev;
                    cur->update_prev->update_next=cur->update_next;
                }
                free(cur);
                return true;
            }
            cur=cur->member_next;
        } while (cur!=stream->memberships);
        
    }
    return false;
}
void __vamos_stream_mark_for_update(__vamos_streaminfo * stream)
{
    if(stream->memberships==0)
    {
        return;
    }
    __vamos_bg_list_node * cur=stream->memberships;
    do
    {
        if(cur->update_next==0)
        {
            if(cur->group->updated==0)
            {
                cur->update_next=cur;
                cur->update_prev=cur;
                cur->group->updated=cur;
            }
            else
            {
                cur->update_next=cur->group->updated;
                cur->update_prev=cur->group->updated->prev;
                cur->update_next->update_prev=cur;
                cur->update_prev->update_next=cur;
            }
        }
        cur=cur->member_next;
    } while (cur!=stream->memberships);
}

int __vamos_advance_permutation_forward(__vamos_bg_list_node** nodes, int permsize, __vamos_bg_list_node* first)
{
    __vamos_bg_list_node** lsn=nodes+(permsize-1);
    __vamos_bg_list_node** pos=lsn;
    while(pos>=nodes)
    {
        incstart:
        (*pos)=(*pos)->next;
        if((*pos)==first)
        {
            pos--;
            continue;
        }
        for(__vamos_bg_list_node** x=nodes;x<pos;x++)
        {
            if((*pos)==*x)
            {
                goto incstart;
            }
        }
        for(__vamos_bg_list_node** x=pos+1;x<=lsn;x++)
        {
            *x=first;
            inner_incstart:
            for(__vamos_bg_list_node** y=nodes;y<x;y++)
            {
                if((*x)==(*y))
                {
                    (*x)=(*x)->next;
                    goto inner_incstart;
                }
            }
        }
        return 1;
    }
    return 0;
}
int __vamos_advance_permutation_backward(__vamos_bg_list_node** nodes, int permsize, __vamos_bg_list_node* last)
{
    __vamos_bg_list_node** lsn=nodes+(permsize-1);
    __vamos_bg_list_node** pos=lsn;
    while(pos>=nodes)
    {
        incstart:
        (*pos)=(*pos)->prev;
        if((*pos)==last)
        {
            pos--;
            continue;
        }
        for(__vamos_bg_list_node** x=nodes;x<pos;x++)
        {
            if((*pos)==*x)
            {
                goto incstart;
            }
        }
        for(__vamos_bg_list_node** x=pos+1;x<=lsn;x++)
        {
            *x=last;
            inner_incstart:
            for(__vamos_bg_list_node** y=nodes;y<x;y++)
            {
                if((*x)==(*y))
                {
                    (*x)=(*x)->prev;
                    goto inner_incstart;
                }
            }
        }
        return 1;
    }
    return 0;
}

size_t __vamos_request_from_buffer(__vamos_streaminfo * stream, size_t count, uint64_t current_round)
{
    if(stream->status > 0 && stream->size1 + stream->size2 < count && (stream->available >= count || stream->lastround < current_round))
    {
        stream->available = vms_arbiter_buffer_peek(stream->buffer, count, &stream->data1, &stream->size1, &stream->data2, &stream->size2);
        stream->lastround = current_round;
    }
    return stream->available;
}