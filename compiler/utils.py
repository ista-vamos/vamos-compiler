# general utils
from typing import List, Tuple, Dict, Any, Set

from parser_indices import *


# Function the preprocess the program string to then generate a C program
def replace_cmd_args(program: str, buffsize: int) -> List[str]:
    """This function replaces @BUFSIZE with a concrete value

    Args:
        program (str): the program we are parsing
        buffsize (int): the concrete value we use to replace @BUFSIZE

    Returns:
        List[str]: the lines of the program
    """    
    answer = []
    for line in program:
        answer.append(line.replace("@BUFSIZE", str(buffsize)))
    return answer


def get_components_dict(tree: Tuple, answer: Dict[str, List[Tuple]]) -> None:
    """It return the computed components in 'answer'. The keys of answer can be one of the following: 'stream_type', 'event_source', 'stream_processor', 'buff_group_def', 'match_fun_def', 'GLOBALS', 'STARTUP', 'CLEANUP', 'LOOPDEBUG', while the valeu is the whole component.
    Args:
        tree (Tuple): a tree of the 'p_components()' (look at this function in parser.py)
        answer (Dict[str, List[Tuple]]): a dict mapping a component name to a list of trees
    """    
    if tree[0] == "components":

        get_components_dict(tree[1], answer)
        get_components_dict(tree[2], answer)
    else:
        name = tree[0]
        if name not in answer.keys():
            answer[name] = []

        answer[name].append(tree)

# List of field declarations
def get_parameters_types_field_decl(
    tree: Tuple, params: List[Dict[str, Tuple]]
) -> None:
    """The result is stored in params. This function gathers data of parameters

    Args:
        tree (Tuple): a list of arguments
        params (List[Tuple[str, str]]): this should be initially set to empty. We fill it by calling recursively this function with dictionaries that have only 2 keys ('name', 'type'), which are the names and the types of the arguments.
    """    
    if tree is not None:
        assert len(tree) == 3
        if tree[0] == "list_field_decl":
            get_parameters_types_field_decl(tree[PLIST_BASE_CASE], params)
            get_parameters_types_field_decl(tree[PLIST_TAIL], params)
        else:

            assert tree[0] == "field_decl"
            if tree[PPFIELD_TYPE][1] == "uint64_t":
                type_ = "uint64_t"
            else:
                type_ = tree[PPFIELD_TYPE][1]
            params.append(
                {
                    "name": tree[1],
                    "type": type_,
                    "is_primitive": is_type_primitive(tree[PPFIELD_TYPE]),
                }
            )


def parse_list_events_agg_func(tree, result):
    if tree[0] == "*":
        result.append(tree[0])
    elif tree[0] == "l-events-hole":
        type1 = parse_list_events_agg_func(tree[1], result)
        type2 = parse_list_events_agg_func(tree[2], result)
        if type1 != type2:
            raise Exception(
                "All parameters of aggregations functions must be of one type"
            )
        return type1
    else:
        assert tree[0] == "event_hole"
        if tree[1][0] == "field_access":
            result.append(tree[1])
            return False
        else:
            assert type(tree[1]) == str
            result.append(tree[1])
            return True


def build_custom_hole(tree, result):
    if tree[0] == "l-hole-attributes":
        build_custom_hole(tree[1], result)
        build_custom_hole(tree[2], result)
    else:
        assert tree[0] == "hole-attribute"
        attribute_type = tree[1]
        attribute = tree[2]
        agg_func = tree[3]
        agg_func_name = agg_func[1]
        agg_func_params = []
        parse_list_events_agg_func(agg_func[2], agg_func_params)
        result.append(
            {
                "type": attribute_type,
                "attribute": attribute,
                "agg_func_name": agg_func_name,
                "agg_func_params": agg_func_params,
            }
        )


def get_events_to_hole_update_data(data, all_events):
    answer = dict()
    for event in all_events:
        answer[event] = []
    for attribute_data in data:
        agg_func = attribute_data["agg_func_name"]
        attribute = attribute_data["attribute"]
        agg_func_params = attribute_data["agg_func_params"]
        if len(agg_func_params) == 0:
            raise Exception("Cannot call aggregation functions without parameters")

        if len(agg_func_params) == 1 and agg_func_params[0] == "*":
            assert agg_func.lower() == "count"
            for event in all_events:
                answer[event].append(
                    {"agg_func": "count", "hole_attr": attribute, "ev_attr": None}
                )
        else:
            for param in agg_func_params:
                assert param[0] == "field_access"
                assert param[2] is None
                event = param[1]
                if event not in answer.keys():
                    raise Exception(
                        "This is weird, all events should be in dictionary answer"
                    )

                answer[event].append(
                    {"agg_func": agg_func, "hole_attr": attribute, "ev_attr": param[3]}
                )
    return answer


def get_processor_rules(tree, result):
    if tree[0] == "perf_layer_list":
        (name1, part1_result) = get_processor_rules(tree[1], result)
        (name2, part2_result) = get_processor_rules(tree[2], result)
        if part1_result is not None:
            return name1, part1_result
        if part2_result is not None:
            return name2, part2_result
        return None, None
    else:
        if tree[0] == "perf_layer_rule":
            event, event_args = get_name_with_args(tree[1])
            stream_type = tree[3]
            process_using, process_using_args = get_name_with_args(tree[4])
            connection_kind_threshold = 2
            if len(tree[5]) >= 4:
                connection_kind_threshold = tree[5][3]
            connection_kind = {
                "type": tree[5][1],
                "size": tree[5][2],
                "threshold": connection_kind_threshold,
            }
            if tree[5][1] != "autodrop":
                print(f"connection kind {tree[5][1]} is not implemented")

            performance_match = tree[6]
            buff_group = tree[7]
            result.append(
                {
                    "event": event,
                    "event_args": event_args,
                    "stream_type": stream_type,
                    "process_using": process_using,
                    "process_using_args": process_using_args,
                    "connection_kind": connection_kind,
                    "performance_match": performance_match,
                    "buff_group": buff_group,
                }
            )
            return None, None
        else:
            assert tree[0] == "custom_hole"
            custom_hole = []
            build_custom_hole(tree[2], custom_hole)
            return tree[1], custom_hole


def get_name_with_args(tree: Tuple):
    if tree is None:
        return None, None
    if tree[0] == "name-with-args":
        args = []
        if tree[2] is None:
            return tree[1], []
        if tree[2][0] == "listids":
            get_list_from_tree(tree[2], args)
        else:
            get_list_from_tree(tree[2], args)
        return tree[1], args
    else:
        return tree, []


def get_name_args_count(tree: Tuple):
    if tree[0] == "name-with-args":
        args = []
        if tree[2] is None:
            return (tree[1], 0)
        if tree[2][0] == "listids":
            get_list_from_tree(tree[2], args)
        else:
            get_list_from_tree(tree[2], args)
        return tree[1], len(args)
    else:
        return tree, 0


def get_list_from_tree(tree: Tuple, result: List[Tuple]) -> None:
    """_summary_

    Args:
        tree (Tuple): _description_
        result (List[Tuple]): _description_
    """ 
    if tree is not None:
        if tree[0] in ["listids", "list_var_or_integer", "expr_list"]:
            get_list_from_tree(tree[PLIST_BASE_CASE], result)
            get_list_from_tree(tree[PLIST_TAIL], result)
        else:
            if type(tree) == str:
                result.append(tree)
            else:
                assert tree[0] in ["ID", "expr", "field_decl"]
                result.append(tree[PLIST_DATA]) 


def count_tree_list_elements(tree: Tuple) -> int:
    """counts the number of expressions in a expr_list tree

    Args:
        tree (Tuple): expr_list tree

    Returns:
        int: count of the number of expressions
    """    
    expressions = []
    return len(get_list_from_tree(tree, expressions))


def is_type_primitive(tree: Tuple) -> bool:
    def is_primitive_type(type_: str) -> bool:
        answer = type_ in  ["int", "bool", "string", "float", "double"]
        return answer
    
    if tree[0] == "type":
        return is_primitive_type(tree[PTYPE_DATA])
    else:
        assert tree[0] == "array"
        return is_type_primitive(tree[PTYPE_DATA])


# event streams utils
def get_events_data(tree: Tuple, events_data: Dict[str, List[Dict[str, str]]]) -> None:
    """we store the result in events_data, we should call initially this function with an empty dictionary

    Args:
        tree (Tuple): a tree of events
        events_data (Dict[str, Dict[str, str]]): we return a dictionary that maps the name of events to  a list that containts dictionaries  with two keys ('name', 'type') describing each of the arguments of the events.
    """    
    if tree[0] == "event_list":
        get_events_data(tree[PLIST_BASE_CASE], events_data)
        get_events_data(tree[PLIST_TAIL], events_data)
    else:
        assert tree[0] == "event_decl"
        event_args: List[
            Dict[str, str]
        ] = [] # the dictionary has as keys "name" and "type"
        if tree[PPEVENT_PARAMS_LIST]:
            get_parameters_types_field_decl(tree[PPEVENT_PARAMS_LIST], event_args)
        events_data[tree[PPEVENT_NAME]] = event_args


def get_stream_to_events_mapping(
    stream_types: List[Tuple], stream_processors_object
) -> Dict[str, Any]:
    
    mapping = dict()
    for tree in stream_types:
        assert tree[0] == "stream_type"
        assert len(tree) == 5
        events_data = dict()
        get_events_data(tree[-1], events_data)
        stream_type = tree[PPSTREAM_TYPE_NAME]
        assert stream_type not in mapping.keys()
        mapping_events = {}
        current_index = 2
        for (index, (event_name, args)) in enumerate(events_data.items()):
            data = {"args": args}
            data.update(
                {
                    "index": index + 2,
                    "enum": f"{stream_type.upper()}_{event_name.upper()}",
                }
            )
            current_index = index + 2
            mapping_events[f"{event_name}"] = data

        mapping_events["hole"] = {
            "index": 1,
            "args": [{"name": "n", "type": "int"}],
            "enum": f"{stream_type.upper()}_HOLE",
        }
        for (_, data) in stream_processors_object.items():
            if data["special_hole"] is not None:
                current_index += 1
                args_hole = []
                for attr in data["special_hole"]:
                    args_hole.append({"name": attr["attribute"], "type": attr["type"]})
                mapping_events[data["hole_name"]] = {
                    "index": current_index,
                    "args": args_hole,
                    "enum": f'{data["hole_name"]}_HOLE',
                }
        mapping[stream_type] = mapping_events
    return mapping


def get_stream_types(event_sources: Tuple) -> Dict[str, Any]:
    mapping = dict()
    for tree in event_sources:
        assert tree[0] == "event_source"
        assert len(tree) == 5
        event_decl = tree[2]
        assert event_decl[0] == "event-decl"
        event_source_name = event_decl[1]
        assert event_source_name not in mapping.keys()
        event_source_tail = tree[-1]
        input_type, _ = get_name_with_args(tree[-2])
        assert event_source_tail[0] == "ev-source-tail"
        if event_source_tail[1] == None:
            output_type = input_type
        else:
            output_type, _ = get_name_with_args(event_source_tail[1])
            if output_type.lower() == "forward":
                output_type = input_type
        mapping[event_source_name] = (input_type, output_type)
    return mapping

def are_all_events_decl_primitive(tree: Tuple) -> bool:
    if tree[0] == "event_list":
        return are_all_events_decl_primitive(
            tree[PLIST_BASE_CASE]
        ) and are_all_events_decl_primitive(tree[PLIST_TAIL])
    else:
        assert tree[0] == "event_decl"
        if tree[PPEVENT_PARAMS_LIST]:
            params = []
            get_parameters_types_field_decl(tree[PPEVENT_PARAMS_LIST], params)
            for param in params:
                if not param["is_primitive"]:
                    return False
        return True


# Performance Layer utils
def get_event_sources_names(event_sources: Tuple, names: List[str]) -> None:
    for tree in event_sources:
        assert tree[0] == "event_source"
        event_src_declaration = tree[2]
        assert event_src_declaration[0] == "event-decl"
        name, _ = get_name_with_args(event_src_declaration[1])
        names.append(name)


def get_event_sources_copies(event_sources: Tuple) -> List[Tuple[str, int]]:
    result = []
    for tree in event_sources:
        assert tree[0] == "event_source"
        event_src_declaration = tree[2]
        copies = 0
        assert event_src_declaration[0] == "event-decl"
        name, _ = get_name_with_args(event_src_declaration[1])
        if event_src_declaration[2] is not None:
            copies = int(event_src_declaration[2])
        result.append((name, copies))
    return result


def get_rule_set_names(tree: Tuple, names: List[str]) -> None:
    if tree is not None:
        if tree[0] == "arb_rule_set_l":
            get_rule_set_names(tree[PLIST_BASE_CASE], names)
            get_rule_set_names(tree[PLIST_TAIL], names)
        else:
            assert tree[0] == "arbiter_rule_set"
            names.append(tree[PPARB_RULE_SET_NAME])


def get_count_events_from_list_calls(tree: Tuple) -> int:
    assert tree[0] != "|"
    if tree[0] == "list_ev_calls":
        return 1 + get_count_events_from_list_calls(tree[PPLIST_EV_CALL_TAIL])
    else:
        assert tree[0] == "ev_call"
        return 1


def get_event_kinds(tree: Tuple, kinds: List[int], mapping: Dict[str, Dict]) -> None:
    assert tree[0] != "|"

    if tree[0] == "list_ev_calls":
        kinds.append(mapping[tree[PPLIST_EV_CALL_EV_NAME]]["index"])
        get_event_kinds(tree[PPLIST_EV_CALL_TAIL], kinds, mapping)
    else:
        assert tree[0] == "ev_call"
        if tree[PPLIST_EV_CALL_EV_NAME] == "hole":
            kinds.append(1)
        else:
            kinds.append(mapping[tree[PPLIST_EV_CALL_EV_NAME]]["index"])


def get_event_kinds_enums(
    tree: Tuple, kinds: List[str], mapping: Dict[str, Dict]
) -> None:
    assert tree[0] != "|"

    kinds.append(mapping[tree[PPLIST_EV_CALL_EV_NAME]]["enum"])
    if tree[0] == "list_ev_calls":
        get_event_kinds_enums(tree[PPLIST_EV_CALL_TAIL], kinds, mapping)


def get_arbiter_output_type(tree: Tuple) -> str:
    ''' returns the stream in which the arbiter will yield results so that the monitor process it
    '''
    assert tree[0] == "arbiter_def"
    return tree[PPARBITER_OUTPUT_TYPE]


def get_parameters_names(
    tree: Tuple,
    stream_name: str,
    mapping: Dict[str, Dict],
    binded_args: Dict[str, Tuple],
    index: int = 0,
    stream_index: int = None,
) -> None:
    if tree[0] == "list_ev_calls":
        ids = []
        get_list_from_tree(tree[PPLIST_EV_CALL_EV_PARAMS], ids)
        assert len(ids) == len(mapping[tree[PPLIST_EV_CALL_EV_NAME]]["args"])
        for (arg_bind, arg) in zip(mapping[tree[PPLIST_EV_CALL_EV_NAME]]["args"], ids):
            binded_args[arg] = (
                stream_name,
                tree[PPLIST_EV_CALL_EV_NAME],
                arg_bind["name"],
                arg_bind["type"],
                index,
                stream_index,
            )
        get_parameters_names(
            tree[PPLIST_EV_CALL_TAIL], stream_name, mapping, binded_args, index + 1
        )
    else:
        assert tree[0] == "ev_call"
        ids = []
        get_list_from_tree(tree[PPLIST_EV_CALL_EV_PARAMS], ids)
        for (arg_bind, arg) in zip(mapping[tree[PPLIST_EV_CALL_EV_NAME]]["args"], ids):
            binded_args[arg] = (
                stream_name,
                tree[PPLIST_EV_CALL_EV_NAME],
                arg_bind["name"],
                arg_bind["type"],
                index,
                stream_index,
            )


def get_buff_math_binded_args(
    tree: Tuple,
    stream_types: Dict[str, Tuple[int, int]],
    mapping: Dict[str, Dict],
    binded_args: Dict[str, Tuple],
    buffer_group_data: Dict[str, Dict],
    match_fun_data: Dict[str, Dict],
) -> None:
    if tree[0] == "l_buff_match_exp":
        get_buff_math_binded_args(
            tree[PLIST_BASE_CASE],
            stream_types,
            mapping,
            binded_args,
            buffer_group_data,
            match_fun_data,
        )
        get_buff_math_binded_args(
            tree[PLIST_TAIL],
            stream_types,
            mapping,
            binded_args,
            buffer_group_data,
            match_fun_data,
        )
    else:
        if tree[0] == "buff_match_exp":
            event_src_ref = tree[PPBUFFER_MATCH_EV_NAME]
            assert event_src_ref[0] == "event_src_ref"
            event_source_name = event_src_ref[1]
            stream_type = stream_types[event_source_name][1]
            stream_index = event_src_ref[2]
            if len(tree) > 3:
                for i in range(2, len(tree)):
                    if tree[i] != "|":
                        get_parameters_names(
                            tree[i],
                            event_source_name,
                            mapping[stream_type],
                            binded_args,
                            stream_index=stream_index,
                        )
        elif tree[0] == "buff_match_exp-choose":
            buffer_name = tree[3]
            binded_streams = []
            get_list_from_tree(tree[2], binded_streams)
            for s in binded_streams:
                stream_types[s] = (
                    buffer_group_data[buffer_name]["input_stream_type"],
                    buffer_group_data[buffer_name]["input_stream_type"],
                )
        else:
            assert tree[0] == "buff_match_exp-args"
            match_fun_name, arg1, arg2 = tree[1], tree[2], tree[3]
            assert match_fun_name in match_fun_data.keys()
            if arg1 is not None:
                fun_bind_args = []
                get_list_from_tree(arg1, fun_bind_args)
                for (arg, t) in zip(
                    fun_bind_args, match_fun_data[match_fun_name]["stream_types"]
                ):
                    stream_types[arg] = (t, t)


def get_events_count(tree: Tuple) -> int:
    if tree[0] == "list_ev_calls":
        return 1 + get_events_count(tree[PPLIST_EV_CALL_TAIL])
    else:
        assert tree[0] == "ev_call"
        return 1


def get_num_events_to_retrieve(
    tree: Tuple, events_to_retrieve: Dict[str, int], match_fun_data: Dict[str, Dict]
) -> None:
    if tree[0] == "l_buff_match_exp":
        get_num_events_to_retrieve(
            tree[PLIST_BASE_CASE], events_to_retrieve, match_fun_data
        )
        get_num_events_to_retrieve(tree[PLIST_TAIL], events_to_retrieve, match_fun_data)
    else:
        if tree[0] == "buff_match_exp":
            event_src_ref = tree[PPBUFFER_MATCH_EV_NAME]
            assert event_src_ref[0] == "event_src_ref"
            event_source_name = event_src_ref[1]
            if len(tree) > 3:
                for i in range(2, len(tree)):
                    if tree[i] != "|":
                        count = get_events_count(tree[i])
                        events_to_retrieve[event_source_name] = count
        else:
            if tree[0] == "buff_match_exp-args":
                match_fun_name = tree[1]
                get_num_events_to_retrieve(
                    match_fun_data[match_fun_name]["buffer_match_expr"],
                    events_to_retrieve,
                    match_fun_data,
                )


def get_count_drop_events_from_l_buff(tree: Tuple, answer: Dict[str, int]) -> None:
    if tree[0] == "l_buff_match_exp":
        get_count_drop_events_from_l_buff(tree[1], answer)
        get_count_drop_events_from_l_buff(tree[2], answer)
    else:
        if tree[0] == "buff_match_exp":
            event_src_ref = tree[PPBUFFER_MATCH_EV_NAME]
            assert event_src_ref[0] == "event_src_ref"
            event_source_name = event_src_ref[1]
            stream_index = event_src_ref[2]
            count = 0

            if len(tree) > 3:
                for i in range(2, len(tree)):

                    if tree[i] == "|":
                        break  # only drop events that are behind |
                    count += get_count_events_from_list_calls(tree[i])
                if count > 0:
                    if stream_index is not None:
                        event_source_name += str(stream_index)
                    assert event_source_name not in answer.keys()
                    answer[event_source_name] = count
        else:
            assert (
                tree[0] == "buff_match_exp-choose" or tree[0] == "buff_match_exp-args"
            )


def get_existing_buffers(type_checker: Any) -> List[str]:
    """
    it returns the buffers we must create for each copy of each event source
    :param type_checker:  TypeChecker object (cannot import it in this file because of recursive imports)
    :return: a list with the name of the buffers
    """
    answer = []
    for (event_source, data) in type_checker.event_sources_data.items():
        if data["copies"]:
            for i in range(data["copies"]):
                name = f"{event_source}{i}"
                answer.append(name)
        else:
            answer.append(event_source)

    return answer


def insert_in_result(
    buffer_name: str, count: int, result: Dict[str, int], existing_buffers: Set[str]
):
    assert count > -1

    if buffer_name in existing_buffers:
        if buffer_name in result.keys():
            result[buffer_name] = max(result[buffer_name], count)
        else:
            result[buffer_name] = count


def get_stream_status(tree, result):
    if tree[0] == "l-ev-src-status":
        get_stream_status(tree[1], result)
        get_stream_status(tree[2], result)
    else:
        assert tree[0] == "ev-src-status"
        result.append(tree[1])


def local_get_buffer_peeks(
    local_tree: Tuple,
    type_checker: Any,
    result: Dict[str, int],
    existing_buffers: Set[str],
) -> None:
    if local_tree[0] == "l_buff_match_exp":
        local_get_buffer_peeks(local_tree[1], type_checker, result, existing_buffers)
        local_get_buffer_peeks(local_tree[2], type_checker, result, existing_buffers)
    else:
        if local_tree[0] == "buff_match_exp-args":
            local_get_buffer_peeks(
                type_checker.match_fun_data[local_tree[1]]["buffer_match_expr"],
                type_checker,
                result,
                existing_buffers,
            )
        elif local_tree[0] == "buff_match_exp-choose":
            pass
        else:
            assert local_tree[0] == "buff_match_exp"
            if len(local_tree) == 3:
                all_status = []
                get_stream_status(local_tree[-1], all_status)
                event_src_ref = local_tree[1]
                event_src_name = event_src_ref[1]
                if event_src_ref[2] is not None:
                    event_src_name += str(event_src_ref[2])
                for status in all_status:
                    if status == "done":
                        # event_src_ref ':' DONE
                        pass
                    elif status == "fail":
                        # event_src_ref ':' FAIL
                        pass
                    elif status == "nothing":
                        # event_src_ref ':' NOTHING
                        insert_in_result(event_src_name, 0, result, existing_buffers)
                    else:
                        # event_src_ref ':' INT

                        insert_in_result(
                            event_src_name, local_tree[-1][1], result, existing_buffers
                        )
            else:
                # assert(len(local_tree) == 4)
                event_src_ref = local_tree[1]
                event_src_name = event_src_ref[1]
                if event_src_ref[2] is not None:
                    event_src_name += str(event_src_ref[2])
                local_count = 0
                for list_event_calls in local_tree[2:]:
                    if list_event_calls != "|":
                        local_count += get_count_events_from_list_calls(
                            list_event_calls
                        )

                insert_in_result(event_src_name, local_count, result, existing_buffers)


def get_buffers_and_peeks(
    tree: Tuple, result: Dict[str, int], type_checker: Any, existing_buffers: Set[str]
) -> None:
    """
    :param tree: tree of arbiter_rules of a rule set
    :param result: dictionary that maps a buffer_name to the number of events that it needs to process
    :param type_checker: TypeChecker object (cannot import it in this file because of recursive imports)
    :param existing_buffers: these are the buffers (NOT buffer groups) explicitly created through 'event source' command
    (not as an product of a choose expression)
    :return:
    """
    # MAIN CODE of this function
    if tree[0] == "arb_rule_list":
        get_buffers_and_peeks(tree[1], result, type_checker, existing_buffers)
        get_buffers_and_peeks(tree[2], result, type_checker, existing_buffers)
    else:
        if tree[0] == "always":
            pass
        elif tree[0] == "arbiter_rule1":
            list_buff_match = tree[1]
            local_get_buffer_peeks(
                list_buff_match, type_checker, result, existing_buffers
            )
        else:
            # assert tree[0] == "arbiter_rule2"
            get_buffers_and_peeks(tree[-1], result, type_checker, existing_buffers)


def get_first_const_rule_set_name(tree: Tuple) -> str:
    assert tree[0] == "arbiter_def"

    rule_set_names = []
    get_rule_set_names(tree[PPARBITER_RULE_SET_LIST], rule_set_names)
    if len(rule_set_names):
        return f"SWITCH_TO_RULE_SET_{rule_set_names[0]}"
    else:
        return "-1"
