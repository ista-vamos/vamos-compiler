# Shamon API for monitors

All core library functions are defined in "shamon.h", with some additional things defined in "mmlib.h" (marked with [MMLIB])

Before any other calls to the library, call: 
```C
initialize_events();
```   

## TYPES:
- control -> struct source_control 
- evstream -> shm_stream* (on the event source side) / shm_arbiter_buffer* (on the arbiter size)
- event -> void* (essentially a pointer to an event struct whose first field is of C type "shm_event")
- evaddr -> void* (typically starts as a pointer to an event but past the first field (so a pointer to where new data is written), and moves further back as more data is written)
- data -> char*/void*
- int -> int/size_t/...

## FUNCTIONS:
### Performance Layer
- `connect(name, cbufsize) : (s/b,c)` -> 
[
 `s = shm_stream_create(name, argc, argv);`
 `b = shm_arbiter_buffer_create(s, sizeof([stream type, possibly including holes]), cbufsize);`
 // <- possibly start new thread for performance layer here (in there, loop on `!shm_arbiter_buffer_active(b)` until it has been set as active, see next line)
 `shm_arbiter_buffer_set_active(b, 1);`
]
  - Connects to an event source via some name
  - ALTERNATIVELY, use `mm_stream_create` [MMLIB] instead of `shm_stream_create`, which has one additional parameter - a number of times it might try to attempt to connect to the stream (if the event source is a bit slow in creating it)

- `fetch(s/b) : e + drop(s,e)` / `(start_forward(s/b,k) + forward_part(a,d,sz)... + finish_forward)` [NOTE: for just forward(s,e) and forward_vardata, please ask Marek] ->
[
  ff = [function pointer to function that looks at events and decides whether to drop them. i.e. this function encodes all the if-stmts and then returns whether the thing inside is forward or drop]
  e = stream_filter_fetch(s,b,ff);
  char* a = shm_arbiter_buffer_write_ptr(buffer);
  memcpy(a, d, sz); a+=sz; ...
  shm_arbiter_buffer_write_finish(b);
  shm_stream_consume(s,1);
]
- fetchND(s/b) : (e,a) + start_forward(s/b, k) + forward_part(a,d,sz)... + finish_forward ->
[
  e = stream_fetch(s,b);
  char* a = shm_arbiter_buffer_write_ptr(buffer);
  memcpy(a, d, sz); a+=sz; ...
  shm_arbiter_buffer_write_finish(b);
  shm_stream_consume(s,1);
]

### Correctness Layer
- peek(b,n) : (e1[], i1, e2[], i2) ->
[
	void* e1;
	size_t i1;
	void* e2;
	size_t i2;
	...
	count = shm_arbiter_buffer_peek(b, n, &e1, &i1, &e2, &i2);
]
- count(e) : i ->
[
	void* e1;
	size_t i1;
	void* e2;
	size_t i2;
	...
	count = shm_arbiter_buffer_peek(b,0, &e1, &i1, &e2, &i2);
]
- consume(b, n) : i ->
[
	shm_arbiter_buffer_drop(b, n);
]
- ALTERNATIVELY, you can use __MM_BUFDROP(b, n, count, fcount, e1, i1, e2, i2);
here, count is the same variable as above, while fcount = i1+i2;
this macro calls shm_arbiter_buffer_drop and adjusts the other variables by n (split across i1 and i2 as appropriate). If i1 becomes 0, it also moves e2/i2 to e1/i1 (so you don't have to skip past the 0-length buffer).

- for retrieve_vardata, please ask Marek