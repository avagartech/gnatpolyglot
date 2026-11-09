import argparse
import os
import os.path as P
import subprocess
import sys

BIN_DIR = P.join(P.dirname(__file__), "..", "bin")

def look_for_files_in_env(files: list[str], env_var_name: str) -> dict[str, None | str] | None:
    """
    Look for required `files` in directories listed in the value of the
    environment variable `env_var_name`. Return the dictionary associating each
    input file to the directory containing it. If one of the requested file
    cannot be retrieved this function returns `None` and displays error message
    about file not being found.
    """
    res : dict[str, None | str] = {f: None for f in files}
    for dir in os.environ.get(env_var_name, "").split(os.pathsep):
        if not dir:
            continue
        for file in files:
            if res[file] is None and os.path.isfile(os.path.join(dir, file)):
                res[file] = dir
    one_not_found = False
    for file, dir in res.items():
        if dir is None:
            one_not_found = True
            print(f"Cannot find \"{file}\" in {env_var_name}")
    return None if one_not_found else res


def native_image_options() -> list[str]:
    """Locate native dependencies and use the host linker's search options."""
    if os.name == "nt":
        return []

    is_macos = sys.platform == "darwin"
    headers_paths = look_for_files_in_env(["libadalang.h"], "C_INCLUDE_PATH")
    # macOS supplies zlib through the SDK; there is no libz.so to locate.
    libraries = ["libadalang.dylib"] if is_macos else ["libadalang.so", "libz.so"]
    libs_paths = look_for_files_in_env(libraries, "LIBRARY_PATH")
    if headers_paths is None or libs_paths is None:
        raise RuntimeError("Missing lib dependencies, cannot continue")

    options = [
        *[f"--native-compiler-options=-I{d}" for d in headers_paths.values()],
        *[f"--native-compiler-options=-L{d}" for d in libs_paths.values()],
    ]
    if is_macos:
        # Apple's linker has no -rpath-link. Add runtime search paths for
        # dependencies whose install names use @rpath instead.
        paths = [
            *libs_paths.values(),
            *os.environ.get("LIBRARY_PATH", "").split(os.pathsep),
            *os.environ.get("DYLD_LIBRARY_PATH", "").split(os.pathsep),
        ]
        options.extend(
            f"--native-compiler-options=-Wl,-rpath,{p}"
            for p in dict.fromkeys(paths) if p
        )
    else:
        paths = os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
        options.extend(
            f"--native-compiler-options=-Wl,-rpath-link={p}"
            for p in paths if p
        )
    return options


if __name__ == "__main__":

    # Parse arguments provided to this script
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--build-mode",
        choices=["dev", "prod", "debug"],
        default="dev",
        help="define the build mode",
    )
    parser.add_argument("--classpath", help="classpath to forward")
    args = parser.parse_args()

    # Get the GraalVM installation
    try:
        graal_home = os.environ["GRAAL_HOME"]
    except:
        raise RuntimeError(
            "Define the 'GRAAL_HOME' environment variable to your local "
            "GraalVM installation directory"
        )

    native_image = (
        P.join(graal_home, "bin", "native-image.cmd")
        if os.name == "nt"
        else P.join(graal_home, "bin", "native-image")
    )

    # Create the dir hierarchy
    os.makedirs(BIN_DIR, exist_ok=True)

    os_specific_options = native_image_options()

    # Create the base Native-Image command
    cmd = [
        native_image,
        "-cp", args.classpath,
        "--no-fallback",
        "-H:+UnlockExperimentalVMOptions",
        "-H:-StrictQueryCodeCompilation",
        *os_specific_options
    ]

    if args.build_mode in ("dev", "debug"):
        cmd.extend(
            [
                "-g",
                "-Ob",
                "-H:-DeleteLocalSymbols",
                "-H:+SourceLevelDebug",
                "-H:+PreserveFramePointer",
                "-H:+IncludeNodeSourcePositions",
            ]
        )
        if args.build_mode == "debug":
            cmd.extend(
                [
                    "-H:+PrintRuntimeCompileMethods",
                    "-H:+TraceNativeToolUsage",
                ]
            )

    final_cmd = cmd + [
        f"com.adacore.gnatpolyglot.cli.GNATpolyglotMain",
        P.join(BIN_DIR, "gnatpolyglot"),
    ]

    # Debug print and run
    print(f"Execute: {final_cmd}", flush=True)
    subprocess.check_call(final_cmd)
