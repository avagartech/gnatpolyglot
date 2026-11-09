import sys
import os
import glob
import subprocess
import yaml
import json
from pathlib import Path
from dataclasses import dataclass

POLYGLOT_HOME = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "gnatpolyglot")
)
RUNTIME_DIR = os.path.join(POLYGLOT_HOME, "runtimes")

NATIVE_RUN = "--native" in sys.argv
POLYGLOT_EXEC = "gnatpolyglot.py"
if NATIVE_RUN:
    POLYGLOT_EXEC = "gnatpolyglot"

def run(
    argv: list[str],
    env: dict[str, str] | None = None,
    pipe: bool = False,
    expect_returncode: int = 0
) -> str | None:
    p = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        env=env,
    )
    out = p.stdout
    if not pipe:
        sys.stdout.write(out)
        sys.stdout.flush()
    if p.returncode != expect_returncode:
        raise RuntimeError(
            f"Expected return code {expect_returncode} but got {p.returncode}"
            + f": {out}" if pipe else ""
        )
    return out


def run_java(main_class: str, class_path: str, argv: list[str]) -> None:
    """
    Run a java command.
    """

    java_exec = os.path.realpath(os.path.join(os.environ["JAVA_HOME"], "bin", "java"))

    extra_args = ["--enable-native-access=ALL-UNNAMED"]
    return run([java_exec, "-cp", class_path, *extra_args, main_class, *argv])


def run_polyglot(
    subcommand: str,
    argv: list[str],
    pipe: bool = False,
    expect_returncode: int = 0
):
    return run(
        [POLYGLOT_EXEC, subcommand, *argv],
        pipe=pipe,
        expect_returncode=expect_returncode
    )


def run_proxy_validator(proxy_location: str, expect_returncode: int = 0) -> None:
    """
    Run the proxy validator on the given proxy json file.
    """
    run_polyglot(
        "validator",
        [proxy_location],
        expect_returncode=expect_returncode
    )


def macos_ada_runtime_flags() -> list[str]:
    """Link the target GNAT runtime when encapsulation is unavailable."""
    compiler = os.environ["POLYGLOT_ADA_COMPILER"]
    result = []
    for name, required in (
        ("adalib/libgnarl.a", True),
        ("adalib/libgnat.a", True),
        ("libemutls_w.a", False),
    ):
        path = run([compiler, f"-print-file-name={name}"], pipe=True).strip()
        if os.path.isfile(path):
            result.append(path)
        elif required:
            raise RuntimeError(f"Cannot find {name} using POLYGLOT_ADA_COMPILER")
    return result


class ScannerConfig:

    def __init__(self, path) -> None:
        with open(os.path.join(path, "test.yaml")) as f:
            self._cfg = yaml.safe_load(f)
        self._root = path

    @property
    def project_file(self) -> str:
        return os.path.join(self._root, self._cfg["project_file"])

    @property
    def input_lib_name(self) -> str:
        if self.input_lang == "ada":
            # Remove the `.gpr` file extension to get the name of the lib
            return os.path.basename(self.project_file)[:-4]
        raise Exception(f"Unknown language {self.input_lang}")

    @property
    def input_lang(self) -> str:
        return self._cfg["input_lang"]

    @property
    def extra_args(self) -> list[str]:
        args = []
        specFiles = ",".join(self._cfg.get("spec_files", []))
        if specFiles != "":
            args.append(f"--spec-files={specFiles}")
        args.extend(self._cfg.get("scanner_extra_args", []))
        return args

    @property
    def input_lib_flags(self) -> list[str]:
        return self._cfg.get("input_lib_flags", [])

    @property
    def output_lib_flags(self) -> list[str]:
        return self._cfg.get("output_lib_flags", [])

    def set_env(self) -> None:
        for p in self._cfg.get("local_project_path", []):
            add_path(os.environ, "GPR_PROJECT_PATH", os.path.join(self._root, p))


def run_scanner(
    input_lang: str,
    project_file: str,
    output_path: str,
    extra_args: list[str] | None = None
) -> None:
    """
    Run a scanner on ``project_file`` and generate the proxy at
    ``output_path``.
    """
    if extra_args is None:
        extra_args = []
    if input_lang == "ada":
        run_polyglot(
            "ada2proxy",
            ["-P", project_file, "-o", output_path, *extra_args]
        )
    else:
        raise Exception(f"Unknown language: {input_lang}")


@dataclass
class CompilationResult:
    lang: str
    exec_cmd : list[str] | None = None
    exec_env : dict[str, str] | None = None
    library_path : str | None = None
    library_name : str | None = None


def compile_main(
    output_lang: str,
    test_file: str,
    output_proxy: str,
    input_proxy: str,
    input_lib: str,
    cflags: list[str] | None = None,
    ldflags: list[str] | None = None,
    deps: list[CompilationResult] = []
) -> CompilationResult:
    """
    Compile the main test file and return a path to its corresponding
    executable.
    """
    if output_lang == "rust":
        import shutil

        test_bin_dir = "test_binary"
        os.makedirs(os.path.join(test_bin_dir, "src"), exist_ok=True)

        shutil.copy(test_file, os.path.join(test_bin_dir, "src", "main.rs"))

        abs_output_proxy = os.path.realpath(output_proxy)
        with open(os.path.join(test_bin_dir, "Cargo.toml"), "w") as f:
            f.write(
                f'[package]\nname = "test_main"\nversion = "0.1.0"\nedition = "2021"\n\n'
                f"[dependencies]\n{input_lib} = {{ path = '{abs_output_proxy}' }}\n"
            )

        env = dict(os.environ)
        for dep in deps:
            if dep.lang == "ada":
                env["POLYGLOT_PROXY_LIB_DIR"] = dep.library_path
                env["POLYGLOT_PROXY_LIB_NAME"] = dep.library_name

        run(
            ["cargo", "build", "--quiet", "--manifest-path", os.path.join(test_bin_dir, "Cargo.toml")],
            env=env,
            pipe=True,
        )

        return CompilationResult(
            lang="rust",
            exec_cmd=[
                os.path.realpath(os.path.join(test_bin_dir, "target", "debug", "test_main"))
            ],
            exec_env={},
        )

    if output_lang == "c++":
        proxy_c_files = glob.glob(os.path.join(output_proxy, "*.cpp"))
        proxy_c_files += glob.glob(
            os.path.join(output_proxy, "runtimes", "ada", "src2cpp", "*.cpp")
        )
        # We may want to use cflags that are incompatible with the ones we use
        # by default (eg. `--std=c++17 when using C++17 constructs...): specifying
        # cflags will overwrite.
        C_FLAGS = cflags or ["-Wall", "-Wextra", "-Werror", "-std=c++11"]

        LD_FLAGS = [
            f"-L{os.path.join(input_proxy, 'lib_agg', 'static', 'dev')}",
            f"-l{input_lib}_proxy_agg",
            *(ldflags if ldflags else [])
        ]
        if sys.platform == "linux":
            LD_FLAGS.extend(["-ldl", "-lpthread"])
        elif sys.platform == "darwin":
            LD_FLAGS.extend(macos_ada_runtime_flags())

        argv = [
            "g++",
            f"-I{os.path.join(output_proxy, 'include')}",
            f"-I{os.path.join(output_proxy, 'runtimes', 'ada', 'src2cpp')}",
            "-o",
            "main",
            test_file,
            *proxy_c_files,
            *LD_FLAGS,
            *C_FLAGS,
        ]
        run(argv)
        return CompilationResult(
            lang="ada",
            exec_cmd=[os.path.realpath("main")],
            exec_env={}
        )
    if output_lang == "java":
        class_path = os.pathsep.join([
            str(list(Path(os.path.join(output_proxy, "target")).glob("*.jar"))[0]),
            *[
                str(p)
                for p in list(
                    Path(os.path.join(output_proxy, "target", "lib")).glob("*.jar")
                )
            ],
        ])

        argv = [
            "javac",
            f"--class-path={class_path}",
            test_file
        ]
        run(argv)
        exec_env = {}
        lib_path_var = (
            "PATH" if os.name == "nt" else
            "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else
            "LD_LIBRARY_PATH"
        )
        for dep in deps:
            if dep.lang != "java":
                add_path(exec_env, lib_path_var, dep.library_path)
        return CompilationResult(
            lang="java",
            exec_cmd=[
                "java" if os.name != "nt" else "java.exe",
                "-ea",
                "--enable-native-access=ALL-UNNAMED",
                "-ea",
                f"--class-path={class_path}{os.pathsep}.",
                test_file.replace(".java", "")
            ],
            exec_env=exec_env
        )
    else:
        raise Exception(f"Unknown language: {output_lang}")


def compile_lib(
    input_lang: str,
    lib_location: str,
    extra_args: list[str] | None = None,
    deps : list[CompilationResult] = []
) -> list[CompilationResult]:
    """
    Compile the generated library at the given path.
    """
    if extra_args is None:
        extra_args = []
    if input_lang == "ada":
        if os.path.isdir(lib_location):
            lib_location = str(list(Path(lib_location).glob("*.gpr"))[0])
        project_args = (
            (["-XLIBRARY_STANDALONE=standard"] if sys.platform == "darwin" else [])
            + extra_args
        )
        run([
            "gprbuild",
            lib_location,
            "-q",
            "-ggdb",
            "-gnatwI",
            "--gpr=2",
            *project_args,
        ])
        inspect = json.loads(run(
            [
                "gprinspect",
                lib_location,
                "--display=json-compact",
                *[arg for arg in project_args if not arg.startswith("-gnat")],
            ],
            pipe=True
        ))
        return [
            CompilationResult(
                lang="ada",
                library_name=inspect.get("projects")[0].get("project").get("library-name"),
                library_path=inspect.get("projects")[0].get("project").get("library-directory")
            )
        ]
    elif input_lang == "java":
        # Compile the Java bindings
        env = dict(os.environ)
        env["MAVEN_OPTS"] = "--enable-native-access=ALL-UNNAMED"
        run([env["MAVEN_EXEC"], "package", "-f", lib_location, "-q"], env=env, pipe=True)

        # Compile the JNI layer
        gpr_file = str(list(Path(lib_location).glob("*.gpr"))[0])
        jni_args = ["-XOS=windows" if os.name == "nt" else "-XOS=unix"]
        for dep in deps:
            jni_args.extend([
                f"-XPROXY_LIB_LOCATION={dep.library_path}",
                f"-XPROXY_LIB={dep.library_name}",
            ])
        return [
            *compile_lib("c", gpr_file, jni_args),
            CompilationResult(
                lang="java",
                library_path=os.path.join(lib_location, "target", "classes")
            )
        ]
    elif input_lang == "rust":
        env = dict(os.environ)
        for dep in deps:
            if dep.lang == "ada":
                env["POLYGLOT_PROXY_LIB_DIR"] = dep.library_path
                env["POLYGLOT_PROXY_LIB_NAME"] = dep.library_name
        run(
            ["cargo", "build", "--quiet", "--manifest-path", os.path.join(lib_location, "Cargo.toml")],
            env=env,
            pipe=True,
        )
        return [
            CompilationResult(
                lang="rust",
                library_path=os.path.join(lib_location, "target", "debug"),
            )
        ]
    elif input_lang in ("c", "c++"):
        if os.path.isdir(lib_location):
            lib_location = str(list(Path(lib_location).glob("*.gpr"))[0])
        run([
            "gprbuild",
            lib_location,
            "-q",
            "-ggdb",
            "-gnatwI",
            "--gpr=2",
            *extra_args,
        ])
        inspect = json.loads(run(
            [
                "gprinspect",
                lib_location,
                "--display=json-compact",
                "-r",
                *extra_args,
            ],
            pipe=True
        ))
        install_path = os.path.abspath("install")
        run([
            "gprinstall",
            lib_location,
            f"--prefix={install_path}",
            "-q",
            "-r",
            "-p",
            "--gpr=2",
            *extra_args,
        ])
        return [
            CompilationResult(
                lang="ada",
                library_name=inspect.get("projects")[0].get("project").get("library-name"),
                library_path=os.path.join(install_path, "bin" if os.name == "nt" else "lib")
            )
        ]
    else:
        raise Exception(f"Unknown language: {input_lang}")


class PrinterConfig():

    def __init__(self, path) -> None:
        with open(os.path.join(path, "test.yaml")) as f:
            self._cfg = yaml.safe_load(f)
        self._root = path

    @property
    def output_lang(self) -> str:
        return self._cfg["output_lang"]

    @property
    def test_file(self) -> str:
        return self._cfg["test_file"]

    @property
    def cflags(self) -> list[str] | None:
        return self._cfg.get("main_cflags")

    @property
    def ldflags(self) -> list[str] | None:
        ld_flags = self._cfg.get("main_ldflags", {})
        if ld_flags:
            if os.name == "nt":
                return ld_flags.get("windows")
            elif sys.platform == "darwin":
                return ld_flags.get("darwin")
            else:
                return ld_flags.get("linux")

    @property
    def output_lib_flags(self) -> list[str]:
        return self._cfg.get("output_lib_flags", [])


def run_printer(output_lang: str, proxy_file: str, output_path: str) -> None:
    """
    Run a scanner on ``project_file`` and generate the proxy at
    ``output_path``.
    """
    if output_lang == "c++":
        run_polyglot("proxy2cpp", [proxy_file, "-o", output_path])
    elif output_lang == "java":
        run_polyglot("proxy2java", [proxy_file, "-o", output_path])
    elif output_lang == "rust":
        run_polyglot("proxy2rust", [proxy_file, "-o", output_path])
    else:
        raise Exception(f"Unknown language: {output_lang}")


def add_path(env: dict[str, str], env_var: str, path: str):
    """
    Adds the path to the ``env_var`` path variable in ``env``
    """
    env[env_var] = "{}{}{}".format(path, os.path.pathsep, env.get(env_var, ""))


def valgrind_cmd(output_lang: str, argv: list[str]):
    suppression_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "package_elab.supp"
    )
    if output_lang in ["c++"]:
        return [
            "valgrind",
            "-q",
            "--leak-check=full",
            "--show-leak-kinds=all",
            "--track-origins=yes",
            "--error-exitcode=2",
            f"--suppressions={suppression_file}",
            *argv
        ]
    return argv


def get_proxy_lib_file(input_lang: str, proxy_location: str) -> str:
    if input_lang == "ada":
        return str(list(Path(proxy_location).glob("*agg.gpr"))[0])
    return ""


def list_generated_sources(proxy_dir: Path | str) -> list[str]:
    sources = os.listdir(Path(proxy_dir, "src").as_posix())
    sources.sort()
    return sources


def run_setup(
    prefix: str = "runtimes",
    check_only=False,
    from_lang:str = "",
    to_lang:str = "",
    expect_returncode: int = 0,
):
    argv = [f"--prefix={prefix}"]
    if from_lang != "":
        argv.append(f"--from-lang={from_lang}")
    if to_lang != "":
        argv.append(f"--to-lang={to_lang}")
    if check_only:
        argv.append("--check-only")
    out = run_polyglot(
        "setup",
        argv,
        pipe=True,
        expect_returncode=expect_returncode
    )
    if check_only and len(out) > 0:
        print(out.replace("\\", "/"), end="")
