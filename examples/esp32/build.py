"""Build the ESP32/WROOM binding probe, or run the same checks on the host."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def run(argv, **kwargs):
    argv = [str(arg) for arg in argv]
    print("Running:", " ".join(argv), flush=True)
    return subprocess.run(argv, check=True, **kwargs)


def compiler_file(compiler, name, env):
    output = subprocess.check_output(
        [str(compiler), "-print-file-name=" + name], env=env, text=True
    ).strip()
    return Path(output).resolve()


def check_xtensa(path):
    header = path.read_bytes()[:52]
    if header[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<H", header, 18)[0] != 94:
        raise RuntimeError(f"Expected a 32-bit little-endian Xtensa ELF: {path}")
    return {"machine": "Xtensa", "bits": 32, "byte_order": "little",
            "flags": hex(struct.unpack_from("<I", header, 36)[0])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ada-compiler", default=os.environ.get("XTENSA_ADA_COMPILER"))
    parser.add_argument("--ada-runtime", default=os.environ.get("ESP32_ADA_RUNTIME"))
    parser.add_argument("--xtensa-config", default=os.environ.get("XTENSA_GNU_CONFIG"))
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--java", default=str(Path(os.environ.get("JAVA_HOME", "")) / "bin/java")
                        if os.environ.get("JAVA_HOME") else "java")
    parser.add_argument("--platformio", default="pio")
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--host-test", action="store_true")
    parser.add_argument("--firmware", action="store_true", help="also link the ESP32 firmware; never flashes")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not args.ada_compiler:
        parser.error("set --ada-compiler or XTENSA_ADA_COMPILER to the GNAT gcc executable")
    if args.host_test and args.firmware:
        parser.error("--host-test and --firmware are separate builds")
    compiler = Path(shutil.which(args.ada_compiler) or args.ada_compiler).resolve()
    if not compiler.is_file():
        parser.error(f"Ada compiler not found: {compiler}")
    prefix = compiler.name.removesuffix("gcc.exe").removesuffix("gcc")
    suffix = ".exe" if compiler.suffix == ".exe" else ""
    ar = compiler.with_name(prefix + "ar" + suffix)
    if not ar.is_file():
        name = subprocess.check_output([str(compiler), "-print-prog-name=ar"], text=True).strip()
        ar = Path(shutil.which(name) or name).resolve()
        if not ar.is_file():
            parser.error(f"Matching archiver not found: {ar}")
    build = (args.build_dir or ROOT / "build" / ("host" if args.host_test else "esp32")).resolve()
    build.mkdir(parents=True, exist_ok=True)
    (build / "validation.json").write_text(json.dumps({
        "target": "host" if args.host_test else "xtensa-esp32-none-elf",
        "build_completed": False, "hardware_tested": False,
    }, indent=2) + "\n")
    env = dict(os.environ)
    env.pop("POLYGLOT_ADA_COMPILER", None)
    flags = ["-c", "-O2", "-gnat2022", "-gnato", "-gnatn",
             "-ffunction-sections", "-fdata-sections", "-fstack-usage", "-I" + str(ROOT / "ada")]
    if not args.host_test:
        if not args.ada_runtime or not args.xtensa_config:
            parser.error("Xtensa builds require --ada-runtime and --xtensa-config")
        runtime = Path(args.ada_runtime).resolve()
        config = Path(args.xtensa_config).resolve()
        if not runtime.is_dir() or not config.is_file():
            parser.error("Ada runtime directory or Xtensa CPU configuration file is missing")
        env["XTENSA_GNU_CONFIG"] = str(config)
        macros = subprocess.check_output([str(compiler), "-dM", "-E", "-x", "c", "-"],
                                         input="", text=True, env=env)
        required = ["#define __XTENSA_WINDOWED_ABI__ 1",
                    "#define __BYTE_ORDER__ __ORDER_LITTLE_ENDIAN__",
                    "#define __SIZEOF_POINTER__ 4"]
        if not all(macro in macros for macro in required):
            raise RuntimeError("The compiler must use the ESP32 LX6 little-endian windowed ABI")
        flags += ["-mlongcalls", "--RTS=" + str(runtime)]
    else:
        env.pop("XTENSA_GNU_CONFIG", None)
    ada_object = build / "abi_probe.o"
    run([compiler, *flags, ROOT / "ada/abi_probe.adb", "-o", ada_object], cwd=build, env=env)
    archive = build / "libabi_probe.a"
    if archive.exists():
        archive.unlink()
    run([ar, "rcs", archive, ada_object], env=env)
    jar = REPO / "gnatpolyglot/proxy2rust/target/proxy2rust.jar"
    if not jar.is_file():
        raise RuntimeError("Build the generator first: mvn package -f gnatpolyglot/pom.xml -pl proxy2rust -am")
    generated = build / "generated"
    run([args.java, "-cp", jar, "com.adacore.gnatpolyglot.proxy2rust.Proxy2Rust", ROOT / "proxy.json",
         "-o", generated, "--embedded"], env=env)
    shutil.copytree(ROOT / "rust", build / "rust", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("target", "Cargo.lock"))
    env["POLYGLOT_PROXY_LIB_DIR"] = str(build)
    env["POLYGLOT_PROXY_LIB_NAME"] = "abi_probe"
    env["CARGO_TARGET_DIR"] = str(build / "target")
    cargo = [args.cargo]
    offline = ["--offline"] if args.offline else []
    report = {"target": "host" if args.host_test else "xtensa-esp32-none-elf",
              "hardware_tested": False, "host_test_passed": None, "firmware_linked": False,
              "ada_object_sha256": hashlib.sha256(ada_object.read_bytes()).hexdigest()}
    if args.host_test:
        runner = build / "runner"
        (runner / "src").mkdir(parents=True, exist_ok=True)
        (runner / "Cargo.toml").write_text('''[package]
name = "polyglot-host-probe"
version = "0.1.0"
edition = "2021"
[dependencies]
polyglot-esp32-probe = { path = "../rust" }
''')
        (runner / "src/main.rs").write_text('''fn main() {
    assert_eq!(polyglot_esp32_probe::polyglot_esp32_self_test(), 0);
    println!("Embedded Ada/Rust host checks passed");
}
''')
        libraries = []
        for name in ("adalib/libgnarl.a", "adalib/libgnat.a", "libemutls_w.a"):
            path = compiler_file(compiler, name, env)
            if path.is_file():
                libraries.append(str(path))
        lines = ["fn main() {"]
        for library in libraries:
            # These are final-application link arguments, used only for host testing.
            literal = json.dumps("cargo:rustc-link-arg=" + library)
            lines.append(f'    println!("{{}}", {literal});')
        lines.append("}")
        (runner / "build.rs").write_text("\n".join(lines) + "\n")
        run([*cargo, "run", *offline, "--manifest-path", runner / "Cargo.toml"], env=env)
        report["host_test_passed"] = True
    else:
        report["ada_elf"] = check_xtensa(ada_object)
        manifest = build / "rust/Cargo.toml"
        manifest.write_text(manifest.read_text().replace('crate-type = ["rlib"]', 'crate-type = ["staticlib"]'))
        run([*cargo, "build", *offline, "--manifest-path", manifest,
             "--release", "--features", "firmware", "--target", "xtensa-esp32-none-elf",
             "-Zbuild-std=core"], env=env)
        rust_archive = build / "target/xtensa-esp32-none-elf/release/libpolyglot_esp32_probe.a"
        linked_archive = build / "libpolyglot_esp32_probe.a"
        shutil.copy2(rust_archive, linked_archive)
        members = subprocess.check_output([str(ar), "t", str(linked_archive)], text=True).splitlines()
        builtins = [member for member in members if member.startswith("compiler_builtins-")]
        if not builtins:
            raise RuntimeError("Expected compiler-builtins objects in the Rust static library")
        # ESP-IDF supplies the ROM/IRAM memory helpers and libgcc. Retain those
        # implementations when flash caches are disabled, as required by the SDK.
        run([ar, "d", linked_archive, *builtins], env=env)
        report["sdk_runtime_objects_removed"] = len(builtins)
        if args.firmware:
            pio_env = {**env, "PLATFORMIO_SETTING_ENABLE_TELEMETRY": "no"}
            pio_env["POLYGLOT_PROBE_BUILD_DIR"] = str(build)
            run([args.platformio, "run", "-d", ROOT / "firmware"], env=pio_env)
            elf = ROOT / "firmware/.pio/build/esp32wroom/firmware.elf"
            report["firmware_elf"] = check_xtensa(elf)
            nm = compiler.with_name(prefix + "nm" + suffix)
            symbols = subprocess.check_output([str(nm), "-S", str(elf)], text=True)
            names = {line.split()[-1] for line in symbols.splitlines() if line.split()}
            expected = {"polyglot_checked_add", "polyglot_fold_64", "polyglot_scale_32",
                        "polyglot_scale_64", "polyglot_negate_16", "polyglot_esp32_self_test"}
            if not expected.issubset(names):
                raise RuntimeError("The firmware is missing an Ada/Rust probe entry point")
            if any(name.startswith(("gnatpolyglot__", "__rust_alloc", "__rust_realloc")) for name in names):
                raise RuntimeError("Unexpected desktop proxy or Rust allocation runtime in the probe")
            undefined = subprocess.check_output([str(nm), "-u", str(elf)], text=True).splitlines()
            report["sdk_undefined_symbols"] = [line.split()[-1] for line in undefined if line.split()]
            if any("polyglot" in name for name in report["sdk_undefined_symbols"]):
                raise RuntimeError("Unresolved binding symbol in the firmware")
            report["probe_code_bytes"] = {
                fields[-1]: int(fields[1], 16)
                for line in symbols.splitlines()
                if len(fields := line.split()) == 4 and fields[-1] in expected
            }
            report["firmware_sha256"] = hashlib.sha256(elf.read_bytes()).hexdigest()
            report["firmware_linked"] = True
    report["build_completed"] = True
    (build / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
