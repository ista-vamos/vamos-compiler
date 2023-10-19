
def posInfoFromParser(p):
    return CodeSpan(CodePos(p.linespan(0)[0],p.lexspan(0)[0]),CodePos(p.linespan(0)[1],p.lexspan(0)[1]))

def posInfoFromParserItem(p,i):
    return CodeSpan(CodePos(p.linespan(i)[0],p.lexspan(i)[0]),CodePos(p.linespan(i)[1],p.lexspan(i)[1]))

stdImports=[
    "<threads.h>",
    "<signal.h>",
    "<stdio.h>",
    "<stdlib.h>",
    "<stdint.h>",
    "<stdatomic.h>",
    "<assert.h>",
    "<limits.h>",
    "<immintrin.h>",
    "\"vamos-buffers/core/arbiter.h\"",
    "\"vamos-buffers/core/monitor.h\"",
    "\"vamos-buffers/core/utils.h\"",
    "\"vamos-buffers/streams/streams.h\"",
    "\"compiler/cfiles/compiler_utils.h\""
]

errors=[]
def registerError(e):
    errors.append(e)

class VamosError:
    def __init__(self, sourcePosns, msg):
        self.posns=sourcePosns
        self.msg=msg

class CodeSpan:
    def __init__(self, start, end):
        self.start=start
        self.end=end
    def StartSpan(self):
        return CodeSpan(self.start, self.start)
    def EndSpan(self):
        return CodeSpan(self.end, self.end)
    def Combine(self, other, right):
        if(right):
            return CodeSpan(self.start, other.end)
        else:
            return CodeSpan(other.start, self.end)

class CodePos:
    def __init__(self, line, col):
        self.line=line
        self.col=col
    def __str__(self):
        return f"[{self.line},{self.col}]"

class ASTNode:
    def __init__(self, posInfo):
        self.pos=posInfo

class VamosSpec:
    def __init__(self, components, arbiter, monitor):
        self.components=components
        self.arbiter=arbiter
        self.monitor=monitor
        self.imports=stdImports

    def initialize(self):
        self.cglobals=None
        self.cstartup=None
        self.ccleanup=None
        self.cloopdebug=None
        self.streamTypes={}
        self.streamProcessors={}
        self.matchFuns={}
        self.bufferGroups={}
        self.eventSources={}
        for component in self.components:
            component.Register(self)

    def initializeMembers(self):
        streamType.initializeMembers(self, [])

        done=False
        while not done:
            done=True
            for streamType in self.streamTypes:
                done=done and streamType.initializeMembers(self)

    def toCCode(self):
        ret=""
        for mprt in self.imports:
            ret+=f"#include {mprt}\n"

        ret+=f"""

#define __vamos_min(a, b) ((a < b) ? (a) : (b))
#define __vamos_max(a, b) ((a > b) ? (a) : (b))

#ifdef NDEBUG
#define vamos_check(cond)
#define vamos_assert(cond)
#else
#define vamos_check(cond) do {{ if (!cond) {{fprintf(stderr, "\033[31m%s:%s:%d: check '" #cond "' failed!\033[0m\\n", __FILE__, __func__, __LINE__); print_buffers_state(); }} }} while(0)
#define vamos_assert(cond) do{{ if (!cond) {{fprintf(stderr, "\033[31m%s:%s:%d: assert '" #cond "' failed!\033[0m\\n", __FILE__, __func__, __LINE__); print_buffers_state(); __work_done = 1; }} }} while(0)
#endif

#define vamos_hard_assert(cond) do{{ if (!cond) {{fprintf(stderr, "\033[31m%s:%s:%d: assert '" #cond "' failed!\033[0m\\n", __FILE__, __func__, __LINE__); print_buffers_state(); __work_done = 1; abort();}} }} while(0)

atomic_int count_event_streams = {len(self.eventSources)};

struct _EVENT_hole
{"{"}
  uint64_t n;
{"}"};
typedef struct _EVENT_hole EVENT_hole;

struct _EVENT_hole_wrapper {"{"}
    shm_event head;
    union {"{"}
        EVENT_hole hole;
    {"}"}cases;
{"}"};

static void init_hole_hole(shm_event *hev) {"{"}
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    h->head.kind = shm_get_hole_kind();
    h->cases.hole.n = 0;
{"}"}

static void update_hole_hole(shm_event *hev, shm_event *ev) {"{"}
    (void)ev;
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    ++h->cases.hole.n;
{"}"}
"""
        for streamType in self.streamTypes:
            ret+=streamType.toEnumDef()

        return ret

class ParameterizedRef(ASTNode):
    def __init__(self, ref, args, posInfo):
        self.ref=ref
        self.args=args
        super().__init__(posInfo)

class Reference(ASTNode):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo)

class CBlock(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)


class CGlobals(CBlock):
    def __init__(self, posInfo, code):
        self.code=code
        super().__init__(posInfo)
    def Register(self, spec):
        spec.cglobals=self

class CStartup(CBlock):
    def __init__(self, posInfo, code):
        self.code=code
        super().__init__(posInfo)
    def Register(self, spec):
        spec.cstartup=self

class CCleanup(CBlock):
    def __init__(self, posInfo, code):
        self.code=code
        super().__init__(posInfo)
    def Register(self, spec):
        spec.ccleanup=self

class CLoopdebug(CBlock):
    def __init__(self, posInfo, code):
        self.code=code
        super().__init__(posInfo)
    def Register(self, spec):
        spec.cloopdebug=self

class FieldDecl(ASTNode):
    def __init__(self, name, type, posInfo):
        self.name=name
        self.type=type
        super().__init__(posInfo)
    def __str__(self):
        return f"{self.name} : {self.type}"

class Event(ASTNode):
    def __init__(self, name, posInfo, fields, creates):
        self.name=name
        self.flds=fields
        self.creates=creates
        self.shareds=[]
        super().__init__(posInfo)
    # def __str__(self):
    #     createstr=""
    #     if(self.creates!=None):
    #         createstr=f" creates {self.creates}"
    #     return f"{self.name}({', '.join(self.fields)}){createstr}"

    def setStreamType(self, streamtype):
        self.streamType=streamtype

    def createCopyFor(self, streamtype):
        ev = Event(self.name, self.posInfo, self.flds, self.creates)
        ev.setStreamType(streamtype)
        ev.initializeIndices(self.index)
        return ev
    
    def initializeIndices(self, idx):
        self.index=idx
        index=0
        self.fields={}
        for field in self.flds:
            if field.name in self.fields:
                registerError(VamosError([field.pos], f"Multiple definitions of field named \"{field.name}\" for event \"{self.name}\" of stream type \"{self.streamType.name}\""))
            else:
                self.fields[field.name]=field
                field.index=index
                index=index+1

    def toEnumName(self):
        return self.name

    def toEnumDef(self):
        return f"{self.toEnumName()} = {self.index},\n"
        

class StreamType(ASTNode):
    def __init__(self, name, posInfo, streamfields, supertype, sharedfields, events):
        self.name=name
        self.fields=streamfields
        self.supertype=supertype
        self.shared=sharedfields
        self.evs=events
        self.initializedMembers=False
        super().__init__(posInfo)
    def __str__(self):
        return f"stream type {self.name}"
    def Register(self, spec):
        if self.name in spec.streamTypes:
            registerError(VamosError([self.pos, spec.streamTypes[self.name].pos], f"Multiple definitions for Stream Type \"{self.name}\""))
        else:
            spec.streamTypes[self.name]=self
    def initializeMembers(self, spec, seen):
        if self.initializedMembers:
            return True
        for event in self.evs:
            event.setStreamType(self)
        if self in seen:
            registerError(VamosError([self.supertype.pos],f"Cycle detected in supertype declaration for Stream Type \"{self.name}\""))
            return False
        if self.supertype is not None:
            self.supertype.resolve(spec)
            if not self.supertype.target.initializeMembers(spec, seen + [self]):
                self.supertype=None
        if self.supertype is not None:
            sharedmatch=False
            if len(self.sharedfields)==len(self.supertype.target.sharedfields):
                if all([x.name==y.name and x.type.equals(y.type) for (x,y) in zip(self.sharedfields, self.supertype.target.sharedfields)]):
                    sharedmatch=True
            if not sharedmatch:
                registerError(VamosError([self.supertype.pos], f"Supertype must have same shared fields as subtype for Stream Type \"{self.name}\""))
                self.supertype = None
        for ev in self.evs:
            ev.fields = self.sharedfields + ev.fields
        index=1
        if self.supertype is not None:
            for ev in self.supertype.events:
                self.evs.append(ev.createCopyFor(self))
                index+=1
        for ev in self.events:
            ev.initializeIndices(index)
            index+=1
        self.initializedMembers=True
        return True
    
    def toEnumName(self):
        return f"{self.name}_kinds"

    def toEnumDef(self):
        ret=f"enum {self.toEnumName()} {{\n"
        for ev in self.events:
            ret+=ev.toEnumDef()
        ret+="}"
        return ret

class StreamTypeRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

    def resolve(self, spec):
        if self.name not in spec.streamTypes:
            registerError(VamosError([self.pos], f"Unknown Stream Type Stream Type \"{self.name}\""))
            self.target=StreamType(self.name, self.pos, [], None, None, None)
            self.target.initializedMembers=True
        else:
            self.target = spec.streamTypes[self.name]

class CustomHole(ASTNode):
    def __init__(self, name, posInfo, parts):
        self.name=name
        self.parts=parts
        super().__init__(posInfo)

class StreamProcessor(ASTNode):
    def __init__(self, name, posInfo, params, fromname, fromargs, toname, toargs, extends, rules, customHole):
        self.name=name
        self.params=params
        self.fromname=fromname
        self.fromargs=fromargs
        self.toname=toname
        self.toargs=toargs
        self.extends=extends
        self.rules=rules
        self.customHole=customHole
        super().__init__(posInfo)
    def Register(self, spec):
        if self.name in spec.streamProcessors:
            registerError(VamosError([self.pos, spec.streamTypes[self.name].pos], f"Multiple definitions for Stream Processor \"{self.name}\""))
        else:
            spec.streamProcessors[self.name]=self

    def toThreadFunName(self):
        return f"__vamos_perf_sp_{self.name}"
    def toFilterFunName(self):
        return f"__vamos_perf_filter_{self.name}"

    def toCPreDecls(self, spec):
        ret = f"""
int {self.toFilterFunName()} ();
int {self.toThreadFunName()} (__vamos_arbiter_buffer *buffer);
"""     
    def toCCode(self, spec):
        ret = f"""
int {self.toThreadFunName()} (__vamos_arbiter_buffer *buffer) {"{"}
    shm_stream *stream = shm_arbiter_buffer_stream(buffer);   
    STREAM_{stream_in_name}_in *inevent;
    STREAM_{stream_out_name}_out *outevent;   

    // wait for active buffer
    while ((!shm_arbiter_buffer_active(buffer))){"{"}
        sleep_ns(10);
    {"}"}
    while(true) {"{"}
        inevent = stream_filter_fetch(stream, buffer, &{self.toFilterFunName()});

        if (inevent == NULL) {"{"}
            // no more events
            break;
        {"}"}
        outevent = shm_arbiter_buffer_write_ptr(buffer);

        {perf_layer_code}
        
        shm_stream_consume(stream, 1);
    {"}"}  
    atomic_fetch_add(&count_event_streams, -1);
    return 0;
{"}"}
"""

class HoleAttribute(ASTNode):
    def __init__(self, name, posInfo, type, aggFunc, args):
        self.name=name
        self.type=type
        self.aggFunc=aggFunc
        self.args=args
        super().__init__(posInfo)

class AggFunction(ASTNode):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo)

class EventReference(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class AggFieldAccess(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class StreamFieldRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class ProcessorRule(ASTNode):
    def __init__(self, posInfo, eventRef, eventParams, createSpec, action):
        self.event=eventRef
        self.params=eventParams
        self.createSpec=createSpec
        self.action=action
        super().__init__(posInfo)

class CreatesSpec(ASTNode):
    def __init__(self, posInfo, limit, streamtype, streaminit, conkind, includedin):
        self.limit=limit
        self.streamtype=streamtype
        self.streaminit=streaminit
        self.conkind=conkind
        self.includein=includedin
        super().__init__(posInfo)

class DirectStreamInit(ASTNode):
    def __init__(self, posInfo, args):
        self.args=args
        super().__init__(posInfo)

class StreamProcessorInit(ASTNode):
    def __init__(self, posInfo, processor, args):
        self.processor=processor
        self.args=args
        super().__init__(posInfo)

class PerformanceIf(ASTNode):
    def __init__(self, posInfo, condition, thencode, elsecode):
        self.condition=condition
        self.thencode=thencode
        self.elsecode=elsecode
        super().__init__(posInfo)

class PerformanceDrop(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class PerformanceForward(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class PerformanceForwardConstruct(ASTNode):
    def __init__(self, posInfo, event, args):
        self.event=event
        self.args=args
        super().__init__(posInfo)

class EventSource(ASTNode):
    def __init__(self, name, posInfo, isDynamic, params, streamtype, streaminit, conkind, includedin):
        self.name=name
        self.isDynamic=isDynamic
        self.params=params
        self.streamtype=streamtype
        self.streminit=streaminit
        self.conkind=conkind
        self.includedin=includedin
        super().__init__(posInfo)
    def Register(self, spec):
        if self.name in spec.eventSources:
            registerError(VamosError([self.pos, spec.eventSources[self.name].pos], f"Multiple definitions for Event Source \"{self.name}\""))
        elif self.name in spec.bufferGroups:
            registerError(VamosError([self.pos, spec.bufferGroups[self.name].pos], f"Naming collision - there cannot both be an Event Source and a Buffer Group named \"{self.name}\""))
        else:
            spec.eventSources[self.name]=self

class StreamProcessorRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class EventSourceRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class BufferGroupRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class AutoDropBufferKind(ASTNode):
    def __init__(self, posInfo, size, minFree):
        self.size=size
        self.minFree=minFree
        super().__init__(posInfo)

class BlockingBufferKind(ASTNode):
    def __init__(self, posInfo, size):
        self.size=size
        super().__init__(posInfo)

class InfiniteBufferKind(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class BufferGroup(ASTNode):
    def __init__(self, name, posInfo, streamType, order, includes):
        self.name=name
        self.streamType=streamType
        self.order=order
        self.includes=includes
        super().__init__(posInfo)
    def Register(self, spec):
        if self.name in spec.bufferGroups:
            registerError(VamosError([self.pos, spec.bufferGroups[self.name].pos], f"Multiple definitions for Buffer Group \"{self.name}\""))
        elif self.name in spec.eventSources:
            registerError(VamosError([self.pos, spec.eventSources[self.name].pos], f"Naming collision - there cannot both be an Event Source and a Buffer Group named \"{self.name}\""))
        else:
            spec.bufferGroups[self.name]=self

class RoundRobinOrder(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class StreamFieldOrder(ASTNode):
    def __init__(self, posInfo, field):
        self.field=field
        super().__init__(posInfo)

class SharedElemOrder(ASTNode):
    def __init__(self, posInfo, aggexp, missingspec):
        self.aggexp=aggexp
        self.missingspec=missingspec
        super().__init__(posInfo)

class AggInt(ASTNode):
    def __init__(self, value, posInfo):
        self.value=value
        super().__init__(posInfo)

class AggID(ASTNode):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo)

class AggFunc(ASTNode):
    def __init__(self, agg, posInfo, arg):
        self.agg=agg
        self.arg=arg
        super().__init__(posInfo)

class AggBinOp(ASTNode):
    def __init__(self, posInfo, left, op, right):
        self.left=left
        self.right=right
        self.op=op
        super().__init__(posInfo)

class AggUnOp(ASTNode):
    def __init__(self, posInfo, op, arg):
        self.op=op
        self.arg=arg
        super().__init__(posInfo)

class MissingWait(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class MissingIgnore(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class MissingAssume(ASTNode):
    def __init__(self, posInfo, expr):
        self.expr=expr
        super().__init__(posInfo)

class BGroupIncludeAll(ASTNode):
    def __init__(self, posInfo, evsource):
        self.eventsource=evsource
        super().__init__(posInfo)

class BGroupIncludeIndex(ASTNode):
    def __init__(self, posInfo, evsource):
        self.eventsource=evsource
        super().__init__(posInfo)

class EventSourceIndexedRef(Reference):
    def __init__(self, name, posInfo, idx):
        self.index=idx
        super().__init__(name, posInfo)

class MatchFun(ASTNode):
    def __init__(self, name, posInfo, sources, params, exp):
        self.name=name
        self.sources=sources
        self.params=params
        self.exp=exp
        super().__init__(posInfo)
    def Register(self, spec):
        if self.name in spec.matchFuns:
            registerError(VamosError([self.pos, spec.matchFuns[self.name].pos], f"Multiple definitions for Match Function \"{self.name}\""))
        else:
            spec.matchFuns[self.name]=self

class Arbiter(ASTNode):
    def __init__(self, posInfo, streamtype, rulesets):
        self.streamtype=streamtype
        self.rulesets=rulesets
        super().__init__(posInfo)

class RuleSet(ASTNode):
    def __init__(self, name, posInfo, rules):
        self.name=name
        self.rules=rules
        super().__init__(posInfo)

class ArbiterRule(ASTNode):
    def __init__(self, posInfo, condition, code):
        self.condition=condition
        self.code=code
        super().__init__(posInfo)

class ArbiterAlwaysCondition(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class ArbiterMatchCondition(ASTNode):
    def __init__(self, posInfo, matchExps, whereCond):
        self.matchExps=matchExps
        self.whereCond=whereCond
        super().__init__(posInfo)

class ArbiterChoice(ASTNode):
    def __init__(self, posInfo, direction, variables, group, filter):
        self.direction=direction
        self.variables=variables
        self.group=group
        self.filter=filter
        super().__init__(posInfo)

class ArbiterChoiceRule(ASTNode):
    def __init__(self, posInfo, choice, rules):
        self.choice=choice
        self.rules=rules
        super().__init__(posInfo)

class ChooseFirst(ASTNode):
    def __init__(self, posInfo, n):
        self.n=n
        super().__init__(posInfo)

class ChooseLast(ASTNode):
    def __init__(self, posInfo, n):
        self.n=n
        super().__init__(posInfo)

class Monitor(ASTNode):
    def __init__(self, posInfo, bufsize, rules):
        self.bufsize=bufsize
        self.rules=rules
        super().__init__(posInfo)

class MonitorRule(ASTNode):
    def __init__(self, posInfo, event, params, condition, code):
        self.event=event
        self.params=params
        self.condition=condition
        self.code=code
        super().__init__(posInfo)

class CCode(ASTNode):
    def __init__(self, posInfo, text):
        self.text=text
        super().__init__(posInfo)

    def merge(self, other, right):
        return other.mergeCode(self, not  right)
    
    def mergeEscape(self, other, right):
        return other.mergeCode(self, not right)
    
    def mergeCode(self, other, right):
        if(right):
            self.text+=other.text
        else:
            self.text=other.text+self.text
        self.pos=self.pos.Combine(other.pos, right)
        return self

class CCodeEmpty(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

    def merge(self, other, right):
        return other
    
    def mergeEscape(self, other, right):
        return other
    
    def mergeCode(self, other, right):
        return other

class CCodeEscape(ASTNode):
    def __init__(self, posInfo, pre, post):
        self.pre=pre
        self.post=post
        super().__init__(posInfo.Combine(pre.pos, False).Combine(post.pos, True))
    
    def merge(self, other, right):
        return other.mergeEscape(self, not right)

    def mergeEscape(self, other, right):
        if(right):
            self.post=self.post.mergeEscape(other, True)
            self.pos=self.pos.Combine(self.post.pos, True)
            return self
        else:
            return other.mergeEscape(self, True)
    
    def mergeCode(self, other, right):
        if(right):
            self.post=self.post.mergeCode(other, True)
            self.pos=self.pos.Combine(self.post.pos, True)
        else:
            self.pre=self.pre.mergeCode(other, False)
            self.pos=self.pos.Combine(self.pre.pos, False)
        return self

class RuleSetReference(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class MatchFunRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class MatchFunCall(ASTNode):
    def __init__(self, posInfo, fun, streamargs, args):
        self.fun=fun
        self.streamargs=streamargs
        self.args=args
        super().__init__(posInfo)

class BufferMatch(ASTNode):
    def __init__(self, posInfo, buffer, pattern):
        self.buffer=buffer
        self.pattern=pattern
        super().__init__(posInfo)

class MatchPatternNothing(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class MatchPatternDone(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

class MatchPatternSize(ASTNode):
    def __init__(self, posInfo, size):
        self.size=size
        super().__init__(posInfo)

class MatchPatternEvents(ASTNode):
    def __init__(self, posInfo, pre, post):
        self.pre=pre
        self.post=post
        super().__init__(posInfo)


class MatchPatternEvent(ASTNode):
    def __init__(self, posInfo, ev, vars):
        self.event=ev
        self.vars=vars
        super().__init__(posInfo)

        
class MatchPatternShared(MatchPatternEvent):
    def __init__(self, posInfo, vars):
        super().__init__(posInfo, "SHARED", vars)

class CCodeField(CCodeEscape):
    def __init__(self, posInfo, receiver, field):
        self.receiver=receiver
        self.field=field
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))

class CCodeContinue(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))

class CCodeSwitchTo(CCodeEscape):
    def __init__(self, posInfo, ruleset):
        self.ruleset=ruleset
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))

class CCodeDrop(CCodeEscape):
    def __init__(self, posInfo, amount, source):
        self.amount=amount
        self.source=source
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))

class CCodeRemove(CCodeEscape):
    def __init__(self, posInfo, amount, source):
        self.amount=amount
        self.source=source
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))

class CCodeAdd(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))

class CCodeYield(CCodeEscape):
    def __init__(self, posInfo, ev, args):
        self.event=ev
        self.args=args
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
