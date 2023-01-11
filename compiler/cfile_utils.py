# all the function declared here return a string of C-code
from typing import Type
from itertools import combinations

from utils import *
from parser_indices import *
from type_checker import TypeChecker, ARBITER_RULE_SET


class StaticCounter:
    declarations_counter = 0
    calls_counter = 0

    match_expr_counter = 0
    match_expr_calls_counter = 0


def get_pure_c_code(component, token) -> str:
    answer = ""
    if token in component.keys():
        for tree in component[token]:
            assert tree[0] == "startup" or tree[0] == "cleanup"
            answer += tree[1]
    return answer


def get_globals_code(components, mapping, stream_types) -> str:
    answer = ""
    if "globals" in components.keys():
        globals = components["globals"]
        answer = f"STREAM_{TypeChecker.arbiter_output_type}_out *arbiter_outevent;\n\n"
        for tree in globals:
            assert tree[0] == "globals"
            answer += get_arb_rule_stmt_list_code(
                tree[1], mapping, {}, stream_types, TypeChecker.arbiter_output_type
            )
    return answer


def declare_order_expressions():
    answer = ""

    for (buff_name, data) in TypeChecker.buffer_group_data.items():
        if data["order"] == "round-robin":
            code = "return false;"
        else:
            code = f"return ((STREAM_{data['in_stream']}_ARGS *) args1)->{data['order']} > ((STREAM_{data['in_stream']}_ARGS *) args2)->{data['order']};"
        answer += f"""
bool {buff_name}_ORDER_EXP (void *args1, void *args2) {"{"}
    {code}
{"}"}        
"""
    return answer


def declare_buffer_groups():
    """This function declare bugger groups and mutex locks"""
    answer = ""

    for (buff_name, data) in TypeChecker.buffer_group_data.items():
        answer += f"""
buffer_group BG_{buff_name};
mtx_t LOCK_{buff_name};
        """
    return answer


def init_buffer_groups():
    answer = ""
    for (buff_name, data) in TypeChecker.buffer_group_data.items():
        includes_str = ""
        if data["arg_includes"] is not None:
            for i in range(data["arg_includes"]):
                includes_str += f"\tbg_insert(&BG_{buff_name}, EV_SOURCE_{data['includes']}_{i}, BUFFER_{data['includes']}{i},stream_args_{data['includes']}_{i},{buff_name}_ORDER_EXP);\n"
        answer += f"""init_buffer_group(&BG_{buff_name});
        if (mtx_init(&LOCK_{buff_name}, mtx_plain) != 0) {"{"}
        printf("mutex init has failed for {buff_name} lock\\n");
        return 1;
    {"}"}
    {includes_str}        
    """

    for (event_source, data) in TypeChecker.event_sources_data.items():
        buff_name = data["include_in"]
        if buff_name is not None:
            if data["copies"]:
                for i in range(data["copies"]):
                    answer += f"""
\tbg_insert(&BG_{buff_name}, EV_SOURCE_{event_source}_{i}, BUFFER_{event_source}{i},stream_args_{event_source}_{i},{buff_name}_ORDER_EXP);\n
        """
            else:
                answer += f"""
\tbg_insert(&BG_{buff_name}, EV_SOURCE_{event_source}, BUFFER_{event_source},stream_args_{event_source},{buff_name}_ORDER_EXP);\n
        """

    return answer


def get_stream_struct_fields(field_declarations):
    if field_declarations is None:
        return ""
    fields = []
    get_parameters_types_field_decl(field_declarations, fields)
    struct_fields = ""
    for field in fields:
        struct_fields += f"\t{field['type']} {field['name']};\n"
    return struct_fields


def stream_arg_structs(stream_types) -> str:
    answer = ""
    for tree in stream_types:
        assert tree[0] == "stream_type"
        if tree[2] is not None:
            struct_fields = get_stream_struct_fields(tree[2])
            answer += f"""
// args for stream type {tree[1]}
struct _{tree[1]}_ARGS {"{"}
{struct_fields}
{"}"}
typedef struct  _{tree[1]}_ARGS  {tree[1]}_ARGS;
            """
    return answer


def events_declaration_structs(stream_name, tree) -> str:
    if tree[0] == "event_list":
        return (
            events_declaration_structs(stream_name, tree[PLIST_BASE_CASE])
            + "\n"
            + events_declaration_structs(stream_name, tree[PLIST_TAIL])
        )
    else:
        assert tree[0] == "event_decl"
        event_name = tree[PPEVENT_NAME]
        fields = []
        if tree[PPEVENT_PARAMS_LIST]:
            get_parameters_types_field_decl(tree[PPEVENT_PARAMS_LIST], fields)
        struct_fields = ""
        index = 0
        for data in fields:
            is_last = index == len(data) - 1
            if not is_last:
                struct_fields += f"\t{data['type']} {data['name']};\n"
            else:
                struct_fields += f"\t{data['type']} {data['name']};\n"

        return f"""struct _EVENT_{stream_name}_{event_name} {"{"}
{struct_fields}
{"}"};
typedef struct _EVENT_{stream_name}_{event_name} EVENT_{stream_name}_{event_name};"""


def stream_type_args_structs(stream_types) -> str:
    answer = ""
    for tree in stream_types:
        assert tree[0] == "stream_type"
        stream_name = tree[PPSTREAM_TYPE_NAME]
        stream_arg_fields = get_stream_struct_fields(tree[2])
        if stream_arg_fields != "":
            answer += f"""
    typedef struct _STREAM_{stream_name}_ARGS {'{'}
    {stream_arg_fields}
    {'}'} STREAM_{stream_name}_ARGS;
            """
    return answer


def instantiate_stream_args():
    answer = ""
    for (stream_name, data) in TypeChecker.event_sources_data.items():
        has_args = len(data["input_stream_args"]) > 0
        processor_name = data["processor_name"]

        if processor_name is not None and processor_name.lower() != "forward":
            if has_args:
                print(
                    f"ignoring declared args of {stream_name}, using stream processor args"
                )
            has_args = len(TypeChecker.stream_processors_data[processor_name]["args"])
        if has_args:
            stream_type = data["input_stream_type"]
            if data["copies"] is not None:
                for i in range(data["copies"]):
                    answer += (
                        f"STREAM_{stream_type}_ARGS *stream_args_{stream_name}_{i};\n"
                    )
            else:
                answer += f"STREAM_{stream_type}_ARGS *stream_args_{stream_name};\n"
    return answer


def initialize_stream_args():
    answer = ""

    for (stream_name, data) in TypeChecker.event_sources_data.items():
        processor_name = data["processor_name"]
        if len(data["input_stream_args"]) > 0:
            stream_type = data["input_stream_type"]
            if data["copies"]:
                for i in range(data["copies"]):
                    answer += f"stream_args_{stream_name}_{i} = malloc(sizeof(STREAM_{stream_type}_ARGS));\n"
            else:
                answer += f"stream_args_{stream_name} = malloc(sizeof(STREAM_{stream_type}_ARGS));\n"
        elif processor_name != "forward":
            current_args = TypeChecker.stream_processors_data[processor_name][
                "output_args"
            ]
            stream_type = TypeChecker.stream_processors_data[processor_name][
                "output_type"
            ]
            if len(current_args) > 0:
                if data["copies"]:
                    for i in range(data["copies"]):
                        answer += f"\tstream_args_{stream_name}_{i} = malloc(sizeof(STREAM_{stream_type}_ARGS));\n"
                else:
                    answer += f"\tstream_args_{stream_name} = malloc(sizeof(STREAM_{stream_type}_ARGS));\n"

    for (event_source, data) in TypeChecker.event_sources_data.items():
        stream_args = TypeChecker.args_table[data["input_stream_type"]]
        if (data["processor_name"] == "forward") or (data["processor_name"] is None):
            if data["copies"]:
                for i in range(data["copies"]):
                    for stream_arg, arg_value in zip(
                        stream_args, data["input_stream_args"]
                    ):
                        arg_name = stream_arg["name"]
                        answer += f"\tstream_args_{event_source}_{i}->{arg_name} = {arg_value};\n"
            else:
                for stream_arg, arg_value in zip(
                    stream_args, data["input_stream_args"]
                ):
                    arg_name = stream_arg["name"]
                    answer += (
                        f"\tstream_args_{event_source}->{arg_name} = {arg_value};\n"
                    )
        else:
            processor_name = data["processor_name"]
            args = TypeChecker.stream_processors_data[processor_name]["args"]
            processor_arg_values = data["processor_args"]
            assert len(processor_arg_values) == len(args)
            declare_args_code = ""
            for (stream_arg, processor_arg) in zip(processor_arg_values, args):
                assert processor_arg[0] == "field_decl"
                arg_name = processor_arg[1]
                assert processor_arg[2][0] == "type"
                arg_type = processor_arg[2][1]
                declare_args_code += f"\t\t{arg_type} {arg_name} = {stream_arg};\n"

            stream_args_init = ""
            current_args = TypeChecker.stream_processors_data[processor_name][
                "output_args"
            ]
            if data["copies"]:
                for i in range(data["copies"]):
                    for stream_arg, arg_value in zip(stream_args, current_args):
                        arg_name = stream_arg["name"]
                        stream_args_init += f"\t\tstream_args_{event_source}_{i}->{arg_name} = {arg_value};\n"
            else:
                for stream_arg, arg_value in zip(stream_args, current_args):
                    arg_name = stream_arg["name"]
                    stream_args_init += (
                        f"\t\tstream_args_{event_source}->{arg_name} = {arg_value};\n"
                    )
            answer += f"""
    {"{"}
{declare_args_code}
{stream_args_init}
    {"}"}
"""
    return answer


def stream_type_structs(stream_types) -> str:
    answer = ""
    # union_events += f"EVENT_{hole_name}_hole {hole_name};"
    special_holes = ""
    for (_, data) in TypeChecker.stream_processors_data.items():
        hole_name = data["hole_name"]
        if hole_name is not None:
            special_holes += f"EVENT_{hole_name}_hole {hole_name};"

    for stream_name in TypeChecker.stream_types_to_events.keys():
        union_events = ""
        for name in TypeChecker.stream_types_to_events[stream_name]:
            union_events += f"EVENT_{stream_name}_{name} {name};"

        union_events += special_holes
        answer += f"""// event declarations for stream type {stream_name}
{events_declaration_structs(stream_name, TypeChecker.stream_types_data[stream_name]["raw_events_list"])}

// input stream for stream type {stream_name}
struct _STREAM_{stream_name}_in {"{"}
    shm_event head;
    union {"{"}
        {union_events}
    {"}"}cases;
{"}"};
typedef struct _STREAM_{stream_name}_in STREAM_{stream_name}_in;

// output stream for stream processor {stream_name}
struct _STREAM_{stream_name}_out {"{"}
    shm_event head;
    union {"{"}
        EVENT_hole hole;
        {union_events}
    {"}"}cases;
{"}"};
typedef struct _STREAM_{stream_name}_out STREAM_{stream_name}_out;
        """
    return answer


def declare_event_sources(event_sources):
    event_srcs_names = []
    get_event_sources_names(event_sources, event_srcs_names)
    answer = ""
    for name in event_srcs_names:
        if TypeChecker.event_sources_data[name]["copies"]:
            for i in range(TypeChecker.event_sources_data[name]["copies"]):
                answer += f"shm_stream *EV_SOURCE_{name}_{i};\n"
        else:
            answer += f"shm_stream *EV_SOURCE_{name};\n"
    return answer


def define_signal_handlers(event_sources):
    event_srcs_names = []
    get_event_sources_names(event_sources, event_srcs_names)
    answer = (
        "static void sig_handler(int sig) {\n" '\tprintf("signal %d caught...", sig);'
    )
    for name in event_srcs_names:
        if TypeChecker.event_sources_data[name]["copies"]:
            for i in range(TypeChecker.event_sources_data[name]["copies"]):
                answer += f"\tshm_stream_detach(EV_SOURCE_{name}_{i});\n"
        else:
            answer += f"\tshm_stream_detach(EV_SOURCE_{name});\n"
    answer += "\t__work_done = 1;\n}"
    return answer


def declare_event_sources_flags(ast):
    assert ast[0] == "main_program"
    event_srcs_names = []
    get_event_sources_names(ast[PMAIN_PROGRAM_EVENT_SOURCES], event_srcs_names)
    answer = ""
    for name in event_srcs_names:
        answer += f"bool is_{name}_done;\n"
    return answer


def stream_type_from_ev_source(event_source):
    stream_type = event_source[3]
    if isinstance(stream_type, tuple):
        assert stream_type[0] == "name-with-args", stream_type
        stream_type = stream_type[1]
    assert isinstance(stream_type, str)
    return stream_type


def events_enum_kinds(event_sources, streams_to_events_map) -> str:
    answer = ""
    for event_source in event_sources:
        assert event_source[0] == "event_source"
        stream_type = stream_type_from_ev_source(event_source)
        answer += f"enum {stream_type}_kinds {{\n"
        assert stream_type in streams_to_events_map, stream_type
        for _, attrs in streams_to_events_map[stream_type].items():
            answer += f"{attrs['enum']} = {attrs['index']},\n"
        answer += "};"
    return answer


def event_sources_conn_code(event_sources, streams_to_events_map) -> str:
    answer = ""
    for event_source in event_sources:
        assert event_source[0] == "event_source"
        event_src_declaration = event_source[2]
        assert event_src_declaration[0] == "event-decl"
        stream_name, args = get_name_with_args(event_src_declaration[1])
        copies = TypeChecker.event_sources_data[stream_name]["copies"]

        processor_name = TypeChecker.event_sources_data[stream_name]["processor_name"]
        if processor_name.lower() == "forward":
            hole_name = "hole"
            processor_name = processor_name.lower()
            out_name = TypeChecker.event_sources_data[stream_name]["input_stream_type"]
        else:
            out_name = TypeChecker.stream_processors_data[processor_name]["output_type"]
            hole_name = TypeChecker.stream_processors_data[processor_name]["hole_name"]

        connection_kind = TypeChecker.event_sources_data[stream_name]["connection_kind"]
        assert connection_kind[0] == "conn_kind"
        buff_size = connection_kind[2]
        min_size_uninterrupt = None

        if len(connection_kind) == 4:
            min_size_uninterrupt = connection_kind[3]

        stream_type = stream_type_from_ev_source(event_source)
        out_event = f"STREAM_{stream_type}_out"
        if copies:
            for i in range(copies):
                name = f"{stream_name}_{i}"
                answer += f"\t// connect to event source {name}\n"
                answer += f"""
                shm_stream_hole_handling hh_{name} = {{
                  .hole_event_size = sizeof({out_event}),
                  .init = &init_hole_{hole_name},
                  .update = &update_hole_{hole_name}
                }};\n
                """
                answer += f'\tEV_SOURCE_{name} = shm_stream_create_from_argv("{name}", argc, argv, &hh_{name});\n'
                answer += f"\tif (!EV_SOURCE_{name}) {{\n"
                answer += f'\t\tfprintf(stderr, "Failed creating stream {name}\\n");'
                answer += "\tabort();}\n"
                answer += f"\tBUFFER_{stream_name}{i} = shm_arbiter_buffer_create(EV_SOURCE_{name},  sizeof(STREAM_{out_name}_out), {buff_size});\n\n"
                if min_size_uninterrupt is not None:
                    answer += f"\tshm_arbiter_buffer_set_drop_space_threshold(BUFFER_{stream_name}{i},{min_size_uninterrupt});\n"
                answer += f"\t// register events in {name}\n"
                for ev_name, attrs in streams_to_events_map[stream_type].items():
                    if ev_name in ("hole", hole_name):
                        continue
                    answer += f"\tif (shm_stream_register_event(EV_SOURCE_{name}, \"{ev_name}\", {attrs['enum']}) < 0) {{\n"
                    answer += f'\t\tfprintf(stderr, "Failed registering event {ev_name} for stream {name} : {stream_type}\\n");\n'
                    answer += f'\t\tfprintf(stderr, "Available events:\\n");\n'
                    answer += f"\t\tshm_stream_dump_events(EV_SOURCE_{name});\n"
                    answer += f"\t\tabort();\n\t}}\n"
        else:
            name = f"{stream_name}"
            answer += f"\t// connect to event source {name}\n"
            answer += f"""
                shm_stream_hole_handling hh_{name} = {{
                  .hole_event_size = sizeof({out_event}),
                  .init = &init_hole_{hole_name},
                  .update = &update_hole_{hole_name}
                }};\n
                """
            answer += f'\tEV_SOURCE_{name} = shm_stream_create_from_argv("{name}", argc, argv, &hh_{name});\n'
            answer += f"\tBUFFER_{stream_name} = shm_arbiter_buffer_create(EV_SOURCE_{name},  sizeof(STREAM_{out_name}_out), {buff_size});\n\n"
            if min_size_uninterrupt is not None:
                answer += f"\tshm_arbiter_buffer_set_drop_space_threshold(BUFFER_{stream_name},{min_size_uninterrupt});\n"
            answer += f"\t// register events in {name}\n"
            for ev_name, attrs in streams_to_events_map[stream_type].items():
                if ev_name in ("hole", hole_name):
                    continue
                answer += f"\tif (shm_stream_register_event(EV_SOURCE_{name}, \"{ev_name}\", {attrs['enum']}) < 0) {{\n"
                answer += f'\t\tfprintf(stderr, "Failed registering event {ev_name} for stream {name} : {stream_type}\\n");\n'
                answer += f'\t\tfprintf(stderr, "Available events:\\n");\n'
                answer += f"\t\tshm_stream_dump_events(EV_SOURCE_{name});\n"
                answer += f"\t\tabort();\n\t}}\n"

    return answer


def declare_evt_srcs_threads() -> str:
    answer = ""
    for (event_source, data) in TypeChecker.event_sources_data.items():
        if data["copies"]:
            for i in range(data["copies"]):
                name = f"{event_source}_{i}"
                answer += f"thrd_t THREAD_{name};\n"
        else:
            answer += f"thrd_t THREAD_{event_source};\n"

    return answer


def declare_arbiter_buffers(components, ast) -> str:
    assert ast[0] == "main_program"
    event_srcs_names = get_event_sources_copies(components["event_source"])

    answer = ""
    for (name, copies) in event_srcs_names:
        if copies == 0:
            answer += f"// Arbiter buffer for event source {name}\n"
            answer += f"shm_arbiter_buffer *BUFFER_{name};\n\n"
        else:
            for i in range(copies):
                answer += f"// Arbiter buffer for event source {name} ({i})\n"
                answer += f"shm_arbiter_buffer *BUFFER_{name}{i};\n\n"
    return answer


def activate_threads() -> str:
    answer = ""
    for (event_source, data) in TypeChecker.event_sources_data.items():
        processor_name = data["processor_name"]
        if processor_name.lower() == "forward":
            tail_perf_layer = f"_{data['input_stream_type']}"
        else:
            tail_perf_layer = ""
        copies = data["copies"]
        if copies:
            for i in range(copies):
                name = f"{event_source}_{i}"
                answer += f"\tthrd_create(&THREAD_{name}, (void*)PERF_LAYER_{processor_name}{tail_perf_layer},BUFFER_{event_source}{i});\n"
        else:
            answer += f"\tthrd_create(&THREAD_{event_source}, (void*)PERF_LAYER_{processor_name}{tail_perf_layer},BUFFER_{event_source});\n"

    return answer


def activate_buffers() -> str:
    answer = ""
    for (event_source, data) in TypeChecker.event_sources_data.items():
        if data["copies"]:
            for i in range(data["copies"]):
                name = f"{event_source}{i}"
                answer += f"\tshm_arbiter_buffer_set_active(BUFFER_{name}, true);\n"
        else:
            answer += f"\tshm_arbiter_buffer_set_active(BUFFER_{event_source}, true);\n"

    return answer


def process_performance_match(tree) -> str:
    if tree[0] == "perf_match1":
        performance_action = tree[PPPERF_MATCH_ACTION]
        if performance_action[0] == "perf_act_drop":
            return "return false;"
        else:

            assert performance_action[0] == "perf_act_forward"
            return "return true;"
    else:
        assert tree[0] == "perf_match2"
        return f"""if ({tree[PPPERF_MATCH_EXPRESSION]}) {"{"}
            {process_performance_match(tree[PPPERF_MATCH_TRUE_PART])}
        {"}"} else {"{"}
            {process_performance_match(tree[PPPERF_MATCH_FALSE_PART])}
        {"}"}
        """


def instantiate_args(stream_name, event_name, new_arg_names):
    original_args = TypeChecker.args_table[f"EVENT_{stream_name}_{event_name}"]
    declared_args = ""
    for (original_arg, new_arg) in zip(original_args, new_arg_names):
        original_name = original_arg["name"]
        arg_type = original_arg["type"]
        declared_args += f"\t\t{arg_type} {new_arg} = ((STREAM_{stream_name}_in *)inevent)->cases.{event_name}.{original_name};\n"
    return declared_args


def build_drop_funcs_conds(rules, stream_name, mapping) -> str:
    for rule in rules:
        # TODO: missing implementation of creates at most
        event = rule["event"]
        return f"""
    if (inevent->kind == {mapping[event]["enum"]}) {"{"}
{instantiate_args(stream_name, event, rule["event_args"])}
        {process_performance_match(rule["performance_match"])}
    {"}"}
        """


def build_should_keep_funcs(mapping) -> str:
    answer = f"""
bool SHOULD_KEEP_forward(shm_stream * s, shm_event * e) {"{"}
    return true;
{"}"}
"""

    for (stream_processor, data) in TypeChecker.stream_processors_data.items():
        performance_layer_rule_list = data["perf_layer_rule_list"]
        stream_type = data["input_type"]
        extend_processor_name = data["extends_node"][0]
        if extend_processor_name is None:
            extend_processor_name = "forward"
        if extend_processor_name.lower() == "forward":
            extend_processor_name = extend_processor_name.lower()
        answer += f"""bool SHOULD_KEEP_{stream_processor}(shm_stream * s, shm_event * inevent) {"{"}
{build_drop_funcs_conds(performance_layer_rule_list, stream_type, mapping[stream_type])}
    return SHOULD_KEEP_{extend_processor_name}(s, inevent);
{"}"}
"""
    return answer


def assign_args(event_name, args, list_expressions, level) -> str:
    expressions = []
    get_expressions(list_expressions, expressions)
    answer = ""
    tabs = "\t" * level
    for (arg, expr) in zip(args, expressions):
        answer += f"{tabs}outevent->cases.{event_name}.{arg[0]} = {expr};\n"
    return answer


def declare_performance_layer_args(
    event_case: str, mapping_in: Dict[str, Any], ids
) -> str:
    to_declare_ids = []
    get_expressions(ids, to_declare_ids)
    assert len(to_declare_ids) == len(mapping_in["args"])
    answer = ""
    args = mapping_in["args"]
    for i in range(len(to_declare_ids)):
        answer += f"{args[i][1]} {to_declare_ids[i]} = inevent->cases.{event_case}.{args[i][0]} ;\n"
    return answer


def build_switch_performance_match(
    tree, input_event, mapping_in, mapping_out, stream_type, level
) -> str:
    if tree[0] == "perf_match1":
        performance_action = tree[PPERF_MATCH_ACTION]
        if performance_action[0] == "perf_act_drop":
            # this shouldn't happen
            return "return 1;"
        else:
            tabs = "\t" * level
            assert performance_action[0] == "perf_act_forward"

            event_out_name = performance_action[PPPERF_ACTION_FORWARD_EVENT]
            if event_out_name.lower() == "forward":
                event_out_name = input_event
                assign_args_code = (
                    f"memcpy(outevent, inevent, sizeof(STREAM_{stream_type}_in));\n"
                )
            else:
                assign_args_code = f"""
{tabs}(outevent->head).kind = {mapping_out[event_out_name]["enum"]};
{tabs}(outevent->head).id = (inevent->head).id;
{declare_performance_layer_args(event_out_name,
                                mapping_in[event_out_name],
                                performance_action[PPPERF_ACTION_FORWARD_EXPRS])}
{assign_args(event_out_name, mapping_out[event_out_name]["args"],
             performance_action[PPPERF_ACTION_FORWARD_EXPRS], level)}
                """

            return f"""

{tabs}{assign_args_code}
{tabs}shm_arbiter_buffer_write_finish(buffer);
            """
    else:
        assert tree[0] == "perf_match2"
        return f"""
        if ({tree[PPPERF_MATCH_EXPRESSION]}) {"{"}
            {build_switch_performance_match(tree[PPPERF_MATCH_TRUE_PART], input_event, mapping_in, mapping_out, level + 1)}
        {"}"} else {"{"}
            {build_switch_performance_match(tree[PPPERF_MATCH_FALSE_PART], input_event, mapping_in, mapping_out, level + 1)}
        {"}"}"""


def get_stream_switch_cases(cases, mapping_in, mapping_out, out_name, level) -> str:
    answer = ""
    for case in cases:
        if case["stream_type"] is None:
            answer += f"""
case {mapping_in[event_name]["enum"]}:
    {build_switch_performance_match(case["performance_match"], event_name, mapping_in, mapping_out, level=level + 1)}
    break;"""
        else:
            assert case["buff_group"] is not None
            assert case["process_using"] is not None
            creates_code = ""
            buffer_kind = case["connection_kind"]["type"]
            event_name, event_args = case["event"], case["event_args"]
            buffer_group = case["buff_group"]
            stream_processor_name = case["process_using"]
            if buffer_kind != "autodrop":
                raise Exception("implement of non-autodrop buffer missing!")
            buff_size = case["connection_kind"]["size"]
            stream_type = case["stream_type"]
            init_stream_args_code = instantiate_args(
                stream_type, event_name, event_args
            )
            original_sp_args = TypeChecker.stream_processors_data[
                stream_processor_name
            ]["output_args"]
            stream_type_args = TypeChecker.args_table[stream_type]

            for (original_arg, new_arg) in zip(
                TypeChecker.args_table[stream_processor_name],
                case["process_using_args"],
            ):
                assert type(new_arg) == str
                init_stream_args_code += (
                    f"{original_arg[2][1]} {original_arg[1]} = {new_arg};\n"
                )

            for (arg, sp_arg) in zip(stream_type_args, original_sp_args):
                init_stream_args_code += (
                    f"stream_args_temp->{arg['name']} = {sp_arg}; \n"
                )

            stream_args_code = f"""
STREAM_{stream_type}_ARGS * stream_args_temp = malloc(sizeof(STREAM_{stream_type}_ARGS));
{init_stream_args_code}
mtx_lock(&LOCK_{buffer_group});
bg_insert(&BG_{buffer_group}, ev_source_temp, temp_buffer,stream_args_temp,{buffer_group}_ORDER_EXP);
mtx_unlock(&LOCK_{buffer_group});
"""
            stream_threshold_code = f""
            min_size_uninterrupt = case["connection_kind"]["threshold"]
            if min_size_uninterrupt > 2:
                stream_threshold_code = f"\tshm_arbiter_buffer_set_drop_space_threshold(temp_buffer,{min_size_uninterrupt});\n"

            hole_name = TypeChecker.stream_processors_data[stream_processor_name][
                "hole_name"
            ]
            out_event = f"STREAM_{stream_type}_out"
            creates_code = f"""
            shm_stream_hole_handling hole_handling = {{
              .hole_event_size = sizeof({out_event}),
              .init = &init_hole_{hole_name},
              .update = &update_hole_{hole_name}
            }};
            shm_stream *ev_source_temp = shm_stream_create_substream(stream, NULL, NULL, NULL, NULL, &hole_handling);
            if (!ev_source_temp) {{
                fprintf(stderr, "Failed creating substream for '{out_name}'\\n");
                abort();
            }}
            shm_arbiter_buffer *temp_buffer = shm_arbiter_buffer_create(ev_source_temp,  sizeof(STREAM_{out_name}_out), {buff_size});
            {stream_threshold_code}
            shm_stream_register_all_events(ev_source_temp);
            {stream_args_code}
            thrd_t temp_thread;
            thrd_create(&temp_thread, (void*)PERF_LAYER_{stream_processor_name}, temp_buffer);
            shm_arbiter_buffer_set_active(temp_buffer, true);
            """
            answer += f"""
                case {mapping_in[event_name]["enum"]}:
                {build_switch_performance_match(case['performance_match'], event_name, mapping_in, mapping_out,stream_type, level=level + 1)}
                {creates_code}
                break;
                """
    return answer


def declare_perf_layer_funcs(mapping) -> str:
    answer = ""

    for stream_type in TypeChecker.stream_types_data.keys():
        answer += f"""
int PERF_LAYER_forward_{stream_type} (shm_arbiter_buffer *buffer) {"{"}
    atomic_fetch_add(&count_event_streams, 1); 
    shm_stream *stream = shm_arbiter_buffer_stream(buffer);   
    void *inevent;
    void *outevent;   

    // wait for active buffer
    while ((!shm_arbiter_buffer_active(buffer))){"{"}
        sleep_ns(10);
    {"}"}
    while(true) {"{"}
        inevent = stream_filter_fetch(stream, buffer, &SHOULD_KEEP_forward);

        if (inevent == NULL) {"{"}
            // no more events
            break;
        {"}"}
        outevent = shm_arbiter_buffer_write_ptr(buffer);

        memcpy(outevent, inevent, sizeof(STREAM_{stream_type}_in));
        shm_arbiter_buffer_write_finish(buffer);
        
        shm_stream_consume(stream, 1);
    {"}"}  
    atomic_fetch_add(&count_event_streams, -1);
    return 0;   
{"}"}
        """
    for (stream_processor, data) in TypeChecker.stream_processors_data.items():
        stream_in_name = data["input_type"]
        stream_out_name = data["output_type"]
        perf_layer_list = data["perf_layer_rule_list"]
        if data["special_hole"] is None:
            hole_name = ""
        else:
            hole_name = f"_{data['hole_name']}"
        perf_layer_code = f"""
                    switch ((inevent->head).kind) {"{"}
        {get_stream_switch_cases(perf_layer_list, mapping[stream_in_name], mapping[stream_out_name], stream_out_name, level=3)}
                    default:
                        memcpy(outevent, inevent, sizeof(STREAM_{stream_in_name}_in));   
                        shm_arbiter_buffer_write_finish(buffer);
                {"}"}
                    """
        answer += f"""int PERF_LAYER_{stream_processor} (shm_arbiter_buffer *buffer) {"{"}
        atomic_fetch_add(&count_event_streams, 1); 
    shm_stream *stream = shm_arbiter_buffer_stream(buffer);   
    STREAM_{stream_in_name}_in *inevent;
    STREAM_{stream_out_name}_out *outevent;   

    // wait for active buffer
    while ((!shm_arbiter_buffer_active(buffer))){"{"}
        sleep_ns(10);
    {"}"}
    while(true) {"{"}
        inevent = stream_filter_fetch(stream, buffer, &SHOULD_KEEP_{stream_processor});

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
    return answer


# BEGIN CORRECTNESS LAYER
def declare_rule_sets(tree):
    assert tree[0] == "arbiter_def"
    rule_set_names = []
    get_rule_set_names(tree[PPARBITER_RULE_SET_LIST], rule_set_names)

    rule_set_declarations = ""
    for name in rule_set_names:
        rule_set_declarations += f"int RULE_SET_{name}();\n"
    return rule_set_declarations


def are_buffers_done():
    code = ""
    for (event_source, data) in TypeChecker.event_sources_data.items():
        copies = data["copies"]
        if copies:
            for i in range(copies):
                code += f"\tif (!shm_arbiter_buffer_is_done(BUFFER_{event_source}{i})) return 0;\n"
        else:
            code += (
                f"\tif (!shm_arbiter_buffer_is_done(BUFFER_{event_source})) return 0;\n"
            )

    for (buffer_group, data) in TypeChecker.buffer_group_data.items():
        code += f"""
    mtx_lock(&LOCK_{buffer_group});
    int BG_{buffer_group}_size = BG_{buffer_group}.size;
    update_size_chosen_streams(BG_{buffer_group}_size);
    is_selection_successful = bg_get_first_n(&BG_{buffer_group}, 1, &chosen_streams);
    mtx_unlock(&LOCK_{buffer_group});
    for (int i = 0; i < BG_{buffer_group}_size; i++) {"{"}
        if (!shm_arbiter_buffer_is_done(chosen_streams[i]->buffer)) return 0;
    {"}"}
"""

    return f"""
bool are_buffers_done() {"{"}
{code}
    return 1;
{"}"}
    """


def arbiter_code(tree, components):
    assert tree[0] == "arbiter_def"

    rule_set_names = []
    get_rule_set_names(tree[PPARBITER_RULE_SET_LIST], rule_set_names)

    rule_set_invocations = ""
    for name in rule_set_names:
        rule_set_invocations += (
            f"\t\tif (!ARB_CHANGE_ && current_rule_set == SWITCH_TO_RULE_SET_{name}) {'{'} \n"
            f"\t\t\tARB_CHANGE_ = RULE_SET_{name}();\n"
            f"\t\t{'}'}\n"
        )

    if len(rule_set_names) > 0:
        return f"""int arbiter() {"{"}

        while (!are_streams_done()) {"{"}
            ARB_CHANGE_ = false;
    {rule_set_invocations}
        {"}"}
        shm_monitor_set_finished(monitor_buffer);
        return 0;
    {"}"}
        """
    else:
        return f"""int arbiter() {"{"}

    while (!are_streams_done()) {"{"}

    {"}"}
    shm_monitor_set_finished(monitor_buffer);
    return 0;
{"}"}
    """


def rule_set_streams_condition(
    tree,
    mapping,
    stream_types,
    inner_code="",
    is_scan=False,
    context=None,
    current_tail=None,
):
    # output_stream should be the output type of the event source
    if tree[0] == "l_buff_match_exp":
        if not is_scan:
            code_tail = rule_set_streams_condition(
                tree[PLIST_TAIL],
                mapping,
                stream_types,
                inner_code,
                is_scan,
                context,
                current_tail,
            )
            code_base = rule_set_streams_condition(
                tree[PLIST_BASE_CASE],
                mapping,
                stream_types,
                code_tail,
                is_scan,
                context,
                tree[PLIST_TAIL],
            )
            return code_base
        else:
            return rule_set_streams_condition(
                tree[PLIST_BASE_CASE], mapping, stream_types, inner_code, is_scan
            ) + rule_set_streams_condition(
                tree[PLIST_TAIL], mapping, stream_types, inner_code, is_scan
            )
    elif tree[0] == "buff_match_exp":
        event_src_ref = tree[1]
        assert event_src_ref[0] == "event_src_ref"
        stream_name = event_src_ref[1]
        out_type = stream_types[stream_name][1]
        if event_src_ref[2] is not None:
            stream_name += f"{str(event_src_ref[2])}"
        if context is not None:
            if stream_name in context.keys():
                stream_name = context[stream_name]
        if len(tree) == 3:
            if not is_scan:
                if tree[PPBUFFER_MATCH_ARG1][1] == "nothing":
                    return f"""if (count_{stream_name} == 0) {"{"}
                    {inner_code}
                    {"}"}"""
                elif tree[PPBUFFER_MATCH_ARG1][1] == "done":
                    if stream_name not in TypeChecker.event_sources_data.keys():
                        return f"""if (count_{stream_name} == 0 && is_buffer_done(BUFFER_{stream_name})) {"{"}
                            {inner_code}
                        {"}"}
                        """
                    else:
                        return f"""if (count_{stream_name} == 0 && is_buffer_done(BUFFER_{stream_name})) {"{"}
                            {inner_code}
                        {"}"}
                        """
                else:
                    # check if there are n events
                    return f"""if (check_at_least_n_events(count_{stream_name}, {tree[PPBUFFER_MATCH_ARG1][1]})) {"{"}
                        {inner_code}
                    {"}"}"""
            return []

        else:
            # assert(len(tree) == 4)
            event_kinds = []
            for i in range(2, len(tree)):
                if tree[i] != "|":
                    get_event_kinds_enums(tree[i], event_kinds, mapping[out_type])

            if not is_scan:

                StaticCounter.calls_counter -= 1
                buffer_name = event_src_ref[1]
                if event_src_ref[2] is not None:
                    buffer_name += str(event_src_ref[2])
                return f"""
                if (are_events_in_head(e1_{buffer_name}, i1_{buffer_name}, e2_{buffer_name}, i2_{buffer_name}, 
                count_{buffer_name}, sizeof(STREAM_{out_type}_out), TEMPARR{StaticCounter.calls_counter}, {len(event_kinds)})) {"{"}
                    {inner_code}

                {"}"}"""
            else:
                return [event_kinds]
    elif tree[0] == "buff_match_exp-choose":
        if is_scan:
            return []
        choose_order = tree[1]

        buffer_name = tree[3]
        if context is not None:
            if buffer_name in context.keys():
                raise Exception("buffer name is in context created in match fun")
        binded_streams = []
        get_list_ids(tree[2], binded_streams)
        return get_buff_groups_combinations_code(
            buffer_name,
            binded_streams,
            choose_order,
            stream_types,
            current_tail,
            inner_code,
        )
    else:
        assert tree[0] == "buff_match_exp-args"
        match_fun_name, arg1, arg2 = tree[1], tree[2], tree[3]
        assert match_fun_name in TypeChecker.match_fun_data.keys()
        if context is None:
            context = {}

        if arg1 is not None:
            fun_bind_args = []
            get_list_ids(arg1, fun_bind_args)
            for (original_name, new_name) in zip(
                TypeChecker.match_fun_data[match_fun_name]["out_args"], fun_bind_args
            ):
                context[original_name] = new_name

        if arg2 is not None:
            new_args = []
            get_list_var_or_int(arg2, new_args)
            for (original_arg, new_arg) in zip(
                TypeChecker.match_fun_data[match_fun_name]["in_args"], new_args
            ):
                if new_arg in context.keys():
                    context[original_arg] = context[new_arg]
                else:
                    context[original_arg] = new_arg
        return rule_set_streams_condition(
            TypeChecker.match_fun_data[match_fun_name]["buffer_match_expr"],
            mapping,
            stream_types,
            inner_code,
            is_scan,
            context,
            current_tail,
        )


def construct_arb_rule_outevent(
    mapping, output_ev_source, output_event, raw_args
) -> str:
    local_args = []

    get_expressions(raw_args, local_args)

    answer = f"""arbiter_outevent->head.kind = {mapping[output_ev_source][output_event]["index"]};
    arbiter_outevent->head.id = arbiter_counter++;
    """
    for (arg, outarg) in zip(
        local_args, mapping[output_ev_source][output_event]["args"]
    ):
        if arg[0] == "field_access":
            field = arg[3]
            object_name = f"stream_args_{arg[1]}"
            if arg[2] is not None:
                object_name += f"_{arg[2]}"
            answer += f"((STREAM_{output_ev_source}_out *) arbiter_outevent)->cases.{output_event}.{outarg['name']} = {object_name}->{field};\n"
        else:
            answer += f"((STREAM_{output_ev_source}_out *) arbiter_outevent)->cases.{output_event}.{outarg['name']} = {arg};\n"
    return answer


def process_arb_rule_stmt(tree, mapping, output_ev_source) -> str:
    if tree[0] == "switch":
        switch_rule_name = tree[PPARB_RULE_STMT_SWITCH_ARB_RULE]
        # TypeChecker.assert_symbol_type(switch_rule_name, ARBITER_RULE_SET)
        return f"current_rule_set = SWITCH_TO_RULE_SET_{switch_rule_name};\n"
    if tree[0] == "yield":
        return f"""
        arbiter_outevent = (STREAM_{TypeChecker.arbiter_output_type}_out *)shm_monitor_buffer_write_ptr(monitor_buffer);
         {construct_arb_rule_outevent(mapping, output_ev_source,
                                      tree[PPARB_RULE_STMT_YIELD_EVENT], tree[PPARB_RULE_STMT_YIELD_EXPRS])}
         shm_monitor_buffer_write_finish(monitor_buffer);
        """
    if tree[0] == "drop":
        event_source_ref = tree[PPARB_RULE_STMT_DROP_EV_SOURCE]
        assert event_source_ref[0] == "event_src_ref"
        event_source_name = event_source_ref[1]
        if event_source_ref[2] is not None:
            event_source_name += f"{event_source_ref[2]}"
        return f"\tshm_arbiter_buffer_drop(BUFFER_{event_source_name}, {tree[PPARB_RULE_STMT_DROP_INT]});\n"
    if tree[0] == "remove":
        buffer_group = tree[2][1]
        return f"mtx_lock(&LOCK_{buffer_group});\nbg_remove(&BG_{buffer_group}, {tree[1]});\nmtx_unlock(&LOCK_{buffer_group});\n"
    if tree == "continue":
        return "local_continue_ = true;"
    assert tree[0] == "field_access"
    target_stream, index, field = tree[1], tree[2], tree[3]
    stream_name = target_stream
    if index is not None:
        stream_name += f"_{index}"
    return f"stream_args_{stream_name}->{field}"


def process_code_stmt_list(
    tree, mapping, binded_args, stream_types, output_ev_source
) -> str:
    assert tree[0] == "ccode_statement_l"
    if len(tree) == 2:
        return tree[PCODE_STMT_LIST_TOKEN1]

    assert len(tree) > 1

    if len(tree) == 3:
        assert tree[PCODE_STMT_LIST_TOKEN2] == ";"
        return process_arb_rule_stmt(
            tree[PCODE_STMT_LIST_TOKEN1], mapping, output_ev_source
        )

    assert len(tree) == 4

    if tree[PCODE_STMT_LIST_TOKEN3] == ";":
        return (
            tree[PCODE_STMT_LIST_TOKEN1]
            + "\n"
            + process_arb_rule_stmt(
                tree[PCODE_STMT_LIST_TOKEN2], mapping, output_ev_source
            )
        )
    else:
        assert tree[PCODE_STMT_LIST_TOKEN2] == ";"
        return (
            process_arb_rule_stmt(
                tree[PCODE_STMT_LIST_TOKEN1], mapping, output_ev_source
            )
            + "\n"
            + tree[PCODE_STMT_LIST_TOKEN3]
        )


def get_arb_rule_stmt_list_code(
    tree, mapping, binded_args, stream_types, output_ev_source
) -> str:
    if tree[0] == "arb_rule_stmt_l":
        return process_code_stmt_list(
            tree[PLIST_BASE_CASE], mapping, binded_args, stream_types, output_ev_source
        ) + get_arb_rule_stmt_list_code(
            tree[PLIST_TAIL], mapping, binded_args, stream_types, output_ev_source
        )
    else:
        assert tree[0] == "ccode_statement_l"
        return process_code_stmt_list(
            tree, mapping, binded_args, stream_types, output_ev_source
        )


def define_binded_args(binded_args, stream_types):
    answer = ""
    for (arg, data) in binded_args.items():
        event_source = data[0]
        event = data[1]
        arg_name = data[2]
        arg_type = data[3]
        stream_type_out = stream_types[event_source][1]
        index = data[4]
        stream_index = data[5]
        if stream_index is not None:
            event_source += str(stream_index)
        answer += (
            f"STREAM_{stream_type_out}_out * event_for_{arg} = (STREAM_{stream_type_out}_out *) "
            f"get_event_at_index(e1_{event_source}, i1_{event_source}, e2_{event_source}, "
            f"i2_{event_source}, sizeof(STREAM_{stream_type_out}_out), {index});\n"
            f"{arg_type} {arg} = event_for_{arg}->cases.{event}.{arg_name};\n\n"
        )
    return answer


def declare_arrays(scanned_kinds) -> str:
    answer = ""
    for kinds in scanned_kinds:
        s_kinds = [str(x) for x in kinds]
        answer += f"int TEMPARR{StaticCounter.declarations_counter}[] = {'{'}{','.join(s_kinds)}{'}'};\n"
        StaticCounter.declarations_counter += 1
    StaticCounter.calls_counter = StaticCounter.declarations_counter
    return answer


# monitor code


def declare_monitor_args(tree, event_name, event_data, count_tabs) -> str:
    tabs = "\t" * count_tabs
    ids = []
    get_list_ids(tree, ids)
    args = event_data["args"]
    assert len(ids) == len(args)

    answer = ""
    for i in range(len(args)):
        answer += f"{tabs}{args[i]['type']} {ids[i]} = received_event->cases.{event_name}.{args[i]['name']};\n"
    return answer


def monitor_events_code(tree, stream_name, possible_events, count_tabs) -> str:
    if tree[0] == "monitor_rule_l":
        return monitor_events_code(
            tree[PLIST_BASE_CASE], stream_name, possible_events, count_tabs
        ) + monitor_events_code(
            tree[PLIST_TAIL], stream_name, possible_events, count_tabs
        )
    else:
        assert tree[0] == "monitor_rule"
        event = tree[PPMONITOR_RULE_EV_NAME]
        if event.lower() == "hole":
            event = "hole"
        tabs = "\t" * count_tabs
        return f"""
{tabs}if (received_event->head.kind == {possible_events[event]["index"]}) {"{"}
{declare_monitor_args(tree[PPMONITOR_RULE_EV_ARGS], event, possible_events[event], count_tabs + 1)}
{tabs}  if ({tree[PPMONITOR_RULE_EXPR][1]}) {"{"}
{tabs}      {tree[PPMONITOR_RULE_CODE]}
{tabs}  {"}"}
{tabs}{"}"}
        """


def monitor_code(tree, mapping, arbiter_event_source) -> str:
    if arbiter_event_source in mapping.keys():
        possible_events = mapping[arbiter_event_source]
    else:
        possible_events = None

    assert tree[0] == "monitor_def"
    if tree[PPMONITOR_RULE_LIST] is not None:
        return f"""
        // monitor
        printf("-- starting monitor code \\n");
        STREAM_{arbiter_event_source}_out * received_event;
        while(true) {"{"}
            received_event = fetch_arbiter_stream(monitor_buffer);
            if (received_event == NULL) {"{"}
                break;
            {"}"}
{monitor_events_code(tree[PPMONITOR_RULE_LIST], arbiter_event_source, possible_events, 2)}
        shm_monitor_buffer_consume(monitor_buffer, 1);
    {"}"}
    """
    else:
        return f"""
// Empty Monitor  
"""


def process_where_condition(tree):
    if tree is None:
        return "true"
    if tree[0] == "l_where_expr":
        return process_where_condition(tree[1]) + process_where_condition(tree[2])
    else:
        assert tree[0] == "base_where_expr"
        if type(tree[1]) == str:
            return tree[1]
        else:
            field_access = tree[1]
            assert field_access[0] == "field_access"
            return process_arb_rule_stmt(field_access, None, None)


def get_choose_statement(binded_streams, buffer_name, choose_order):
    at_least = len(binded_streams)
    choose_count = at_least
    if (choose_order is None) or (choose_order[1] == "first"):
        choose_statement = ""
        if choose_order is None:
            choose_statement += (
                "// does not specifies order, we take first n even sources\n"
            )
        else:
            if choose_order[2]:
                choose_count = choose_order[2]
        choose_statement += f"is_selection_successful = bg_get_first_n(&BG_{buffer_name}, {at_least}, &chosen_streams);\n"
    else:
        assert choose_order[1] == "last"
        if choose_order[2]:
            choose_count = choose_order[2]
        choose_statement = f"is_selection_successful = bg_get_last_n(&BG_{buffer_name}, {at_least}, &chosen_streams);\n"
    return choose_statement, choose_count


def get_buff_groups_combinations_code(
    buffer_name,
    binded_streams,
    choose_order,
    stream_types,
    current_tail,
    inner_code,
    tree=None,
    choose_condition=None,
):
    assert buffer_name in TypeChecker.buffer_group_data.keys()

    if choose_condition is None:
        choose_code = "true"
    else:
        choose_code = process_where_condition(choose_condition)

    stream_type = TypeChecker.buffer_group_data[buffer_name]["in_stream"]

    def declare_indices():
        answer = ""
        for (index, name) in enumerate(binded_streams):
            answer += f"int index_{name} = {index};"
        return answer

    def get_local_inner_code():
        answer = ""
        for name in binded_streams:
            answer += f"shm_stream *{name} = chosen_streams[index_{name}]->stream;\n"
            answer += f"shm_arbiter_buffer *BUFFER_{name} = chosen_streams[index_{name}]->buffer;\n"
            answer += f"STREAM_{stream_type}_ARGS *stream_args_{name} = (STREAM_{stream_type}_ARGS *)chosen_streams[index_{name}]->args;\n"
            buffer_peeks_res = dict()
            existing_buffers = set()
            existing_buffers.add(name)
            if current_tail is not None:
                # buffer peeks
                local_get_buffer_peeks(
                    current_tail, TypeChecker, buffer_peeks_res, existing_buffers
                )
            else:
                assert tree is not None
                get_buffers_and_peeks(
                    tree, buffer_peeks_res, TypeChecker, existing_buffers
                )
            if name in buffer_peeks_res.keys():
                answer += f"char* e1_{name}; size_t i1_{name}; char* e2_{name}; size_t i2_{name};\n"
                answer += f"int count_{name} = shm_arbiter_buffer_peek(BUFFER_{name}, {buffer_peeks_res[name]}, "
                answer += f"(void**)&e1_{name}, &i1_{name}, (void**)&e2_{name}, &i2_{name});\n"

        answer += f"""
if({choose_code} ) {"{"}
    current_matches_+=1;
    {inner_code}
{"}"}
            """
        return answer

    loop_code = ""
    choose_statement, choose_count = get_choose_statement(
        binded_streams, buffer_name, choose_order
    )
    for (index, name) in enumerate(binded_streams):
        unique_index_code = ""
        for prev_name in binded_streams[:index]:
            unique_index_code += f"if(index_{name} == index_{prev_name}){'{'} index_{name}++; continue;{'}'}\n"
        if index > 0:
            loop_code += f"index_{name} = 0;\n"
        loop_code += f"while(index_{name} < BG_{buffer_name}_size && current_matches_ < expected_matches_){'{'}\n"
        loop_code += f"{unique_index_code}\n"
    loop_code += get_local_inner_code()
    # close loops parenthesis
    for name in binded_streams[::-1]:
        loop_code += f"index_{name}++;\n"
        loop_code += f"{'}'}\n"
    return f"""
{"{"}
    mtx_lock(&LOCK_{buffer_name});
    bg_update(&BG_{buffer_name}, {buffer_name}_ORDER_EXP);
    int BG_{buffer_name}_size = BG_{buffer_name}.size;
    update_size_chosen_streams(BG_{buffer_name}_size);
    {choose_statement}
    mtx_unlock(&LOCK_{buffer_name});
    if (is_selection_successful) {"{"}
        int expected_matches_ = {choose_count};
        int current_matches_ = 0;
        {declare_indices()}
        {loop_code}
    {"}"}
{"}"}
"""


def arbiter_rule_code(tree, mapping, stream_types, output_ev_source) -> str:
    # output_stream should be the output type of the event source
    if tree[0] == "arb_rule_list":
        return arbiter_rule_code(
            tree[PLIST_BASE_CASE], mapping, stream_types, output_ev_source
        ) + arbiter_rule_code(tree[PLIST_TAIL], mapping, stream_types, output_ev_source)
    else:

        if tree[0] == "arbiter_rule1":
            binded_args = dict()
            get_buff_math_binded_args(
                tree[PPARB_RULE_LIST_BUFF_EXPR],
                stream_types,
                mapping,
                binded_args,
                TypeChecker.buffer_group_data,
                TypeChecker.match_fun_data,
            )
            events_to_retrieve = dict()
            get_num_events_to_retrieve(
                tree[PPARB_RULE_LIST_BUFF_EXPR],
                events_to_retrieve,
                TypeChecker.match_fun_data,
            )
            scanned_conditions = rule_set_streams_condition(
                tree[PPARB_RULE_LIST_BUFF_EXPR], mapping, stream_types, is_scan=True
            )
            stream_drops_code = ""
            stream_drops = dict()
            get_count_drop_events_from_l_buff(tree[1], stream_drops)
            if len(stream_drops.keys()) != 0:
                assert len(stream_drops.keys()) > 0
                for (stream, count) in stream_drops.items():
                    stream_drops_code += (
                        f"\tshm_arbiter_buffer_drop(BUFFER_{stream}, {count});\n"
                    )
            inner_code = f"""
            {define_binded_args(binded_args, stream_types)}
           
            if({process_where_condition(tree[PPARB_RULE_CONDITION_CODE])}) {"{"}
                bool local_continue_ = false;
                {get_arb_rule_stmt_list_code(tree[PPARB_RULE_STMT_LIST], mapping, binded_args, stream_types, output_ev_source)}
                {stream_drops_code}

                if (!local_continue_) {"{"}
                    return 1;
                {"}"}
            {"}"}
            """
            return f"""
            {declare_arrays(scanned_conditions)}
            {rule_set_streams_condition(tree[PPARB_RULE_LIST_BUFF_EXPR], mapping, stream_types, inner_code)}
            """
        else:
            assert tree[0] == "arbiter_rule2"
            binded_streams = []
            get_list_ids(tree[2], binded_streams)
            choose_condition = tree[4]

            choose_order = tree[1]
            buffer_name = tree[3]
            # TODO: get output type of event source correctly
            for stream in binded_streams:
                stream_types[stream] = (
                    TypeChecker.buffer_group_data[buffer_name]["in_stream"],
                    TypeChecker.buffer_group_data[buffer_name]["in_stream"],
                )
            for stream in binded_streams:
                stream_types[stream] = (
                    TypeChecker.buffer_group_data[buffer_name]["in_stream"],
                    TypeChecker.buffer_group_data[buffer_name]["in_stream"],
                )
            inner_code = arbiter_rule_code(
                tree[5], mapping, stream_types, output_ev_source
            )
            return get_buff_groups_combinations_code(
                buffer_name,
                binded_streams,
                choose_order,
                stream_types,
                None,
                inner_code,
                tree[5],
                choose_condition,
            )


def buffer_peeks(tree, existing_buffers):
    answer = ""
    buffers_to_peek = (
        dict()
    )  # maps buffer_name to the number of elements we want to retrieve from the buffer
    get_buffers_and_peeks(tree, buffers_to_peek, TypeChecker, existing_buffers)
    for (buffer_name, desired_count) in buffers_to_peek.items():
        answer += (
            f"char* e1_{buffer_name}; size_t i1_{buffer_name}; char* e2_{buffer_name}; size_t i2_{buffer_name};\n"
            f"int count_{buffer_name} = shm_arbiter_buffer_peek(BUFFER_{buffer_name}, {desired_count}, "
            f"(void**)&e1_{buffer_name}, &i1_{buffer_name}, (void**)&e2_{buffer_name}, &i2_{buffer_name});\n"
        )

    return answer


def print_dll_node_code(buffer_group_name, buffer_to_src_idx):
    buffer_group_type = TypeChecker.buffer_group_data[buffer_group_name]["in_stream"]
    assert buffer_group_type in buffer_to_src_idx.keys()

    print_args_code = ""

    for arg_data in TypeChecker.stream_types_data[buffer_group_type]["arg_types"]:
        iterpol_code = ""
        if arg_data["type"] in ["int", "uint16_t", "int16_t"]:
            interpol_code = "%d"
        elif arg_data["type"] in ["uint64_t"]:
            interpol_code = "%lu"
        else:
            raise Exception(f"implement interpolation code {arg_data['type']}")
        print_args_code += f'\tprintf("{arg_data["name"]} = {interpol_code}\\n", ((STREAM_{buffer_group_type}_ARGS *) current->args)->{arg_data["name"]});\n'

    return f"""
    printf(\"{buffer_group_name}[%d].ARGS{"{"}\", i);
{print_args_code}
    printf(\"{"}"}\\n\");
    char* e1_BG; size_t i1_BG; char* e2_BG; size_t i2_BG;
    int COUNT_BG_TEMP_ = shm_arbiter_buffer_peek(current->buffer, 5, (void**)&e1_BG, &i1_BG, (void**)&e2_BG, &i2_BG);
    printf(\"{buffer_group_name}[%d].buffer{"{"}\\n\", i);
    print_buffer_prefix(current->buffer, {buffer_to_src_idx[buffer_group_type]}, i1_BG + i2_BG, COUNT_BG_TEMP_, e1_BG, i1_BG, e2_BG, i2_BG);
    printf(\"{"}"}\\n\");
"""


def check_progress(rule_set_name, tree, existing_buffers):
    buffers_to_peek = (
        dict()
    )  # maps buffer_name to the number of elements we want to retrieve from the buffer
    get_buffers_and_peeks(tree, buffers_to_peek, TypeChecker, existing_buffers)

    answer = "_Bool ok = 1;\n"
    n = 0
    if buffers_to_peek:
        for (buffer_name, desired_count) in buffers_to_peek.items():
            answer += f"if (count_{buffer_name} >= {desired_count}) {'{'}"
            n += 1
        answer += "\tok = 0;\n"
        answer += "}" * n

    answer += "\n"

    answer += "if (ok == 0) {\n"

    buffer_to_src_idx = {bn: -1 for bn in existing_buffers}
    for (event_source_index, stream_type) in enumerate(
        TypeChecker.stream_types_data.keys()
    ):
        buffer_to_src_idx[stream_type] = event_source_index

    for (ev_source, data) in TypeChecker.event_sources_data.items():
        src_idx = buffer_to_src_idx[data["output_stream_type"]]
        if data["copies"]:
            for i in range(data["copies"]):
                buffer_name = ev_source + str(i)
                if buffer_name in buffers_to_peek.keys():
                    answer += f"\tfprintf(stderr, \"Prefix of '{buffer_name}':\\n\");\n"
                    answer += f"\tcount_{buffer_name} = shm_arbiter_buffer_peek(BUFFER_{buffer_name}, 5, (void**)&e1_{buffer_name}, &i1_{buffer_name}, (void**)&e2_{buffer_name}, &i2_{buffer_name});\n"
                    answer += f"\tprint_buffer_prefix(BUFFER_{buffer_name}, {src_idx}, i1_{buffer_name} + i2_{buffer_name}, count_{buffer_name}, e1_{buffer_name}, i1_{buffer_name}, e2_{buffer_name}, i2_{buffer_name});\n"
        else:
            buffer_name = ev_source
            if buffer_name in buffers_to_peek.keys():
                answer += f"\tfprintf(stderr, \"Prefix of '{buffer_name}':\\n\");\n"
                answer += f"\tcount_{buffer_name} = shm_arbiter_buffer_peek(BUFFER_{buffer_name}, 5, (void**)&e1_{buffer_name}, &i1_{buffer_name}, (void**)&e2_{buffer_name}, &i2_{buffer_name});\n"
                answer += f"\tprint_buffer_prefix(BUFFER_{buffer_name}, {src_idx}, i1_{buffer_name} + i2_{buffer_name}, count_{buffer_name}, e1_{buffer_name}, i1_{buffer_name}, e2_{buffer_name}, i2_{buffer_name});\n"
    answer += f"fprintf(stderr, \"No rule in rule set '{rule_set_name}' matched even though there was enough events, CYCLING WITH NO PROGRESS (exiting)!\\n\");"
    answer += "__work_done=1; abort();"
    answer += "}\n"

    answer += f"if (++RULE_SET_{rule_set_name}_nomatch_cnt > 8000000) {{\
        \tRULE_SET_{rule_set_name}_nomatch_cnt = 0;"
    answer += f"\tfprintf(stderr, \"\\033[31mRule set '{rule_set_name}' cycles long time without progress\\033[0m\\n\");"
    for (ev_source, data) in TypeChecker.event_sources_data.items():

        src_idx = buffer_to_src_idx[data["output_stream_type"]]
        if data["copies"]:
            for i in range(data["copies"]):
                buffer_name = ev_source + str(i)
                if buffer_name in buffers_to_peek.keys():
                    answer += f"\tfprintf(stderr, \"Prefix of '{buffer_name}':\\n\");\n"
                    answer += f"\tcount_{buffer_name} = shm_arbiter_buffer_peek(BUFFER_{buffer_name}, 5, (void**)&e1_{buffer_name}, &i1_{buffer_name}, (void**)&e2_{buffer_name}, &i2_{buffer_name});\n"
                    answer += f"\tprint_buffer_prefix(BUFFER_{buffer_name}, {src_idx}, i1_{buffer_name} + i2_{buffer_name}, count_{buffer_name}, e1_{buffer_name}, i1_{buffer_name}, e2_{buffer_name}, i2_{buffer_name});\n"
        else:
            buffer_name = ev_source
            if buffer_name in buffers_to_peek.keys():
                answer += f"\tfprintf(stderr, \"Prefix of '{buffer_name}':\\n\");\n"
                answer += f"\tcount_{buffer_name} = shm_arbiter_buffer_peek(BUFFER_{buffer_name}, 5, (void**)&e1_{buffer_name}, &i1_{buffer_name}, (void**)&e2_{buffer_name}, &i2_{buffer_name});\n"
                answer += f"\tprint_buffer_prefix(BUFFER_{buffer_name}, {src_idx}, i1_{buffer_name} + i2_{buffer_name}, count_{buffer_name}, e1_{buffer_name}, i1_{buffer_name}, e2_{buffer_name}, i2_{buffer_name});\n"
    for (buffer_group, data) in TypeChecker.buffer_group_data.items():
        answer += f'printf("***** BUFFER GROUPS *****\\n");\n'
        answer += f'printf("***** {buffer_group} *****\\n");\n'
        answer += f"dll_node *current = BG_{buffer_group}.head;\n"
        answer += f"{'{'}int i = 0; \n while (current){'{'} {print_dll_node_code(buffer_group, buffer_to_src_idx)} current = current->next;\n i+=1;\n{'}'}\n{'}'}"

    answer += 'fprintf(stderr, "Seems all rules are waiting for some events that are not coming\\n");'
    answer += "}\n"

    return answer


def build_rule_set_functions(tree, mapping, stream_types, existing_buffers):
    def local_explore_rule_list(local_tree) -> str:
        if local_tree[0] == "arb_rule_list":
            return local_explore_rule_list(local_tree[1]) + local_explore_rule_list(
                local_tree[2]
            )
        elif local_tree[0] == "always":
            return f""""""
        else:
            assert local_tree[0] == "arbiter_rule1" or local_tree[0] == "arbiter_rule2"
            return arbiter_rule_code(
                local_tree, mapping, stream_types, TypeChecker.arbiter_output_type
            )

    def local_explore_arb_rule_set_list(local_tree) -> str:
        if local_tree is not None:
            if local_tree[0] == "arb_rule_set_l":
                return local_explore_arb_rule_set_list(
                    local_tree[1]
                ) + local_explore_arb_rule_set_list(local_tree[2])
            else:
                assert local_tree[0] == "arbiter_rule_set"
                rule_set_name = local_tree[1]
                return (
                    f"int RULE_SET_{rule_set_name}() {'{'}\n"
                    f"{buffer_peeks(local_tree[2], existing_buffers)}"
                    f"{local_explore_rule_list(local_tree[2])}"
                    f"{check_progress(rule_set_name, local_tree[2], existing_buffers)}"
                    f"{TypeChecker.always_code}"
                    f"\treturn 0;\n"
                    f"{'}'}"
                )
        else:
            return ""

    assert tree[0] == "arbiter_def"

    arbiter_rule_set_list = tree[2]
    return local_explore_arb_rule_set_list(arbiter_rule_set_list)


def destroy_all():
    answer = ""

    # destroy buffer groups
    for buffer_group in TypeChecker.buffer_group_data.keys():
        answer += f"\tdestroy_buffer_group(&BG_{buffer_group});\n"
        answer += f"\tmtx_destroy(&LOCK_{buffer_group});\n"

    # destroy event sources
    for (event_source, data) in TypeChecker.event_sources_data.items():
        if data["copies"]:
            for i in range(data["copies"]):
                name = f"{event_source}_{i}"
                answer += f"\tshm_stream_destroy(EV_SOURCE_{name});\n"
        else:
            answer += f"\tshm_stream_destroy(EV_SOURCE_{event_source});\n"

    # destroy buffers
    for (event_source, data) in TypeChecker.event_sources_data.items():
        if data["copies"]:
            for i in range(data["copies"]):
                name = f"{event_source}{i}"
                answer += f"\tshm_arbiter_buffer_free(BUFFER_{name});\n"
        else:
            answer += f"\tshm_arbiter_buffer_free(BUFFER_{event_source});\n"

    answer += "\tfree(monitor_buffer);\n"
    answer += "\tfree(chosen_streams);\n"

    for (stream_name, data) in TypeChecker.event_sources_data.items():
        if len(data["input_stream_args"]) > 0:
            if data["copies"]:
                for i in range(data["copies"]):
                    answer += f"\tfree(stream_args_{stream_name}_{i});\n"
            else:
                answer += f"\tfree(stream_args_{stream_name});\n"
    return answer


def get_event_at_head():
    return f"""
int get_event_at_head(shm_arbiter_buffer *b) {"{"}
    void * e1; size_t i1;
    void * e2; size_t i2;

    int count = shm_arbiter_buffer_peek(b, 0, &e1, &i1, &e2, &i2);
    if (count == 0) {"{"}
        return -1;
    {"}"}
    shm_event * ev = (shm_event *) (e1);
    return ev->kind;
{"}"}
    """


def print_event_name(stream_types, mapping):
    def local_build_if_from_events(events) -> str:
        answer = ""
        for (event, data) in events.items():
            answer += f"""
        if (event_index == {data['index']} ) {"{"}
            printf("{event}\\n");
            return;
        {"}"}
            """
        return answer

    code = ""
    for (event_source_index, (event_source, data)) in enumerate(
        TypeChecker.event_sources_data.items()
    ):

        output_type = stream_types[event_source][0]
        code += f"""
    if(ev_src_index == {event_source_index}) {"{"}
        {local_build_if_from_events(mapping[output_type])}
        printf("No event matched! this should not happen, please report!\\n");
        return;
    {"}"}
        """

    return f"""
void print_event_name(int ev_src_index, int event_index) {"{"}
    if (event_index == -1) {"{"}
        printf("None\\n");
        return;
    {"}"}

    if (event_index == 1) {"{"}
        printf("hole\\n");
        return;
    {"}"}

    {code}
    printf("Invalid event source! this should not happen, please report!\\n");
{"}"}
    """


def get_event_name(stream_types, mapping):
    def local_build_if_from_events(events) -> str:
        answer = ""
        for (event, data) in events.items():
            answer += f"""
        if (event_index == {data['index']} ) {"{"}
            return "{event}";
        {"}"}
            """
        return answer

    code = ""
    for (event_source_index, output_type) in enumerate(
        TypeChecker.stream_types_data.keys()
    ):
        code += f"""
    if(ev_src_index == {event_source_index}) {"{"}
        {local_build_if_from_events(mapping[output_type])}
        fprintf(stderr, "No event matched! this should not happen, please report!\\n");
        return "";
    {"}"}
        """

    return f"""
const char *get_event_name(int ev_src_index, int event_index) {"{"}
    if (event_index == -1) {"{"}
        return "<none>";
    {"}"}
    
    if (event_index == 1) {"{"}
        return "hole";
    {"}"}
    
    {code}
    printf("Invalid event source! this should not happen, please report!\\n");
    return 0;
{"}"}
    """


def print_buffers_state():
    code = "int count;\n" "void *e1, *e2;\n" "size_t i1, i2;\n\n"
    for (event_source_index, (event_source, data)) in enumerate(
        TypeChecker.event_sources_data.items()
    ):
        copies = data["copies"]
        if copies:
            for i in range(copies):
                buffer_name = event_source + str(i)
                code += f"\tfprintf(stderr, \"Prefix of '{buffer_name}':\\n\");\n"
                code += f"\tcount = shm_arbiter_buffer_peek(BUFFER_{buffer_name}, 10, &e1, &i1, &e2, &i2);\n"
                code += f"\tprint_buffer_prefix(BUFFER_{buffer_name}, {event_source_index}, i1 + i2, count, e1, i1, e2, i2);\n"
        else:
            buffer_name = event_source
            code += f"\tfprintf(stderr, \"Prefix of '{buffer_name}':\\n\");\n"
            code += f"\tcount = shm_arbiter_buffer_peek(BUFFER_{buffer_name}, 10, (void**)&e1, &i1, (void**)&e2, &i2);\n"
            code += f"\tprint_buffer_prefix(BUFFER_{buffer_name}, {event_source_index}, i1 + i2, count, e1, i1, e2, i2);\n"
    return f"""
void print_buffers_state() {"{"}
    int event_index;
{code}
{"}"}

static void print_buffer_state(shm_arbiter_buffer *buffer) {{
    int count;
    void *e1, *e2;
    size_t i1, i2;
    count = shm_arbiter_buffer_peek(buffer, 10, (void**)&e1, &i1, (void**)&e2, &i2);
    print_buffer_prefix(buffer, -1, i1 + i2, count, e1, i1, e2, i2);
}}

"""


def declare_const_rule_set_names(tree):
    assert tree[0] == "arbiter_def"

    rule_set_names = []
    get_rule_set_names(tree[PPARBITER_RULE_SET_LIST], rule_set_names)

    ans = ""
    for (index, name) in enumerate(rule_set_names):
        ans += f"const int SWITCH_TO_RULE_SET_{name} = {index};\n"
    return ans


def declare_rule_set_counters(tree):
    assert tree[0] == "arbiter_def"

    rule_set_names = []
    get_rule_set_names(tree[PPARBITER_RULE_SET_LIST], rule_set_names)

    ans = ""
    for (index, name) in enumerate(rule_set_names):
        ans += f"static size_t RULE_SET_{name}_nomatch_cnt = 0;\n"
    return ans


def get_imports():
    return f"""
#include <threads.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdatomic.h>
#include <assert.h>
#include <limits.h>

#include "shamon/core/arbiter.h"
#include "shamon/core/monitor.h"
#include "shamon/core/utils.h"
#include "shamon/streams/streams.h"

#include "compiler/cfiles/compiler_utils.h"
"""


def special_hole_structs():
    answer = ""
    for (stream_processor, data) in TypeChecker.stream_processors_data.items():
        if data["special_hole"] is not None:
            # TODO: set correctly data types of fields
            hole_name = data["hole_name"]
            fields = ""
            for data_arg in data["special_hole"]:
                fields += f"\t{data_arg['type']} {data_arg['attribute']};\n"
            answer += f"""
struct _EVENT_{hole_name}_hole
{"{"}
{fields}
{"}"};
typedef struct _EVENT_{hole_name}_hole EVENT_{hole_name}_hole;
"""
    return answer


def get_special_holes_init_code(streams_to_events_map):
    answer = ""
    for (stream_processor, data) in TypeChecker.stream_processors_data.items():
        stream_type_in = data["input_type"]
        data_hole = data["special_hole"]
        hole_name = data["hole_name"]
        init_attributes = ""
        for attr_data in data_hole:
            if attr_data["agg_func_name"].upper() == "COUNT":
                value = 0
            elif attr_data["agg_func_name"].upper() == "MIN":
                if attr_data["type"] == "int":
                    value = "INT_MAX"
                elif attr_data["type"] == "uint64_t":
                    value = "ULLONG_MAX"
                else:
                    raise Exception(
                        f"We dont cover this data {attr_data['type']} for agg function {attr_data['agg_func_name']}."
                    )
            elif attr_data["agg_func_name"].upper() == "MAX":
                if attr_data["type"] == "int":
                    value = "INT_MIN"
                elif attr_data["type"] == "uint64_t":
                    value = "0"
                else:
                    raise Exception(
                        f"We dont cover this data {attr_data['type']} for agg function {attr_data['agg_func_name']}."
                    )
            else:
                raise Exception(
                    f"Unknown aggregation function {attr_data['agg_func_name']}."
                )

            init_attributes += f"\th->{attr_data['attribute']} = {value};\n"
        hole_enum = streams_to_events_map[stream_type_in][hole_name]["enum"]
        answer += f"""
static void init_hole_{hole_name}(shm_event *hev) {"{"}
  STREAM_{stream_type_in}_in *e = (STREAM_{stream_type_in}_in*) hev;
  e->head.kind = {hole_enum};

  EVENT_{hole_name}_hole *h = &e->cases.{hole_name};
  {init_attributes}
{"}"}
"""
    return answer


def get_special_holes_update_code(mapping):

    answer = ""
    for (stream_processor, data) in TypeChecker.stream_processors_data.items():
        stream_type = data["input_type"]
        data_events = mapping[stream_type]
        hole_name = data["hole_name"]
        all_events = list(TypeChecker.stream_types_data[stream_type]["events"].keys())
        event_to_holes_data = get_events_to_hole_update_data(
            data["special_hole"], all_events
        )
        update_attributes_code = ""
        for event in all_events:
            event_code = ""
            event_hole_data_ = event_to_holes_data[event]
            for event_hole_data in event_hole_data_:
                if event_hole_data["ev_attr"] is None:
                    assert event_hole_data["agg_func"] == "count"
                    event_code += f"\t\t\th->{event_hole_data['hole_attr']}++;\n"
                else:
                    if event_hole_data["agg_func"] == "count":
                        event_code += f"\t\t\th->{event_hole_data['hole_attr']}+=((STREAM_{stream_type}_in *) ev)->cases.{event}.{event_hole_data['ev_attr']};\n"
                    elif event_hole_data["agg_func"] == "MAX":
                        event_code += f"\t\t\th->{event_hole_data['hole_attr']} = __vamos_max(h->{event_hole_data['hole_attr']},((STREAM_{stream_type}_in *) ev)->cases.{event}.{event_hole_data['ev_attr']});\n"
                    elif event_hole_data["agg_func"] == "MIN":
                        event_code += f"\t\t\th->{event_hole_data['hole_attr']} = __vamos_min(h->{event_hole_data['hole_attr']},((STREAM_{stream_type}_in *) ev)->cases.{event}.{event_hole_data['ev_attr']});\n"
                    else:
                        raise Exception("Not implmented")
            update_attributes_code += f"""
        case {data_events[event]["enum"]}:
{event_code}
            break;"""
        answer += f"""
static void update_hole_{hole_name}(shm_event *hev, shm_event *ev) {"{"}
    STREAM_{stream_type}_in *e = (STREAM_{stream_type}_in*) hev;
    EVENT_{hole_name}_hole *h = &e->cases.{hole_name};
    switch (ev->kind) {"{"}
{update_attributes_code}
    {"}"}
{"}"}
"""
    return answer


def generate_special_hole_functions(streams_to_events_map):
    answer = f"{get_special_holes_init_code(streams_to_events_map)}\n"
    answer += f"{get_special_holes_update_code(streams_to_events_map)}\n"

    return answer


def outside_main_code(
    components,
    streams_to_events_map,
    stream_types,
    ast,
    arbiter_event_source,
    existing_buffers,
):
    return f"""

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
{events_enum_kinds(components["event_source"], streams_to_events_map)}
{special_hole_structs()}
{stream_type_structs(components["stream_type"])}
{generate_special_hole_functions(streams_to_events_map)}

{stream_type_args_structs(components["stream_type"])}


{instantiate_stream_args()}
int arbiter_counter;
bool ARB_CHANGE_ = false;
// monitor buffer
shm_monitor_buffer *monitor_buffer;

bool is_selection_successful;
dll_node **chosen_streams; // used in rule set for get_first/last_n
int current_size_chosen_stream = 0;

void update_size_chosen_streams(const int s) {"{"}
    if (s > current_size_chosen_stream) {"{"}
        free(chosen_streams);
        chosen_streams = (dll_node **) calloc(s, sizeof(dll_node*));
        current_size_chosen_stream = s;
    {"}"}
{"}"}

// globals code
{get_globals_code(components, streams_to_events_map, stream_types)}
{build_should_keep_funcs(streams_to_events_map)}

atomic_int count_event_streams = 0;

// declare event streams
{declare_event_sources(components["event_source"])}

// event sources threads
{declare_evt_srcs_threads()}

// declare arbiter thread
thrd_t ARBITER_THREAD;
{declare_const_rule_set_names(ast[2])}
{declare_rule_set_counters(ast[2])}
int current_rule_set = {get_first_const_rule_set_name(ast[2])};

{declare_arbiter_buffers(components, ast)}


// buffer groups
{declare_order_expressions()}
{declare_buffer_groups()}

{declare_perf_layer_funcs(streams_to_events_map)}

// variables used to debug arbiter
long unsigned no_consecutive_matches_limit = 1UL<<35;
int no_matches_count = 0;

bool are_there_events(shm_arbiter_buffer * b) {"{"}
  return shm_arbiter_buffer_is_done(b) > 0;
{"}"}

{are_buffers_done()}

static int __work_done = 0;
/* TODO: make a keywork from this */
void done() {{
    __work_done = 1;
}}

static inline bool are_streams_done() {"{"}
    assert(count_event_streams >=0);
    return (count_event_streams == 0 && are_buffers_done() && !ARB_CHANGE_) || __work_done;
{"}"}

static inline bool is_buffer_done(shm_arbiter_buffer *b) {"{"}
    return shm_arbiter_buffer_is_done(b);
{"}"}


static inline
bool check_at_least_n_events(size_t count, size_t n) {"{"}
    // count is the result after calling shm_arbiter_buffer_peek
	return count >= n;
{"}"}

static
bool are_events_in_head(char* e1, size_t i1, char* e2, size_t i2, int count, size_t ev_size, int event_kinds[], int n_events) {"{"}
    assert(n_events > 0);
	if (count < n_events) {"{"}
	    return false;
    {"}"}

	int i = 0;
	while (i < i1) {"{"}
	    shm_event * ev = (shm_event *) (e1);
	     if (ev->kind != event_kinds[i]) {"{"}
	        return false;
	    {"}"}
        if (--n_events == 0)
            return true;
	    i+=1;
	    e1 += ev_size;
	{"}"}

	i = 0;
	while (i < i2) {"{"}
	    shm_event * ev = (shm_event *) e2;
	     if (ev->kind != event_kinds[i1+i]) {"{"}
	        return false;
	    {"}"}
        if (--n_events == 0)
            return true;
	    i+=1;
	    e2 += ev_size;
	{"}"}

	return true;
{"}"}

/*
static inline dump_event_data(shm_event *ev, size_t ev_size) {{
    unsigned char *data = ev;
    fprintf(stderr, "[");
    for (unsigned i = sizeof(*ev); i < ev_size; ++i) {{
        fprintf(stderr, "0x%x ", data[i]);
    }}
    fprintf(stderr, "]");
}}
*/

{get_event_name(stream_types, streams_to_events_map)}

/* src_idx = -1 if unknown */
static void
print_buffer_prefix(shm_arbiter_buffer *b, int src_idx, size_t n_events, int cnt, char* e1, size_t i1, char* e2, size_t i2) {"{"}
    if (cnt == 0) {{
        fprintf(stderr, " empty\\n");
        return;
    }}
    const size_t ev_size = shm_arbiter_buffer_elem_size(b);
    int n = 0;
	int i = 0;
	while (i < i1) {"{"}
	    shm_event * ev = (shm_event *) (e1);
        fprintf(stderr, "  %d: {{id: %5lu, kind: %3lu", ++n,
                shm_event_id(ev), shm_event_kind(ev));
        if (src_idx != -1)
            fprintf(stderr, " -> %-12s", get_event_name(src_idx, shm_event_kind(ev)));
        /*dump_event_data(ev, ev_size);*/
        fprintf(stderr, "}}\\n");
        if (--n_events == 0)
            return;
	    i+=1;
	    e1 += ev_size;
	{"}"}

	i = 0;
	while (i < i2) {"{"}
	    shm_event * ev = (shm_event *) e2;
        fprintf(stderr, "  %d: {{id: %5lu, kind: %3lu", ++n,
                shm_event_id(ev), shm_event_kind(ev));
        if (src_idx != -1)
            fprintf(stderr, " -> %-12s", get_event_name(src_idx, shm_event_kind(ev)));
        /*dump_event_data(ev, ev_size);*/
        fprintf(stderr, "}}\\n");

        if (--n_events == 0)
            return;
	    i+=1;
	    e2 += ev_size;
	{"}"}
{"}"}



static inline
shm_event * get_event_at_index(char* e1, size_t i1, char* e2, size_t i2, size_t size_event, int element_index) {"{"}
	if (element_index < i1) {"{"}
		return (shm_event *) (e1 + (element_index*size_event));
	{"}"} else {"{"}
		element_index -=i1;
		return (shm_event *) (e2 + (element_index*size_event));
	{"}"}
{"}"}

//arbiter outevent
STREAM_{arbiter_event_source}_out *arbiter_outevent;
{declare_rule_sets(ast[2])}
{print_event_name(stream_types, streams_to_events_map)}
{get_event_at_head()}
{print_buffers_state()}
{build_rule_set_functions(ast[2], streams_to_events_map, stream_types, existing_buffers)}
{arbiter_code(ast[2], components)}

{define_signal_handlers(components["event_source"])}

static void setup_signals() {{
    if (signal(SIGINT, sig_handler) == SIG_ERR) {{
	perror("failed setting SIGINT handler");
    }}

    if (signal(SIGABRT, sig_handler) == SIG_ERR) {{
	perror("failed setting SIGINT handler");
    }}

    if (signal(SIGIOT, sig_handler) == SIG_ERR) {{
	perror("failed setting SIGINT handler");
    }}

    if (signal(SIGSEGV, sig_handler) == SIG_ERR) {{
	perror("failed setting SIGINT handler");
    }}
}}
    """


def get_c_program(
    components,
    ast,
    streams_to_events_map,
    stream_types,
    arbiter_event_source,
    existing_buffers,
):
    program = f"""

{get_imports()}

{outside_main_code(components, streams_to_events_map, stream_types, ast, arbiter_event_source, existing_buffers)}
int main(int argc, char **argv) {"{"}
    setup_signals();

    arbiter_counter = 10;
	{get_pure_c_code(components, 'startup')}
    {initialize_stream_args()}

    {event_sources_conn_code(components['event_source'], streams_to_events_map)}
     // activate buffers
     printf("-- creating buffers\\n");
    {activate_buffers()}
 	monitor_buffer = shm_monitor_buffer_create(sizeof(STREAM_{arbiter_event_source}_out), {TypeChecker.monitor_buffer_size});

 	 // init buffer groups
     printf("-- initializing buffer groups\\n");
     {init_buffer_groups()}

     // create source-events threads
     printf("-- creating performance threads\\n");
     {activate_threads()}

     // create arbiter thread
     printf("-- creating arbiter thread\\n");
     thrd_create(&ARBITER_THREAD, arbiter, 0);

     {monitor_code(ast[3], streams_to_events_map, arbiter_event_source)}

     printf("-- cleaning up\\n");
     {destroy_all()}

{get_pure_c_code(components, 'cleanup')}
{"}"}
"""
    return program
