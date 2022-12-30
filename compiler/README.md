# Compiler for VAMOS

This is a compiler for a best-effort third-party monitoring middleware.

## Requirements
Python 3 (we use Python 3.8.9).

## Usage

### Generating a Monitor From a Vamos Specification
To compile a VAMOS specification into `C` code, specify the path where the VAMOS specification is (i.e `INPUT_FILE`), and the path to write the `C` code of the monitor.

```bash
python main.py <INPUT_FULE> -o <OUTPUT_FILE>
```
### Integration with Tessla

Given a Tessla specification and a Vamos specification:

1. Generate the Tessla monitor using Tessla's Jar file (available <a href="https://git.tessla.io/tessla/tessla/builds/artifacts/rust-compiler/raw/target/scala-2.13/tessla-assembly-1.2.3.jar?job=deploy" target="_blank">here</a>):

```bash
java -jar tessla.jar compile-rust  <TESSLA_SPECIFICATION_FILE> --project-dir <OUTPUT_DIR>
```

2. Run the compiler over this `OUTPUT_DIR`. Specify an `OUTPUT_FILE` where the final monitor is going to be written and a VAMOS specification file:

```bash
python3 compiler/main.py -o <OUTPUT_FILE> --with-tessla <VAMOS_SPECIFICATION_FILE> --dir <OUTPUT_DIR>
```

The compiler will update the `Cargo.toml` file and generate a Foreign Function Interface (FFI) so that the final monitor can make use of Tessla-generated code.

3. Generate a static library by running `cargo build` inside `OUTPUT_DIR`. This will generate the file `<OUTPUT_DIR>/target/debug/libmonitor.a`, which you have to link when compiling the final monitor.




