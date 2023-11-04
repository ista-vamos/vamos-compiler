from ply.yacc import yacc
from type_checker import *
from utils import *
from parser_indices import *
from vamos import *
import sys

precedence = (
    ('left', 'AND', 'OR'),
    ('right', 'NOT'),
    ('left', 'DOUBLEQ'),
    ('left', 'GEQ', 'LEQ', 'GT', 'LT'),
    ('left', 'BAND', '|'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES'),
    ('right', 'UMINUS')
)

# this is the entry point
def p_main_program(p):
    """
    main_program : components arbiter_definition monitor_definition
    """
    p[0] = VamosSpec(p[1], p[2], p[3])


def p_empty(p):
    'empty : '
    p[0]=None

def p_components(p):
    """
    components : component components
               | component
    """

    if len(p) == 2:
        p[0] = [p[1]]
    else:
        assert len(p) == 3
        p[0] = p[2].copy()
        p[0].insert(0,p[1])


def p_component(p):
    """
    component : stream_type
              | event_source
              | stream_processor
              | buff_group_def
              | match_fun_def
    """
    p[0] = p[1]

def p_globals(p):
    """
    component : GLOBALS BEGIN_CCODE c_codes CCODE_end
    """
    p[0] = CGlobals(posInfoFromParser(p), p[3])

def p_startup(p):
    """
    component : STARTUP BEGIN_CCODE c_codes CCODE_end
    """
    p[0] = CStartup(posInfoFromParser(p), p[3])

def p_cleanup(p):
    """
    component : CLEANUP BEGIN_CCODE c_codes CCODE_end
    """
    p[0] = CCleanup(posInfoFromParser(p), p[3])

def p_loopdebug(p):
    """
    component : LOOPDEBUG BEGIN_CCODE c_codes CCODE_end
    """
    p[0] = CLoopdebug(posInfoFromParser(p), p[3])

# BEGIN event streams
def p_stream_type(p):
    """
    stream_type : STREAM TYPE ID stream_fields stream_type_extends shared_spec aggregate_spec '{' event_list '}'
    """
    p[0]=StreamType(p[3], posInfoFromParser(p), p[4], p[5], p[6], p[7], p[9])

def p_stream_type_extends(p):
    """
    stream_type_extends : empty
                        | EXTENDS ID
    """
    if(len(p)==3):
        p[0]=StreamTypeRef(p[2], posInfoFromParser(p))
    else:
        p[0]=None

def p_aggregate_spec(p):
    """
    aggregate_spec : empty
                   | AGGREGATE '(' list_aggregate_field_decl ')'
    """
    if(len(p)==5):
        p[0]=p[3]
    else:
        p[0]=[]

def p_shared_spec(p):
    """
    shared_spec : empty
                | SHARED '(' list_field_decl ')'
    """
    if(len(p)==5):
        p[0]=p[3]
    else:
        p[0]=[]
  
def p_event_declaration(p):
    """
    event_decl : ID '(' list_field_decl ')' creates_spec
    """

    # Type checker
    # TypeChecker.insert_into_args_table(p[PEVENT_NAME], EVENT_NAME, params)
    p[0] = Event(p[1], posInfoFromParser(p), p[3], p[5])

def p_creates_spec(p):
    """
    creates_spec : empty
                 | CREATES ID
    """
    if(len(p)==3):
        p[0]=StreamTypeRef(p[2], posInfoFromParser(p))
    else:
        p[0]=None

def p_id(p):
    """
    id : ID
    """
    p[0] = VamosID(p[1], posInfoFromParser(p))

def p_list(p):
    """
    list_field_decl : empty
                    | ne_list_field_decl
    list_aggregate_field_decl : empty
                              | ne_list_aggregate_field_decl
    expression_list : empty
                    | ne_expression_list
    id_list : empty
            | ne_id_list
    c_expr_list : empty
                | ne_c_expr_list
    id_or_int_list : empty
                   | ne_id_or_int_list
    ev_match_list : empty
                  | ne_ev_match_list
    """
    if(p[1]==None):
        p[0]=[]
    else:
        p[0]=p[1]

def p_nelist(p):
    """
    ne_id_list : id
               | id ',' ne_id_list
    ne_list_field_decl : field_decl
                       | field_decl ',' ne_list_field_decl
    ne_list_aggregate_field_decl : ne_list_aggregate_field_decl
                       | aggregate_field_decl ',' ne_list_field_decl
    event_list : event_decl ';'
               | event_decl ';' event_list
    ne_expression_list : expression
                       | expression ',' ne_expression_list
    processor_rule_list : processor_rule
                        | processor_rule ';'
                        | processor_rule ';' processor_rule_list
    list_hole_attributes : hole_attribute ';'
                         | hole_attribute ';' list_hole_attributes
    agg_arg_list : agg_arg
                 | agg_arg ',' agg_arg_list
    ne_order_expr_list : order_expr
                       | order_expr ',' ne_order_expr_list
    ne_bg_includes_list : bg_include
                        | bg_include ',' ne_bg_includes_list
    ne_c_expr_list : c_exprs
                   | c_exprs CCODE_COMMA ne_c_expr_list
    ne_id_or_int_list : id_or_int
                      | id_or_int ',' ne_id_or_int_list
    """
    if len(p) == 4:
        p[0] = p[PLIST_TAIL_WITH_SEP].copy()
        p[0].insert(0, p[PLIST_BASE_CASE])
    else:
        p[0] = [p[PLIST_BASE_CASE]]

def p_opt_parenthesized_list(p):
    """
    opt_expression_list : empty
                        | '(' expression_list ')'
    stream_fields : empty
                  | '(' list_field_decl ')'
    opt_id_list : empty
                | '(' id_list ')'
    opt_bracket_id_list : empty
                | '[' id_list ']'
    """
    if(len(p)==2):
        p[0]=[]
    else:
        p[0]=p[2]

def p_field_declaration(p):
    """
    field_decl : ID ':' type
    """
    p[0] = FieldDecl(p[PFIELD_NAME], p[PFIELD_TYPE], posInfoFromParser(p))

def p_agg_field_decl(p):
    """
    aggregate_field_decl : type ID '=' agg_expr
    """
    p[0] = AggFieldDecl(p[2], posInfoFromParser(p), p[1], p[3])

# END event streams

# BEGIN performance layer specifications

def p_stream_processor(p):
    """
    stream_processor : STREAM PROCESSOR ID stream_fields ':' ID opt_expression_list ARROW ID opt_expression_list processor_extends_spec '{' processor_rule_list custom_hole '}'
    """
    p[0]=StreamProcessor(p[3], posInfoFromParser(p), p[4], ParameterizedRef(StreamTypeRef(p[6], posInfoFromParserItem(p,6)), p[7], posInfoFromParserItem(p,6).Combine(posInfoFromParserItem(p,7), True)), ParameterizedRef(StreamTypeRef(p[9], posInfoFromParserItem(p,9)), p[10], posInfoFromParserItem(p,9).Combine(posInfoFromParserItem(p,10), True)), p[11], p[13], p[14])

def p_processor_extends_spec(p):
    """
    processor_extends_spec : empty
                           | EXTENDS ID opt_expression_list
    """
    if(len(p)==2):
        p[0]=None
    else:
        p[0]=ParameterizedRef(StreamProcessorRef(p[2], posInfoFromParserItem(p,2)), p[3], posInfoFromParser(p))


def p_custom_hole(p):
    """
    custom_hole : empty
                | HOLE ID '{' list_hole_attributes '}'
    """

    if(len(p)==2):
        p[0]=None
    else:
        p[0] = CustomHole(p[2], posInfoFromParser(p), p[4])

def p_hole_attribute(p):
    """
    hole_attribute : ID "=" agg_func '(' agg_func_args ')'
    """
    p[0] = HoleAttribute(p[1], posInfoFromParser(p), p[3], p[5])

def p_aggfunc(p):
    """
    agg_func : COUNT
             | MIN
             | MAX
    """
    p[0] = AggFunction(p[1], posInfoFromParser(p))


def p_agg_func_params(p):
    """
    agg_func_args : TIMES
                  | agg_arg_list
    """
    p[0] = p[1]

def p_agg_arg_id(p):
    """
    agg_arg : ID
    """
    p[0] = AggEventAccess(posInfoFromParser(p), EventReference(p[1], posInfoFromParser(p)))

def p_agg_arg_field(p):
    """
    agg_arg : id '.' id
    """
    p[0] = AggFieldAccess(p[3], posInfoFromParser(p), p[1])

def p_processor_rule(p):
    """
    processor_rule : ON ID opt_id_list creates_part performance_action
    """
    p[0] = ProcessorRule(posInfoFromParser(p), EventReference(p[2], posInfoFromParserItem(p, 2)), p[3], p[4], p[5])

def p_stream_initialization(p):
    """stream_init_expr : opt_expression_list
                        | PROCESS USING ID opt_expression_list
    """
    if(len(p)==2):
        p[0] = DirectStreamInit(posInfoFromParser(p), p[1])
    else:
        p[0] = StreamProcessorInit(posInfoFromParser(p), StreamProcessorRef(p[3], posInfoFromParserItem(p,3)), p[4])

def p_creates_part(p):
    """
    creates_part : CREATES creates_limit ID stream_init_expr TO connection_kind include_spec
    """
    p[0] = CreatesSpec(posInfoFromParser(p), p[2], StreamTypeRef(p[3], posInfoFromParserItem(p,2)), p[4], p[6], p[7])
    

def p_creates_limit(p):
    """
    creates_limit : empty
                  | AT MOST INT
    """
    if(len(p)==2):
        p[0]=-1
    else:
        p[0]=int(p[3])

def p_include_spec(p):
    """
    include_spec : empty
                 | INCLUDE IN ne_id_list
    """
    if(len(p)==2):
        p[0]=[]
    else:
        p[0]=[id.toBufGroupRef() for id in p[3]]


def p_performance_action_if(p):
    """
    performance_action : IF '(' expression ')' THEN performance_action ELSE performance_action
    """
    p[0] = PerformanceIf(posInfoFromParser(p), p[3], p[6], p[8])


def p_performance_action_drop(p):
    """
    performance_action : DROP
    """
    p[0] = PerformanceDrop(posInfoFromParser(p))

def p_performance_action_forward_construct(p):
    """
    performance_action : FORWARD ID '(' expression_list ')'
    """
    p[0] = PerformanceForwardConstruct(posInfoFromParser(p), EventReference(p[2], posInfoFromParserItem(p, 2)), p[4])

def p_performance_action_forward(p):
    """
    performance_action : FORWARD
    """
    p[0] = PerformanceForward(posInfoFromParser(p))

def p_dynamic_flag_empty(p):
    """
    dyn_flag : empty
    """
    p[0]=False

def p_dynamic_flag_dynamic(p):
    """
    dyn_flag : DYNAMIC
    """
    p[0]=True


def p_event_source_size_1(p):
    """
    event_source_size : empty
    """
    p[0] = 1

def p_event_source_size_n(p):
    """
    event_source_size : '[' INT ']'
    """
    p[0] = int(p[2])

def p_event_source(p):
    """
    event_source : dyn_flag EVENT SOURCE ID event_source_size stream_fields ':' ID stream_init_expr TO connection_kind include_spec
    """
    p[0] = EventSource(p[4], posInfoFromParser(p), p[5], p[1], p[6], StreamTypeRef(p[8], posInfoFromParserItem(p,8)), p[9], p[11], p[12])


def p_connection_kind_autodrop(p):
    """
    connection_kind : AUTODROP '(' INT ')'
                    | AUTODROP '(' INT ',' INT ')'
    """
    minFree=1
    if(len(p)>5):
        minFree=int(p[5])
    p[0] = AutoDropBufferKind(posInfoFromParser(p), int(p[3]), minFree)

def p_connection_kind_blocking(p):
    """
    connection_kind : BLOCKING '(' INT ')'
    """
    p[0]=BlockingBufferKind(posInfoFromParser(p), int(p[3]))

def p_connection_kind_infinite(p):
    """
    connection_kind : INFINITE
    """
    p[0]=InfiniteBufferKind(posInfoFromParser(p))

# END performance layer specifications

# BEGIN advanced features
def p_buff_group_def(p):
    """
    buff_group_def : BUFFER GROUP ID ':' ID order_spec bg_includes_spec
    """
    p[0]=BufferGroup(p[3], posInfoFromParser(p), StreamTypeRef(p[5], posInfoFromParserItem(p,5)), p[6], p[7])
def p_order_spec(p):
    """
    order_spec : empty
               | ORDER BY order_list
    """
    if(len(p)>2):
        p[0] = p[3]
    else:
        p[0] = [RoundRobinOrder(posInfoFromParser(p))]

def p_order_list(p):
    """
    order_list : order_expr
               | '[' ne_order_expr_list ']'
    """
    if(len(p)>2):
        p[0] = p[2]
    else:
        p[0] = [p[1]]

def p_order_expr(p):
    """
    order_expr : ROUND ROBIN
               | ID
               | SHARED agg_expr missing_spec
    """
    if len(p) == 3:
        p[0] = RoundRobinOrder(posInfoFromParser(p))
    elif len(p) == 2:
        p[0] = StreamFieldOrder(posInfoFromParser(p), StreamFieldRef(p[1], posInfoFromParserItem(p,1)))
    else:
        p[0] = SharedElemOrder(posInfoFromParser(p), p[2], p[3])

def p_agg_expr_int(p):
    """
    agg_expr : INT
    """
    p[0] = AggInt(p[1], posInfoFromParser(p))

def p_agg_expr_id(p):
    """
    agg_expr : ID
    """
    p[0] = AggID(p[1], posInfoFromParser(p))
    
def p_agg_expr_agg(p):
    """
    agg_expr : agg_func ID
    """
    p[0] = AggFunc(p[1], posInfoFromParser(p), p[2])
    
def p_agg_expr_binop(p):
    """
    agg_expr : agg_expr PLUS agg_expr
             | agg_expr MINUS agg_expr
             | agg_expr TIMES agg_expr
    """
    p[0] = AggBinOp(posInfoFromParser(p), p[1], p[2], p[3])
    
def p_agg_expr_unop(p):
    """
    agg_expr : MINUS agg_expr %prec UMINUS
    """
    p[0] = AggUnOp(posInfoFromParser(p), p[1], p[2])
    
def p_missing_wait(p):
    """
    missing_spec : WAIT
    """
    p[0] = MissingWait(posInfoFromParser(p))

def p_missing_ignore(p):
    """
    missing_spec : IGNORE
    """
    p[0] = MissingIgnore(posInfoFromParser(p))

def p_missing_assume(p):
    """
    missing_spec : ASSUME agg_expr
    """
    p[0] = MissingAssume(posInfoFromParser(p), p[2])

def p_bufgroup_includes(p):
    """
    bg_includes_spec : empty
                     | INCLUDES ne_bg_includes_list
    """
    if(len(p)==2):
        p[0] = []
    else:
        p[0] = p[2]

def p_bufgroup_include_all(p):
    """
    bg_include : ID
               | ID '[' ALL ']'
    """
    p[0] = BGroupIncludeAll(posInfoFromParser(p), EventSourceRef(p[1], posInfoFromParserItem(p,1)))
    
def p_bufgroup_include_idx(p):
    """
    bg_include : ID '[' INT ']'
    """
    p[0] = BGroupIncludeIndex(posInfoFromParser(p), EventSourceRef(p[1], posInfoFromParserItem(p,1)), p[3])

def p_evsource_ref(p):
    """
    evsourceref : ID
                | ID '[' INT ']'
    """
    idx=0
    if(len(p)>2):
        idx=int(p[3])
    p[0] = EventSourceIndexedRef(EventSourceRef(p[1], posInfoFromParserItem(p,1)), posInfoFromParser(p), idx)

def p_match_fun_def(p):
    """
    match_fun_def : MATCH FUN ID opt_bracket_id_list stream_fields '=' ne_list_buff_match_exp
    """
    p[0] = MatchFun(p[3], posInfoFromParser(p), p[4], p[5], p[7])


# END advanced features

# BEGIN arbiter Specification
def p_arbiter_definition(p):
    """
    arbiter_definition : ARBITER ':' ID '{' arbiter_rule_sets '}'
    """
    p[0] = Arbiter(posInfoFromParser(p), StreamTypeRef(p[3], posInfoFromParserItem(p, 3)), p[5])

def p_arbiter_rule_sets_from_rules(p):
    """
    arbiter_rule_sets : arbiter_rule_list
    """
    p[0]=[RuleSet("default", posInfoFromParser(p), p[1])]

def p_arbiter_rule_sets_from_rule_sets(p):
    """
    arbiter_rule_sets : arbiter_rule_set_list
    """
    p[0]=p[1]

def p_arbiter_rule_set_list(p):
    """
    arbiter_rule_set_list : arbiter_rule_set
                          | arbiter_rule_set arbiter_rule_set_list
    """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[2]
        p[0].insert(0,p[1])


def p_arbiter_rule_set(p):
    """
    arbiter_rule_set : RULE SET ID '{' arbiter_rule_list '}'
    """
    #TypeChecker.insert_symbol(p[PARB_RULE_SET_NAME], ARBITER_RULE_SET)

    p[0] = RuleSet(p[3], posInfoFromParser(p), p[5])


def p_arbiter_rule_list(p):
    """
    arbiter_rule_list : empty
                      | arbiter_rule arbiter_rule_list
    """
    if len(p) == 2:
        p[0] = []
    else:
        p[0] = p[2]
        p[0].insert(0,p[1])

def p_arbiter_rule_match(p):
    """
    arbiter_rule : arbiter_cond BEGIN_CCODE c_arb_stmts CCODE_end
    """
    p[0] = ArbiterRule(posInfoFromParser(p), p[1], p[3])

def p_arbiter_rule_choice(p):
    """
    arbiter_rule : arbiter_choose '{' arbiter_rule_list '}'
    """
    p[0] = ArbiterChoiceRule(posInfoFromParser(p), p[1], p[3])

def p_arbiter_cond_always(p):
    """
    arbiter_cond : ALWAYS
    """
    p[0] = ArbiterAlwaysCondition(posInfoFromParser(p))

def p_arbiter_cond_match(p):
    """
    arbiter_cond : ON ne_list_buff_match_exp arbiter_where
    """
    p[0] = ArbiterMatchCondition(posInfoFromParser(p), p[2], p[3])
    
def p_arbiter_choose(p):
    """
    arbiter_choose : CHOOSE choose_direction ne_id_list FROM ID arbiter_where
    """
    p[0] = ArbiterChoice(posInfoFromParser(p), p[2], p[3], BufferGroupRef(p[5], posInfoFromParserItem(p,5)), p[6])

def p_arbiter_opt_number_int(p):
    """
    opt_number : INT
    """
    p[0] = int(p[1])

def p_arbiter_opt_number_empty(p):
    """
    opt_number : empty
    """
    p[0] = 1
def p_arbiter_opt_number_any(p):
    """
    opt_number : ALL
    """
    p[0]=-1

def p_arbiter_choose_direction_empty(p):
    """
    choose_direction : empty
    """
    p[0] = ChooseFirst(posInfoFromParser(p), -1)

def p_arbiter_choose_direction_first(p):
    """
    choose_direction : FIRST opt_number
    """
    p[0] = ChooseFirst(posInfoFromParser(p), p[2])

def p_arbiter_choose_direction_last(p):
    """
    choose_direction : LAST opt_number
    """
    p[0] = ChooseLast(posInfoFromParser(p), p[2])

def p_def_arbiter_where_empty(p):
    """
    arbiter_where : empty
    """
    p[0] = None

def p_def_arbiter_where(p):
    """
    arbiter_where : WHERE BEGIN_CCODE c_exprs CCODE_end
    """
    p[0] = p[3]

def p_buff_match_exprs(p):
    """
    ne_list_buff_match_exp : buffer_match_exp
                           | buffer_match_exp ',' ne_list_buff_match_exp
    """
    p[0]=p[1]
    if(len(p)>2):
        p[0]=p[0]+p[3]

def p_buff_match_exp(p):
    """
    buffer_match_exp : match_fun_call
                     | ev_buf_match
                     | arbiter_choose buffer_match_exp
    """
    p[0]=[p[1]]
    if(len(p)>2):
        p[0]=p[0]+p[2]

def p_id_or_int_id(p):
    """
    id_or_int : ID
    """
    p[0]=p[1]

def p_id_or_int_int(p):
    """
    id_or_int : INT
    """
    p[0]=int(p[1])

def p_buff_match_fun_call(p):
    """
    match_fun_call : ID opt_bracket_id_list '(' id_or_int_list ')'
    """
    p[0] = MatchFunCall(posInfoFromParser(p), MatchFunRef(p[1], posInfoFromParserItem(p,1)), p[2], p[4])

def p_buff_match_match(p):
    """
    ev_buf_match : evsourceref ':' ev_buf_match_state
    """
    p[0] = BufferMatch(posInfoFromParser(p), p[1], p[3])

def p_buff_match_state_nothing(p):
    """
    ev_buf_match_state : NOTHING
    """
    p[0] = MatchPatternNothing(posInfoFromParser(p))

def p_buff_match_state_done(p):
    """
    ev_buf_match_state : DONE
    """
    p[0] = MatchPatternDone(posInfoFromParser(p))

def p_buff_match_state_int(p):
    """
    ev_buf_match_state : INT
    """
    p[0] = MatchPatternSize(posInfoFromParser(p), int(p[1]))

def p_buff_match_state_match(p):
    """
    ev_buf_match_state : ev_match_list '|' ev_match_list
    """
    p[0] = MatchPatternEvents(posInfoFromParser(p), p[1], p[3])

def p_buff_ev_match_list(p):
    """
    ne_ev_match_list : ev_match
                     | ev_match ne_ev_match_list
    """
    p[0]=[p[1]]
    if(len(p)>2):
        p[0]=p[0]+p[2]

def p_ev_match(p):
    """
    ev_match : ID '(' id_list ')'
    """
    p[0]=MatchPatternEvent(posInfoFromParser(p), EventReference(p[1], posInfoFromParserItem(p,1)), p[3])

def p_ev_match_shared(p):
    """
    ev_match : SHARED '(' id_list ')'
    """
    p[0]=MatchPatternShared(posInfoFromParser(p), p[3])

def p_ev_match_ignored(p):
    """
    ev_match : '_'
    """
    p[0]=MatchPatternIgnored(posInfoFromParse(p))


# END arbiter Specification

# BEGIN monitor Specification


def p_monitor_definition(p):
    """
    monitor_definition : MONITOR monitor_bufsize '{' monitor_rule_list '}'
    """
    p[0] = Monitor(posInfoFromParser(p), p[2], p[4])

def p_monitor_bufsize_default(p):
    """
    monitor_bufsize : empty
                    | '(' ')'
    """
    p[0] = 1

def p_monitor_bufsize_size(p):
    """
    monitor_bufsize : '(' INT ')'
    """
    p[0]=int(p[2])

def p_monitor_rule_list(p):
    """
    monitor_rule_list : monitor_rule
                      | monitor_rule monitor_rule_list
    """
    p[0]=[p[1]]
    if(len(p)>2):
        p[0]=p[0]+p[2]


def p_monitor_rule(p):
    """
    monitor_rule : ON ID '(' id_list ')' monitor_where BEGIN_CCODE c_codes CCODE_end
    """
    p[0] = MonitorRule(posInfoFromParser(p), EventReference(p[2], posInfoFromParserItem(p,2)), p[4], p[6], p[8])

def p_monitor_where(p):
    """
    monitor_where : empty
                  | WHERE BEGIN_CCODE c_codes CCODE_end
    """
    if(len(p)>2):
        p[0] = p[3]
    else:
        p[0] = None

# END monitor Specification

def p_type_inner(p):
    """
    type : type_inner
    """
    p[0] = p[1]

def p_type_named(p):
    """
    type_inner : ID
    """
    p[0]=TypeNamed(posInfoFromParser(p), p[1])

def p_type_ptr(p):
    """
    type_inner : type_inner TIMES
    """
    p[0]=TypePointer(posInfoFromParser(p), p[1])
    

def p_type_arr(p):
    """
    type_inner : type_inner '[' ']'
    """
    p[0]=TypeArray(posInfoFromParser(p), p[1])
    

def p_expression_var(p):
    """
    expression : ID
    """
    p[0] = ExprVar(p[1], posInfoFromParser(p))

def p_expression_int(p):
    """
    expression : INT
    """
    p[0] = ExprInt(p[1], posInfoFromParser(p))

def p_expression_bool(p):
    """
    expression : BOOL
    """
    if(p[1]=="true"):
        p[0] = ExprTrue(posInfoFromParser(p))
    else:
        p[0] = ExprFalse(posInfoFromParser(p))

def p_expression_binop(p):
    """
    expression : expression DOUBLEQ expression
               | expression GEQ expression
               | expression LEQ expression
               | expression GT expression
               | expression LT expression
               | expression OR expression
               | expression AND expression
               | expression BAND expression
               | expression '|' expression
               | expression PLUS expression
               | expression MINUS expression
               | expression TIMES expression
    """
    p[0] = ExprBinOp(posInfoFromParser(p), p[2], p[1], p[3])

def p_expression_unop(p):
    """
    expression : MINUS expression
               | NOT expression
    """
    p[0] = ExprUnOp(posInfoFromParser(p), p[1], p[2])

def p_expression_ccode(p):
    """
    expression : c_codes
    """
    p[0] = p[1]

def p_expression_fieldacc(p):
    """
    expression : FIELD_ACCESS
    """
    p[0] = p[1]

def p_expression_parens(p):
    """
    expression : '(' expression ')'
    """
    p[0] = p[2]

def p_field_access(p):
    """
    FIELD_ACCESS : evsourceref '.' id
    """
    p[0] = FieldAccess(posInfoFromParser(p), p[1], p[3])


def p_error(p):
    if p is None:
        print(f"Syntax error, no additional information :(", file=sys.stderr)
    else:
        print(f"Syntax error at line {p.lineno} (value={p.value}, token={p.type}) .. {p}", file=sys.stderr)

def p_c_rawcode(p):
    """
    c_expr : CCODE_TOKEN
           | CCODE_OPAREN c_exprs CCODE_CPAREN
           | CCODE_OBRACE c_exprs CCODE_CBRACE
    c_arb_stmt : CCODE_TOKEN
               | CCODE_OPAREN c_arb_stmts CCODE_CPAREN
               | CCODE_OBRACE c_arb_stmts CCODE_CBRACE
    c_code : CCODE_TOKEN
           | CCODE_OPAREN c_codes CCODE_CPAREN
           | CCODE_OBRACE c_codes CCODE_CBRACE
    """
    if(len(p)==2):
        p[0]=CCode(posInfoFromParser(p), p[1])
    else:
        p[0]=p[2].mergeCode(CCode(posInfoFromParserItem(p,1), p[1]), False).mergeCode(CCode(posInfoFromParserItem(p,3),p[3]), True)

def p_c_rawcodes_empty(p):
    """
    c_exprs : empty
    c_arb_stmts : empty
    c_codes : empty
    """
    p[0] = CCodeEmpty(posInfoFromParser(p))

def p_c_rawcodes_ne(p):
    """
    c_exprs : c_expr c_exprs
    c_arb_stmts : c_arb_stmt c_arb_stmts
    c_codes : c_code c_codes
    """
    p[0] = p[1].merge(p[2], True)

def p_c_field(p):
    """
    c_expr : CCODE_FIELD
    c_arb_stmt : CCODE_FIELD
    """
    p[0]=CCodeField(posInfoFromParser(p), EventSourceIndexedRef(p[1][0], posInfoFromParserItem(p,1), p[1][1]), StreamFieldRef(p[1][2], posInfoFromParserItem(p,1)))

def p_c_astmt_yield(p):
    """
    c_arb_stmt : CCODE_YIELD c_expr_list CCODE_CPAREN CCODE_SEMICOLON
    """
    p[0]=CCodeYield(posInfoFromParser(p), EventReference(p[1], posInfoFromParserItem(p,1)), p[2])
    
def p_c_astmt_continue(p):
    """
    c_arb_stmt : CCODE_CONTINUE
    """
    p[0]=CCodeContinue(posInfoFromParser(p))

def p_c_astmt_switchto(p):
    """
    c_arb_stmt : CCODE_SWITCHTO
    """
    p[0]=CCodeSwitchTo(posInfoFromParser(p), RuleSetReference(p[1], posInfoFromParserItem(p,1)))


def p_c_astmt_drop(p):
    """
    c_arb_stmt : CCODE_DROP
    """
    p[0]=CCodeDrop(posInfoFromParser(p), p[1][0], EventSourceIndexedRef(p[1][1], posInfoFromParserItem(p,1), p[1][2]))


def p_c_astmt_remove(p):
    """
    c_arb_stmt : CCODE_REMOVE
    """
    p[0]=CCodeRemove(posInfoFromParser(p), EventSourceIndexedRef(p[1][0], posInfoFromParserItem(p,1), p[1][1]), BufferGroupRef(p[1][2], posInfoFromParserItem(p,1)))


def p_c_astmt_add(p):
    """
    c_arb_stmt : CCODE_ADD
    """
    p[0]=CCodeAdd(posInfoFromParser(p), EventSourceIndexedRef(p[1][0], posInfoFromParserItem(p,1), p[1][1]), BufferGroupRef(p[1][2], posInfoFromParserItem(p,1)))




# public interface
def parse_program(tokens, lexer, s: str):
    parser = yacc(debug=None)

    # Parse an expression
    ast = parser.parse(s, lexer=lexer, tracking=True)
    return ast
