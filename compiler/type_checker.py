from typing import Dict, Set, Optional
from copy import deepcopy

from tokens import reserved
from utils import *

# define some types:
RESERVED = "reserved"
EVENT_NAME = "event_name"
EVENT_SOURCE_NAME = "event_source_name"
STREAM_PROCESSOR_NAME = "stream_processor_name"
STREAM_TYPE_NAME = "stream_type"
MATCH_FUN_NAME = "match_fun_name"
ARBITER_RULE_SET = "arbiter_rule_set"


class TypeChecker:

    symbol_table: Dict[str, str] = dict()  # maps symbols to types
    args_table: Dict[
        str, List[str]
    ] = dict()  # maps symbol (that represents a function) to a list of the
    # types of its arguments
    stream_events_are_primitive: Dict[
        str, bool
    ] = dict()  # maps 'stream type' declaration to the events that are declared inside
    event_sources_types: Dict[
        str, Tuple[str, str]
    ] = dict()  # ev_source_name -> (input type, output type)
    stream_types_to_events: Dict[
        str, Set[str]
    ] = dict()  # maps a stream name to the name of events that can happen
    max_choose_size: int = 0
    arbiter_output_type: Optional[str] = None
    event_sources_data: Dict[str, Dict[str, Any]] = dict()
    stream_processors_data: Dict[str, Dict[str, Any]] = dict()
    buffer_group_data: Dict[str, Dict[str, Any]] = dict()
    match_fun_data: Dict[str, Dict[str, Any]] = dict()
    match_expr_funcs: List[Any] = []
    monitor_buffer_size: int = 4
    stream_types_data: Dict[str, Dict[str, Any]] = dict()
    always_code = ""

    @staticmethod
    def clean_checker():
        TypeChecker.symbol_table = dict()
        TypeChecker.args_table = dict()
        TypeChecker.add_reserved_keywords()

    @staticmethod
    def get_stream_events(stream_types):
        for ast in stream_types:
            assert ast[0] == "stream_type"
            assert len(ast) == 5
            stream_name = ast[PPSTREAM_TYPE_NAME]
            assert stream_name in TypeChecker.symbol_table.keys()

            extends_node = ast[3]
            if extends_node is not None:
                assert extends_node[0] == "extends-node"
                mother_stream = extends_node[1]
                assert mother_stream in TypeChecker.symbol_table.keys()
                names = deepcopy(TypeChecker.stream_types_to_events[mother_stream])
            else:
                names = []
            get_events_names(ast[-1], names)
            for name in names:
                TypeChecker.insert_symbol(f"{stream_name}_{name}", EVENT_NAME)
            assert stream_name not in TypeChecker.stream_types_to_events.keys()
            TypeChecker.stream_types_to_events[stream_name] = set(names)

    @staticmethod
    def add_reserved_keywords():
        for keyword in reserved.keys():
            TypeChecker.symbol_table[keyword] = RESERVED

    @staticmethod
    def symbol_exists(symbol: str) -> bool:
        return symbol in TypeChecker.symbol_table.keys()

    @staticmethod
    def get_symbol_type(symbol: str) -> str:
        if symbol.lower() == "hole":
            return EVENT_NAME
        return TypeChecker.symbol_table[symbol]

    @staticmethod
    def assert_symbol_type(symbol: str, type_: str):
        if TypeChecker.get_symbol_type(symbol) != type_:
            raise Exception(
                f"{symbol} is expected to be of type {type_}, instead is {TypeChecker.get_symbol_type(symbol)}"
            )

    @staticmethod
    def insert_symbol(symbol: str, type_: str) -> None:
        if TypeChecker.symbol_exists(symbol):
            raise Exception(
                f"Symbol {symbol}  of type {TypeChecker.get_symbol_type(symbol)} already exists"
            )
        TypeChecker.symbol_table[symbol] = type_

    @staticmethod
    def is_symbol_in_args_table(symbol):
        return symbol in TypeChecker.args_table.keys()

    @staticmethod
    def insert_into_args_table(
        symbol: str, symbol_type: str, args_: Dict[str, str]
    ) -> None:
        TypeChecker.insert_symbol(symbol, symbol_type)
        assert TypeChecker.symbol_exists(symbol)

        assert not TypeChecker.is_symbol_in_args_table(symbol)
        TypeChecker.args_table[symbol] = args_

    @staticmethod
    def get_stream_types_data(stream_types):
        for stream_type in stream_types:
            stream_name = stream_type[1]

            stream_args_names = []
            get_parameters_names_field_decl(stream_type[2], stream_args_names)
            stream_args_types = []
            get_parameters_types_field_decl(stream_type[2], stream_args_types)
            extends_node = stream_type[3]
            if extends_node is not None:
                raise Exception("missing implementation to extend stream types")
            event_list = stream_type[4]
            events = dict()
            get_events_data(event_list, events)
            for (event, args) in events.items():
                TypeChecker.insert_into_args_table(
                    f"EVENT_{stream_name}_{event}", EVENT_NAME, args
                )
            TypeChecker.stream_types_data[stream_name] = {
                "args": stream_args_names,
                "arg_types": stream_args_types,
                "events": events,
                "raw_events_list": event_list,
            }

    @staticmethod
    def assert_num_args_match(symbol, expected_n):
        if symbol.lower() == "hole":
            if expected_n != 1:
                raise Exception("Event hole takes 1 argument.")
        elif len(TypeChecker.args_table[symbol]) != expected_n:
            raise Exception(
                f"Only {expected_n} arguments provided to function {symbol} that receives {len(TypeChecker.args_table[symbol])} arguments."
            )

    @staticmethod
    def insert_event_list(symbol, event_list_tree):
        assert symbol in TypeChecker.symbol_table.keys()
        TypeChecker.stream_events_are_primitive[symbol] = are_all_events_decl_primitive(
            event_list_tree
        )

    @staticmethod
    def is_event_in_stream(stream: str, event_name: str):
        if event_name == "hole":
            return True
        return event_name in TypeChecker.stream_types_to_events[stream]

    @staticmethod
    def check_performance_match(ast, output_type):
        if ast[0] == "perf_match2": 
            # IF '(' expression ')' THEN performance_match ELSE performance_match
            TypeChecker.check_performance_match(
                ast[PPPERF_MATCH_TRUE_PART], output_type
            )
            TypeChecker.check_performance_match(
                ast[PPPERF_MATCH_FALSE_PART], output_type
            )
        else:
            assert ast[0] == "perf_match1" # performance_action
            perf_action = ast[PPPERF_MATCH_ACTION]
            output_event = perf_action[PPPERF_ACTION_FORWARD_EVENT]
            if not TypeChecker.is_event_in_stream(output_type, output_event):
                raise Exception(
                    f"Event {output_event} does not happen in stream {output_type}."
                )

    @staticmethod
    def check_list_buff_exprs(ast):
        if ast is not None:
            if ast[0] == "l_buff_match_exp":
                TypeChecker.check_list_buff_exprs(ast[PLIST_BASE_CASE])
                TypeChecker.check_list_buff_exprs(ast[PLIST_TAIL])
            else:
                assert ast[0] == "buff_match_exp"
                event_source = ast[PPBUFFER_MATCH_EV_NAME]
                for i in range(1, len(ast)):
                    TypeChecker.check_event_calls(ast[i], event_source)

    @staticmethod
    def add_always_code(node):
        assert node[0] == "always"
        TypeChecker.always_code += node[2]

    @staticmethod
    def is_event_in_event_source(event_source, event, is_input=True):
        types = TypeChecker.event_sources_types[event_source]
        if is_input:
            stream = types[0]
        else:
            stream = types[1]
        return TypeChecker.is_event_in_stream(stream, event)

    @staticmethod
    def check_event_calls(ast, stream_name):
        if ast[0] == "list_ev_calls":
            event = ast[PPLIST_EV_CALL_EV_NAME]
            if not TypeChecker.is_event_in_event_source(stream_name, event):
                raise Exception(
                    f"Event source {stream_name} does not considers event {event}"
                )
            TypeChecker.check_event_calls(ast[PPLIST_EV_CALL_TAIL], stream_name)
        elif ast[0] == "ev_call":
            event = ast[PPLIST_EV_CALL_EV_NAME]
            if not TypeChecker.is_event_in_event_source(stream_name, event):
                raise Exception(
                    f"Event source {stream_name} does not considers event {event}"
                )

    @staticmethod
    def get_stream_processors_data(stream_processors):

        for tree in stream_processors:
            assert tree[0] == "stream_processor"
            stream_processor_name, args = get_name_with_args(tree[1])
            input_type, input_args = get_name_with_args(tree[2])
            output_type, output_args = get_name_with_args(tree[3])
            extends_node = get_name_with_args(tree[4][1])
            processor_rules = []
            hole_name, special_hole = get_processor_rules(tree[5], processor_rules)
            TypeChecker.stream_processors_data[stream_processor_name] = {
                "args": args,
                "input_type": input_type,
                "input_args": input_args,
                "output_type": output_type,
                "output_args": output_args,
                "extends_node": extends_node,
                "perf_layer_rule_list": processor_rules,
                "special_hole": special_hole,
                "hole_name": hole_name,
            }

    @staticmethod
    def insert_event_source_data(tree):
        assert tree[0] == "event_source"
        is_dynamic, event_src_declaration, name_arg_input_type, event_src_tail = (
            tree[1],
            tree[2],
            tree[3],
            tree[4],
        )

        # processing event_source_decl
        assert event_src_declaration[0] == "event-decl"
        name, args = get_name_with_args(event_src_declaration[1])
        copies = event_src_declaration[2]

        # processing input type
        stream_type_name, stream_args = get_name_with_args(name_arg_input_type)

        # processing tail
        assert event_src_tail[0] == "ev-source-tail"
        connection_kind = event_src_tail[2]
        if event_src_tail[1] == None:
            processor_name = "forward"
            output_type = stream_type_name
            processor_args = []
        else:
            processor_name, processor_args = get_name_with_args(event_src_tail[1])
            if processor_name.lower() == "forward":
                processor_name = "forward"
                output_type = stream_type_name
                processor_args = []
            else:
                output_type = TypeChecker.stream_processors_data[processor_name][
                    "output_type"
                ]

        # process include in part
        include_in = event_src_tail[3]

        data = {
            "copies": copies,
            "args": args,
            "input_stream_type": stream_type_name,
            "input_stream_args": stream_args,
            "output_stream_type": output_type,
            "processor_name": processor_name,
            "processor_args": processor_args,
            "connection_kind": connection_kind,
            "include_in": include_in,
        }
        assert name not in TypeChecker.event_sources_data.keys()
        TypeChecker.event_sources_data[name] = data

    @staticmethod
    def add_buffer_group_data(tree):
        assert tree[0] == "buff_group_def"
        buffer_name, input_stream, includes, arg_includes, order_by = (
            tree[1],
            tree[2],
            tree[3],
            tree[4],
            tree[5],
        )

        if arg_includes is not None:
            if arg_includes == "all":
                arg_includes = TypeChecker.event_sources_data[includes]["copies"]
            arg_includes = int(arg_includes)

        if order_by is not None:
            assert order_by[0] == "order_expr"
            order = order_by[1]
        else:
            order = "round-robin"
        data = {
            "in_stream": input_stream,
            "includes": includes,
            "arg_includes": arg_includes,
            "order": order,
        }
        assert buffer_name not in TypeChecker.buffer_group_data.keys()
        TypeChecker.buffer_group_data[buffer_name] = data

    @staticmethod
    def add_match_fun_data(tree):
        def local_get_stream_types(local_tree, local_result):
            if local_tree[0] == "l_buff_match_exp":
                local_get_stream_types(local_tree[1], local_result)
                local_get_stream_types(local_tree[2], local_result)
            else:
                assert local_tree[0] in [
                    "buff_match_exp-choose",
                    "buff_match_exp-args",
                    "buff_match_exp",
                ]
                if local_tree[0] == "buff_match_exp-choose":
                    buffer_name = local_tree[-1]
                    binded_args = []
                    get_list_ids(local_tree[2], binded_args)
                    for ba in binded_args:
                        local_result[ba] = TypeChecker.buffer_group_data[buffer_name][
                            "in_stream"
                        ]

        assert tree[0] == "match_fun_def"

        match_name, temp_output_args, temp_input_args, buffer_match_expr = (
            tree[1],
            tree[2],
            tree[3],
            tree[4],
        )

        output_args = []
        if temp_output_args is not None:
            get_list_ids(temp_output_args, output_args)
        input_args = []
        if temp_input_args is not None:
            get_list_var_or_int(temp_input_args, input_args)

        stream_types = dict()
        local_get_stream_types(buffer_match_expr, stream_types)
        arr_stream_types = []
        for a in output_args:
            arr_stream_types.append(stream_types[a])
        assert len(arr_stream_types) == len(output_args)
        data = {
            "out_args": output_args,
            "in_args": input_args,
            "buffer_match_expr": buffer_match_expr,
            "stream_types": arr_stream_types,
        }
        assert match_name not in TypeChecker.match_fun_data.keys()
        TypeChecker.match_fun_data[match_name] = data
