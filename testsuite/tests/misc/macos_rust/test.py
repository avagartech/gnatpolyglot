"""Link a generated Rust crate to real Ada code without the scanner dependency."""

import json
import os
from pathlib import Path
import shutil

from utils import POLYGLOT_HOME, run


runtime = (Path(POLYGLOT_HOME) / "runtimes").resolve()
Path("smoke.gpr").write_text(f'''
with "{runtime}/ada/gnatpolyglot-ada.gpr";
library project Smoke is
   for Languages use ("Ada");
   for Source_Dirs use ("src");
   for Object_Dir use "obj";
   for Library_Dir use "lib";
   for Library_Name use "smoke";
end Smoke;
''')
Path("smoke_agg.gpr").write_text(f'''
aggregate library project Smoke_Agg is
   for Project_Files use ("smoke.gpr",
      "{runtime}/ada/gnatpolyglot-ada.gpr",
      "{runtime}/gnatpolyglot/gnatpolyglot.gpr");
   for Library_Name use "smoke_agg";
   for Library_Dir use "lib_agg";
   for Object_Dir use "obj_agg";
   for Library_Kind use "static";
   for Library_Standalone use "standard";
   for Library_Auto_Init use "true";
   for Interfaces use ("smoke.ads", "gnatpolyglot.ads", "gnatpolyglot-ada.ads",
      "gnatpolyglot-ada-arrays.ads", "gnatpolyglot-ada-arrays-native.ads",
      "gnatpolyglot-ada-strings.ads", "gnatpolyglot-exceptions.ads");
end Smoke_Agg;
''')
run(["gprbuild", "-q", "-p", "-P", "smoke_agg.gpr"], pipe=True)

def function(name, symbol, parameters):
    return {
        "kind": "function", "name": {"names": ["smoke", name]}, "doc": "",
        "symbol": symbol,
        "type": {
            "kind": "function", "parameters": [
                {"name": p, "type": {"kind": "typename", "name": {"names": ["sint32"]}},
                 "transfer": {"required_owner": "any"}} for p in parameters
            ],
            "return_type": {"kind": "typename", "name": {"names": ["sint32"]}},
            "return_owner": "unknown",
        },
    }

# This fixture deliberately bypasses Ada2Proxy so that the Darwin linker and
# Rust generator can be tested before building Libadalang's Java bindings.
Path("proxy.json").write_text(json.dumps({
    "name": "macos_smoke", "input_language": "ada",
    "modules": [{"name": {"names": ["smoke"]}, "declarations": [
        function("add", "macos_smoke_add", ["left", "right"]),
        function("initial_value", "macos_smoke_initial", []),
    ]}],
}))
Path("bindings").mkdir()
java_home = os.environ.get("JAVA_HOME") or os.environ["GRAAL_HOME"]
run([
    str(Path(java_home) / "bin/java"), "-cp",
    str(Path(POLYGLOT_HOME) / "proxy2rust/target/proxy2rust.jar"),
    "Generate.java", "proxy.json", "bindings", str(runtime),
], pipe=True)
Path("runner/src").mkdir(parents=True)
shutil.copyfile("main.rs", "runner/src/main.rs")
Path("runner/Cargo.toml").write_text('''[package]
name = "macos_smoke_runner"
version = "0.1.0"
edition = "2021"
[dependencies]
macos_smoke = { path = "../bindings" }
''')
env = {
    **os.environ,
    "POLYGLOT_PROXY_LIB_DIR": str(Path("lib_agg").resolve()),
    "POLYGLOT_PROXY_LIB_NAME": "smoke_agg",
}
cargo = ["cargo", "run", "--quiet", "--offline", "--manifest-path", "runner/Cargo.toml"]
run(cargo, env=env)

outputs = list(Path("runner/target/debug/build").glob("macos_smoke-*/output"))
before = {output: output.stat().st_mtime_ns for output in outputs}
Path("lib_agg/unrelated.txt").write_text("This file does not affect the native archive.\n")
assert run(cargo, env=env, pipe=True).strip() == "macOS Ada/Rust smoke passed"
assert before == {output: output.stat().st_mtime_ns for output in outputs}, (
    "Cargo reran the build script for an unrelated file in the native library directory"
)

# Changing the library location/name must rerun the generated build script.
# Also verify that Cargo handles native library directories containing spaces.
alternate = Path("alternate libraries").resolve()
alternate.mkdir()
shutil.copyfile("lib_agg/libsmoke_agg.a", alternate / "libsmoke_alternate.a")
env["POLYGLOT_PROXY_LIB_DIR"] = str(alternate)
env["POLYGLOT_PROXY_LIB_NAME"] = "smoke_alternate"
assert run(cargo, env=env, pipe=True).strip() == "macOS Ada/Rust smoke passed"
outputs = list(Path("runner/target/debug/build").glob("macos_smoke-*/output"))
assert any(
    f"cargo:rustc-link-search=native={alternate}" in output.read_text()
    and "cargo:rustc-link-lib=static=smoke_alternate" in output.read_text()
    for output in outputs
), "Cargo did not refresh the generated crate's native library settings"
