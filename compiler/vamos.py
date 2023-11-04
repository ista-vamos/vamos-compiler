
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
        if line.startswith("}"):
            depth-=1
            indent=' '*depth*INDENT
        ret+=indent+line+"\n"
        if line.startswith("{"):
            depth+=1
            indent=' '*depth*INDENT
    return ret

def insertInNormalizedCCode(code, keyword, insertion):
    lines=code.split("\n")
    ret=""
    for line in lines:
        if line.lstrip().startswith(keyword):
            indent=line[0:((len(line)-len(line.lstrip())))]
            ret+=normalizeCCode(insertion, indent)+"\n"
        else:
            ret+=line+"\n"
    return ret

def parenthesize(code):
    if (code.lstrip().startswith("(") and code.rstrip().endswith(")")) or not code.find(" ")>=0:
        return code
    return "("+code+")"

vamos_varidcount=11

def createid(name):
    global vamos_varidcount
    vamos_varidcount+=1
    return str(name)+"_"+str(vamos_varidcount)

def varid(name):
    return "__vamos_var_"+createid(name)

def labelid(name):
    return "__vamos_label_"+createid(name)

def funid(name):
    return "__vamos_fun_"+createid(name)

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
    print("/".join([str(pos) for pos in e.posns])+": "+e.msg)

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
    def __str__(self):
        return str(self.start)

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

class VamosID(ASTNode):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo)
    def toBufGroupRef(self):
        return BufferGroupRef(self.name, self.pos)
    def toStreamTypeRef(self):
        return StreamTypeRef(self.name, self.pos)
    def toStreamProcessorRef(self):
        return StreamProcessorRef(self.name, self.pos)
    def toEventRef(self):
        return EventReference(self.name, self.pos)
    def toEventSourceRef(self):
        return EventSourceRef(self.name, self.pos)
    def toStreamFieldRef(self):
        return StreamFieldRef(self.name, self.pos)
    def toFieldRef(self):
        return FieldRef(self.name, self.pos)
    def __str__(self):
        return self.name
    def toStr(self):
        return str(self)


class VamosSpec:
    def __init__(self, components, arbiter, monitor):
        self.components=components
        self.arbiter=arbiter
        self.monitor=monitor
        self.imports=stdImports

    def check(self):
        self.initialize()
        self.initializeMembers()
        for evsource in self.eventSources.values():
            evsource.check(self)

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
        #self.streamTypes[""]=StreamType("", LibCodeSpan(), [], None, [], [], [])
        #self.streamProcessors["FORWARD"]=StreamProcessor("FORWARD", LibCodeSpan(), [], ParameterizedRef(StreamTypeRef("", LibCodeSpan()), [], LibCodeSpan()), ParameterizedRef(StreamTypeRef("", LibCodeSpan()), [], LibCodeSpan()), None, [], None)
        for component in self.components:
            component.Register(self)

    def getEventSource(self, name):
        name=str(name)
        if name not in self.eventSources:
            return None
        return self.eventSources[name]
    
    def getBufferGroup(self, name):
        name=str(name)
        if name not in self.bufferGroups:
            return None
        return self.bufferGroups[name]

    def getArbiterStreamType(self):
        return self.arbiter.streamtype.target
    
    def getStreamType(self, name):
        name=str(name)
        if name not in self.streamTypes:
            return None
        return self.streamTypes[name]
    
    def getStreamProcessor(self, name):
        name=str(name)
        if name not in self.streamProcessors:
            return None
        return self.streamProcessors[name]

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
        for bgroup in self.bufferGroups.values():
            bgroup.initialize(self)
        self.arbiter.initialize(self)
        self.monitor.initialize(self)


    def toCCode(self):
        ret=""
        for mprt in self.imports:
            ret+=f"#include {mprt}\n"

        ret+=f"""
#include <threads.h>
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
thread_local int perf_case = 0;

struct _EVENT_hole
{"{"}
  uint64_t n;
{"}"};
typedef struct _EVENT_hole EVENT_hole;

struct _EVENT_hole_wrapper {"{"}
    vms_event head;
    union {"{"}
        EVENT_hole hole;
    {"}"}cases;
{"}"};

static void init_hole_hole(vms_event *hev) {"{"}
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    h->head.kind = vms_event_get_hole_kind();
    h->cases.hole.n = 0;
{"}"}

static void update_hole_hole(vms_event *hev, vms_event *ev) {"{"}
    (void)ev;
    struct _EVENT_hole_wrapper *h = (struct _EVENT_hole_wrapper *) hev;
    h->cases.hole.n+=1;
{"}"}
"""
        if self.cglobals is not None:
            ret+=normalizeCCode(self.cglobals.toCCode(self),"")
        for streamType in self.streamTypes.values():
            ret+=f"{streamType.toEnumDef()}\n"
            ret+=f"{streamType.toCPreDecls()}\n"
        for streamProc in self.streamProcessors.values():
            ret+=f"{streamProc.toCPreDecls(self)}"
        for evsource in self.eventSources.values():
            ret+=evsource.toCPreDecls(self)
        for bg in self.bufferGroups.values():
            ret+=f"{bg.toCPreDecls(self)}"
        for streamType in self.streamTypes.values():
            ret+=f"{streamType.toCDefs()}\n"
        for streamProc in self.streamProcessors.values():
            ret+=f"{streamProc.toCCode(self)}"
        for evsource in self.eventSources.values():
            ret+=evsource.toCCode(self)
        for bg in self.bufferGroups.values():
            ret+=f"{bg.toCCode(self)}"
        ret+=self.arbiter.toCCode(self)
        ret+=self.monitor.toCCode(self)

        ret+=self.toCMainMethod()

        #deduplicate empty lines, and remove them immediately after opening braces and immediately before closing braces
        lines=ret.split("\n")
        ret=""
        lastempty=False
        lastobrace=False
        lineno=0
        for line in lines:
            lineno+=1
            if line.isspace() or len(line.lstrip())==0:
                lastempty=True
                continue
            if lastempty==True:
                if lastobrace==False and line.lstrip().rstrip()!='}':
                    ret+="\n"
            lastempty=False
            ret+=line+"\n"
            lastobrace=line.lstrip().rstrip()=='{'
        return ret
    
    def toCMainMethod(self):
        ret="char namebuf[128];\n"
        ret+="int main(int argc, char **argv)\n{\n"
        if self.cstartup is not None:
            ret+="\n//startup code\n"
            ret+="@STARTUP@\n"

        for bg in self.bufferGroups.values():
            ret+="__vamos_init_buffer_group(&"+bg.toCVariable()+", &"+bg.orderfunname+");\n"

        for evsource in self.eventSources.values():
            ret+=evsource.toCInitCode(self, "namebuf")
                    
        ret+="__vamos_monitor_buffer = vms_monitor_buffer_create(sizeof("+self.arbiter.streamtype.target.toEventStructName()+"), "+str(self.monitor.bufsize)+");"
        ret+="\nthrd_create(&__vamos_thrd_arbiter, arbiter, 0);"

        ret+="\nint returncode = monitor();\n"

        if self.ccleanup is not None:
            ret+="\n//cleanup code\n"
            ret+="@CLEANUP@\n"
        ret+="return returncode;\n"
        ret+="}\n"

        ret=normalizeGeneratedCCode(ret, 0)
        if self.cstartup is not None:
            ret=insertInNormalizedCCode(ret, "@STARTUP@", self.cstartup.toCCode(self))
        if self.ccleanup is not None:
            ret=insertInNormalizedCCode(ret, "@CLEANUP@", self.ccleanup.toCCode(self))
        return normalizeGeneratedCCode(ret, 0)

class ParameterizedRef(ASTNode):
    def __init__(self, ref, args, posInfo):
        self.name=ref.name
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
    def toCCode(self, spec):
        env = Environment(spec)
        return self.code.toCCode(spec)

class CStartup(CBlock):
    def __init__(self, posInfo, code):
        self.code=code
        super().__init__(posInfo)
    def Register(self, spec):
        spec.cstartup=self
    def toCCode(self, spec):
        env = Environment(spec)
        return self.code.toCCode(spec)

class CCleanup(CBlock):
    def __init__(self, posInfo, code):
        self.code=code
        super().__init__(posInfo)
    def Register(self, spec):
        spec.ccleanup=self
    def toCCode(self, spec):
        env = Environment(spec)
        return self.code.toCCode(spec)

class CLoopdebug(CBlock):
    def __init__(self, posInfo, code):
        self.code=code
        super().__init__(posInfo)
    def Register(self, spec):
        spec.cloopdebug=self
    def toCCode(self, spec):
        env = Environment(spec)
        return self.code.toCCode(spec)

class FieldDecl(ASTNode):
    def __init__(self, name, type, posInfo):
        self.name=name
        self.type=type
        super().__init__(posInfo)
    def __str__(self):
        return f"{self.name} : {self.type}"
    def toCCode(self):
        return self.toPrefixedCCode("")
    def toCName(self):
        return self.name
    def toPrefixedCCode(self, prefix):
        return f"{self.type.toCCode()} {prefix}{self.name}"
    def toSubstitutedCCode(self, newname):
        return f"{self.type.toCCode()} {newname}"

    
class AggFieldDecl(ASTNode):
    def __init__(self, name, posInfo, type, aggexp):
        self.name=name
        self.type=type
        self.aggexp=aggexp
        super().__init__(posInfo)
    def toInitCCode(self, target, streamtype, env):
        return target+"->"+self.name+" = "+self.aggexp.toInitCCode(self.type, streamtype, env)+";\n"

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
        self.streamtype=streamtype

    def createCopyFor(self, streamtype):
        ev = Event(self.name, self.pos, self.flds, self.creates)
        ev.setStreamType(streamtype)
        ev.initializeIndices(self.index)
        return ev
    
    def initializeIndices(self, idx):
        self.index=idx
        index=len(self.streamtype.sharedflds)
        self.fields={}
        for field in self.flds:
            if field.name in self.streamtype.sharedflds:
                registerError(VamosError([field.pos], f"Definition of field named \"{field.name}\" for event \"{self.name}\" clashed with shared field of stream type \"{self.streamtype.name}\""))
            elif field.name in self.fields:
                registerError(VamosError([field.pos], f"Multiple definitions of field named \"{field.name}\" for event \"{self.name}\" of stream type \"{self.streamtype.name}\""))
            else:
                self.fields[field.name]=field
                field.index=index
                index=index+1

    def allFields(self):
        return [x for x in self.streamtype.sharedFields().values()]+[x for x in self.fields.values()]

    def toEnumName(self):
        return f"__vamos_ekind_{self.streamtype.name}_{self.name}"

    def toEnumDef(self):
        return f"{' '*INDENT}{self.toEnumName()} = {self.index}"

    def toStructName(self):
        return f"__vamos_event_{self.streamtype.name}_{self.name}"

    def toFieldStructName(self):
        return f"__vamos_eventfields_{self.streamtype.name}_{self.name}"

    def toCPreDecls(self):
        return f"""
struct _{self.toStructName()};
struct _{self.toFieldStructName()};
typedef struct _{self.toStructName()} {self.toStructName()};
"""
#typedef struct _{self.toFieldStructName()} {self.toFieldStructName()};
    
    def toCDef(self):
        fields=";\n    ".join([fld.toCCode() for fld in sorted(self.fields.values(),key=lambda field: field.index)])
        if len(self.fields) > 0:
            fields+=";\n"
        return f"""
struct _{self.toStructName()}
{"{"}
    {fields}
{"};"}
"""
# struct _{self.toFieldStructName()}
# {"{"}
#     {self.streamtype.toSharedFieldDef()}{self.toFieldStructName()} fields;
# {"};"}

    def getField(self, fieldname):
        if fieldname in self.fields:
            return self.fields[fieldname]
        for fld in self.streamtype.sharedflds:
            if fld.name == fieldname:
                return fld
        return None

    def toFieldAccess(self, receiver, fieldname):
        if fieldname in self.fields:
            return f"{receiver}->cases.{self.name}.{self.fields[fieldname].toCName()}"
        else:
            return self.streamtype.toSharedFieldAccess(receiver, fieldname)
        
    def generateMatchAssignments(self, spec, receiver, params, indnt):
        ret=""
        flds = sorted(self.allFields(),key=lambda field: field.index)
        for fld,param in zip(flds,params):
            ret+=indnt+fld.type.toCCode()+" "+str(param)+" = "+self.toFieldAccess(receiver, fld.name)+";\n"
        return ret
    
    def toArbiterYieldCCode(self, spec):
        ret=f"inline void __arbiter_yield_{self.name}({', '.join([fld.toPrefixedCCode('__arg_') for fld in sorted(self.allFields(),key=lambda field: field.index)])})\n"
        ret+="{\n"
        ret+=self.streamtype.toEventStructName()+" * arbiter_outevent = ("+self.streamtype.toEventStructName()+" *)vms_monitor_buffer_write_ptr(__vamos_monitor_buffer);\n"
        ret+="arbiter_outevent->head.kind = "+str(self.index)+";\n"
        ret+="arbiter_outevent->head.id = arbiter_counter++;\n"
        for field in self.allFields():
              ret+=self.toFieldAccess("arbiter_outevent", field.name)+" = __arg_"+field.name+";\n"
        ret+="vms_monitor_buffer_write_finish(__vamos_monitor_buffer);\n"
        ret+="}\n"
        return normalizeGeneratedCCode(ret, 0)
    
    def toEventRegistrationCode(self, env, strmvar):
        ret="if (vms_stream_register_event((vms_stream *)"+strmvar+", \""+self.name+"\", "+self.toEnumName()+") < 0)\n{\n"
        ret+='fprintf(stderr, "Failed registering event \\"'+self.name+'\\" for stream type '+self.streamtype.name+'\\n");\n'
        ret+='fprintf(stderr, "Available events:\\n");\n'
        ret+="vms_stream_dump_events((vms_stream *)"+strmvar+");\n"
        ret+="abort();\n"
        ret+="}\n"
        return ret

class StreamType(ASTNode):
    def __init__(self, name, posInfo, streamfields, supertype, sharedfields, aggfields, events):
        self.name=name
        self.flds=streamfields
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
        self.fields={}
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
        # for ev in self.evs:
        #     ev.flds = self.sharedflds + ev.flds
        index=0
        for fld in self.sharedflds:
            fld.index=index
            index+=1
        index=1
        if self.supertype is not None:
            for ev in self.supertype.events:
                self.evs.append(ev.createCopyFor(self))
                index+=1
        for ev in self.evs:
            ev.initializeIndices(index)
            self.events[ev.name]=ev
            index+=1
        for fld in self.flds:
            self.fields[fld.name]=fld
        self.initializedMembers=True
        return True
    
    def generateSharedMatchAssignments(self, spec, receiver, params):
        ret=""
        flds = sorted(self.sharedflds,key=lambda field: field.index)
        for fld,param in zip(flds,params):
            ret+=fld.type.toCCode()+" "+str(param)+" = "+self.toSharedFieldAccess(receiver, fld.name)+";\n"
        return ret
        
    def toSharedFieldAccess(self, receiver, fieldname):
        return receiver+"->shared."+fieldname

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
        else:
            ret+=f"\n{indnt}__vamos_streaminfo __info;"
        for field in self.fields.values():
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
        ret+=f"\n{indnt}vms_event head;"
        ret+=f"\n{indnt}struct"
        ret+=f"\n{indnt}"+"{"
        for fld in self.sharedFields().values():
            ret+="\n"+(indnt*2)+fld.toCCode()+";"
        ret+=f"\n{indnt}"+"} shared;"
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
        return dict([[fld.name,fld] for fld in self.sharedflds])
    
    # def toSharedFieldDef(self):
    #     if self.supertype is not None:
    #         return self.supertype.target.toSharedFieldDef()
    #     return ""
    
    def getStreamField(self, fieldname):
        if fieldname in self.fields:
            return self.fields[fieldname]
        if self.supertype is not None:
            return self.supertype.target.getStreamField(fieldname)
        return None
    
    def toCFieldAccess(self, field, varid):
        if field.name in self.fields:
            return f"((({self.toStreamFieldStructName()}*){varid})->{field.target.toCName()})"
        elif self.supertype is not None:
            self.supertype.toCFieldAccess(field, varid)
        else:
            registerError(VamosError([self.pos], f"Unknown stream field \"{field.name}\" for stream type \"{self.name}\""))

    def toCInitCode(self, receiver, args, env):
        offset = 0
        ret = ""
        fieldcount=len(self.fields.values())
        accessor="->"
        if(receiver.find("->")>=0):
            accessor="."
        if(fieldcount!=0):
            subargs=args[:-fieldcount]
        else:
            subargs=args
        if self.supertype is not None:
             ret+=self.supertype.toCInitCode(self, receiver+accessor+"__parent", subargs, env)
        for fld,arg in zip(self.fields.values(), args[-fieldcount:]):
            ret+=receiver+accessor+fld.name+" = "+arg+";\n"
        aggfieldstruct="(("+self.toAggFieldStructName()+"*)"+receiver+accessor
        curtype = self
        while curtype.supertype is not None:
            aggfieldstruct+="__parent."
            curtype=curtype.supertype.target
        aggfieldstruct+="__info.aggfields)"
        for fld in self.aggfields:
            ret+=fld.toCInitCode(aggfieldstruct, self, env)
        return ret
    
    def toEventRegistrationCode(self, env, strmvar):
        ret=""
        for ev in self.events.values():
            ret+=ev.toEventRegistrationCode(env, strmvar)
        return ret

class StreamTypeRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

    def resolve(self, env):
        self.target=env.getStreamType(self.name)
        if self.target is None:
            registerError(VamosError([self.pos], f"Unknown Stream Type \"{self.name}\""))
            self.target=StreamType(self.name, self.pos, [], None, None, None)
            self.target.initializedMembers=True

class CustomHole(ASTNode):
    def __init__(self, name, posInfo, parts):
        self.name=name
        self.parts=parts
        super().__init__(posInfo)
    def check(self, streamproc, env):
        if self.name in streamproc.tostream.target.events:
            self.event=streamproc.tostream.target.events[self.name]
            for fld in self.event.allFields():
                found=False
                for part in self.parts:
                    if part.name == fld.name:
                        found=True
                        part.type=fld.type
                        break
                if not found:
                    registerError(VamosError([self.pos], f'Hole specification is missing attribute for field "{fld.name}"'))
            for part in self.parts:
                found=False
                for fld in self.event.allFields():
                    if part.name==fld.name:
                        found=True
                        break
                if not found:
                    registerError(VamosError([self.pos], f'Hole specification contains attribute for unknown field "{part.name}"'))
                part.check(streamproc, env)
        else:
            registerError(VamosError([self.pos], f"Stream Type \"{streamproc.tostream.target.name}\" does not contain an event named \"{self.name}\""))
    def toCPreDecls(self, streamproc, env):
        ret=""
        ret+="void __vamos_inithole_"+streamproc.name+"(vms_event * holeev);\n"
        ret+="void __vamos_updatehole_"+streamproc.name+"(vms_event * holeev, vms_event * newev);\n"
        return ret

    def toCCode(self, streamproc, env):
        ret=""
        ret+="void __vamos_inithole_"+streamproc.name+"(vms_event * holeev)\n{\n"
        ret+=streamproc.tostream.target.toEventStructName()+" * myholeev = ("+streamproc.tostream.target.toEventStructName()+" *)holeev;\n"
        for part in self.parts:
            ret+=part.toInitCCode(self.event, "myholeev")
        ret+="}\n"
        ret+="void __vamos_updatehole_"+streamproc.name+"(vms_event * holeev, vms_event * newev)\n{\n"
        ret+=streamproc.tostream.target.toEventStructName()+" * myholeev = ("+streamproc.tostream.target.toEventStructName()+" *)holeev;\n"
        ret+=streamproc.fromstream.target.toEventStructName()+" * mynewev = ("+streamproc.fromstream.target.toEventStructName()+" *)newev;\n"
        for event in streamproc.fromstream.target.events.values():
            ret+="if(mynewev->head.kind == "+event.toEnumName()+")\n{\n"
            for part in self.parts:
                ret+=part.toCCode("myholeev", "mynewev", self.event, event)
            ret+="}\nelse "
        ret+="\n{\n"
        ret+='printf("Unknown event kind received!\\n");\n'
        ret+="abort();\n"
        ret+="}\n"
        ret+="}\n"
        return ret
    
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
        if self.extends is not None and self.extends.name != "FORWARD":
            self.extends.resolve(spec)
            if not self.extends.target.initializeMembers(spec, seen+[self]):
                return False
        self.initialized=True
        for rule in self.rules:
            rule.initialize(self, Environment(spec))
        self.initholefunname="__vamos_inithole_FORWARD"
        self.updateholefunname="__vamos_updatehole_FORWARD"
        if self.customHole is not None:
            self.customHole.check(self, Environment(spec))
            self.initholefunname="__vamos_inithole_"+self.name
            self.updateholefunname="__vamos_updatehole_"+self.name
        return True

    def toThreadFunName(self):
        return f"__vamos_perf_sp_{self.name}"
    def toFilterFunName(self):
        return f"__vamos_perf_filter_{self.name}"
    def toInitFunName(self):
        return f"__vamos_perf_createsp_{self.name}"

    def toCPreDecls(self, spec):
        ret = f"void {self.toInitFunName()}({', '.join([self.tostream.target.toStreamFieldStructName()+' * nstream']+[fld.toCCode() for fld in self.params])});\n"
        ret+=f"int {self.toFilterFunName()}();\n"
        ret+=f"int {self.toThreadFunName()}(void * buffer);\n"
        if self.customHole is not None:
            ret+=self.customHole.toCPreDecls(self, Environment(spec))
        return ret

    def toCCode(self, spec):
        ret = ""
        filtercode=""
        forwardcode=""
        caseno = 1
        env=Environment(spec)
        for rule in self.rules:
            caseno,fcode,fwdcode,createscode = rule.toCCodes(env, self.fromstream, caseno+1)
            filtercode+=fcode
            forwardcode+=fwdcode
            ret+=createscode
        if self.customHole:
            ret+=self.customHole.toCCode(self, env)
        ret+=f"void {self.toInitFunName()}({', '.join([self.tostream.target.toStreamFieldStructName()+' * nstream']+[fld.toCCode() for fld in self.params])})\n"
        ret+="{\n"
        ret+=self.tostream.target.toCInitCode("nstream", [arg.toCCode(env) for arg in self.tostream.args], env)
        ret+="}\n"
        ret+="int "+self.toFilterFunName()+"(vms_stream * s, vms_event * ev)\n{\n"
        ret+=self.fromstream.target.toEventStructName()+" * __vamos_inevent = ("+self.fromstream.target.toEventStructName()+"*)ev;\n"
        ret+=filtercode
        ret+="\n{\n"
        ret+="perf_case = 1;\n"
        ret+="return true;\n"
        ret+="}\n"
        ret+="}\n"
        ret+="int "+self.toThreadFunName()+"(void * ___vamos_source)\n{\n"
        ret+=self.tostream.target.toStreamFieldStructName()+" * __vamos_source = ("+self.tostream.target.toStreamFieldStructName()+" *)___vamos_source;\n"
        ret+="vms_stream *stream = (vms_stream *)__vamos_source;\n"
        ret+="vms_arbiter_buffer *buffer = __vamos_source->__info.buffer;\n"
        ret+=self.fromstream.target.toEventStructName()+" *__vamos_inevent;\n"
        ret+=self.tostream.target.toEventStructName()+" *__vamos_outevent;\n"
        ret+="// wait for active buffer\n"
        ret+="while ((!vms_arbiter_buffer_active(buffer)))\n{\n"
        ret+="sleep_ns(10);\n"
        ret+="}\n"
        ret+="while(true)\n{\n"
        ret+="__vamos_inevent = stream_filter_fetch(stream, buffer, &"+self.toFilterFunName()+");\n"
        ret+="if (__vamos_inevent == NULL)\n{\n"
        ret+="// no more events\n"
        ret+="break;\n"
        ret+="}\n"
        ret+="__vamos_outevent = vms_arbiter_buffer_write_ptr(buffer);\n"
        ret+="switch(perf_case)\n"
        ret+="{\n"
        ret+="case 1:\n"
        ret+="{\n"
        ret+="memcpy(__vamos_outevent, __vamos_inevent, sizeof("+self.fromstream.target.toEventStructName()+"));\n"
        ret+="vms_arbiter_buffer_write_finish(buffer);\n"
        ret+="break;\n"
        ret+="}\n"
        ret+=forwardcode
        ret+="}\n"
        ret+="vms_stream_consume(stream, 1);\n"
        ret+="}\n"
        ret+="atomic_fetch_add(&count_event_streams, -1);\n"
        ret+="return 0;\n"
        ret+="}\n"
        return normalizeGeneratedCCode(ret, 0)

class HoleAttribute(ASTNode):
    def __init__(self, name, posInfo, aggFunc, args):
        self.name=name
        self.aggfun=aggFunc
        self.args=args
        super().__init__(posInfo)
    def check(self, streamproc, env):
        if self.args == "*":
            if not self.aggfun.name=="COUNT":
                registerError(VamosError([self.pos], "Invalid aggregation function for arbitrary events: "+self.aggfun.name))
        else:
            for arg in self.args:
                arg.check(self.aggfun, streamproc, env)

    def toCCode(self, target, receiver, holeevent, event):
        ret=""
        if str(self.args) == "*":
            ret+=self.aggfun.toCCode(holeevent.toFieldAccess(target, self.name), None)
        else:
            for arg in self.args:
                ret+=arg.toCCode(self.aggfun, receiver, holeevent.toFieldAccess(target, self.name), event)
        return ret
    
    def toInitCCode(self, holeevent, target):
        ret=""
        ret+=self.aggfun.toInitCCode(holeevent.toFieldAccess(target, self.name), self.type)
        return ret

class AggFunction(ASTNode):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo)
    def toCCode(self, target, newval):
        if self.name=="MAX" and newval is not None:
            return target+" = __vamos_max("+target+", "+newval+");\n"
        elif self.name=="MIN" and newval is not None:
            return target+" = __vamos_max("+target+", "+newval+");\n"
        elif self.name=="COUNT":
            return target+" = "+target+" + 1;\n"
        return ""
    def toInitCCode(self, target, type):
        ret=""
        type=str(type)
        if self.name=="MAX":
            ret+=target+f" = (({type})-1<({type})0)?sizeof({type})==sizeof(long long)?LLONG_MIN:sizeof({type})==sizeof(long)?LONG_MIN:sizeof({type})==sizeof(int)?INT_MIN:sizeof({type})==sizeof(short)?SHRT_MIN:sizeof({type})==sizeof(signed char)?SCHAR_MIN:0:0;\n"
        if self.name=="MIN":
            ret+=target+f" = (({type})-1<({type})0)?sizeof({type})==sizeof(long long)?LLONG_MAX:sizeof({type})==sizeof(long)?LONG_MAX:sizeof({type})==sizeof(int)?INT_MAX:sizeof({type})==sizeof(short)?SHRT_MAX:sizeof({type})==sizeof(signed char)?SCHAR_MAX:0:"
            ret+=f"sizeof({type})==sizeof(unsigned long long)?ULLONG_MAX:sizeof({type})==sizeof(unsigned long)?ULONG_MAX:sizeof({type})==sizeof(unsigned int)?UINT_MAX:sizeof({type})==sizeof(unsigned short)?USHRT_MAX:sizeof({type})==sizeof(unsigned char)?UCHAR_MAX:0;\n"
        if self.name=="COUNT":
            ret+=target+" = 0;\n"
        return ret

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

class AggEventAccess(ASTNode):
    def __init__(self, posInfo, event):
        self.event=event
        super().__init__(posInfo)
    def check(self, aggfunc, streamproc, env):
        self.event.resolve(streamproc.fromstream.target, env)
        if aggfunc.name not in ["COUNT"]:
            registerError(VamosError([self.pos], "Invalid aggregation function for event reference: "+aggfunc.name))
    def toCCode(self, aggfunc, receiver, target, event):
        ret=""
        if event==self.event.target:
            ret += aggfunc.toCCode(target, None)
        return ret

class AggFieldAccess(ASTNode):
    def __init__(self, fieldname, posInfo, eventname):
        self.field=fieldname.toFieldRef()
        self.event=eventname.toEventRef()
        super().__init__( posInfo)
    def check(self, aggfunc, streamproc, env):
        self.event.resolve(streamproc.fromstream.target, env)
        self.field.resolve(self.event.target)
    def toCCode(self, aggfunc, receiver, target, event):
        ret=""
        if event==self.event.target:
            ret += aggfunc.toCCode(target, self.event.target.toFieldAccess(receiver, self.field.name))
        return ret


class StreamFieldRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)
    def resolve(self, streamtype):
        self.streamtype=streamtype
        self.target=self.streamtype.target.getStreamField(self.name)
        if self.target is None:
            registerError(VamosError([self.pos], f"Unknown shared field \"{self.name}\" in stream type \"{self.streamtype.target.name}\""))

class ProcessorRule(ASTNode):
    def __init__(self, posInfo, eventRef, eventParams, createSpec, action):
        self.event=eventRef
        self.params=eventParams
        self.createSpec=createSpec
        self.action=action
        super().__init__(posInfo)

    def initialize(self, processor, env):
        self.parent=processor
        self.event.resolve(processor.fromstream.target, env)
        self.createSpec.check(env)

    def toCCodes(self, env, streamtype, caseno):
        createsdata=None
        createscode=""
        if self.createSpec is not None:
            env.createsEvent=self.event
            createscode=self.createSpec.toCCode(env, self.params)
            createsdata=(self.params,self.createSpec.funname)
        filtercode=f"if(__vamos_inevent->head.kind == {self.event.target.toEnumName()})\n{'{'}\n"
        matchassigns=self.event.target.generateMatchAssignments(env, "__vamos_inevent", self.params, "")
        filtercode+=matchassigns
        fltrno, fltrtxt=self.action.toFilterCCode(env, streamtype, caseno)
        fwdno, forwardcode=self.action.toFwdCCode(env, streamtype, matchassigns, createsdata, caseno)
        filtercode+=fltrtxt
        filtercode+="}\nelse "
        return (fltrno, filtercode, forwardcode, createscode)
    


class CreatesSpec(ASTNode):
    def __init__(self, posInfo, limit, streamtype, streaminit, conkind, includedin):
        self.limit=limit
        self.inputtype=streamtype
        self.streaminit=streaminit
        self.conkind=conkind
        self.includein=includedin
        super().__init__(posInfo)
    def check(self, env):
        self.inputtype.resolve(env)
        self.streaminit.check(self.inputtype, env)
        for incl in self.includein:
            incl.resolve(env)
    def toCCode(self, env, params):
        env=Environment(env)
        ret=""
        if self.limit >= 0:
            self.limitvar = varid("createslimit")
            ret+="static uint64_t "+self.limitvar+" = 0;"
        self.funname = funid("createsspec")
        ret+="void "+self.funname+"("+", ".join(["vms_stream * stream"]+[fld.toSubstitutedCCode(param) for fld,param in zip(env.getCreatesEvent().target.allFields(),params)])+")\n{\n"
        if(self.limit >= 0):
            ret+="if("+self.limitvar+" >= "+str(self.limit)+")\n{\n"
            ret+="return;\n"
            ret+="}\n"
            ret+="else\n"
            ret+="{\n"
            ret+=self.limitvar+"++;\n"
            ret+="}\n"
        strmtype = self.streaminit.streamtype
        ret+=strmtype.target.toStreamFieldStructName()+" * nstream = ("+strmtype.target.toStreamFieldStructName()+"*)malloc(sizeof("+strmtype.target.toStreamFieldStructName()+")+sizeof("+strmtype.target.toAggFieldStructName()+")+sizeof(intptr_t));\n"
        ret+="if(nstream == 0)\n{\n"
        ret+='printf("Could not allocate data for newly created stream!\\n");\n'
        ret+="abort();\n"
        ret+="}\n"

        ret+=self.streaminit.toHoleHandlingDef(env)
        ret+="nstream->__info.stream = vms_stream_create_substream(stream, NULL, NULL, NULL, NULL, "+self.streaminit.toHoleHandlingRef()+");\n"
        ret+="if (!nstream->__info.stream)\n{\n"
        ret+='fprintf(stderr, \"Failed creating substream for \\\"'+env.getCreatesEvent().name+'\\\"\\n\");\n'
        ret+="abort();\n"
        ret+="}\n"

        ret+=self.conkind.toCCode(env, "nstream", strmtype.target.toEventStructName())
        #ret+=self.inputtype.target.toEventRegistrationCode(env, "nstream")
        ret+=self.streaminit.toCCode(env, "nstream")

        for incl in self.includein:
            ret+=incl.target.generateAddCode("nstream")
        ret+="vms_arbiter_buffer_set_active(nstream->__info.buffer, true);\n"
        ret+=f"thrd_create(&(((__vamos_streaminfo *)nstream)->thread), {self.streaminit.toThreadFunName()}, (vms_stream *)nstream);\n"

        ret+="}\n"
        return normalizeGeneratedCCode(ret, 0)

class DirectStreamInit(ASTNode):
    def __init__(self, posInfo, streamtype, args):
        self.args=args
        super().__init__(posInfo)
    def check(self, streamtype, env):
        self.streamtype=streamtype
        self.holehandlingvar = varid("holehandlingdirect_"+self.streamtype.name)
    def toCCode(self, env, streamvar):
        ret=self.streamtype.target.toCInitCode(streamvar, [arg.toCCode(env) for arg in self.args], env)
        return normalizeGeneratedCCode(ret, 1)
    def toThreadFunName(self):
        return ""
    def toHoleHandlingDef(self, env):
        ret = "vms_stream_hole_handling "+self.holehandlingvar+" =\n"
        ret+="{\n"
        ret+=".hole_event_size = sizeof("+self.streamtype.target.toEventStructName()+"),\n"
        ret+=".init = &__vamos_inithole_FORWARD,\n"
        ret+=".update = &__vamos_updatehole_FORWARD\n"
        ret+="};\n"
        return ret
    def toHoleHandlingRef(self):
        return "&"+self.holehandlingvar

class StreamProcessorInit(ASTNode):
    def __init__(self, posInfo, processor, args):
        self.processor=processor
        self.args=args
        super().__init__(posInfo)
    def check(self, streamtype, env):
        self.holehandlingvar = varid("holehandling_"+self.processor.name)
        self.processor.resolve(env)
        self.streamtype=self.processor.target.tostream
    def toCCode(self, env, streamvar):
        ret=self.processor.target.toInitFunName()+"("+", ".join([streamvar]+[arg.toCCode(env) for arg in self.args])+");"
        return normalizeGeneratedCCode(ret, 1)
    def toThreadFunName(self):
        return self.processor.target.toThreadFunName()
    def toHoleHandlingDef(self, env):
        ret = "vms_stream_hole_handling "+self.holehandlingvar+" =\n"
        ret+="{\n"
        ret+=".hole_event_size = sizeof("+self.streamtype.target.toEventStructName()+"),\n"
        ret+=".init = &"+self.processor.target.initholefunname+",\n"
        ret+=".update = &"+self.processor.target.updateholefunname+"\n"
        ret+="};\n"
        return ret
    def toHoleHandlingRef(self):
        return "&"+self.holehandlingvar

class PerformanceIf(ASTNode):
    def __init__(self, posInfo, condition, thencode, elsecode):
        self.condition=condition
        self.thencode=thencode
        self.elsecode=elsecode
        super().__init__(posInfo)

    def isDrop(self):
        return self.thencode.isDrop() and self.elsecode.isDrop()
    
    def toFilterCCode(self, env, streamtype, caseno):
        if self.isDrop():
            return (caseno, "return false;\n")
        else:
            ret="if("+self.condition.toCCode(env)+")\n"
            ret+="{\n"
            tcno, tctxt = self.thencode.toFilterCCode(env, streamtype, caseno)
            ret+=tctxt
            ret+="}\n"
            ret+="else\n"
            ret+="{\n"
            ecno, ectxt = self.elsecode.toFilterCCode(env, streamtype, tcno+1)
            ret+=ectxt
            ret+="}\n"
            return (ecno, ret)

    def toFwdCCode(self, env, streamtype, matchassigns, createsdata, caseno):
        tcno, tctxt = self.thencode.toFwdCode(env, streamtype, matchassigns, createsdata, caseno)
        ecno, ectxt = self.elsecode.toFwdCode(env, streamtype, matchassigns, createsdata, tcno+1)
        return (ecno, tctxt+ectxt)

class PerformanceDrop(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    
    def isDrop(self):
        return True
    def isRawForward(self, args):
        return False

    def toFilterCCode(self, spec, streamtype, caseno):
        return (caseno, "return false;\n")
    def toFwdCCode(self, env, streamtype, caseno):
        return (caseno,"")

class PerformanceForward(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def isDrop(self):
        return False
    def isRawForward(self, args):
        return True
    def toFilterCCode(self, spec, streamtype, caseno):
        return (caseno, "perf_case = "+str(caseno)+";\nreturn true;\n")
    def toFwdCCode(self, env, streamtype, matchassigns, createsdata, caseno):
        ret="case "+str(caseno)+":\n{\n"
        ret+="memcpy(__vamos_outevent, __vamos_inevent, sizeof("+streamtype.target.toEventStructName()+"));\n"
        ret+="vms_arbiter_buffer_write_finish(buffer);\n"
        if(createsdata is not None):
            ret+=matchassigns
            matchparams, createsfunname = createsdata
            ret+=createsfunname+"("+", ".join(["stream"]+[str(mp) for mp in matchparams])+");\n"
        ret+="break;\n}\n"
        return (caseno, ret)

class PerformanceForwardConstruct(ASTNode):
    def __init__(self, posInfo, event, args):
        self.event=event
        self.args=args
        super().__init__(posInfo)
    def check(self, env):
        self.event.resolve(env)
    def isDrop(self):
        return False
    def isRawForward(self, args):
        return len(args)==len(self.args) and all([x==y for x,y in zip(args,self.args)])
    def toFilterCCode(self, spec, streamtype, caseno):
        return (caseno, "perf_case = "+str(caseno)+";\nreturn true;\n")
    def toFwdCCode(self, env, streamtype, matchassigns, createsdata, caseno):
        ret="case "+str(caseno)+":\n{\n"
        ret+=matchassigns
        ret+=self.event.target.generateFieldAssigns("__vamos_outevent", [arg.toCCode(env) for arg in self.args])
        ret+="vms_arbiter_buffer_write_finish(buffer);\n"
        if(createsdata is not None):
            matchparams, createsfunname = createsdata
            ret+=createsfunname+"("+", ".join(["stream"]+[str(mp) for mp in matchparams])+");"
        ret+="break;\n}\n"
        return (caseno, ret)

class EventSource(ASTNode):
    def __init__(self, name, posInfo, size, isDynamic, params, streamtype, streaminit, conkind, includedin):
        self.name=name
        self.size=size
        self.isDynamic=isDynamic
        self.params=params
        self.inputtype=streamtype
        self.streaminit=streaminit
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
    def check(self, spec):
        self.inputtype.resolve(spec)
        self.streaminit.check(self, spec)
        for incl in self.includedin:
            incl.resolve(spec)
    def toCVar(self):
        return self.cVar
    def toCPreDecls(self, spec):
        ret=""
        if not self.isDynamic:
            self.cVar = varid("evsource")
            ret=self.streaminit.streamtype.target.toStreamFieldStructName()
            ret+=" "+self.cVar
            if self.size > 1:
                ret+="["+str(self.size)+"]"
            ret+=";\n"
        return ret
    def toInitFunName(self):
        return "__vamos_evsrcinit_"+self.name
    def toCCode(self, spec):
        env=Environment(spec)
        ret="void "+self.toInitFunName()+"("+self.streaminit.streamtype.target.toStreamFieldStructName()+" * __vamos_evsdata, int64_t __vamos_index, int argc, char ** argv)\n{\n"
        ret+=self.conkind.toBufferInitCode("__vamos_evsdata", self.streaminit)
        ret+=self.streaminit.toCCode(env, "__vamos_evsdata")
        ret+=self.inputtype.target.toEventRegistrationCode(env, "__vamos_evsdata")
        for incl in self.includedin:
            ret+=incl.target.generateAddCode("__vamos_evsdata")
            for bg in spec.bufferGroups.values():
                for incl in bg.includes:
                    ret+=incl.generateIncludeCode(bg, self, "__vamos_evsdata", "__vamos_index")
        ret+="vms_arbiter_buffer_set_active(__vamos_evsdata->buffer, true);\n"
        ret+=f"thrd_create(&(((__vamos_streaminfo *)__vamos_evsdata)->thread), {self.streaminit.toThreadFunName()}, (vms_stream *)__vamos_evsdata);\n"
        ret+="}\n"
        return normalizeGeneratedCCode(ret, 0)
    def toCInitCode(self, spec, strbufname):
        ret=self.streaminit.toHoleHandlingDef(spec)
        if self.isDynamic:
            countervar=varid("dynevcnt")
            strmvar=varid("strm")
            sfsvar=varid("sfs")
            ret+="int64_t "+countervar+" = 1;\n"
            ret+="while(true)\n{\n"
            ret+="snprintf("+strbufname+", 128, \"\%s\%z\", \""+self.name+"\", "+countervar+");\n"
            ret+="vms_stream * "+strmvar+" = vms_stream_create_from_argv("+strbufname+", argc, argv, "+self.streaminit.toHoleHandlingRef()+");\n"
            ret+="if("+strmvar+" == 0)\n{\n"
            ret+="break;\n"
            ret+="}\n"
            ret+=self.streaminit.streamtype.target.toStreamFieldStructName()+" * "+sfsvar+" = ("+self.streaminit.streamtype.target.toStreamFieldStructName()+"*)malloc(sizeof("+self.streaminit.streamtype.target.toStreamFieldStructName()+"));\n"
            ret+="if("+sfsvar+"==0)\n{\n"
            ret+='printf("Could not allocate dynamic event source data!\\n");\n'
            ret+="abort();"
            ret+="}\n"
            ret+=self.countervar+"++;\n"
            ret+=sfsvar+"->__info.stream = "+strmvar+";\n"
            ret+=self.toInitFunName()+"("+sfsvar+", "+countervar+", argc, argv);\n"
            ret+="}\n"
        else:
            if self.size > 1:
                for i in range(0,self.size):
                    ret+=self.toCVar()+"["+str(i)+"].__info.stream = vms_stream_create_from_argv(\""+self.name+str(i+1)+"\", argc, argv, "+self.streaminit.toHoleHandlingRef()+");\n"
                    ret+=self.toInitFunName()+"(&"+self.toCVar()+"["+str(i)+"], "+str(i+1)+", argc, argv);\n"
            else:
                ret+=self.toCVar()+".__info.stream = vms_stream_create_from_argv(\""+self.name+"\", argc, argv, "+self.streaminit.toHoleHandlingRef()+");\n"
                ret+=self.toInitFunName()+"(&"+self.toCVar()+", 0, argc, argv);\n"
        return ret

class StreamProcessorRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)

    def resolve(self, env):
        self.target = env.getStreamProcessor(self.name)
        if self.target is None:
            print(f"Unknown Stream Processor \"{self.name}\"")
            registerError(VamosError([self.pos], f"Unknown Stream Processor \"{self.name}\""))
            self.target=StreamProcessor(self.name, self.pos, None, None, None, None, [], None)
            self.target.initializedMembers=True


class EventSourceRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)
    def resolve(self, env):
        self.target=env.getEventSource(self.name)
        if self.target is None:
            registerError(VamosError([self.pos], f"Unknown event source \"{self.name}\""))
        else:
            if self.target.isDynamic:
                registerError(VamosError([self.pos], f"Event source \"{self.name}\" is dynamic and as such can only be referenced via the buffer group that includes it."))


class BufferGroupRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)
    def resolve(self, env):
        self.target = env.getBufferGroup(self.name)
        if self.target is None:
            registerError(VamosError([self.pos], f"Unknown Buffer Group \"{self.name}\""))
            self.target = BufferGroup(self.name, self.pos, "", RoundRobinOrder(self.pos), [])



class AutoDropBufferKind(ASTNode):
    def __init__(self, posInfo, size, minFree):
        self.size=size
        self.minFree=minFree
        super().__init__(posInfo)
    def toCCode(self, env, var, eventStructName): #, eventName, eventStructName, initHoleFun, updateHoleFun):
        ret=""
        ret+=var+"->__info.buffer = vms_arbiter_buffer_create("+var+"->__info.stream,  sizeof("+eventStructName+"), "+str(self.size)+");\n"
        ret+="vms_arbiter_buffer_set_drop_space_threshold("+var+"->__info.buffer, "+str(self.minFree)+");\n"
        ret+="vms_stream_register_all_events("+var+"->__info.stream);\n"
        return ret
    def toBufferInitCode(self, var, streamproc):
        ret=""
        ret+=var+"->__info.buffer = vms_arbiter_buffer_create("+var+"->__info.stream,  sizeof("+streamproc.streamtype.target.toEventStructName()+"), "+str(self.size)+");\n"
        ret+="vms_arbiter_buffer_set_drop_space_threshold("+var+"->__info.buffer, "+str(self.minFree)+");\n"
        return ret


class BlockingBufferKind(ASTNode):
    def __init__(self, posInfo, size):
        self.size=size
        super().__init__(posInfo)
    def toCCode(env):
        print("Blocking buffers not implemented!\n")
        exit()
    def toBufferInitCode(self, var, streamproc):
        print("Blocking buffers not implemented!\n")
        exit()

class InfiniteBufferKind(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def toCCode(env):
        print("Infinite buffers not implemented!\n")
        exit()
    def toBufferInitCode(self, var, streamproc):
        print("Infinite buffers not implemented!\n")
        exit()

class BufferGroup(ASTNode):
    def __init__(self, name, posInfo, streamType, order, includes):
        self.name=name
        self.streamtype=streamType
        self.order=order
        self.includes=includes
        super().__init__(posInfo)
    def initialize(self, spec):
        self.streamtype.resolve(spec)
        env=Environment(spec)
        for ord in self.order:
            ord.initialize(self.streamtype, env)
        for incl in self.includes:
            incl.resolve(env)
    def Register(self, spec):
        self.orderfunname=funid("bg_order_"+self.name)
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
    
    def toCPreDecls(self, spec):
        ret="__vamos_buffer_group "+self.toCVariable()+";\n"
        ret+="int "+self.orderfunname+"(__vamos_buffer_group * bg, __vamos_bg_list_node * node1, __vamos_bg_list_node * node2);"
        return normalizeGeneratedCCode(ret,0)
    
    def toCCode(self, spec):
        ret=""
        env=Environment(spec)
        ret+="int "+self.orderfunname+"(__vamos_buffer_group * bg, __vamos_bg_list_node * node1, __vamos_bg_list_node * node2)\n{\n"
        ret+=self.streamtype.target.toStreamFieldStructName()+" * stream1 = ("+self.streamtype.target.toStreamFieldStructName()+" *)node1->stream;\n"
        ret+=self.streamtype.target.toStreamFieldStructName()+" * stream2 = ("+self.streamtype.target.toStreamFieldStructName()+" *)node2->stream;\n"
        for ord in self.order:
            ret+=ord.toCCode(env)
        ret+="return 0;\n"
        ret+="}\n"
        return normalizeGeneratedCCode(ret,0)
        
    def generateAddCode(self, streamvar):
        return "__vamos_bg_add(&"+self.toCVariable()+", (__vamos_streaminfo *)"+streamvar+");\n"



class RoundRobinOrder(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def initialize(self, streamtype, env):
        pass
    def toCCode(self, env):
        ret="if(node1->id != node2->id)\n{\n"
        ret+="if(node1->id < node2->id)\n{\n"
        ret+="if(node2->id <= bg->lastfirst || bg->lastfirst < node1->id)\n{\n"
        ret+="return -1;\n"
        ret+="}\n"
        ret+="return 1;\n"
        ret+="}\n"
        ret+="if(node1->id <= bg->lastfirst || bg->lastfirst < node2->id)\n{\n"
        ret+="return 1;\n"
        ret+="}\n"
        ret+="return -1;\n"
        ret+="}\n"
        ret+="}\n"
        return ret

class StreamFieldOrder(ASTNode):
    def __init__(self, posInfo, field):
        self.field=field
        super().__init__(posInfo)
    def initialize(self, streamtype, env):
        self.field.resolve(streamtype)
        self.streamtype=streamtype
    def toCCode(self, env):
        var1=varid("strmfield1")
        var2=varid("strmfield2")
        ret=""
        ret+=self.field.target.type.toCCode()+" "+var1+" = "+self.streamtype.target.toCFieldAccess(self.field, "stream1")+";\n"
        ret+=self.field.target.type.toCCode()+" "+var2+" = "+self.streamtype.target.toCFieldAccess(self.field, "stream2")+";\n"
        ret+="if("+var1+" != "+var2+")\n{\n"
        ret+="if("+var1+" < "+var2+")\n{\n"
        ret+="return -1;\n"
        ret+="}\n"
        ret+="return 1;\n"
        ret+="}\n"
        return ret

class SharedElemOrder(ASTNode):
    def __init__(self, posInfo, aggexp, missingspec):
        self.aggexp=aggexp
        self.missingspec=missingspec
        super().__init__(posInfo)

class AggInt(ASTNode):
    def __init__(self, value, posInfo):
        self.value=value
        super().__init__(posInfo)
    def toCInitCode(self, type, streamtype, env):
        return str(self.value)
    

class AggID(ASTNode):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo)
    def toCInitCode(self, type, streamtype, env):
        return "0"


class AggFunc(ASTNode):
    def __init__(self, agg, posInfo, arg):
        self.agg=agg
        self.arg=arg
        super().__init__(posInfo)
    def toCInitCode(self, type, streamtype, env):
        if(self.agg=="COUNT"):
            return "0"
        elif(self.agg=="MAX"):
            ret= f"(((({type})-1)<0)?("
            #signed
            ret+=f"(sizeof({type})==sizeof(long long))?(LLONG_MIN):("
            ret+=f"(sizeof({type}==sizeof(long))?(LONG_MIN):("
            ret+=f"(sizeof({type}==sizeof(int))?(INT_MIN):("
            ret+=f"(sizeof({type}==sizeof(short))?(SHRT_MIN):("
            ret+=f"(sizeof({type}==sizeof(char))?(SCHAR_MIN):\"ERROR!\""
            ret+="))))):("
            #unsigned
            ret+="0"
            ret+="))"
            return ret
        elif(self.agg=="MIN"):
            ret=f"(sizeof({type})==sizeof(unsigned long long))?(ULLONG_MAX):("
            ret+=f"(sizeof({type}==sizeof(unsigned long))?(ULONG_MAX):("
            ret+=f"(sizeof({type}==sizeof(unsigned int))?(UINT_MAX):("
            ret+=f"(sizeof({type}==sizeof(unsigned short))?(USHRT_MAX):("
            ret+=f"(sizeof({type}==sizeof(unsigned char))?(UCHAR_MAX):\"ERROR!\""
            ret+="))))zoo"
            return ret
        else:
            print("Unknown Aggregate Function!")
            exit()

class AggBinOp(ASTNode):
    def __init__(self, posInfo, left, op, right):
        self.left=left
        self.right=right
        self.op=op
        super().__init__(posInfo)
    def toCInitCode(self, type, streamtype, env):
        return "("+parenthesize(self.left.toInitCCode(type, streamtype, env))+" "+self.op+" "+parenthesize(self.right.toInitCCode(type, streamtype, env))+")"

class AggUnOp(ASTNode):
    def __init__(self, posInfo, op, arg):
        self.op=op
        self.arg=arg
        super().__init__(posInfo)
    def toCInitCode(self, type, streamtype, env):
        return "("+self.op+parenthesize(self.arg.toInitCCode(type, streamtype, env))+")"

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
    def initialize(self, env):
        self.eventsource.resolve(env)
    def generateIncludeCode(self, bg, evsource, streamvar, indexvar):
        if(evsource==self.eventsource.target):
            return bg.generateAddCode(streamvar)
        else:
            return ""

class BGroupIncludeIndex(ASTNode):
    def __init__(self, posInfo, evsource):
        self.eventsource=evsource
        super().__init__(posInfo)
    def initialize(self, env):
        self.eventsource.resolve(env)
    def generateIncludeCode(self, bg, evsource, streamvar, indexvar):
        if(evsource==self.eventsource.target):
            ret="if("+indexvar+" == "+str(self.eventsource.index)+")\n{\n"
            ret+=bg.generateAddCode(streamvar)
            ret+="}\n"
            return ret
        else:
            return ""

class EventSourceIndexedRef(Reference):
    def __init__(self, name, posInfo, idx):
        self.index=idx
        if isinstance(name,str):
            name=EventSourceRef(name, posInfo)
        super().__init__(name, posInfo)
    def resolve(self, env):
        self.name.resolve(env)
        self.target = self.name.target
    def toStreamVar(self):
        return self.target.toCVar()

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
        ret="uint64_t arbiter_counter = 10;\n"
        ret+="thrd_t __vamos_thrd_arbiter;\n"
        ret+="vms_monitor_buffer *__vamos_monitor_buffer;\n"
        for event in self.streamtype.target.events.values():
            ret+=event.toArbiterYieldCCode(spec)
        for ruleset in self.rulesets:
            ret+=ruleset.toCPreDecls(spec)
        for ruleset in self.rulesets:
            ret+=ruleset.toCCode(0, Environment(spec))
        ret+="int arbiter()\n{\n"
        baseindent=' '*INDENT
        indnt=baseindent
        ret+=indnt+"int all_done=0;\n"
        ret+=indnt+"int __vamos_matched = 0;\n"
        ret+=indnt+"uint64_t __vamos_roundid=1;\n"
        ret+=indnt+"while(!all_done)\n"+indnt+"{\n"
        indnt+=baseindent
        for bg in spec.bufferGroups.values():
            ret+=indnt+"__vamos_bg_process_updates(&"+bg.toCVariable()+");\n"
            ret+=indnt+"__vamos_bg_process_inserts(&"+bg.toCVariable()+");\n"
        if len(self.rulesets)>1:
            ret+=indnt+"switch(__vamos_current_arbiter_ruleset)\n"+indnt+"{\n"
            indnt+=baseindent
            for ruleset in self.rulesets:
                ret+=indnt+"case "+ruleset.toCEnumValue()+":\n"
                ret+=indnt+"{\n"
                ret+=indnt+"__vamos_matched = "+ruleset.toCallCCode("__vamos_roundid++")+";\n"
                ret+=indnt+baseindent+"break;\n"
                ret+=indnt+"}\n"
            indnt=baseindent*2
            ret+=indnt+"}\n"
        else:
            ret+=indnt+self.rulesets[0].toCallCCode("__vamos_roundid++")+";\n"
        indnt=' '*INDENT
        ret+=indnt+"}\n"
        ret+=indnt+"vms_monitor_set_finished(monitor_buffer);\n"
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
    def toFunName(self):
        return "__vamos_ruleset_fun_"+self.name;
    def toCEnumValue(self):
        return "__vamos_ruleset_enum_"+self.name;
    def toCPreDecls(self, spec):
        return "int "+self.toFunName()+"(uint64_t __vamos_roundid);\n"
    def toCCode(self, depth, env):
        ret="int "+self.toFunName()+"(uint64_t __vamos_roundid)\n{\n"
        ret+=(' '*INDENT)+"int __vamos_hasmatched=0;\n"
        ret+=(' '*INDENT)+"int __vamos_continue=0;\n"
        for rule in self.rules:
            ret+=rule.toCCode(1, env)
        return ret+(' '*INDENT)+"return __vamos_hasmatched;\n}\n"
    def toCallCCode(self, arg):
        return self.toFunName()+"("+arg+")"

class ArbiterRule(ASTNode):
    def __init__(self, posInfo, condition, code):
        self.condition=condition
        self.code=code
        super().__init__(posInfo)
    def initialize(self, env):
        env=Environment(env)
        self.drops=self.condition.initialize(env)
        self.code.initialize(env)

    def toCCode(self, depth, env):
        env=Environment(env)
        tmplt=self.condition.toCCode(depth, env)
        wrap=""
        for key in self.drops.keys():
            if(self.drops[key] > 0):
                wrap+="if(((__vamos_streaminfo *)"+key.toCVar()+")->drop_on_match < "+str(self.drops[key])+")\n{\n"
                wrap+="((__vamos_streaminfo *)"+key.toCVar()+")->drop_on_match = "+str(self.drops[key])+";\n"
                wrap+="}\n"
        wrap+="@WRAP@\n"
        code = self.code.toCCode(env)
        for key in self.drops.keys():
            if(self.drops[key] > 0):
                wrap+="if(((__vamos_streaminfo *)"+key.toCVar()+")->drop_on_match > 0)\n{\n"
                wrap+="vms_arbiter_buffer_drop(((__vamos_streaminfo *)"+key.toCVar()+")->buffer, ((__vamos_streaminfo *)"+key.toCVar()+")->drop_on_match);\n"
                wrap+="((__vamos_streaminfo *)"+key.toCVar()+")->drop_on_match = 0;\n"
                wrap+="}\n"
        wrap+="__vamos_hasmatched = 1;\n"
        wrap+="if(!__vamos_continue)\n{\n"
        wrap+="return 1;\n"
        wrap+="}\n"
        wrap=normalizeGeneratedCCode(wrap, depth)
        code=insertInNormalizedCCode(wrap, "@WRAP@", code)
        return insertInNormalizedCCode(tmplt, "@SUBST@", code)

class ArbiterAlwaysCondition(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def initialize(self, env):
        return {}
    def toCCode(self, depth, env):
        return ' '*INDENT*depth+"@SUBST@\n"

class ArbiterMatchCondition(ASTNode):
    def __init__(self, posInfo, matchExps, whereCond):
        self.matchExps=matchExps
        self.whereCond=whereCond
        super().__init__(posInfo)
    def initialize(self, env):
        ret={}
        for matchExp in self.matchExps:
            mret=matchExp.initialize(env)
            for key in mret.keys():
                if key in ret:
                    ret[key]=max(mret[key],ret[key])
                else:
                    ret[key]=mret[key]
        if self.whereCond is not None:
            self.whereCond.initialize(env)
        return ret
    def toCCode(self, depth, env):
        stck=[]
        for matchExp in self.matchExps:
            template=matchExp.toCCode(depth, env)
            depth+=1
            stck=[stck, template]
        fin=' '*INDENT*depth+"@SUBST@\n"
        if self.whereCond is not None:
            fin=self.whereCond.toCCode(env)
        while len(stck)==2:
            fin=insertInNormalizedCCode(stck[1], "@INSERT@", fin)
            stck=stck[0]
        return fin

class ArbiterChoice(ASTNode):
    def __init__(self, posInfo, direction, variables, group, filter):
        self.direction=direction
        self.variables=variables
        self.group=group
        self.filter=filter
        super().__init__(posInfo)
    def initialize(self, env):
        self.group.resolve(env)
        self.varvars={}
        for var in self.variables:
            self.varvars[var] = varid(var)
            env.addEventSourceVar(0, self.group, var, self.varvars[var])
        self.filter.initialize(env)
        return {}
    def toCCode(self, depth, env):
        ret=""
        for var in self.variables:
            ret+=env.addEventSourceVar(depth, self.group, var, self.varvars[var])
        ret+=self.direction.toCCode(depth, self.group, self.filter, self.variables, env)
        return ret

class ArbiterChoiceRule(ASTNode):
    def __init__(self, posInfo, choice, rules):
        self.choice=choice
        self.rules=rules
        super().__init__(posInfo)
    def initialize(self, env):
        env=Environment(env)
        self.choice.initialize(env)
        for rule in self.rules:
            rule.initialize(env)
    def toCCode(self, depth, env):
        env=Environment(env)
        ret=self.choice.toCCode(depth, env)
        ruleret=""
        for rule in self.rules:
            ruleret+=rule.toCCode(depth+1, env)
        ret=insertInNormalizedCCode(ret,"@INSERT@", ruleret)
        return ret

class ChooseSources(ASTNode):
    def __init__(self, posInfo, n):
        self.n=int(n)
        super().__init__(posInfo)
    def toCCode(self, depth, group, filter, vars, env):
        ret=""
        if(self.n==0):
            return ""
        else:
            anyleftvar = varid("combinations_left")
            ret = f"int {anyleftvar} = {group.target.readsize()}>={len(vars)};\n"
            ret +=f"if({anyleftvar})\n{'{'}\n"
            itervar=varid("source_iter")
            ret+="__vamos_bg_list_node * "+itervar+" = "+self.getInitialSource(group)+";\n"
            ret+=(itervar+" = "+self.getNextSource(itervar)+";\n").join([env.getEventSource(var).varid+" = ("+group.target.streamtype.target.toReferenceType()+")"+itervar+"->stream;\n" for var in vars])
            permvar=""
            if(self.n!=1):
                if(len(vars)>1):
                    permvar = varid("permutations")
                    ret += f"__vamos_bg_list_node* {permvar}[] = "+"{"+", ".join([env.getEventSource(var).varid for var in vars])+"};\n"
                cyclecountcond=""
                if self.n > 1:
                    cyclecountvar = varid("cycle_count")
                    ret+= f"uint64_t {cyclecountvar} = 0;\n"
                    cyclecountcond=f" && {cyclecountvar} < {self.n}"
                ret+= f"do\n"+"{\n"
                if(len(vars)>1):
                    cnt=0
                    for var in vars:
                        ret+=env.getEventSource(var).varid+" = "+permvar+"["+str(cnt)+"];\n"
                        cnt+=1
            if filter is not None:
                ret+="if("+filter.toCCode(env)+")\n{\n"
            ret+="@INSERT@\n"
            if(self.n>1):
                ret+=cyclecountvar+"++;\n"
            if filter is not None:
                ret+="}\n"
            if(self.n!=1):
                if(len(vars)>1):
                    ret+=anyleftvar+" = "+self.getNextPermutation(permvar, len(vars), group)
                else:
                    ret+=env.getEventSource(vars[0]).varid+" = "+self.getNextSource(env.getEventSource(vars[0]).varid)+";\n"
                    ret+=anyleftvar+" = "+env.getEventSource(vars[0]).varid+" != "+self.getInitialSource(group)+";\n"
                ret+="}"+f"\nwhile({anyleftvar}{cyclecountcond});\n"
            ret+="}\n"
        return normalizeGeneratedCCode(ret, depth)


class ChooseFirst(ChooseSources):
    def __init__(self, posInfo, n):
        super().__init__(posInfo, n)
    def getInitialSource(self, group):
        return group.target.toCVariable()+".head"
    def getNextSource(self, dllVar):
        return dllVar+"->next"
    def getNextPermutation(self, permvar, permsize, group):
        return f"advance_permutation_forward({permvar}, {permsize}, {group.target.toCVariable()}.head);\n"


class ChooseLast(ChooseSources):
    def __init__(self, posInfo, n):
        super().__init__(posInfo, n)
    def getInitialSource(self, group):
        return group.target.toCVariable()+".head->prev"
    def getNextSource(self, dllVar):
        return dllVar+"->prev"
    def getNextPermutation(self, permvar, permsize, group):
        return f"advance_permutation_backward({permvar}, {permsize}, {group.target.toCVariable()}.head->prev);\n"


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
            registerError(VamosError([self.pos], f"Expected {len(self.event.target.allFields())} pattern match parameters for event \"{self.event.target.name}\", but found {len(self.params)}"))
        env=Environment(spec)
        self.condition.initialize(env)
        self.code.initialize(env)
    
    def toCCode(self, spec, indnt, baseindent):
        ret=indnt+f"if(received_event->head.kind == {self.event.target.toEnumName()})\n"
        ret+=indnt+"{\n"
        ret+=self.event.target.generateMatchAssignments(spec, f"received_event", self.params, indnt+baseindent)
        if self.condition is not None and self.condition.toCCode(spec).lstrip().rstrip()!="true":
            ret+=f"{indnt}{baseindent}if({self.condition.toCCode(spec)})\n"
            ret+=indnt+baseindent+"{\n"
            ret+=normalizeCCode(self.code.toCCode(spec), indnt+(baseindent*2))
            ret+="\n"+indnt+(baseindent*2)+"vms_monitor_buffer_consume(__vamos_monitor_buffer, 1);"
            ret+="\n"+indnt+(baseindent*2)+"continue;\n"
            ret+=indnt+baseindent+"}\n"
        else:
            ret+=normalizeCCode(self.code.toCCode(spec), indnt+baseindent)
            ret+="\n"+indnt+baseindent+"vms_monitor_buffer_consume(__vamos_monitor_buffer, 1);"
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
    def toCCode(self, env):
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
    def toCCode(self, env):
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
    def toCCode(self, env):
        return self.pre.toCCode(env)+self.toCCodeEscape(env)+self.post.toCCode(env)

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
        return {self.buffer.target:self.pattern.initialize(self.buffer, env)}
    def toCCode(self, depth, env):
        return self.pattern.toCCode(depth, env)

class MatchPatternNothing(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def initialize(self, buffer, env):
        self.buffer=buffer
        return 0
    def toCCode(self, depth, env):
        ret=env.requestFromBuffer(self.buffer, 0)
        ret+="if("+env.eventsInBuffer(self.buffer)+" == 0)\n{\n@INSERT@\n}\n"
        return normalizeGeneratedCCode(ret, depth)

class MatchPatternDone(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def initialize(self, buffer, env):
        self.buffer=buffer
        return 0
    def toCCode(self, depth, env):
        ret=env.requestFromBuffer(self.buffer, 0)
        ret+="if("+env.checkBufferIsDone(self.buffer)+")\n{\n@INSERT@\n}\n"
        return normalizeGeneratedCCode(ret, depth)

class MatchPatternSize(ASTNode):
    def __init__(self, posInfo, size):
        self.size=size
        super().__init__(posInfo)
    def initialize(self, buffer, env):
        self.buffer=buffer
        return 0
    def toCCode(self, depth, env):
        ret=env.requestFromBuffer(self.buffer, 0)
        ret+="if("+env.eventsInBuffer(self.buffer)+" >= "+str(self.size)+")\n{\n@INSERT@\n}\n"
        return normalizeGeneratedCCode(ret, depth)

class MatchPatternEvents(ASTNode):
    def __init__(self, posInfo, pre, post):
        self.pre=pre
        self.post=post
        super().__init__(posInfo)
    def initialize(self, buffer, env):
        self.buffer=buffer
        self.evvar=varid("event")
        for mev in self.pre + self.post:
            mret=mev.initialize(buffer, env)
        return len(self.pre)
    def toCCode(self, depth, env):
        ret=env.requestFromBuffer(self.buffer, len(self.pre)+len(self.post))
        ret+="if("+env.eventsInBuffer(self.buffer)+" >= "+str(len(self.pre)+len(self.post))+")\n{\n"
        ret+=self.buffer.target.streamtype.target.toEventStructName()+" * "+self.evvar+";\n"
        ret+="@INSERT@\n}\n"
        cnt=0
        for mev in self.pre + self.post:
            nmatch="if(((__vamos_streaminfo *)"+self.buffer.toStreamVar()+")->size1 > "+str(cnt)+")\n{\n"
            nmatch+=self.evvar+" = (("+self.buffer.target.streamtype.target.toEventStructName()+" *)((__vamos_streaminfo *)"+self.buffer.toStreamVar()+")->data1)["+str(cnt)+"];\n"
            nmatch+="}\nelse\n{\n"
            nmatch+=self.evvar+" = (("+self.buffer.target.streamtype.target.toEventStructName()+" *)((__vamos_streaminfo *)"+self.buffer.toStreamVar()+")->data2)["+str(cnt)+"-((__vamos_streaminfo *)"+self.buffer.toStreamVar()+")->size1];\n"
            nmatch+="}\n"
            nmatch+=mev.toCCode(env, self.evvar)
            ret=insertInNormalizedCCode(ret, "@INSERT@", nmatch)
        return normalizeGeneratedCCode(ret, depth)

class MatchPatternEvent(ASTNode):
    def __init__(self, posInfo, ev, vars):
        self.event=ev
        self.vars=vars
        super().__init__(posInfo)
    def initialize(self, buffer, env):
        self.buffer=buffer
        self.event.resolve(self.buffer.target.streamtype.target, env)

    def toCCode(self, env, receiver):
        ret="if("+receiver+"->head.kind == "+self.event.target.toEnumName()+")\n{\n"
        ret+=self.event.target.generateMatchAssignments(env, receiver, self.vars, "")
        ret+="@INSERT@\n}\n"
        return ret

        
class MatchPatternShared(MatchPatternEvent):
    def __init__(self, posInfo, vars):
        super().__init__(posInfo, "SHARED", vars)
    def initialize(self, buffer, env):
        self.buffer=buffer
    def toCCode(self, env, receiver):
        ret=self.buffer.target.streamtype.target.generateSharedMatchAssignments(env, receiver, self.vars)
        ret+="@INSERT@\n"
        return ret

class MatchPatternIgnored(ASTNode):
    def __init__(self, posInfo):
        super().__init__(posInfo)
    def initialize(self, buffer, env):
        pass
    def toCCode(self, env, receiver):
        return "@INSERT@\n"

class CCodeField(CCodeEscape):
    def __init__(self, posInfo, receiver, field):
        self.receiver=receiver
        self.field=field
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.receiver.resolve(env)
        self.field.resolve(self.receiver.target.streamtype)

    def toCCodeEscape(self, env):
        return self.receiver.target.toCFieldAccess(env, self.field)

class CCodeContinue(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def toCCodeEscape(self, spec):
        return "__vamos_continue = 1;\n"
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
    def toCCodeEscape(self, env):
        return "vms_arbiter_buffer_drop(((__vamos_streaminfo *)"+self.source.target.toCVar()+")->buffer, "+str(self.amount)+");\n"

class CCodeRemove(CCodeEscape):
    def __init__(self, posInfo, source, group):
        self.group=group
        self.source=source
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.source.resolve(env)
        self.group.resolve(env)
    def toCCodeEscape(self, env):
        return ""

class CCodeAdd(CCodeEscape):
    def __init__(self, posInfo, source, group):
        self.group=group
        self.source=source
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.source.resolve(env)
        self.group.resolve(env)
    def toCCodeEscape(self, env):
        return ""

class CCodeYield(CCodeEscape):
    def __init__(self, posInfo, ev, args):
        self.event=ev
        self.args=args
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def initializeEscape(self, env):
        self.event.resolve(env.getArbiterStreamType(), env)
    def toCCodeEscape(self, env):
        return "__arbiter_yield_"+self.event.name+"("+", ".join([arg.toCCode(env) for arg in self.args])+");"

class ExprVar(CCodeEscape):
    def __init__(self, name, posInfo):
        self.name=name
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False
    def toCCode(self, env):
        return self.name

class ExprInt(CCodeEscape):
    def __init__(self, val, posInfo):
        self.value=int(val)
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False
    def toCCode(self, env):
        return str(self.value)
        
class ExprTrue(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False
    def toCCode(self, env):
        return "1"

class ExprFalse(CCodeEscape):
    def __init__(self, posInfo):
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return False
    def toCCode(self, env):
        return "0"

class ExprBinOp(CCodeEscape):
    def __init__(self, posInfo, op, left, right):
        self.op=op
        self.left=left
        self.right=right
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return self.left.containsCCode() or self.right.containsCCode()
    def toCCode(self, env):
        return "("+parenthesize(self.left.toCCode(env))+" "+self.op+" "+parenthesize(self.right.toCCode(env))+")"

class ExprUnOp(CCodeEscape):
    def __init__(self, posInfo, op, rand):
        self.op=op
        self.rand=rand
        super().__init__(posInfo, CCodeEmpty(posInfo.StartSpan()), CCodeEmpty(posInfo.EndSpan()))
    def containsCCode(self):
        return self.rand.containsCCode()
    def toCCode(self, env):
        return "("+self.op+parenthesize(self.rand.toCCode(env))+")"

class FieldAccess(ASTNode):
    def __init__(self, posInfo, evsource, fieldname):
        self.field=fieldname.toStreamFieldRef()
        self.evsource=evsource
        super().__init__(posInfo)
    def check(self, env):
        self.evsource.resolve(env)
        self.field.resolve(self.evsource.streaminit.streamtype.target)

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

class FieldRef(Reference):
    def __init__(self, name, posInfo):
        super().__init__(name, posInfo)
    def resolve(self, event):
        self.target = event.getField(self.name)
        if self.target is None:
            registerError(VamosError([self.pos], f'Unknown field "{self.name}" for event "{event.name}"'))

class EventSourceVar:
    def __init__(self, name, streamtype, varid):
        self.name=name
        self.streamtype=streamtype
        self.varid=varid
        self.isDynamic=False
    def toCFieldAccess(self, env, field):
        return self.streamtype.target.toCFieldAccess(field, self.varid)
    def toCVar(self):
        return self.varid


class Environment:
    def __init__(self, parent):
        self.parent=parent
        self.eventSourceVars={}
        self.createsEvent=None

    def addEventSourceVar(self, depth, group, var, newvarid):
        self.eventSourceVars[str(var)]=EventSourceVar(str(var), group.target.streamtype, newvarid)
        return f"{' '*INDENT*depth}{group.target.streamtype.target.toReferenceType()} {newvarid};\n"
    
    def getBufferGroup(self, name):
        return self.parent.getBufferGroup(name)

    def getEventSource(self, name):
        name=str(name)
        if name in self.eventSourceVars:
            return self.eventSourceVars[name]
        return self.parent.getEventSource(name)
    
    def getStreamType(self, name):
        return self.parent.getStreamType(name)
    
    def getStreamProcessor(self, name):
        return self.parent.getStreamProcessor(name)
    
    def getArbiterStreamType(self):
        return self.parent.getArbiterStreamType()

    def checkBufferIsDone(self, buffer):
        return "(((__vamos_streaminfo *)"+buffer.toStreamVar()+")->status == -1)"
    def eventsInBuffer(self, buffer):
        return "(((__vamos_streaminfo *)"+buffer.toStreamVar()+")->available)"
    def requestFromBuffer(self, buffer, count):
        return "__vamos_request_from_buffer((__vamos_streaminfo *)"+buffer.toStreamVar()+", "+str(count)+", __vamos_roundid);\n"

    def getCreatesEvent(self):
        if self.createsEvent is None:
            return self.parent.getCreatesEvent()
        return self.createsEvent