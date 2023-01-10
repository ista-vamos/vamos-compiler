import ply.lex as lex
from ply.yacc import yacc
from lexer import MyLexer
from type_checker import *
from utils import *
from tokens import *
from parser_indices import *


# this is the entry point
def p_main_program(p):
    """
    main_program : components arbiter_definition monitor_definition
    """
    p[0] = ("main_program", p[1], p[2], p[3])


def p_components(p):
    """
    components : component components
               | component
    """

    if len(p) == 2:
        p[0] = p[1]
    else:
        assert len(p) == 3
        p[0] = ("components", p[1], p[2])


def p_component(p):
    """
    component : stream_type
              | event_source
              | stream_processor
              | buff_group_def
              | match_fun_def
              | GLOBALS '{' arbiter_rule_stmt_list '}'
              | GLOBALS BEGIN_CCODE arbiter_rule_stmt_list
              | STARTUP '{' CCODE_TOKEN '}'
              | STARTUP BEGIN_CCODE CCODE_TOKEN
              | CLEANUP '{' CCODE_TOKEN '}'
              | CLEANUP BEGIN_CCODE CCODE_TOKEN
    """

    if p[1] not in ["globals", "startup", "cleanup"]:
        p[0] = p[1]
    else:
        if len(p) == 3:
            p[0] = (p[1], p[2])
        else:
            p[0] = (p[1], p[3])


# BEGIN event streams
def p_stream_type(p):
    """
    stream_type : STREAM TYPE ID '(' list_field_decl ')' extends_node '{' event_list '}'
                | STREAM TYPE ID '(' list_field_decl ')' '{' event_list '}'
                | STREAM TYPE ID extends_node '{' event_list '}'
                | STREAM TYPE ID '{' event_list '}'
    """
    stream_name = p[3]
    field_declarations = None
    extends_node = None
    if len(p) == 7:
        # STREAM TYPE ID '{' event_list '}'
        events_list = p[5]
    elif len(p) == 8:
        # STREAM TYPE ID extends_node '{' event_list '}'
        #    1     2   3      4        5      6       7
        extends_node = p[4]
        events_list = p[6]
    elif len(p) == 11:
        # STREAM TYPE ID '(' list_field_decl ')' extends_node '{' event_list '}'
        #   1      2   3  4         5         6       7        8      9       10
        field_declarations = p[5]
        extends_node = p[7]
        events_list = p[9]
    else:
        # STREAM TYPE ID '(' list_field_decl ')' '{' event_list '}'
        #   1      2   3  4        5          6   7      8       9
        assert len(p) == 10
        field_declarations = p[5]
        events_list = p[8]

    p[0] = ("stream_type", stream_name, field_declarations, extends_node, events_list)
    params = []
    if field_declarations is not None:
        get_parameters_types_field_decl(field_declarations, params)
    TypeChecker.insert_into_args_table(stream_name, STREAM_TYPE_NAME, params)

    TypeChecker.insert_event_list(stream_name, events_list)


def p_event_declaration_list(p):
    """
    event_list : event_decl ';'
               | event_decl ';' event_list
    """
    if len(p) == 3:
        p[0] = p[PLIST_BASE_CASE]
    else:
        assert len(p) == 4
        p[0] = ("event_list", p[PLIST_BASE_CASE], p[PLIST_TAIL_WITH_SEP])


def p_event_declaration(p):
    """
    event_decl : ID '(' list_field_decl ')'
               | ID '(' ')'
               | ID '(' list_field_decl ')' CREATES ID
               | ID '(' ')' CREATES ID
    """

    event_params_token = None
    creates_stream = None
    params = []
    if len(p) == 5 or len(p) == 7:
        event_params_token = p[PEVENT_PARAMS_LIST]
        get_parameters_types_field_decl(p[PEVENT_PARAMS_LIST], params)
    if len(p) == 7:
        creates_stream = p[6]
    elif len(p) == 6:
        creates_stream = p[5]

    # Type checker
    # TypeChecker.insert_into_args_table(p[PEVENT_NAME], EVENT_NAME, params)
    p[0] = ("event_decl", p[PEVENT_NAME], event_params_token, creates_stream)


def p_field_declaration_list(p):
    """
    list_field_decl : field_decl
                    | field_decl ',' list_field_decl
    """
    if len(p) == 2:
        p[0] = p[PLIST_BASE_CASE]
    else:
        assert len(p) == 4
        p[0] = ("list_field_decl", p[PLIST_BASE_CASE], p[PLIST_TAIL_WITH_SEP])


def p_field_declaration(p):
    """
    field_decl : ID ':' type
    """
    p[0] = ("field_decl", p[PFIELD_NAME], p[PFIELD_TYPE])


# END event streams

# BEGIN performance layer specifications


def p_stream_processor(p):
    """
    stream_processor : STREAM PROCESSOR name_with_args ':' name_with_args right_arrow name_with_args extends_node '{' processor_rule_list '}'
                 | STREAM PROCESSOR name_with_args ':' name_with_args right_arrow name_with_args '{' processor_rule_list '}'
    """
    name_with_args = p[3]
    input_type = p[5]
    output_type = p[7]
    extends_node = None
    perf_layer_rule_list = None
    if len(p) == 11:
        # STREAM PROCESSOR name_with_args ':' name_with_args right_arrow name_with_args '{' perf_layer_rule_list '}'
        #   1        2           3         4          5            6           7         8           9           10
        perf_layer_rule_list = p[9]
        # TypeChecker.assert_symbol_type(p[PEVENT_SOURCE_INPUT_TYPE], STREAM_TYPE_NAME)
        # TypeChecker.assert_symbol_type(p[PEVENT_SOURCE_OUTPUT_TYPE], STREAM_TYPE_NAME)
        # TypeChecker.check_args_are_primitive(p[PEVENT_SOURCE_OUTPUT_TYPE])
        # TypeChecker.check_args_are_primitive(p[PEVENT_SOURCE_INPUT_TYPE])
    else:
        assert len(p) == 12
        # STREAM PROCESSOR name_with_args ':' name_with_args right_arrow name_with_args extends_node '{' perf_layer_rule_list '}'
        #   1        2           3         4          5            6           7              8       9           10
        extends_node = p[8]
        perf_layer_rule_list = p[10]
    p[0] = (
        "stream_processor",
        name_with_args,
        input_type,
        output_type,
        extends_node,
        perf_layer_rule_list,
    )
    stream_proc_name, args_stream_proc = get_name_with_args(name_with_args)
    TypeChecker.insert_into_args_table(
        stream_proc_name, STREAM_PROCESSOR_NAME, args_stream_proc
    )

    input_stream_name, c_args_input = get_name_args_count(input_type)
    output_stream_name, c_args_output = get_name_args_count(output_type)
    # TypeChecker.check_args_are_primitive(input_stream_name)
    # TypeChecker.check_args_are_primitive(output_stream_name)

    TypeChecker.assert_num_args_match(input_stream_name, c_args_input)
    TypeChecker.assert_num_args_match(output_stream_name, c_args_output)


def p_right_arrow(p):
    """
    right_arrow : '-' '>'
    """
    p[0] = ("right_arrow", "->")


def p_processor_rule_list(p):
    """
    processor_rule_list : custom_hole
                        | processor_rule
                        | processor_rule ';'
                        | processor_rule ';' processor_rule_list
    """
    if len(p) < 4:
        assert len(p) > 1
        p[0] = p[1]
    else:
        assert len(p) == 4
        p[0] = ("perf_layer_list", p[PLIST_BASE_CASE], p[3])


def p_custom_hole(p):
    """
    custom_hole : ID '{' list_hole_attributes '}'
    """

    p[0] = ("custom_hole", p[1], p[3])


def p_list_hole_attributes(p):
    """
    list_hole_attributes : hole_attribute ';'
                         | hole_attribute ';' list_hole_attributes
    """
    if len(p) == 3:
        p[0] = p[1]
    else:
        p[0] = ("l-hole-attributes", p[1], p[3])


def p_hole_attribute(p):
    """
    hole_attribute : ID ID "=" agg_func
    """

    p[0] = ("hole-attribute", p[1], p[2], p[4])


def p_aggfunc(p):
    """
    agg_func : COUNT '(' agg_func_params ')'
             | MIN '(' agg_func_params ')'
             | MAX '(' agg_func_params ')'
    """
    p[0] = ("agg_func", p[1], p[3])


def p_agg_func_params(p):
    """
    agg_func_params : '*'
                    | list_events_hole
    """
    p[0] = p[1]


def p_list_events_hole(p):
    """
    list_events_hole : event_hole
                     | event_hole ',' list_events_hole
    """

    if len(p) == 2:
        p[0] = p[1]
    else:
        assert len(p) == 4
        p[0] = ("l-events-hole", p[1], p[3])


def p_event_hole(p):
    """
    event_hole : ID
               | FIELD_ACCESS
    """

    p[0] = ("event_hole", p[1])


def p_processor_rule(p):
    """
    processor_rule : ON name_with_args performance_match
                    | ON name_with_args creates_part process_using_part processor_rule_tail performance_match
    """

    on_event = p[2]
    creates_at_most = None
    process_using = None
    include_in = None
    if len(p) == 4:
        # ON name_with_args performance_match
        stream_name = None
        connection_kind = None
        performance_match = p[3]
    else:
        assert len(p) == 7

        creates_part = p[3]
        assert creates_part[0] == "creates-part"
        creates_at_most = creates_part[1]

        process_using_part = p[4]
        assert process_using_part[0] == "process-using-part"
        stream_name = process_using_part[1]
        process_using = process_using_part[2]

        include_part = p[5]
        assert include_part[0] == "proc-rule-tail"
        connection_kind = include_part[1]
        include_in = include_part[2]

        performance_match = p[6]

    p[0] = (
        "perf_layer_rule",
        on_event,
        creates_at_most,
        stream_name,
        process_using,
        connection_kind,
        performance_match,
        include_in,
    )

    # event_name, c_event_args = get_name_args_count(on_event)
    # TypeChecker.assert_symbol_type(event_name, EVENT_NAME)
    # TypeChecker.assert_num_args_match(p[PPERF_LAYER_EVENT][1], c_event_args)

    # TODO: Missing more type checking for the rest of parameters


def p_creates_part(p):
    """
    creates_part : CREATES AT MOST INT
                 | CREATES
    """
    if len(p) > 2:
        p[0] = ("creates-part", p[4])
    else:
        p[0] = ("creates-part", None)


def p_process_using_part(p):
    """
    process_using_part : ID
                       | ID PROCESS USING name_with_args
    """
    process_using = None
    if len(p) > 2:
        process_using = p[4]
    p[0] = ("process-using-part", p[1], process_using)


def p_processor_rule_tail(p):
    """
    processor_rule_tail : TO connection_kind
                        | TO connection_kind INCLUDE IN ID
    """
    conn_kind = p[2]
    include_in = None
    if len(p) > 3:
        include_in = p[5]
    p[0] = ("proc-rule-tail", conn_kind, include_in)


def p_performance_match(p):
    """
    performance_match : performance_action
                      | IF '(' expression ')' THEN performance_match ELSE performance_match
    """
    if len(p) == 2:
        p[0] = ("perf_match1", p[PPERF_MATCH_ACTION])
    else:
        # IF ( expression ) THEN performance_match ELSE performance_match
        # 1  2      3     4   5          6           7          8
        assert len(p) == 8
        p[0] = (
            "perf_match2",
            p[PPERF_MATCH_EXPRESSION],
            p[PPERF_MATCH_TRUE_PART],
            p[PPERF_MATCH_FALSE_PART],
        )


def p_performance_action(p):
    """
    performance_action : DROP
                       | FORWARD ID '(' expression_list ')'
                       | FORWARD
    """
    if len(p) == 2:
        if p[1] == "drop":
            p[0] = ("perf_act_drop", p[PPERF_ACTION_DROP])
        else:
            assert p[1] == "forward"
            p[0] = ("perf_act_forward", p[PPERF_ACTION_DROP])
    else:
        TypeChecker.assert_symbol_type(p[PPERF_ACTION_FORWARD_EVENT], EVENT_NAME)
        length_exprs = get_count_list_expr(p[PPERF_ACTION_FORWARD_EXPRS])
        TypeChecker.assert_num_args_match(p[PPERF_ACTION_FORWARD_EVENT], length_exprs)
        p[0] = (
            "perf_act_forward",
            p[PPERF_ACTION_FORWARD_EVENT],
            p[PPERF_ACTION_FORWARD_EXPRS],
        )


def p_event_source(p):
    """
    event_source : DYNAMIC EVENT SOURCE event_source_decl ':' name_with_args  event_source_tail
                 | EVENT SOURCE event_source_decl ':' name_with_args event_source_tail
    """

    is_dynamic = False
    if len(p) == 7:
        event_src_declaration = p[3]
        stream = p[5]
        event_src_tail = p[6]
    else:
        assert len(p) == 8
        is_dynamic = True
        event_src_declaration = p[4]
        stream = p[6]
        event_src_tail = p[7]

    p[0] = ("event_source", is_dynamic, event_src_declaration, stream, event_src_tail)
    stream, c_stream_args = get_name_args_count(stream)
    # TypeChecker.assert_num_args_match(stream, c_stream_args)
    # TODO: check type of stream type?


def p_event_source_decl(p):
    """
    event_source_decl : name_with_args
                      | name_with_args '[' INT ']'
    """
    event = p[1]
    arg = None

    if len(p) == 5:
        arg = p[3]
    else:
        assert len(p) == 2
    p[0] = ("event-decl", event, arg)
    name, args = get_name_with_args(event)
    TypeChecker.insert_into_args_table(name, EVENT_SOURCE_NAME, args)


def p_event_source_tail(p):
    """
    event_source_tail : PROCESS USING name_with_args ev_src_include_part
                      | ev_src_include_part
    """
    process_using = None

    if len(p) == 2:
        ev_src_include_part = p[1]
    else:
        ev_src_include_part = p[4]
        process_using = p[3]
    connection_kind = ev_src_include_part[1]
    include_in = ev_src_include_part[2]
    p[0] = ("ev-source-tail", process_using, connection_kind, include_in)

    # if process_using is not None:
    #     name, c_args = get_name_args_count(process_using)
    #     if name.lower() != "forward":
    #         TypeChecker.assert_symbol_type(name, STREAM_PROCESSOR_NAME)
    #         TypeChecker.assert_num_args_match(name, c_args)


def p_ev_src_include_part(p):
    """
    ev_src_include_part : TO connection_kind
                        | TO connection_kind INCLUDE IN ID
    """

    conn_kind = p[2]
    include_in = None
    if len(p) > 3:
        include_in = p[5]
    p[0] = ("ev_src_inc_part", conn_kind, include_in)


def p_connection_kind(p):
    """
    connection_kind : AUTODROP '(' INT ')'
                    | AUTODROP '(' INT ',' INT ')'
                    | BLOCKING '(' INT ')'
                    | INFINITE
    """
    if len(p) == 2:
        p[0] = ("conn_kind", p[PCONN_KIND_NAME], None)
    elif len(p) == 7:
        # AUTODROP '(' INT ',' INT ')'
        #    1      2   3   4   5   6
        p[0] = ("conn_kind", p[PCONN_KIND_NAME], p[PCONN_KIND_INT], p[5])
    else:
        p[0] = ("conn_kind", p[PCONN_KIND_NAME], p[PCONN_KIND_INT])


# END performance layer specifications

# BEGIN advanced features
def p_buff_group_def(p):
    """
    buff_group_def : BUFFER GROUP ID ':' ID ORDER BY order_expr INCLUDES ID '[' int_or_all ']'
                   | BUFFER GROUP ID ':' ID INCLUDES ID '[' int_or_all ']'
                   | BUFFER GROUP ID ':' ID ORDER BY order_expr
                   | BUFFER GROUP ID ':' ID
    """
    buffer_group_name = p[3]
    stream_type = p[5]
    includes = None
    arg_includes = None
    order_by = None
    if len(p) > 6:
        if p[6] == "order":
            order_by = p[8]
            if len(p) > 11:
                includes = p[10]
                arg_includes = p[12]
        else:
            assert p[6] == "include"
            includes = p[7]
            arg_includes = p[9]

    p[0] = (
        "buff_group_def",
        buffer_group_name,
        stream_type,
        includes,
        arg_includes,
        order_by,
    )
    # TypeChecker.insert_symbol(buffer_group_name, BUFFER_GROUP_NAME)
    # TypeChecker.assert_symbol_type(stream_type, STREAM_TYPE_NAME)
    # if includes is not None:
    #     TypeChecker.assert_symbol_type(includes, EVENT_SOURCE_NAME)
    # TypeChecker.add_buffer_group_data(p[0])


def p_int_or_all(p):
    """
    int_or_all : INT
               | ALL
    """
    p[0] = p[1]


def p_match_fun_def(p):
    """
    match_fun_def : MATCH FUN ID '[' listids ']' '(' list_field_decl ')' '=' list_buff_match_exp
                  | MATCH FUN ID '[' ']' '(' list_field_decl ')' '=' list_buff_match_exp
                  | MATCH FUN ID '[' listids ']' '('  ')' '=' list_buff_match_exp
    """

    match_fun_name = p[3]
    arg1 = None
    arg2 = None
    if len(p) == 12:
        #  MATCH FUN ID '[' listids ']' '(' listids ')' '=' list_buff_match_exp
        arg1 = p[5]
        arg2 = p[8]
        buffer_match_expr = p[11]
    elif p[5] == "]":
        # MATCH FUN ID '[' ']' '(' listids ')' '=' list_buff_match_exp
        arg2 = p[7]
        buffer_match_expr = p[10]
    else:
        assert len(p) == 11
        # MATCH FUN ID '[' listids ']' '('  ')' '=' list_buff_match_exp
        arg1 = p[5]
        buffer_match_expr = p[10]
    p[0] = ("match_fun_def", match_fun_name, arg1, arg2, buffer_match_expr)

    # TypeChecker.add_match_fun_data(p[0])
    if arg2 is not None:
        ids = []
        get_list_ids(arg2, ids)
        # TypeChecker.insert_into_args_table(match_fun_name, MATCH_FUN_NAME, ids)
    # else:
    # TypeChecker.insert_symbol(match_fun_name, MATCH_FUN_NAME)
    if arg1 is not None:
        ids = []
        get_list_ids(arg1, ids)
        # TypeChecker.logical_copies[match_fun_name] = ids # TODO: maybe this should be in a diff. data structure
        # for id in ids:
        #     TypeChecker.insert_symbol(id, EVENT_SOURCE_NAME)


# END advanced features

# BEGIN arbiter Specification
def p_arbiter_definition(p):
    """
    arbiter_definition : ARBITER ':' ID '{' arbiter_rule_set_list '}'
                       | ARBITER ':' ID '{' '}'
                       | ARBITER ':' ID '{' arbiter_rule_list '}'
    """

    # TypeChecker.assert_symbol_type(p[ARBITER_OUTPUT_TYPE], STREAM_TYPE_NAME)
    if len(p) == 6:
        p[0] = ("arbiter_def", p[ARBITER_OUTPUT_TYPE], None)
    else:
        if (
            p[ARBITER_RULE_SET_LIST][0] == "arb_rule_set_l"
            or p[ARBITER_RULE_SET_LIST][0] == "arbiter_rule_set"
        ):
            p[0] = ("arbiter_def", p[ARBITER_OUTPUT_TYPE], p[ARBITER_RULE_SET_LIST])
        else:
            arbiter_rule_set_l = (
                "arbiter_rule_set",
                "default",
                p[ARBITER_RULE_SET_LIST],
            )
            p[0] = ("arbiter_def", p[ARBITER_OUTPUT_TYPE], arbiter_rule_set_l)


def p_arbiter_rule_set_list(p):
    """
    arbiter_rule_set_list : arbiter_rule_set
                          | arbiter_rule_set arbiter_rule_set_list
    """
    if len(p) == 2:
        p[0] = p[PLIST_BASE_CASE]
    else:
        p[0] = ("arb_rule_set_l", p[PLIST_BASE_CASE], p[PLIST_TAIL])


def p_arbiter_rule_set(p):
    """
    arbiter_rule_set : RULE SET ID '{' arbiter_rule_list '}'
    """
    TypeChecker.insert_symbol(p[PARB_RULE_SET_NAME], ARBITER_RULE_SET)

    p[0] = ("arbiter_rule_set", p[PARB_RULE_SET_NAME], p[PARB_RULE_LIST])


def p_arbiter_rule_list(p):
    """
    arbiter_rule_list : arbiter_rule
                      | arbiter_rule arbiter_rule_list
    """
    if len(p) == 2:
        p[0] = p[PLIST_BASE_CASE]
    else:
        p[0] = ("arb_rule_list", p[PLIST_BASE_CASE], p[PLIST_TAIL])


def p_arbiter_rule(p):
    """
    arbiter_rule : ON list_buff_match_exp WHERE BEGIN_CCODE ccode_l_where_expression BEGIN_CCODE arbiter_rule_stmt_list
                 | ON list_buff_match_exp BEGIN_CCODE arbiter_rule_stmt_list
                 | ALWAYS BEGIN_CCODE CCODE_TOKEN
                 | CHOOSE listids arb_choose_middle_part '{' arbiter_rule_list '}'
                 | CHOOSE choose_order listids arb_choose_middle_part '{' arbiter_rule_list '}'
    """
    if p[1] == "always":
        choose_count = None
        assert len(p) == 4
        p[0] = ("always", ("base_where_expr", "true"), p[3])
        TypeChecker.add_always_code(p[0])
    elif p[1] == "on":
        if len(p) == 5:
            p[0] = ("arbiter_rule1", p[2], None, p[4])
        else:
            # ON list_buff_match_exp WHERE BEGIN_CCODE ccode_l_where_expression BEGIN_CCODE arbiter_rule_stmt_list
            # 1           2            3           4                    5         6                7
            p[0] = ("arbiter_rule1", p[2], p[5], p[7])
        choose_count = None
    else:
        if len(p) == 8:
            # CHOOSE choose_order listids arb_choose_middle_part '{' arbiter_rule_list '}'
            #    1      2            3               4            5          6          7

            middle_part = p[4]
            p[0] = ("arbiter_rule2", p[2], p[3], middle_part[1], middle_part[2], p[6])
            choose_count = p[2][2]
        else:
            assert len(p) == 7
            # CHOOSE listids arb_choose_middle_part '{' arbiter_rule_list '}'
            #   1       2            3               4          5          6
            middle_part = p[3]
            p[0] = ("arbiter_rule2", None, p[2], middle_part[1], middle_part[2], p[5])
            choose_count = get_count_list_ids(p[2])

    if choose_count is not None:
        TypeChecker.max_choose_size = max(TypeChecker.max_choose_size, choose_count)


def p_arb_choose_middle_part(p):
    """
    arb_choose_middle_part : FROM ID WHERE BEGIN_CCODE ccode_l_where_expression
                           | FROM ID
    """
    where_expression = None

    if len(p) > 3:
        where_expression = p[5]

    p[0] = ("arb-choose-middle-part", p[2], where_expression)


def p_ccode_l_where_expression(p):
    """
    ccode_l_where_expression : CCODE_TOKEN
                             | FIELD_ACCESS ';'
                             | CCODE_TOKEN ccode_l_where_expression
                             | FIELD_ACCESS ';' ccode_l_where_expression
    """
    if len(p) == 2:
        p[0] = ("base_where_expr", p[1])
    elif len(p) == 3:
        if p[2] == ";":
            p[0] = ("base_where_expr", p[1])
        else:
            p[0] = ("l_where_expr", ("base_where_expr", p[1]), p[2])
    else:
        if p[2] == ";":
            p[0] = ("l_where_expr", ("base_where_expr", p[1]), p[3])
        else:
            p[0] = ("l_where_expr", ("base_where_expr", p[1]), p[2])


def p_arbiter_choose_order(p):
    """
    choose_order : FIRST INT
                 | LAST INT
                 | FIRST
                 | LAST
    """

    arg1 = p[1]

    if len(p) > 2:
        arg2 = p[2]
    else:
        arg2 = 1

    p[0] = ("choose-order", arg1, arg2)


def p_list_buff_match_exp(p):
    """
    list_buff_match_exp : buffer_match_exp
                        | buffer_match_exp ',' list_buff_match_exp
    """
    if len(p) == 2:
        p[0] = p[PLIST_BASE_CASE]
    else:
        assert len(p) == 4
        p[0] = ("l_buff_match_exp", p[PLIST_BASE_CASE], p[PLIST_TAIL_WITH_SEP])


def p_buffer_match_exp(p):
    """
    buffer_match_exp : ID '[' listids ']' '(' list_var_or_integer ')'
                     | ID '[' ']' '(' list_var_or_integer ')'
                     | ID '[' listids ']' '(' ')'
                     | ID '(' ')'
                     | CHOOSE choose_order listids FROM ID
                     | CHOOSE listids FROM ID
                     | event_src_ref ':' ev_src_status
                     | event_src_ref ':' '|' list_event_calls
                     | event_src_ref ':' list_event_calls '|'
                     | event_src_ref ':' list_event_calls '|' list_event_calls
    """

    if p[2] == "[":
        # TypeChecker.assert_symbol_type(p[1], MATCH_FUN_NAME)
        arg1 = None
        arg2 = None
        if len(p) == 7:
            arg1 = p[3]
            arg2 = p[6]
        else:
            assert len(p) == 6
            if p[3] == "]":
                arg2 = p[5]
            else:
                arg1 = p[3]
        p[0] = ("buff_match_exp-args", p[1], arg1, arg2)

    elif p[2] == "(":
        TypeChecker.assert_symbol_type(p[1], MATCH_FUN_NAME)
        p[0] = ("buff_match_exp-args", p[1], None, None)
    elif p[1] == "choose":
        choose_order = None
        if len(p) == 6:
            # CHOOSE choose_order listids FROM ID
            #   1           2         3     4   5
            choose_order = p[2]
            args = p[3]
            buffer_name = p[5]
        else:
            args = p[2]
            buffer_name = p[4]
        p[0] = ("buff_match_exp-choose", choose_order, args, buffer_name)
        # TypeChecker.assert_symbol_type(p[4], BUFFER_GROUP_NAME)
    elif len(p) == 4:
        # TypeChecker.assert_symbol_type(p[1][1], EVENT_SOURCE_NAME)
        p[0] = ("buff_match_exp", p[PBUFFER_MATCH_EV_NAME], p[PBUFFER_MATCH_ARG1])
    elif len(p) == 5:
        # TODO: fix this check
        # TypeChecker.assert_symbol_type(p[1][1], EVENT_SOURCE_NAME)
        p[0] = (
            "buff_match_exp",
            p[PBUFFER_MATCH_EV_NAME],
            p[PBUFFER_MATCH_ARG1],
            p[PBUFFER_MATCH_ARG2],
        )
    else:
        TypeChecker.assert_symbol_type(p[1][1], EVENT_SOURCE_NAME)
        p[0] = (
            "buff_match_exp",
            p[PBUFFER_MATCH_EV_NAME],
            p[PBUFFER_MATCH_ARG1],
            "|",
            p[PBUFFER_MATCH_ARG3],
        )


def p_ev_src_status(p):
    """
    ev_src_status : NOTHING
                  | DONE
                  | INT
    """
    p[0] = ("ev-src-status", p[1])


def p_event_src_ref(p):
    """
    event_src_ref : ID
                  | ID '[' INT ']'
    """

    event = p[1]
    param = None
    if len(p) > 2:
        param = p[3]
    p[0] = ("event_src_ref", event, param)


def p_order_expr(p):
    """
    order_expr : ROUND ROBIN
               | ID
    """
    if len(p) == 3:
        p[0] = ("order_expr", "round-robin")
    if p[1] == "$":
        p[0] = ("order_expr", p[2])
    else:
        assert len(p) == 2
        p[0] = ("order_expr", p[1])


def p_list_event_calls(p):
    """
    list_event_calls : ID '(' listids ')'
                     | ID '(' ')'
                     | ID '(' ')' list_event_calls
                     | ID '(' listids  ')' list_event_calls
    """

    # TODO: what is E^H
    # TypeChecker.assert_symbol_type(p[PLIST_EV_CALL_EV_NAME], EVENT_NAME)
    if len(p) == 4:
        # ID '(' ')'
        p[0] = ("ev_call", p[PLIST_EV_CALL_EV_NAME], None)
    elif len(p) == 5:
        if p[3] == ")":
            # ID '(' ')' list_event_calls
            p[0] = ("list_ev_calls", p[PLIST_EV_CALL_EV_NAME], None, p[4])
        else:
            # ID '(' listids ')'
            p[0] = ("ev_call", p[PLIST_EV_CALL_EV_NAME], p[PLIST_EV_CALL_EV_PARAMS])
            list_ids_length = get_count_list_ids(p[PLIST_EV_CALL_EV_PARAMS])
            # TypeChecker.assert_num_args_match(p[PLIST_EV_CALL_EV_NAME], list_ids_length)
    else:
        assert len(p) == 6
        # ID '(' listids  ')' list_event_calls
        p[0] = (
            "list_ev_calls",
            p[PLIST_EV_CALL_EV_NAME],
            p[PLIST_EV_CALL_EV_PARAMS],
            p[PLIST_EV_CALL_TAIL],
        )
        list_ids_length = get_count_list_ids(p[PLIST_EV_CALL_EV_PARAMS])
        # TypeChecker.assert_num_args_match(p[PLIST_EV_CALL_EV_NAME], list_ids_length)


def p_arbiter_rule_stmt_list(p):
    """
    arbiter_rule_stmt_list : ccode_statement_list
                           | ccode_statement_list arbiter_rule_stmt_list
    """

    if len(p) == 2:
        p[0] = p[PLIST_BASE_CASE]
    else:
        p[0] = ("arb_rule_stmt_l", p[PLIST_BASE_CASE], p[PLIST_TAIL])


def p_ccode_statement_list(p):
    """
    ccode_statement_list : CCODE_TOKEN
                         | CCODE_TOKEN arbiter_rule_stmt ';'
                         | arbiter_rule_stmt ';'
                         | arbiter_rule_stmt ';' CCODE_TOKEN
                         |
    """

    if len(p) == 1:
        #
        p[0] = ("ccode_statement_l", "")
    elif len(p) == 2:
        # CCODE_TOKEN
        p[0] = ("ccode_statement_l", p[PCODE_STMT_LIST_TOKEN1])
    elif len(p) == 3:
        # arbiter_rule_stmt ';'
        p[0] = (
            "ccode_statement_l",
            p[PCODE_STMT_LIST_TOKEN1],
            p[PCODE_STMT_LIST_TOKEN2],
        )
    else:
        assert len(p) == 4
        # CCODE_TOKEN arbiter_rule_stmt ';'
        # arbiter_rule_stmt ';' CCODE_TOKEN
        p[0] = (
            "ccode_statement_l",
            p[PCODE_STMT_LIST_TOKEN1],
            p[PCODE_STMT_LIST_TOKEN2],
            p[PCODE_STMT_LIST_TOKEN3],
        )


def p_arbiter_rule_stmt(p):
    """
    arbiter_rule_stmt : YIELD ID '(' expression_list ')'
                      | YIELD ID '(' ')'
                      | SWITCH TO ID
                      | CONTINUE
                      | DROP INT FROM event_src_ref
                      | REMOVE ID FROM event_src_ref
                      | ADD ID FROM event_src_ref
                      | FIELD_ACCESS
    """

    if p[1] == "yield":
        if len(p) == 6:
            p[0] = (
                "yield",
                p[PARB_RULE_STMT_YIELD_EVENT],
                p[PARB_RULE_STMT_YIELD_EXPRS],
            )
        else:
            assert len(p) == 5
            p[0] = ("yield", p[PARB_RULE_STMT_YIELD_EVENT], None)
        # TypeChecker.assert_symbol_type(p[PARB_RULE_STMT_YIELD_EVENT], EVENT_NAME)
        # count_expr_list = get_count_list_expr(p[PARB_RULE_STMT_YIELD_EXPRS])
        # TypeChecker.assert_num_args_match(p[PARB_RULE_STMT_YIELD_EVENT], count_expr_list)
    elif p[1] == "add" or p[1] == "remove":
        p[0] = (p[1], p[2], p[4])
    elif len(p) == 5:
        assert p[1] == "drop"
        p[0] = ("drop", p[PARB_RULE_STMT_DROP_INT], p[PARB_RULE_STMT_DROP_EV_SOURCE])
        event_source_name = p[PARB_RULE_STMT_DROP_EV_SOURCE][1]
        # TypeChecker.assert_symbol_type(event_source_name, EVENT_SOURCE_NAME)
    elif len(p) == 2:
        if p[0] == "continue":
            p[0] = "continue"
        else:
            p[0] = p[1]
    else:
        assert p[1] == "switch"
        p[0] = ("switch", p[PARB_RULE_STMT_SWITCH_ARB_RULE])


# END arbiter Specification

# BEGIN monitor Specification


def p_monitor_definition(p):
    """
    monitor_definition : MONITOR '{' monitor_rule_list '}'
    monitor_definition : MONITOR '{' '}'
    monitor_definition : MONITOR '(' INT ')' '{' monitor_rule_list '}'
    monitor_definition : MONITOR '(' INT ')' '{' '}'
    monitor_definition : MONITOR '(' ')' '{' '}'
    """
    monitor_rule_list = None
    if len(p) == 7:
        TypeChecker.monitor_buffer_size = int(p[3])
    elif len(p) == 6 or len(p) == 4:
        pass
    elif len(p) == 8:
        TypeChecker.monitor_buffer_size = int(p[3])
        monitor_rule_list = p[6]
    else:
        assert len(p) == 5
        monitor_rule_list = p[3]
    p[0] = ("monitor_def", monitor_rule_list)


def p_monitor_rule_list(p):
    """
    monitor_rule_list : monitor_rule
                      | monitor_rule monitor_rule_list
    """

    if len(p) == 2:
        p[0] = p[PLIST_BASE_CASE]
    else:
        p[0] = ("monitor_rule_l", p[PLIST_BASE_CASE], p[PLIST_TAIL])


def p_monitor_rule(p):
    """
    monitor_rule : ON ID '(' listids ')' WHERE BEGIN_CCODE expression BEGIN_CCODE CCODE_TOKEN
                 | ON ID '(' ')' WHERE BEGIN_CCODE expression BEGIN_CCODE CCODE_TOKEN
    """

    # ON ID '(' listids ')' WHERE BEGIN_CCODE expression BEGIN_CCODE CCODE_TOKEN
    #  1  2  3    4      5   6       7            8          9          10

    if p[4] == ")":
        listids = None
        expression = p[7]
        code = p[9]
    else:
        listids = p[4]
        expression = p[8]
        code = p[10]
    # TypeChecker.assert_symbol_type(p[PMONITOR_RULE_EV_NAME], EVENT_NAME)
    # if listids:
    # TypeChecker.assert_num_args_match(p[PMONITOR_RULE_EV_NAME], get_count_list_ids(p[PMONITOR_RULE_EV_ARGS]))
    p[0] = ("monitor_rule", p[2], listids, expression, code)


# END monitor Specification


def p_extends_node(p):
    """
    extends_node : EXTENDS name_with_args
    """

    if len(p) == 3:
        p[0] = ("extends-node", p[2])
    else:
        assert False


def p_name_with_args(p):
    """
    name_with_args : ID '(' expression_list ')'
                   | ID '(' list_field_decl ')'
                   | ID
                   | ID '(' ')'
                   | FORWARD
    """
    if len(p) == 2:
        p[0] = p[1]
    elif len(p) == 4:
        p[0] = ("name-with-args", p[1], None)
    else:
        p[0] = ("name-with-args", p[1], p[3])


def p_type(p):
    """
    type : ID
         | type '[' ']'
    """
    if len(p) == 2:
        p[0] = ("type", p[PTYPE_NAME])
    else:
        assert len(p) == 4
        p[0] = ("array", p[PTYPE_NAME])


def p_expression_list(p):
    """
    expression_list : expression
                    | expression ',' expression_list
    """

    if len(p) == 2:
        p[0] = p[PLIST_BASE_CASE]
    else:
        assert len(p) == 4
        p[0] = ("expr_list", p[PLIST_BASE_CASE], p[PLIST_TAIL_WITH_SEP])


def p_expression(p):
    """
    expression : ID
               | INT
               | BOOL
               | CCODE_TOKEN
               | FIELD_ACCESS
    """
    if len(p) == 2:
        p[0] = ("expr", p[1])
    else:
        raise Exception("this should not happen")
        # assert(len(p) == 4)
        # p[0] = ('binop', p[2], p[1], p[3])


def p_listids(p):
    """
    listids : ID
            | ID ',' listids
    """
    if len(p) == 2:
        p[0] = ("ID", p[PLIST_BASE_CASE])
    elif len(p) == 4:
        p[0] = ("listids", p[PLIST_BASE_CASE], p[PLIST_TAIL_WITH_SEP])
    elif len(p) == 1:
        p[0] = "empty"
    else:
        assert False


def p_list_var_or_integer(p):
    """
    list_var_or_integer : var_or_integer list_var_or_integer
                        | var_or_integer
    """
    if len(p) == 2:
        p[0] = p[1]
    else:
        assert len(p) == 3
        p[0] = ("list_var_or_integer", p[1], p[2])


def p_var_or_integer(p):
    """
    var_or_integer : ID
                   | INT
    """
    p[0] = p[1]


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


# public interface
def parse_program(s: str):
    l = MyLexer()
    lexer = lex.lex(object=l)
    parser = yacc(debug=None)

    # Parse an expression
    ast = parser.parse(s)
    return ast
