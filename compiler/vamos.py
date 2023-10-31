
import json
from json import JSONEncoder

BUFFER_GROUP_TYPE = "buffer_group"
BUFFER_GROUP_INIT_FUN = "init_buffer_group"
BUFFER_GROUP_DESTROY_FUN = "destroy_buffer_group"

def posInfoFromParser(p):
    return CodeSpan(CodePos(p.linespan(0)[0],p.lexspan(0)[0]),CodePos(p.linespan(0)[1],p.lexspan(0)[1]))

def posInfoFromParserItem(p,i):
    return CodeSpan(CodePos(p.linespan(i)[0],p.lexspan(i)[0]),CodePos(p.linespan(i)[1],p.lexspan(i)[1]))

def normalizeCCode(code, indent):
    lines=code.split("\n")
    newlines=[]
    start=""
    for line in lines:
        if len(line.lstrip())>0:
            start=line[0:((len(line)-len(line.lstrip())))]
            break
    for line in lines:
        if line.startswith(start):
            newlines.append(line.replace(start, indent, 1))
        else:
            newlines.append(line)
    return "\n".join(newlines)

def normalizeGeneratedCCode(code, depth):
    indent=' '*depth*INDENT
    lines=code.split("\n")
    ret=""
    for line in [l.lstrip() for l in lines]:
        if line.startsWith("}"):
            depth-=1
            indent=' '*depth*INDENT
        ret+=indent+line+"\n"
        if line.startsWith("{"):
            depth+=1
            indent=' '*depth*INDENT
    return ret

vamos_varidcount=11

def createid(name):
    global vamos_varidcount
    vamos_varidcount+=1
    return name+"_"+str(vamos_varidcount)

def varid(name):
    return "__vamos_var_"+createid(name)

def labelid(name):
    return "__vamos_label"+createid(name)

class MyEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__   
    
INDENT=4

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

class LibCodePos:
    def __init__(self):
        pass
    def __str__(self):
        return "[LIB]"
    
class LibCodeSpan(CodeSpan):
    def __init__(self):
        super().__init__(LibCodePos(), LibCodePos())

class ASTNode:
    def __init__(self, posInfo):
        self.pos=posInfo

class VamosSpec:
    def __init__(self, components, arbiter, monitor):
        self.components=components
        self.arbiter=arbiter
        self.monitor=monitor
        self.imports=stdImports

    def check(self):
        self.initialize()
        self.initializeMembers()

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
        self.streamTypes[""]=StreamType("", LibCodeSpan(), [], None, [], [], [])
        self.streamProcessors["FORWARD"]=StreamProcessor("FORWARD", LibCodeSpan(), [], ParameterizedRef(StreamTypeRef("", LibCodeSpan()), [], LibCodeSpan()), ParameterizedRef(StreamTypeRef("", LibCodeSpan()), [], LibCodeSpan()), None, [], None)
        for component in self.components:
            component.Register(self)

    def getEventSource(self, name):
        if name not in self.eventSources:
            return None
        return self.eventSources[name]
    
    def getBufferGroup(self, name):
        if name not in self.bufferGroups:
            return None
        return self.bufferGroups[name]

    def getArbiterStreamType(self):
        return self.arbiter.streamtype.target
    
    def initializeMembers(self):
        done=False
        while not done:
            done=True
            for streamType in self.streamTypes.values():
                done=done and streamType.initializeMembers(self, [])
        done=False
        while not done:
            done=True
            for streamProc in self.streamProcessors.values():
                done=done and streamProc.initializeMembers(self, [])
        self.arbiter.initialize(self)
        self.monitor.initialize(self)
        for bgroup in self.bufferGroups.values():
            bgroup.initialize(self)


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
    h->cases.hole.n+=1;
{"}"}
"""
        for streamType in self.streamTypes.values():
            ret+=f"{streamType.toEnumDef()}\n"
            ret+=f"{streamType.toCPreDecls()}\n"
        for streamProc in self.streamProcessors.values():
            ret+=f"{streamProc.toCPreDecls(self)}"
        for streamType in self.streamTypes.values():
            ret+=f"{streamType.toCDefs()}\n"
        for streamProc in self.streamProcessors.values():
            ret+=f"{streamProc.toCCode(self)}"
        ret+=self.arbiter.toCCode(self)
        ret+=self.monitor.toCCode(self)
        return ret

class ParameterizedRef(ASTNode):
    def __init__(self, ref, args, posInfo):
        self.ref=ref
        self.args=args
        super().__init__(posInfo)

    def resolve(self, spec):
        self.ref.resolve(spec)
        self.target=self.ref.target

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
    def toCCode(self):
        return f"{self.type.toCCode()} {self.name}"
    def toCName(self):
        return self.name
    
class AggFieldDecl(ASTNode):
    def __init__(self, name, posInfo, aggexp):
        self.name=name
        self.aggexp=aggexp
        super().__init__(posInfo)

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
        index=len(self.streamType.sharedflds)
        self.fields={}
        for field in self.flds:
            if field.name in self.streamType.sharedflds:
                registerError(VamosError([field.pos], f"Definition of field named \"{field.name}\" for event \"{self.name}\" clashed with shared field of stream type \"{self.streamType.name}\""))
            elif field.name in self.fields:
                registerError(VamosError([field.pos], f"Multiple definitions of field named \"{field.name}\" for event \"{self.name}\" of stream type \"{self.streamType.name}\""))
            else:
                self.fields[field.name]=field
                field.index=index
                index=index+1

    def allFields(self):
        return self.streamType.sharedFields()+[x for x in self.fields.values()]

    def toEnumName(self):
        return f"__vamos_ekind_{self.streamType.name}_{self.name}"

    def toEnumDef(self):
        return f"{' '*INDENT}{self.toEnumName()} = {self.index}"

    def toStructName(self):
        return f"__vamos_event_{self.streamType.name}_{self.name}"

    def toFieldStructName(self):
        return f"__vamos_eventfields_{self.streamType.name}_{self.name}"

    def toCPreDecls(self):
        return f"""
struct _{self.toStructName()};
struct _{self.toFieldStructName()};
typedef struct _{self.toStructName()} {self.toStructName()};
typedef struct _{self.toFieldStructName()} {self.toFieldStructName()};
"""
    
    def toCDef(self):
        fields=";\n    ".join([fld.toCCode() for fld in sorted(self.fields.values(),key=lambda field: field.index)])
        if len(self.fields) > 0:
            fields+=";\n"
        return f"""
struct _{self.toStructName()} {"{"}
    {fields}
{"}"}
struct _{self.toFieldStructName()} {"{"}
    {self.streamType.toSharedFieldDef()}{self.toFieldStructName()} fields;
{"}"}
"""
    def toFieldAccess(self, receiver, fieldname):
        if fieldname in self.fields:
            return f"{receiver}.fields.{self.fields[fieldname].toCName()}"
        else:
            return self.streamtype.toSharedFieldAccess(receiver, fieldname)
        
    def generateMatchAssignments(self, spec, receiver, params, indnt):
        ret=""
        flds = sorted(self.allFields(),key=lambda field: field.index)
        for fld,param in zip(flds,params):
            ret+=indnt+fld.type.toCCode()+" "+param+" = "+self.toFieldAccess(receiver, fld.name)+";\n"
        return ret

class StreamType(ASTNode):
    def __init__(self, name, posInfo, streamfields, supertype, sharedfields, aggfields, events):
        self.name=name
        self.fields=streamfields
        self.supertype=supertype
        self.sharedflds=sharedfields
        self.evs=events
        self.aggfields=aggfields
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
        self.events={}
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
            if len(self.sharedflds)==len(self.supertype.target.sharedflds):
                if all([x.name==y.name and x.type.equals(y.type) for (x,y) in zip(self.sharedflds, self.supertype.target.sharedflds)]):
                    sharedmatch=True
            if not sharedmatch:
                registerError(VamosError([self.supertype.pos], f"Supertype must have same shared fields as subtype for Stream Type \"{self.name}\""))
                self.supertype = None
        for ev in self.evs:
            ev.flds = self.sharedflds + ev.flds
        index=1
        if self.supertype is not None:
            for ev in self.supertype.events:
                self.evs.append(ev.createCopyFor(self))
                index+=1
        for ev in self.evs:
            ev.initializeIndices(index)
            self.events[ev.name]=ev
            index+=1
        self.initializedMembers=True
        return True
    
    def toEnumName(self):
        return f"{self.name}_kinds"

    def toEnumDef(self):
        ret=f"enum {self.toEnumName()}\n{'{'}\n"
        ret+=",\n".join([ev.toEnumDef() for ev in sorted(self.events.values(),key=lambda ev: ev.index)])
        ret+="\n};"
        return ret
    
    def toStreamFieldStructName(self):
        return f"__vamos_stflds_{self.name}"
    def toAggFieldStructName(self):
        return f"__vamos_aggflds_{self.name}"
    def toEventStructName(self):
        return f"__vamos_strmev_{self.name}"

    def toCPreDecls(self):
        ret=f"typedef struct _{self.toStreamFieldStructName()} {self.toStreamFieldStructName()};\n"
        ret+=f"typedef struct _{self.toAggFieldStructName()} {self.toAggFieldStructName()};\n"
        ret+=f"typedef struct _{self.toEventStructName()} {self.toEventStructName()};\n"
        for event in self.events.values():
            ret+=event.toCPreDecls()
        return ret
    
    def toReferenceType(self):
        return f"{self.toStreamFieldStructName()}*"

    def toCDefs(self):
        indnt=' '*INDENT
        ret=""
        for event in self.events.values():
            ret+=event.toCDef()

        ret+=f"""struct _{self.toStreamFieldStructName()}
{"{"}"""
        if self.supertype is not None:
            ret+=f"\n{indnt}{self.supertype.toStreamFieldStructName()} __parent;"
        for field in self.fields:
            ret+=f"\n{indnt}{field.toCCode()};"
        ret+=f"""
{"};"}
"""
        ret+=f"""struct _{self.toAggFieldStructName()}
{"{"}"""
        if self.supertype is not None:
            ret+=f"\n{indnt}{self.supertype.toStreamFieldStructName()} __parent;"
        for field in self.aggfields:
            ret+=f"\n{indnt}{field.toCCode()};"
        ret+=f"""
{"};"}
"""
        ret+=f"""struct _{self.toEventStructName()}
{"{"}"""
        ret+=f"\n{indnt}shm_event head;"
        ret+=f"\n{indnt}union\n"
        ret+=indnt+"{"
        for event in self.events.values():
            ret+=f"\n{indnt*2}{event.toStructName()} {event.name};"
        ret+="\n"+indnt+"} cases;"
        ret+=f"""
{"};"}
"""
        return ret

    def sharedFields(self):
        if self.supertype is not None:
            return self.supertype.target.sharedFields()
        return self.sharedflds
    
    def toSharedFieldDef(self):
        if self.supertype is not None:
            return self.supertype.target.toSharedFieldDef()
        return ""
        

class StreamTypeRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

    def resolve(self, spec):
        if self.name not in spec.streamTypes:
            registerError(VamosError([self.pos], f"Unknown Stream Type \"{self.name}\""))
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
    def __init__(self, name, posInfo, params, fromStream, toStream, extends, rules, customHole):
        self.name=name
        self.params=params
        self.fromstream=fromStream
        self.tostream=toStream
        self.extends=extends
        self.rules=rules
        self.customHole=customHole
        self.initialized=False
        super().__init__(posInfo)
    def Register(self, spec):
        if self.name in spec.streamProcessors:
            registerError(VamosError([self.pos, spec.streamTypes[self.name].pos], f"Multiple definitions for Stream Processor \"{self.name}\""))
        else:
            spec.streamProcessors[self.name]=self

    def initializeMembers(self, spec, seen):
        if self in seen:
            registerError(VamosError([self.extends.pos], f"Inheritance cycle detected for Stream Processor \"{self.name}\""))
            self.extends=None
            return False
        if self.initialized is True:
            return True
        self.fromstream.resolve(spec)
        self.tostream.resolve(spec)
        if self.extends is not None:
            self.extends.resolve(spec)
            if not self.extends.target.initializeMembers(spec, seen+[self]):
                return False
        self.initialized=True
        for rule in self.rules:
            rule.initialize(self, spec)
        return True

    def toThreadFunName(self):
        return f"__vamos_perf_sp_{self.name}"
    def toFilterFunName(self):
        return f"__vamos_perf_filter_{self.name}"

    def toCPreDecls(self, spec):
        ret = f"""
int {self.toFilterFunName()} ();
int {self.toThreadFunName()} (__vamos_arbiter_buffer *buffer);
"""
        return ret

    def toCCode(self, spec):
        ret = ""
        vars=set()
        filtercode=""
        forwardcode=""
        prefix = f"__vamos_perf_var_{self.name}"
        caseno = 1
        for rule in self.rules:
            vars.update(rule.toCVars(spec, prefix))
            fcode,case,fwdcode = rule.toCCodes(spec, prefix, caseno)
            filtercode+=fcode
            if case == caseno:
                forwardcode+=fwdcode
        for tp,nm in vars:
            ret+=tp+" "+nm+";\n"
        ret+=f"""
int {self.toFilterFunName()} (shm_stream * s, shm_event * inevent) {"{"}{filtercode}
{' '*INDENT}{"{"}
{' '*INDENT}{"}"}
{"}"}
int {self.toThreadFunName()} (__vamos_arbiter_buffer *buffer) {"{"}
    shm_stream *stream = shm_arbiter_buffer_stream(buffer);   
    STREAM_{self.fromstream.ref.name}_in *inevent;
    STREAM_{self.fromstream.ref.name}_out *outevent;   

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

        {forwardcode}
        
        shm_stream_consume(stream, 1);
    {"}"}  
    atomic_fetch_add(&count_event_streams, -1);
    return 0;
{"}"}
"""
        return ret

class HoleAttribute(ASTNode):
    def __init__(self, name, posInfo, aggFunc, args):
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
    def resolve(self, streamtype, env):
        if self.name not in streamtype.events:
            registerError(VamosError([self.pos], f"Unknown Event \"{self.name}\" in Stream Type \"{streamtype.name}\""))
            self.target=Event(self.name, self.pos, [], None)
            self.target.initializedMembers=True
        else:
            self.target = streamtype.events[self.name]


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

    def initialize(self, processor, spec):
        self.parent=processor
        self.event.resolve(processor.fromstream.target, spec)

    def toCVars(self, spec, prefix):
        event=self.event.target
        fields = sorted(event.allFields(),key=lambda fld:fld.index)
        vars=set()
        for field in fields:
            vars.add((field.type.toCType(spec), f"{prefix}_{field.type.toCVarComponent(spec)}_{field.index}"))
        return vars

    def toCCodes(self, spec, prefix, caseno):
        forwardcode=""
        filtercode=f"\n{' '*INDENT}if(inevent->kind == {self.event.target.toEnumName()})\n{' '*INDENT+'{'}"
        self.action.toFilterCCode(spec, prefix, 2)
        filtercode+=(' '*INDENT)+"}\n"+(' '*INDENT)+"else"
        return filtercode, caseno, forwardcode
    


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

    def isDrop(self):
        return self.thencode.isDrop() and self.elsecode.isDrop()
    
    def toFilterCCode(self, spec, prefix, depth):
        tabin=' '*(INDENT*depth)
        if self.isDrop():
            return f"""
{tabin}return false;
"""
        else:
            ret=f"""
{tabin}if()
{tabin}{"{"}
{self.thencode.toFilterCCode(spec, prefix, depth+1)}
{tabin}{"}"}
{tabin}else
{tabin}{"{"}
{self.thencode.toFilterCCode(spec, prefix, depth+1)}
{tabin}{"}"}
"""

    def toCCode(self, spec, prefix, depth):
        if(self.thencode.isDrop()):
            return self.elsecode.toCCode(spec, prefix, depth)
        if(self.elsecode.isDrop()):
            return self.thencode.toCCode(spec, prefix, depth)
        indent=" "*(depth*INDENT)
        return f"""{indent}if({self.condition.toCCode(spec, prefix, depth+1)})
{indent}{"{"}
{self.thencode.toCCode(spec, prefix, depth+1)}
{indent}{"}"}
{indent}"else"
{indent}{"{"}
{self.elsecode.toCCode(spec, prefix, depth+1)}
{indent}{"}"}"""

class PerformanceDrop(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    
    def isDrop(self):
        return True
    def isRawForward(self, args):
        return False

    def toFilterCCode(self, spec, prefix, depth):
        return "return false;"
    def toCCode(self, spec, depth):
        indent=" "*(depth*INDENT)
        return f"""
"""

class PerformanceForward(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def isDrop(self):
        return False
    def isRawForward(self, args):
        return True
    def toFilterCCode(self, spec, prefix, depth):
        return "return true;"

class PerformanceForwardConstruct(ASTNode):
    def __init__(self, posInfo, event, args):
        self.event=event
        self.args=args
        super().__init__(posInfo)
    def isDrop(self):
        return False
    def isRawForward(self, args):
        return len(args)==len(self.args) and all([x==y for x,y in zip(args,self.args)])

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

    def resolve(self, spec):
        if self.name not in spec.streamProcessors:
            print(f"Unknown Stream Processor \"{self.name}\"")
            registerError(VamosError([self.pos], f"Unknown Stream Processor \"{self.name}\""))
            self.target=StreamProcessor(self.name, self.pos, None, None, None, None, [], None)
            self.target.initializedMembers=True
        else:
            self.target = spec.streamProcessors[self.name]


class EventSourceRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

class BufferGroupRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)
    def resolve(self, env):
        self.target = env.getBufferGroup(self.name)
        if self.target is None:
            registerError(VamosError([self.posInfo], f"Unknown Buffer Group \"{self.name}\""))
            self.target = BufferGroup(self.name, self.pos, "", RoundRobinOrder(self.pos), [])



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
    def initialize(self, spec):
        self.streamType.resolve(spec)
    def Register(self, spec):
        if self.name in spec.bufferGroups:
            registerError(VamosError([self.pos, spec.bufferGroups[self.name].pos], f"Multiple definitions for Buffer Group \"{self.name}\""))
        elif self.name in spec.eventSources:
            registerError(VamosError([self.pos, spec.eventSources[self.name].pos], f"Naming collision - there cannot both be an Event Source and a Buffer Group named \"{self.name}\""))
        else:
            spec.bufferGroups[self.name]=self
    
    def toCVariable(self):
        return "__vamos_bufgroup_"+self.name

    def readsize(self):
        return self.toCVariable()+".size"


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
    def resolve(self, env):
        self.target = env.getEventSource(self.name)
        if self.target is None:
            registerError(VamosError([self.pos], f"Unknown Event Source \"{self.name}\""))

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
    def apply(self, sourceargs, args, pos):
        if len(sourceargs) != len(self.sources):
            registerError(VamosError([pos], f"Invalid call to match function \"{self.name}\" - expected {len(self.sources)} source arguments, but found {len(sourceargs)}"))
        if len(args) != len(self.params):
            registerError(VamosError([pos], f"Invalid call to match function \"{self.name}\" - expected {len(self.params)} arguments, but found {len(args)}"))
        return [exp.substitute(zip(self.sources, sourceargs), zip(self.params, args)) for exp in self.exp]

class Arbiter(ASTNode):
    def __init__(self, posInfo, streamtype, rulesets):
        self.streamtype=streamtype
        self.rulesets=rulesets
        super().__init__(posInfo)
    
    def initialize(self, spec):
        self.streamtype.resolve(spec)
        for ruleset in self.rulesets:
            ruleset.initialize(Environment(spec))
    
    def toCCode(self, spec):
        ret="int arbiter()\n{\n"
        baseindent=' '*INDENT
        indnt=baseindent
        ret+=indnt+"int all_done=0;\n"
        ret+=indnt+"while(!all_done)\n"+indnt+"{\n"
        indnt+=baseindent
        if len(self.rulesets)>1:
            ret+=indnt+"switch(__vamos_current_arbiter_ruleset)\n"+indnt+"{\n"
            indnt+=baseindent
            for ruleset in self.rulesets:
                ret+=indnt+"case "+ruleset.toCEnumValue()+":\n"
                ret+=indnt+"{\n"
                ret+=ruleset.toCCode(4, Environment(spec))
                ret+=indnt+baseindent+"break;\n"
                ret+=indnt+"}\n"
            indnt=baseindent*2
            ret+=indnt+"}\n"
        else:
            ret+=self.rulesets[0].toCCode(2, Environment(spec))
        indnt=' '*INDENT
        ret+=indnt+"}\n"
        ret+=indnt+"shm_monitor_set_finished(monitor_buffer);\n"
        ret+=indnt+"return 0;\n"
        ret+="}\n"
        return ret

class RuleSet(ASTNode):
    def __init__(self, name, posInfo, rules):
        self.name=name
        self.rules=rules
        super().__init__(posInfo)
    def initialize(self, env):
        for rule in self.rules:
            rule.initialize(env)
    def toCCode(self, depth, env):
        ret=""
        for rule in self.rules:
            ret+=rule.toCCode(depth, env)
        return ret

class ArbiterRule(ASTNode):
    def __init__(self, posInfo, condition, code):
        self.condition=condition
        self.code=code
        super().__init__(posInfo)
    def initialize(self, env):
        self.condition.initialize(env)
        self.code.initialize(env)

    def toCCode(self, depth, env):
        return ""

class ArbiterAlwaysCondition(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def initialize(self, env):
        pass

class ArbiterMatchCondition(ASTNode):
    def __init__(self, posInfo, matchExps, whereCond):
        self.matchExps=matchExps
        self.whereCond=whereCond
        super().__init__(posInfo)
    def initialize(self, env):
        for matchExp in self.matchExps:
            matchExp.initialize(env)
        if self.whereCond is not None:
            self.whereCond.initialize(env)

class ArbiterChoice(ASTNode):
    def __init__(self, posInfo, direction, variables, group, filter):
        self.direction=direction
        self.variables=variables
        self.group=group
        self.filter=filter
        super().__init__(posInfo)
    def initialize(self, env):
        self.group.resolve(env)
        self.filter.initialize(env)
    def toCCode(self, depth, env):
        indnt=' '*INDENT*depth
        ret=""
        for var in self.variables:
            ret+=env.addEventSourceVar(depth, self.group, var)
        ret+=self.direction.toCCode(depth, self.group, self.filter, self.variables, env)
        return ret

class ArbiterChoiceRule(ASTNode):
    def __init__(self, posInfo, choice, rules):
        self.choice=choice
        self.rules=rules
        super().__init__(posInfo)
    def initialize(self, env):
        self.choice.initialize(env)
        for rule in self.rules:
            rule.initialize(env)
    def toCCode(self, depth, env):
        ret=""
        ret+=self.choice.toCCode(depth, env)
        return ret

class ChooseFirst(ASTNode):
    def __init__(self, posInfo, n):
        self.n=n
        super().__init__(posInfo)
    def toCCode(self, depth, group, filter, vars, env):
        if(self.n==0):
            return ""
        elif(self.n==1):
            ret=f"if({group.target.readsize()}>={len(vars)})\n{'{'}\n"
            cnt=0
            for var in vars:
                ret+=env.getEventSource(var).varid+" = "+group.target.getBufferFromStart(cnt)+";\n"
                cnt+=1
        else:
            anyleftvar = varid("combinations_left")
            ret = f"int {anyleftvar} = {group.target.readsize()}>={len(vars)};\n"
            cyclecountcond=""
            if self.n > 0:
                cyclecountvar = varid("cycle_count")
                ret+= f"uint64_t {cyclecountvar} = 0;\n"
                cyclecountcond=f" && {cyclecountvar} < {self.n}"
            ret+= f"while({anyleftvar}{cyclecountcond})\n"+"{\n"
        return ret


class ChooseLast(ASTNode):
    def __init__(self, posInfo, n):
        self.n=n
        super().__init__(posInfo)
    def toCCode(self, depth, group, filter, vars, env):
        return ""

class Monitor(ASTNode):
    def __init__(self, posInfo, bufsize, rules):
        self.bufsize=bufsize
        self.rules=rules
        super().__init__(posInfo)

    def initialize(self, spec):
        for rule in self.rules:
            rule.initialize(spec.arbiter.streamtype.target, spec)
        
    def toCCode(self, spec):
        baseindent=' '*INDENT
        indnt=baseindent
        ret="int monitor()\n{\n"
        ret+=indnt+spec.arbiter.streamtype.target.toEventStructName()+"* received_event;\n"
        ret+=indnt+"while(true)\n"
        ret+=indnt+"{\n"
        indnt+=baseindent
        ret+=indnt+"received_event = ("+spec.arbiter.streamtype.target.toEventStructName()+"*)fetch_arbiter_stream(__vamos_monitor_buffer);\n"
        ret+=indnt+"if (received_event == NULL)\n"
        ret+=indnt+"{\n"
        ret+=indnt+baseindent+"break;\n"
        ret+=indnt+"}\n"
        for rule in self.rules:
            ret+=rule.toCCode(spec, indnt, baseindent)
        indnt=baseindent
        ret+=indnt+"}\n"
        ret+="}\n"
        return ret

class MonitorRule(ASTNode):
    def __init__(self, posInfo, event, params, condition, code):
        self.event=event
        self.params=params
        self.condition=condition
        self.code=code
        super().__init__(posInfo)

    def initialize(self, streamType, spec):
        self.event.resolve(streamType, spec)
        if len(self.event.target.allFields()) != len(self.params):
            registerError(VamosError([self.posInfo], f"Expected {len(self.event.target.allFields())} pattern match parameters for event \"{self.event.target.name}\", but found {len(self.params)}"))
        env=Environment(spec)
        self.condition.initialize(env)
        self.code.initialize(env)
    
    def toCCode(self, spec, indnt, baseindent):
        ret=indnt+f"if(received_event->head.kind == {self.event.target.toEnumName()})\n"
        ret+=indnt+"{\n"
        ret+=self.event.target.generateMatchAssignments(spec, "received_event", self.params, indnt+baseindent)
        if self.condition is not None and self.condition.toCCode(spec).lstrip().rstrip()!="true":
            ret+=f"{indnt}{baseindent}if({self.condition.toCCode(spec)})\n"
            ret+=indnt+baseindent+"{\n"
            ret+=normalizeCCode(self.code.toCCode(spec), indnt+(baseindent*2))
            ret+="\n"+indnt+(baseindent*2)+"shm_monitor_buffer_consume(__vamos_monitor_buffer, 1);"
            ret+="\n"+indnt+(baseindent*2)+"continue;\n"
            ret+=indnt+baseindent+"}\n"
        else:
            ret+=normalizeCCode(self.code.toCCode(spec), indnt+baseindent)
            ret+="\n"+indnt+baseindent+"shm_monitor_buffer_consume(__vamos_monitor_buffer, 1);"
            ret+="\n"+indnt+baseindent+"continue;\n"
        ret+=indnt+"}\n"
        return ret

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
    def containsCCode(self):
        return True
    def initialize(self, env):
        pass
    def toCCode(self, spec):
        return self.text

class CCodeEmpty(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)

    def merge(self, other, right):
        return other
    
    def mergeEscape(self, other, right):
        return other
    
    def mergeCode(self, other, right):
        return other
    def containsCCode(self):
        return True
    def initialize(self, env):
        pass
    def toCCode(self, spec):
        return ""

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
    
    def initialize(self, env):
        self.pre.initialize(env)
        self.initializeEscape(env)
        self.post.initialize(env)

    def mergeCode(self, other, right):
        if(right):
            self.post=self.post.mergeCode(other, True)
            self.pos=self.pos.Combine(self.post.pos, True)
        else:
            self.pre=self.pre.mergeCode(other, False)
            self.pos=self.pos.Combine(self.pre.pos, False)
        return self
    def containsCCode(self):
        return True

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
    def initialize(self, env):
        self.buffer.resolve(env)

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
    def initializeEscape(self, env):
        self.receiver.resolve(env)

    def toCCode(self, spec):
        return self.receiver.target.toCFieldAccess(spec, self.field)

class CCodeContinue(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def toCCode(self, spec):
        return "goto __vamos_arbiter_continue;"
    def initializeEscape(self, env):
        pass

class CCodeSwitchTo(CCodeEscape):
    def __init__(self, posInfo, ruleset):
        self.ruleset=ruleset
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.ruleset.resolve(env)

class CCodeDrop(CCodeEscape):
    def __init__(self, posInfo, amount, source):
        self.amount=amount
        self.source=source
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.source.resolve(env)

class CCodeRemove(CCodeEscape):
    def __init__(self, posInfo, source, group):
        self.group=group
        self.source=source
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.source.resolve(env)
        self.group.resolve(env)

class CCodeAdd(CCodeEscape):
    def __init__(self, posInfo, source, group):
        self.group=group
        self.source=source
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.source.resolve(env)
        self.group.resolve(env)

class CCodeYield(CCodeEscape):
    def __init__(self, posInfo, ev, args):
        self.event=ev
        self.args=args
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.event.resolve(env.getArbiterStreamType(), env)

class ExprVar(CCodeEscape):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False

class ExprInt(CCodeEscape):
    def __init__(self, val, posInfo):
        self.value=int(val)
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False
        
class ExprTrue(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False

class ExprFalse(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False

class ExprBinOp(CCodeEscape):
    def __init__(self, posInfo, op, left, right):
        self.op=op
        self.left=left
        self.right=right
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return self.left.containsCCode() or self.right.containsCCode()

class ExprUnOp(CCodeEscape):
    def __init__(self, posInfo, op, rand):
        self.op=op
        self.rand=rand
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return self.rand.containsCCode()



class TypeNamed(ASTNode):
    def __init__(self, posInfo, name):
        self.name=name
        super().__init__(posInfo)
    def toCCode(self):
        return self.name
    def toCType(self, spec):
        return self.name
    def toCVarComponent(self, spec):
        return self.name+"_reg"
    def __str__(self):
        return self.toCCode()
        
class TypePointer(ASTNode):
    def __init__(self, posInfo, type):
        self.type=type
        super().__init__(posInfo)
    def toCCode(self):
        return self.name+'*'
    def toCType(self, spec):
        return self.name+'*'
    def toCVarComponent(self, spec):
        return self.name+'_ptr'
    def __str__(self):
        return self.toCCode()
        
class TypeArray(ASTNode):
    def __init__(self, posInfo, type):
        self.type=type
        super().__init__(posInfo)
    def toCCode(self):
        return self.name+"[]"
    def toCType(self, spec):
        return self.name+"[]"
    def toCVarComponent(self, spec):
        return self.name+"_arr"
    def __str__(self):
        return self.toCCode()

class EventSourceVar:
    def __init__(self, name, streamtype, varid):
        self.name=name
        self.streamtype=streamtype
        self.varid=varid


class Environment:
    def __init__(self, parent):
        self.parent=parent
        self.eventSourceVars={}

    def addEventSourceVar(self, depth, group, var):
        newvarid=varid(var)
        self.eventSourceVars[var]=EventSourceVar(var, group.target.streamType, newvarid)
        return f"{' '*INDENT*depth}{group.target.streamType.target.toReferenceType()} {newvarid};\n"
    
    def getBufferGroup(self, name):
        return self.parent.getBufferGroup(name)

    def getEventSource(self, name):
        if name in self.eventSourceVars:
            return self.eventSourceVars[name]
        return self.parent.getEventSource(name)
    
    def getArbiterStreamType(self):
        return self.parent.getArbiterStreamType()

