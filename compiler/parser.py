
from ply.yacc import yacc
from type_checker import *
from utils import *
from parser_indices import *
from vamos import *

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
    # stream_name = p[3]
    # field_declarations = None
    # extends_node = None
    # if len(p) == 7:
    #     # STREAM TYPE ID '{' event_list '}'
    #     events_list = p[5]
    # elif len(p) == 8:
    #     # STREAM TYPE ID extends_node '{' event_list '}'
    #     #    1     2   3      4        5      6       7
    #     extends_node = p[4]
    #     events_list = p[6]
    # elif len(p) == 11:
    #     # STREAM TYPE ID '(' list_field_decl ')' extends_node '{' event_list '}'
    #     #   1      2   3  4         5         6       7        8      9       10
    #     field_declarations = p[5]
    #     extends_node = p[7]
    #     events_list = p[9]
    # else:
    #     # STREAM TYPE ID '(' list_field_decl ')' '{' event_list '}'
    #     #   1      2   3  4        5          6   7      8       9
    #     assert len(p) == 10
    #     field_declarations = p[5]
    #     events_list = p[8]

    # p[0] = ("stream_type", stream_name, field_declarations, extends_node, events_list)
    # params = []
    # if field_declarations is not None:
    #     get_parameters_types_field_decl(field_declarations, params)
    # TypeChecker.insert_into_args_table(stream_name, STREAM_TYPE_NAME, params)

    # TypeChecker.insert_event_list(stream_name, events_list)

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
    ne_id_list : ID
               | ID ',' ne_id_list
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
    aggregate_field_decl : ID '=' agg_expr
    """
    p[0] = AggFieldDecl(p[1], posInfoFromParser(p), p[3])

# END event streams

# BEGIN performance layer specifications

def p_stream_processor(p):
    """
    stream_processor : STREAM PROCESSOR ID stream_fields ':' ID opt_expression_list ARROW ID opt_expression_list processor_extends_spec '{' processor_rule_list custom_hole '}'
    """
    p[0]=StreamProcessor(p[3], posInfoFromParser(p), p[4], ParameterizedRef(StreamTypeRef(p[6], posInfoFromParserItem(p,6)), p[7], posInfoFromParserItem(p,6).Combine(posInfoFromParserItem(p,7), True)), ParameterizedRef(StreamTypeRef(p[9], posInfoFromParserItem(p,9)), p[10], posInfoFromParserItem(p,9).Combine(posInfoFromParserItem(p,10), True)), p[11], p[13], [14])
    # name_with_args = p[3]
    # input_type = p[5]
    # output_type = p[7]
    # extends_node = None
    # perf_layer_rule_list = None
    # if len(p) == 11:
    #     # STREAM PROCESSOR name_with_args ':' name_with_args ARROW name_with_args '{' perf_layer_rule_list '}'
    #     #   1        2           3         4          5      6           7         8           9           10
    #     perf_layer_rule_list = p[9]
    #     # TypeChecker.assert_symbol_type(p[PEVENT_SOURCE_INPUT_TYPE], STREAM_TYPE_NAME)
    #     # TypeChecker.assert_symbol_type(p[PEVENT_SOURCE_OUTPUT_TYPE], STREAM_TYPE_NAME)
    #     # TypeChecker.check_args_are_primitive(p[PEVENT_SOURCE_OUTPUT_TYPE])
    #     # TypeChecker.check_args_are_primitive(p[PEVENT_SOURCE_INPUT_TYPE])
    # else:
    #     assert len(p) == 12
    #     # STREAM PROCESSOR name_with_args ':' name_with_args ARROW name_with_args extends_node '{' perf_layer_rule_list '}'
    #     #   1        2           3         4          5      6           7              8       9           10
    #     extends_node = p[8]
    #     perf_layer_rule_list = p[10]
    # p[0] = (
    #     "stream_processor",
    #     name_with_args,
    #     input_type,
    #     output_type,
    #     extends_node,
    #     perf_layer_rule_list,
    # )
    # stream_proc_name, args_stream_proc = get_name_with_args(name_with_args)
    # TypeChecker.insert_into_args_table(
    #     stream_proc_name, STREAM_PROCESSOR_NAME, args_stream_proc
    # )

    # input_stream_name, c_args_input = get_name_args_count(input_type)
    # output_stream_name, c_args_output = get_name_args_count(output_type)
    # # TypeChecker.check_args_are_primitive(input_stream_name)
    # # TypeChecker.check_args_are_primitive(output_stream_name)

    # TypeChecker.assert_num_args_match(input_stream_name, c_args_input)
    # TypeChecker.assert_num_args_match(output_stream_name, c_args_output)

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

# def p_hole_attribute_legacy(p):
#     """
#     hole_attribute : ID ID "=" agg_func '(' agg_func_args ')'
#     """
#     p[0] = HoleAttribute(p[2], posInfoFromParser(p), p[1], p[4], p[6])

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
    p[0] = EventReference(p[1], posInfoFromParser(p))

def p_agg_arg_field(p):
    """
    agg_arg : FIELD_ACCESS
    """
    p[0] = AggFieldAccess(p[1], posInfoFromParser(p))

def p_processor_rule(p):
    """
    processor_rule : ON ID opt_id_list creates_part performance_action
    """
    p[0] = ProcessorRule(posInfoFromParser(p), EventReference(p[2], posInfoFromParserItem(p, 2)), p[3], p[4], p[5])

    # event_name, c_event_args = get_name_args_count(on_event)
    # TypeChecker.assert_symbol_type(event_name, EVENT_NAME)
    # TypeChecker.assert_num_args_match(p[PPERF_LAYER_EVENT][1], c_event_args)

    # TODO: Missing more type checking for the rest of parameters

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
    p[0] = CreatesSpec(posInfoFromParser(p), StreamTypeRef(p[2], posInfoFromParserItem(p,2)), p[3], p[4], p[6], p[7])
    

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
        p[0]=p[3]


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
    # if len(p) == 2:
    #     if p[1] == "drop":
    #         p[0] = ("perf_act_drop", p[PPERF_ACTION_DROP])
    #     else:
    #         assert p[1] == "forward"
    #         p[0] = ("perf_act_forward", p[PPERF_ACTION_DROP])
    # else:
    #     TypeChecker.assert_symbol_type(p[PPERF_ACTION_FORWARD_EVENT], EVENT_NAME)
    #     length_exprs = get_count_list_expr(p[PPERF_ACTION_FORWARD_EXPRS])
    #     TypeChecker.assert_num_args_match(p[PPERF_ACTION_FORWARD_EVENT], length_exprs)
    #     p[0] = (
    #         "perf_act_forward",
    #         p[PPERF_ACTION_FORWARD_EVENT],
    #         p[PPERF_ACTION_FORWARD_EXPRS],
    #     )
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


def p_event_source(p):
    """
    event_source : dyn_flag EVENT SOURCE ID stream_fields ':' ID stream_init_expr TO connection_kind include_spec
    """
    p[0] = EventSource(p[4], posInfoFromParser(p), p[1], p[5], StreamTypeRef(p[7], posInfoFromParserItem(p,7)), p[8], p[10], p[11])


# def p_event_source_decl(p):
#     """
#     event_source_decl : name_with_args
#                       | name_with_args '[' INT ']'
#     """
#     event = p[1]
#     arg = None

#     if len(p) == 5:
#         arg = p[3]
#     else:
#         assert len(p) == 2
#     p[0] = ("event-decl", event, arg)
#     name, args = get_name_with_args(event)
#     TypeChecker.insert_into_args_table(name, EVENT_SOURCE_NAME, args)



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
    # TypeChecker.insert_symbol(buffer_group_name, BUFFER_GROUP_NAME)
    # TypeChecker.assert_symbol_type(stream_type, STREAM_TYPE_NAME)
    # if includes is not None:
    #     TypeChecker.assert_symbol_type(includes, EVENT_SOURCE_NAME)
    # TypeChecker.add_buffer_group_data(p[0])

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
    bg_include : evsourceref
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

    # match_fun_name = p[3]
    # arg1 = None
    # arg2 = None
    # if len(p) == 12:
    #     #  MATCH FUN ID '[' listids ']' '(' listids ')' '=' list_buff_match_exp
    #     arg1 = p[5]
    #     arg2 = p[8]
    #     buffer_match_expr = p[11]
    # elif p[5] == "]":
    #     # MATCH FUN ID '[' ']' '(' listids ')' '=' list_buff_match_exp
    #     arg2 = p[7]
    #     buffer_match_expr = p[10]
    # else:
    #     assert len(p) == 11
    #     # MATCH FUN ID '[' listids ']' '('  ')' '=' list_buff_match_exp
    #     arg1 = p[5]
    #     buffer_match_expr = p[10]
    # p[0] = ("match_fun_def", match_fun_name, arg1, arg2, buffer_match_expr)

    # # TypeChecker.add_match_fun_data(p[0])
    # if arg2 is not None:
    #     ids = []
    #     get_list_ids(arg2, ids)
    #     # TypeChecker.insert_into_args_table(match_fun_name, MATCH_FUN_NAME, ids)
    # # else:
    # # TypeChecker.insert_symbol(match_fun_name, MATCH_FUN_NAME)
    # if arg1 is not None:
    #     ids = []
    #     get_list_ids(arg1, ids)
    #     # TypeChecker.logical_copies[match_fun_name] = ids # TODO: maybe this should be in a diff. data structure
    #     # for id in ids:
    #     #     TypeChecker.insert_symbol(id, EVENT_SOURCE_NAME)


# END advanced features

# BEGIN arbiter Specification
def p_arbiter_definition(p):
    """
    arbiter_definition : ARBITER ':' ID '{' arbiter_rule_sets '}'
    """
    p[0] = Arbiter(posInfoFromParser(p), StreamTypeRef(p[3], posInfoFromParserItem(p, 3)), p[5])
    # # TypeChecker.assert_symbol_type(p[ARBITER_OUTPUT_TYPE], STREAM_TYPE_NAME)
    # if len(p) == 6:
    #     p[0] = ("arbiter_def", p[ARBITER_OUTPUT_TYPE], None)
    # else:
    #     if (
    #         p[ARBITER_RULE_SET_LIST][0] == "arb_rule_set_l"
    #         or p[ARBITER_RULE_SET_LIST][0] == "arbiter_rule_set"
    #     ):
    #         p[0] = ("arbiter_def", p[ARBITER_OUTPUT_TYPE], p[ARBITER_RULE_SET_LIST])
    #     else:
    #         arbiter_rule_set_l = (
    #             "arbiter_rule_set",
    #             "default",
    #             p[ARBITER_RULE_SET_LIST],
    #         )
    #         p[0] = ("arbiter_def", p[ARBITER_OUTPUT_TYPE], arbiter_rule_set_l)

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

# def p_arbiter_rule(p):
#     """
#     arbiter_rule : ON list_buff_match_exp WHERE BEGIN_CCODE ccode_l_where_expression BEGIN_CCODE arbiter_rule_stmt_list
#                  | ON list_buff_match_exp BEGIN_CCODE arbiter_rule_stmt_list 
#                  | ALWAYS BEGIN_CCODE CCODE_TOKEN
#                  | CHOOSE listids arb_choose_middle_part '{' arbiter_rule_list '}'
#                  | CHOOSE choose_order listids arb_choose_middle_part '{' arbiter_rule_list '}'
#     """
#     if p[1] == "always":
#         choose_count = None
#         assert len(p) == 4
#         p[0] = ("always", ("base_where_expr", "true"), p[3])
#         TypeChecker.add_always_code(p[0])
#     elif p[1] == "on":
#         if len(p) == 5:
#             p[0] = ("arbiter_rule1", p[2], None, p[4])
#         else:
#             # ON list_buff_match_exp WHERE BEGIN_CCODE ccode_l_where_expression BEGIN_CCODE arbiter_rule_stmt_list
#             # 1           2            3           4                    5         6                7
#             p[0] = ("arbiter_rule1", p[2], p[5], p[7])
#         choose_count = None
#     else:
#         if len(p) == 8:
#             # CHOOSE choose_order listids arb_choose_middle_part '{' arbiter_rule_list '}'
#             #    1      2            3               4            5          6          7

#             middle_part = p[4]
#             p[0] = ("arbiter_rule2", p[2], p[3], middle_part[1], middle_part[2], p[6])
#             choose_count = p[2][2]
#         else:
#             assert len(p) == 7
#             # CHOOSE listids arb_choose_middle_part '{' arbiter_rule_list '}'
#             #   1       2            3               4          5          6
#             middle_part = p[3]
#             p[0] = ("arbiter_rule2", None, p[2], middle_part[1], middle_part[2], p[5])
#             choose_count = get_count_list_ids(p[2])

#     if choose_count is not None:
#         TypeChecker.max_choose_size = max(TypeChecker.max_choose_size, choose_count)


# def p_ccode_l_where_expression(p):
#     """
#     ccode_l_where_expression : CCODE_TOKEN
#                              | FIELD_ACCESS ';'
#                              | CCODE_TOKEN ccode_l_where_expression
#                              | FIELD_ACCESS ';' ccode_l_where_expression
#     """
#     if len(p) == 2:
#         p[0] = ("base_where_expr", p[1])
#     elif len(p) == 3:
#         if p[2] == ";":
#             p[0] = ("base_where_expr", p[1])
#         else:
#             p[0] = ("l_where_expr", ("base_where_expr", p[1]), p[2])
#     else:
#         if p[2] == ";":
#             p[0] = ("l_where_expr", ("base_where_expr", p[1]), p[3])
#         else:
#             p[0] = ("l_where_expr", ("base_where_expr", p[1]), p[2])


# def p_arbiter_choose_order(p):
#     """
#     choose_order : FIRST INT
#                  | LAST INT
#                  | FIRST
#                  | LAST
#     """

#     arg1 = p[1]

#     if len(p) > 2:
#         arg2 = p[2]
#     else:
#         arg2 = 1

#     p[0] = ("choose-order", arg1, arg2)

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

# def p_buffer_match_exp(p):
#     """
#     buffer_match_exp : ID '[' listids ']' '(' list_var_or_integer ')'
#                      | ID '[' ']' '(' list_var_or_integer ')'
#                      | ID '[' listids ']' '(' ')'
#                      | ID '(' ')'
#                      | CHOOSE choose_order listids FROM ID
#                      | CHOOSE listids FROM ID
#                      | event_src_ref ':' ev_src_status
#                      | event_src_ref ':' '|' list_event_calls
#                      | event_src_ref ':' list_event_calls '|'
#                      | event_src_ref ':' list_event_calls '|' list_event_calls
#     """

#     if p[2] == "[":
#         # TypeChecker.assert_symbol_type(p[1], MATCH_FUN_NAME)
#         arg1 = None
#         arg2 = None
#         if len(p) == 7:
#             arg1 = p[3]
#             arg2 = p[6]
#         else:
#             assert len(p) == 6
#             if p[3] == "]":
#                 arg2 = p[5]
#             else:
#                 arg1 = p[3]
#         p[0] = ("buff_match_exp-args", p[1], arg1, arg2)

#     elif p[2] == "(":
#         TypeChecker.assert_symbol_type(p[1], MATCH_FUN_NAME)
#         p[0] = ("buff_match_exp-args", p[1], None, None)
#     elif p[1] == "choose":
#         choose_order = None
#         if len(p) == 6:
#             # CHOOSE choose_order listids FROM ID
#             #   1           2         3     4   5
#             choose_order = p[2]
#             args = p[3]
#             buffer_name = p[5]
#         else:
#             args = p[2]
#             buffer_name = p[4]
#         p[0] = ("buff_match_exp-choose", choose_order, args, buffer_name)
#         # TypeChecker.assert_symbol_type(p[4], BUFFER_GROUP_NAME)
#     elif len(p) == 4:
#         # TypeChecker.assert_symbol_type(p[1][1], EVENT_SOURCE_NAME)
#         p[0] = ("buff_match_exp", p[PBUFFER_MATCH_EV_NAME], p[PBUFFER_MATCH_ARG1])
#     elif len(p) == 5:
#         # TODO: fix this check
#         # TypeChecker.assert_symbol_type(p[1][1], EVENT_SOURCE_NAME)
#         p[0] = (
#             "buff_match_exp",
#             p[PBUFFER_MATCH_EV_NAME],
#             p[PBUFFER_MATCH_ARG1],
#             p[PBUFFER_MATCH_ARG2],
#         )
#     else:
#         TypeChecker.assert_symbol_type(p[1][1], EVENT_SOURCE_NAME)
#         p[0] = (
#             "buff_match_exp",
#             p[PBUFFER_MATCH_EV_NAME],
#             p[PBUFFER_MATCH_ARG1],
#             "|",
#             p[PBUFFER_MATCH_ARG3],
#         )

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

# def p_list_event_calls(p):
#     """
#     list_event_calls : ID '(' listids ')'
#                      | ID '(' ')'
#                      | ID '(' ')' list_event_calls
#                      | ID '(' listids  ')' list_event_calls
#     """

#     # TODO: what is E^H
#     # TypeChecker.assert_symbol_type(p[PLIST_EV_CALL_EV_NAME], EVENT_NAME)
#     if len(p) == 4:
#         # ID '(' ')'
#         p[0] = ("ev_call", p[PLIST_EV_CALL_EV_NAME], None)
#     elif len(p) == 5:
#         if p[3] == ")":
#             # ID '(' ')' list_event_calls
#             p[0] = ("list_ev_calls", p[PLIST_EV_CALL_EV_NAME], None, p[4])
#         else:
#             # ID '(' listids ')'
#             p[0] = ("ev_call", p[PLIST_EV_CALL_EV_NAME], p[PLIST_EV_CALL_EV_PARAMS])
#             list_ids_length = get_count_list_ids(p[PLIST_EV_CALL_EV_PARAMS])
#             # TypeChecker.assert_num_args_match(p[PLIST_EV_CALL_EV_NAME], list_ids_length)
#     else:
#         assert len(p) == 6
#         # ID '(' listids  ')' list_event_calls
#         p[0] = (
#             "list_ev_calls",
#             p[PLIST_EV_CALL_EV_NAME],
#             p[PLIST_EV_CALL_EV_PARAMS],
#             p[PLIST_EV_CALL_TAIL],
#         )
#         list_ids_length = get_count_list_ids(p[PLIST_EV_CALL_EV_PARAMS])
#         # TypeChecker.assert_num_args_match(p[PLIST_EV_CALL_EV_NAME], list_ids_length)


# def p_arbiter_rule_stmt_list(p):
#     """
#     arbiter_rule_stmt_list : ccode_statement_list
#                            | ccode_statement_list arbiter_rule_stmt_list
#     """

#     if len(p) == 2:
#         p[0] = p[PLIST_BASE_CASE]
#     else:
#         p[0] = ("arb_rule_stmt_l", p[PLIST_BASE_CASE], p[PLIST_TAIL])


# def p_ccode_statement_list(p):
#     """
#     ccode_statement_list : CCODE_TOKEN
#                          | CCODE_TOKEN arbiter_rule_stmt ';'
#                          | arbiter_rule_stmt ';'
#                          | arbiter_rule_stmt ';' CCODE_TOKEN
#                          |
#     """

#     if len(p) == 1:
#         #
#         p[0] = ("ccode_statement_l", "")
#     elif len(p) == 2:
#         # CCODE_TOKEN
#         p[0] = ("ccode_statement_l", p[PCODE_STMT_LIST_TOKEN1])
#     elif len(p) == 3:
#         # arbiter_rule_stmt ';'
#         p[0] = (
#             "ccode_statement_l",
#             p[PCODE_STMT_LIST_TOKEN1],
#             p[PCODE_STMT_LIST_TOKEN2],
#         )
#     else:
#         assert len(p) == 4
#         # CCODE_TOKEN arbiter_rule_stmt ';'
#         # arbiter_rule_stmt ';' CCODE_TOKEN
#         p[0] = (
#             "ccode_statement_l",
#             p[PCODE_STMT_LIST_TOKEN1],
#             p[PCODE_STMT_LIST_TOKEN2],
#             p[PCODE_STMT_LIST_TOKEN3],
#         )


# def p_arbiter_rule_stmt(p):
#     """
#     arbiter_rule_stmt : YIELD ID '(' expression_list ')'
#                       | YIELD ID '(' ')'
#                       | SWITCH TO ID
#                       | CONTINUE
#                       | DROP INT FROM event_src_ref
#                       | REMOVE ID FROM event_src_ref
#                       | ADD ID FROM event_src_ref
#                       | FIELD_ACCESS
#     """

#     if p[1] == "yield":
#         if len(p) == 6:
#             p[0] = (
#                 "yield",
#                 p[PARB_RULE_STMT_YIELD_EVENT],
#                 p[PARB_RULE_STMT_YIELD_EXPRS],
#             )
#         else:
#             assert len(p) == 5
#             p[0] = ("yield", p[PARB_RULE_STMT_YIELD_EVENT], None)
#         # TypeChecker.assert_symbol_type(p[PARB_RULE_STMT_YIELD_EVENT], EVENT_NAME)
#         # count_expr_list = get_count_list_expr(p[PARB_RULE_STMT_YIELD_EXPRS])
#         # TypeChecker.assert_num_args_match(p[PARB_RULE_STMT_YIELD_EVENT], count_expr_list)
#     elif p[1] == "add" or p[1] == "remove":
#         p[0] = (p[1], p[2], p[4])
#     elif len(p) == 5:
#         assert p[1] == "drop"
#         p[0] = ("drop", p[PARB_RULE_STMT_DROP_INT], p[PARB_RULE_STMT_DROP_EV_SOURCE])
#         event_source_name = p[PARB_RULE_STMT_DROP_EV_SOURCE][1]
#         # TypeChecker.assert_symbol_type(event_source_name, EVENT_SOURCE_NAME)
#     elif len(p) == 2:
#         if p[0] == "continue":
#             p[0] = "continue"
#         else:
#             p[0] = p[1]
#     else:
#         assert p[1] == "switch"
#         p[0] = ("switch", p[PARB_RULE_STMT_SWITCH_ARB_RULE])


# END arbiter Specification

# BEGIN monitor Specification


def p_monitor_definition(p):
    """
    monitor_definition : MONITOR monitor_bufsize '{' monitor_rule_list '}'
    """
    p[0] = Monitor(posInfoFromParser(p), p[2], p[4])
    # monitor_rule_list = None
    # if len(p) == 7:
    #     TypeChecker.monitor_buffer_size = int(p[3])
    # elif len(p) == 6 or len(p) == 4:
    #     pass
    # elif len(p) == 8:
    #     TypeChecker.monitor_buffer_size = int(p[3])
    #     monitor_rule_list = p[6]
    # else:
    #     assert len(p) == 5
    #     monitor_rule_list = p[3]
    # p[0] = ("monitor_def", monitor_rule_list)

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
    # # ON ID '(' listids ')' WHERE BEGIN_CCODE expression BEGIN_CCODE CCODE_TOKEN
    # #  1  2  3    4      5   6       7            8          9          10

    # if p[4] == ")":
    #     listids = None
    #     expression = p[7]
    #     code = p[9]
    # else:
    #     listids = p[4]
    #     expression = p[8]
    #     code = p[10]
    # # TypeChecker.assert_symbol_type(p[PMONITOR_RULE_EV_NAME], EVENT_NAME)
    # # if listids:
    # # TypeChecker.assert_num_args_match(p[PMONITOR_RULE_EV_NAME], get_count_list_ids(p[PMONITOR_RULE_EV_ARGS]))
    # p[0] = ("monitor_rule", p[2], listids, expression, code)

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


# def p_extends_node(p):
#     """
#     extends_node : EXTENDS name_with_args
#     """

#     if len(p) == 3:
#         p[0] = ("extends-node", p[2])
#     else:
#         assert False


# def p_name_with_args(p):
#     """
#     name_with_args : ID '(' expression_list ')'
#                    | ID '(' list_field_decl ')'
#                    | ID
#                    | ID '(' ')'
#                    | FORWARD
#     """
#     if len(p) == 2:
#         p[0] = p[1]
#     elif len(p) == 4:
#         p[0] = ("name-with-args", p[1], None)
#     else:
#         p[0] = ("name-with-args", p[1], p[3])

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
    FIELD_ACCESS : ID '.' ID
                 | ID '[' INT ']' '.' ID
    """

    stream = p[1]
    index = None
    field = None
    if len(p) > 4:
        assert len(p) == 7
        index = p[3]
        field = p[6]
    else:
        assert len(p) == 4
        field = p[3]
    p[0] = ("field_access", stream, index, field)


def p_error(p):
    print(f"Syntax error at line {p.lineno} (value={p.value}, token={p.type})")

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
