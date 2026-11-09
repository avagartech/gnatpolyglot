"""Build an STM32 Cortex-M Ada/Rust probe; this command never flashes hardware."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from targets import TARGETS, check_arm_attributes, check_compiler_macros, check_elf, check_vectors

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SHARED = ROOT.parent / "esp32"


def run(argv, **kwargs):
    command = [str(arg) for arg in argv]
    print("Running:", " ".join(command), flush=True)
    return subprocess.run(command, check=True, **kwargs)


def output(argv, **kwargs):
    return subprocess.check_output([str(arg) for arg in argv], text=True, **kwargs).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chip", choices=TARGETS, default="stm32f405rg")
    parser.add_argument("--ada-compiler", default=os.environ.get("ARM_ADA_COMPILER"))
    parser.add_argument("--ada-runtime", type=Path, default=os.environ.get("STM32_ADA_RUNTIME"))
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--java", default=str(Path(os.environ["JAVA_HOME"]) / "bin/java")
                        if os.environ.get("JAVA_HOME") else "java")
    parser.add_argument("--build-dir", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host-test", action="store_true")
    mode.add_argument("--firmware", action="store_true", help="also link a complete bare-metal image")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    target = TARGETS[args.chip]
    if not args.ada_compiler:
        parser.error("select a GNAT gcc executable with --ada-compiler or ARM_ADA_COMPILER")
    compiler = Path(shutil.which(args.ada_compiler) or args.ada_compiler).resolve()
    if not compiler.is_file():
        parser.error(f"Ada compiler not found: {compiler}")
    prefix = compiler.name.removesuffix("gcc.exe").removesuffix("gcc")
    suffix = ".exe" if compiler.suffix == ".exe" else ""

    def tool(name):
        path = compiler.with_name(prefix + name + suffix)
        if name == "ar" and not path.is_file() and args.host_test:
            candidate = output([compiler, "-print-prog-name=ar"])
            path = Path(shutil.which(candidate) or candidate).resolve()
        if not path.is_file():
            parser.error(f"Matching {name} tool not found: {path}")
        return path

    ar = tool("ar")
    name = "host-" + target.chip if args.host_test else target.chip
    build = (args.build_dir or ROOT / "build" / name).resolve()
    build.mkdir(parents=True, exist_ok=True)
    report = {"chip": target.chip, "target": "host" if args.host_test else target.rust_target,
              "build_completed": False, "hardware_tested": False,
              "host_test_passed": False, "firmware_linked": False}
    report_path = build / "validation.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    env = dict(os.environ)
    for key in ("POLYGLOT_ADA_COMPILER", "XTENSA_GNU_CONFIG"):
        env.pop(key, None)
    flags = ["-c", "-O2", "-gnat2022", "-gnato", "-gnatn", "-g",
             "-ffunction-sections", "-fdata-sections", "-fstack-usage",
             "-I" + str(SHARED / "ada")]
    if not args.host_test:
        runtime = (args.ada_runtime or compiler.parent.parent / prefix.rstrip("-") /
                   "lib/gnat" / target.runtime).resolve()
        if not runtime.is_dir():
            parser.error(f"Compatible Ada runtime directory missing: {runtime}; use --ada-runtime")
        macros = output([compiler, *target.compiler_flags, "-dM", "-E", "-x", "c", "-"],
                        input="", env=env)
        report["compiler_abi"] = check_compiler_macros(macros, target)
        flags += [*target.compiler_flags, "--RTS=" + str(runtime)]
        guard = build / "target_abi.ads"
        guard.write_text('''with System;
package Target_ABI with Pure is
   pragma Compile_Time_Error (System.Word_Size /= 32, "a 32-bit Ada runtime is required");
   pragma Compile_Time_Error (Standard'Address_Size /= 32, "32-bit Ada addresses are required");
end Target_ABI;
''')
        run([compiler, *flags, "-gnatc", guard], cwd=build, env=env)
        report["ada_runtime"] = str(runtime)
    ada_object = build / "abi_probe.o"
    run([compiler, *flags, SHARED / "ada/abi_probe.adb", "-o", ada_object], cwd=build, env=env)
    archive = build / "libabi_probe.a"
    archive.unlink(missing_ok=True)
    run([ar, "rcs", archive, ada_object], env=env)
    report["ada_object_sha256"] = hashlib.sha256(ada_object.read_bytes()).hexdigest()

    jar = REPO / "gnatpolyglot/proxy2rust/target/proxy2rust.jar"
    if not jar.is_file():
        raise RuntimeError("Build the generator first: mvn package -f gnatpolyglot/pom.xml -pl proxy2rust -am")
    # Reuse the reviewed scalar contract and Ada fixture; only the crate name changes.
    contract = json.loads((SHARED / "proxy.json").read_text())
    contract["name"] = "stm32_bindings"
    proxy = build / "proxy.json"
    proxy.write_text(json.dumps(contract, indent=2) + "\n")
    run([args.java, "-cp", jar, "com.adacore.gnatpolyglot.proxy2rust.Proxy2Rust", proxy,
         "-o", build / "generated", "--embedded"], env=env)
    shutil.copytree(ROOT / "rust", build / "rust", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("target", "Cargo.lock"))
    env.update(POLYGLOT_PROXY_LIB_DIR=str(build), POLYGLOT_PROXY_LIB_NAME="abi_probe",
               CARGO_TARGET_DIR=str(build / "target"))
    offline = ["--offline"] if args.offline else []
    if args.host_test:
        runner = build / "runner"
        (runner / "src").mkdir(parents=True, exist_ok=True)
        (runner / "Cargo.toml").write_text('''[package]
name = "polyglot-stm32-host"
version = "0.1.0"
edition = "2021"
[dependencies]
polyglot-stm32-probe = { path = "../rust" }
''')
        (runner / "src/main.rs").write_text('''fn main() {
    assert_eq!(polyglot_stm32_probe::polyglot_stm32_self_test(), 0);
    println!("STM32 Ada/Rust host checks passed");
}
''')
        lines = ["fn main() {"]
        for library in ("adalib/libgnarl.a", "adalib/libgnat.a", "libemutls_w.a"):
            path = Path(output([compiler, "-print-file-name=" + library], env=env)).resolve()
            if path.is_file():
                literal = json.dumps("cargo:rustc-link-arg=" + str(path))
                lines.append(f'    println!("{{}}", {literal});')
        lines.append("}")
        (runner / "build.rs").write_text("\n".join(lines) + "\n")
        run([args.cargo, "run", *offline, "--manifest-path", runner / "Cargo.toml"], env=env)
        report["host_test_passed"] = True
    else:
        report["ada_elf"] = check_elf(ada_object)
        readelf = tool("readelf")
        report["ada_attributes"] = check_arm_attributes(output([readelf, "-A", ada_object], env=env), target)
        manifest = build / "rust/Cargo.toml"
        manifest.write_text(manifest.read_text().replace('crate-type = ["rlib"]', 'crate-type = ["staticlib"]'))
        # Force the CPU for all dependencies, including when a caller has ambient RUSTFLAGS.
        # ENCODED_RUSTFLAGS also safely handles paths/arguments containing spaces.
        env.pop("RUSTFLAGS", None)
        env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(["-C", "target-cpu=" + target.cpu])
        run([args.cargo, "build", *offline, "--manifest-path", manifest, "--release",
             "--features", "firmware", "--target", target.rust_target], env=env)
        rust_archive = build / "target" / target.rust_target / "release/libpolyglot_stm32_probe.a"
        shutil.copy2(rust_archive, build / "libpolyglot_stm32_probe.a")
        if args.firmware:
            memory = ("MEMORY {\n"
                      f" FLASH (rx) : ORIGIN = 0x{target.flash_origin:x}, LENGTH = {target.flash_bytes}\n"
                      f" RAM (rwx) : ORIGIN = 0x{target.ram_origin:x}, LENGTH = {target.ram_bytes}\n"
                      "}\n")
            (build / "memory.ld").write_text(memory)
            c_flags = [*target.compiler_flags, "-O2", "-g", "-ffreestanding", "-fno-builtin",
                       "-ffunction-sections", "-fdata-sections", "-fno-unwind-tables",
                       "-fno-asynchronous-unwind-tables", "-Wall", "-Wextra", "-Werror"]
            for source in ("startup.S", "main.c"):
                run([compiler, *c_flags, "-DPOLYGLOT_CHIP_ID=" + str(target.chip_id),
                     "-DPOLYGLOT_CPUID_PART=" + str(target.cpuid_part), "-c",
                     ROOT / "firmware" / source, "-o", build / (source + ".o")], env=env)
            elf = build / "firmware.elf"
            run([compiler, *target.compiler_flags, "-nostdlib", "-Wl,--gc-sections", "-Wl,-z,noexecstack",
                 "-Wl,--build-id=none", "-Wl,-Map=" + str(build / "firmware.map"),
                 "-L" + str(build), "-T", ROOT / "firmware/link.ld",
                 build / "startup.S.o", build / "main.c.o", "-Wl,--start-group",
                 build / "libpolyglot_stm32_probe.a", archive, "-lgcc", "-Wl,--end-group",
                 "-o", elf], cwd=build, env=env)
            report["firmware_elf"] = check_elf(elf, executable=True)
            report["firmware_attributes"] = check_arm_attributes(output([readelf, "-A", elf], env=env), target)
            binary = build / "firmware.bin"
            run([tool("objcopy"), "-O", "binary", elf, binary], env=env)
            run([tool("objcopy"), "-O", "ihex", elf, build / "firmware.hex"], env=env)
            report["vectors"] = check_vectors(binary.read_bytes(), target,
                                               int(report["firmware_elf"]["entry"], 16))
            nm = tool("nm")
            symbols = output([nm, "-S", elf], env=env).splitlines()
            names = {line.split()[-1] for line in symbols if line.split()}
            expected = {"polyglot_checked_add", "polyglot_fold_64", "polyglot_scale_32",
                        "polyglot_scale_64", "polyglot_negate_16", "polyglot_stm32_self_test",
                        "polyglot_stm32_result", "polyglot_stm32_done", "Reset_Handler"}
            if not expected <= names:
                raise RuntimeError("Missing firmware symbols: " + ", ".join(sorted(expected - names)))
            if any(name.startswith(("gnatpolyglot__", "__rust_alloc", "__rust_realloc")) for name in names):
                raise RuntimeError("Unexpected desktop proxy or Rust allocation runtime")
            undefined = output([nm, "-u", elf], env=env)
            if undefined:
                raise RuntimeError("Unresolved firmware symbols: " + undefined)
            fields = {line.split()[-1]: line.split() for line in symbols if line.split()}
            report["result_address"] = "0x" + fields["polyglot_stm32_result"][0]
            report["probe_code_bytes"] = {
                name: int(values[1], 16) for name, values in fields.items()
                if name in expected and len(values) == 4 and values[2].lower() == "t"
            }
            sections = output([tool("size"), "-A", elf], env=env)
            report["section_sizes"] = {p[0]: int(p[1]) for line in sections.splitlines()
                                       if len(p := line.split()) == 3 and p[0].startswith(".")}
            report["flash_image_bytes"] = binary.stat().st_size
            report["reserved_stack_bytes"] = 4096
            report["firmware_sha256"] = hashlib.sha256(elf.read_bytes()).hexdigest()
            report["firmware_linked"] = True
    report["build_completed"] = True
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
