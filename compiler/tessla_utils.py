
from operator import pos
from cfile_utils import *
import os

state_type = '''State<
(),
fn(TesslaValue<(TesslaInt, TesslaInt, TesslaInt)>, i64) -> Result<(), ()>,
fn(TesslaValue<(TesslaInt, TesslaInt, TesslaInt)>, i64) -> Result<(), ()>,
fn(TesslaOption<TesslaValue<(TesslaInt, TesslaInt)>>, i64) -> Result<(), ()>,
fn(TesslaOption<TesslaValue<(TesslaInt, TesslaInt)>>, i64) -> Result<(), ()>,
>'''

def update_toml(output_dir: str) -> None:
    toml_file_path = f"{output_dir}/Cargo.toml"
    current_part = ""
    sections = dict()
    if os.path.isfile(toml_file_path):
        file =  open(toml_file_path, "r")
        lines = file.readlines()
        file.close()


        for line in lines:
            line = line.replace("\n", "")
            if len(line) > 0:
                if line[0] == '[':
                    current_part = line
                    assert (current_part not in sections.keys())
                    sections[current_part] = set()
                else:
                    if current_part != "[lib]" or not ("crate-type" in line):
                        sections[current_part].add(line)

        sections["[lib]"].add('crate-type = [\"staticlib\"]')

        answer = ""
        for (section, lib) in sections.items():
            if answer == "":
                answer+= f"{section}\n"
            else:
                answer+= f"\n{section}\n"
            
            for l in lib:
                answer += f"{l}\n"
        file =  open(toml_file_path, "w")
        file.write(answer)
        file.close()
    else:
        raise Exception(f"file {toml_file_path} does not exists")

def get_rust_file_args(args):
    args_result = ""
    value_args = ""

    for (arg, datatype) in args:
        if args_result != "":
            args_result +=","
            value_args += ","

        if datatype.strip() == "bool":
            args_result += f"{arg}: c_int"
            value_args += f"Value({arg} == 1)"
        else:
            args_result += f"{arg}: c_{datatype}"
            value_args += f"Value({arg}.into())"

    return args_result, value_args


def get_rust_code(possible_events):
    answer = ""

    for (event_name, data) in possible_events.items():
        if event_name.lower() != "hole":

            args, Value_args = get_rust_file_args(data["args"])
            if len(args) > 0:
                args+=","
            Value_args = f"Value(({Value_args}))"
            answer+=f'''
#[no_mangle]
extern "C" fn RUST_FFI_{event_name} (mut bs : &mut {state_type}, {args} ts : c_long) {"{"}
    bs.step(ts.into(), false).expect("Step failed");
    bs.set_{event_name}({Value_args});
    bs.flush().expect("Flush failed");
{"}"}
'''
    return answer

def get_rust_file(mapping, arbiter_event_source) -> str:
    possible_events = mapping[arbiter_event_source]
    return f'''
#[no_mangle]
extern "C" fn moninit() -> Box<{state_type}>
{"{"}
    Box::new(State::default())
{"}"}

{get_rust_code(possible_events)}
'''

def received_events_declare_args(event_name, data):
    answer = ""
    for (arg, datatype) in data["args"]:
        answer+=f"\t\t\t{datatype} {arg} = received_event->cases.{event_name}.{arg};\n"
    return answer

def rust_monitor_events_code(possible_events):
    answer = ""
    for (event_name, data) in possible_events.items():
        if event_name.lower() != "hole":
            args = ""

            for (arg, _) in data["args"]:
                if args != "":
                    args+=", "
                args += f"{arg}"
            if len(args) > 0:
                args+=","
            answer += f'''
        if (received_event->head.kind == {data["index"]}) {"{"}
            {received_events_declare_args(event_name, data)}
            RUST_FFI_{event_name}(monstate,{args} curtimestamp++);
        {"}"}

'''
    return answer

def tessla_monitor_code(tree, mapping, arbiter_event_source) -> str:
    if arbiter_event_source in mapping.keys():
        possible_events = mapping[arbiter_event_source]
    else:
        possible_events = None
        print("WARNING: monitor does not define a stream type (Empty monitor generated)")

    assert (tree[0] == "monitor_def")
    if possible_events is not None:
        return f'''
            // monitor
            void* monstate = moninit();
            long curtimestamp = 1;
            STREAM_{arbiter_event_source}_out * received_event;
            while(true) {"{"}
                received_event = fetch_arbiter_stream(monitor_buffer);
                if (received_event == NULL) {"{"}
                    break;
                {"}"}
{rust_monitor_events_code(possible_events)}
            shm_monitor_buffer_consume(monitor_buffer, 1);
            {"}"}
        '''
    else:
        return f'''
    // Empty Monitor  
    '''


def declare_extern_functions(mapping, arbiter_event_source):
    if arbiter_event_source in mapping.keys():
        possible_events = mapping[arbiter_event_source]
    else:
        possible_events = None
        print("WARNING: monitor does not define a stream type (Empty monitor generated)")

    if possible_events is not None:
        answer = "extern void* moninit();\n"
        for (event_name, data) in possible_events.items():
            if event_name.lower() != "hole":
                args = ""
                for (arg, datatype) in data["args"]:
                    if args != "":
                        args += ", "
                    args += f"{datatype} {arg}"
                if len(args) > 0:
                    args += ", "
                answer += f"extern void RUST_FFI_{event_name}(void *monstate, {args}long curtimestamp);\n"
        return answer
    else:
        print("No possible events for monitor!")

def get_c_interface(components,ast, streams_to_events_map, stream_types,
                    arbiter_event_source, existing_buffers) -> str:
    return f'''
{get_imports()}

{outside_main_code(components, streams_to_events_map, stream_types, ast, arbiter_event_source, existing_buffers)}
{declare_extern_functions(streams_to_events_map, arbiter_event_source)}
int main(int argc, char **argv) {"{"}
    setup_signals();

	chosen_streams = (dll_node *) malloc({get_count_events_sources()}); // the maximum size this can have is the total number of event sources
	arbiter_counter = malloc(sizeof(int));
	*arbiter_counter = 10;
	{get_pure_c_code(components, 'startup')}
{initialize_stream_args()}

{event_sources_conn_code(components['event_source'], streams_to_events_map)}
     // activate buffers
{activate_buffers()}
 	monitor_buffer = shm_monitor_buffer_create(sizeof(STREAM_{arbiter_event_source}_out), {TypeChecker.monitor_buffer_size});

 		// init buffer groups
	{init_buffer_groups()}

     // create source-events threads
{activate_threads()}

     // create arbiter thread
     thrd_create(&ARBITER_THREAD, arbiter, 0);

 {tessla_monitor_code(ast[3], streams_to_events_map, arbiter_event_source)}

{destroy_all()}

{get_pure_c_code(components, 'cleanup')}
{"}"}
'''