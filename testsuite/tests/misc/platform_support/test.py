"""Check native build and launcher settings without requiring Libadalang."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from utils import POLYGLOT_HOME


cli = Path(POLYGLOT_HOME) / "cli"
spec = importlib.util.spec_from_file_location("polyglot_make", cli / "make.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    includes = root / "include"
    libs = root / "lib with spaces"
    includes.mkdir()
    libs.mkdir()
    (includes / "libadalang.h").touch()
    (libs / "libadalang.dylib").touch()
    other_libs = root / "other libraries"
    other_libs.mkdir()
    (other_libs / "libadalang.dylib").touch()

    env = {
        "C_INCLUDE_PATH": str(includes),
        "LIBRARY_PATH": str(libs) + os.pathsep + str(other_libs),
        "DYLD_LIBRARY_PATH": str(libs) + os.pathsep + "/other/libs",
        "LD_LIBRARY_PATH": "/linux/libs",
    }
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(sys, "platform", "darwin"),
        patch.object(os, "name", "posix"),
    ):
        options = build.native_image_options()
        assert f"--native-compiler-options=-L{libs}" in options
        assert f"--native-compiler-options=-L{other_libs}" not in options
        assert f"--native-compiler-options=-Wl,-rpath,{other_libs}" in options
        assert options.count(f"--native-compiler-options=-Wl,-rpath,{libs}") == 1
        assert "--native-compiler-options=-Wl,-rpath,/other/libs" in options
        assert not any("rpath-link" in opt for opt in options)

    (libs / "libadalang.so").touch()
    (libs / "libz.so").touch()
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(sys, "platform", "linux"),
        patch.object(os, "name", "posix"),
    ):
        options = build.native_image_options()
        assert "--native-compiler-options=-Wl,-rpath-link=/linux/libs" in options
        assert not any("-Wl,-rpath," in opt for opt in options)

    with patch.object(os, "name", "nt"):
        assert build.native_image_options() == []

    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(os, "name", "posix"),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        try:
            build.native_image_options()
        except RuntimeError:
            pass
        else:
            raise AssertionError("Missing dependencies must stop native-image builds")

    for platform, os_name, variable in (
        ("darwin", "posix", "DYLD_LIBRARY_PATH"),
        ("linux", "posix", "LD_LIBRARY_PATH"),
        ("win32", "nt", "PATH"),
    ):
        launcher_env = {"GRAAL_HOME": "/graal", variable: "/native/libs"}
        with (
            patch.dict(os.environ, launcher_env, clear=True),
            patch.object(sys, "platform", platform),
            patch.object(os, "name", os_name),
            patch.object(sys, "argv", ["gnatpolyglot.py", "--help"]),
            patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as run,
        ):
            try:
                runpy.run_path(str(cli / "gnatpolyglot.py"), run_name="__main__")
            except SystemExit as exc:
                assert exc.code == 0
            argv = run.call_args.args[0]
            assert "-Djava.library.path=/native/libs" in argv
            assert argv[-1] == "--help"

    with (
        patch.dict(os.environ, {"GRAAL_HOME": "/graal", "LIBRARY_PATH": "/native/libs"}, clear=True),
        patch.object(sys, "platform", "darwin"),
        patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as run,
    ):
        try:
            runpy.run_path(str(cli / "gnatpolyglot.py"), run_name="__main__")
        except SystemExit:
            pass
        assert "-Djava.library.path=/native/libs" in run.call_args.args[0]

    # Exercise generated Rust build scripts as executables, including selecting a
    # target OS different from the host. No target standard libraries or
    # native Ada dependencies are needed for this check.
    if shutil.which("rustc"):
        proxy = root / "proxy.json"
        proxy.write_text(json.dumps({
            "name": "platform_bindings", "input_language": "ada", "modules": [],
        }))
        java_home = os.environ.get("JAVA_HOME") or os.environ["GRAAL_HOME"]
        generator = [
            str(Path(java_home) / "bin/java"), "-cp",
            str(Path(POLYGLOT_HOME) / "proxy2rust/target/proxy2rust.jar"),
            "com.adacore.gnatpolyglot.proxy2rust.Proxy2Rust", str(proxy),
        ]
        for embedded in (False, True):
            generated = root / ("embedded" if embedded else "desktop")
            options = (["--embedded"] if embedded else
                       ["--with-runtime", str(Path(POLYGLOT_HOME) / "runtimes")])
            subprocess.run([*generator, "-o", str(generated), *options],
                           check=True, capture_output=True, text=True)
            binary = generated / ("build.exe" if os.name == "nt" else "build")
            subprocess.run(["rustc", str(generated / "build.rs"), "-o", str(binary)], check=True)
            for target, system_libraries in (
                ("linux", {"dl", "pthread"}),
                ("windows", {"advapi32"}),
                ("macos", set()),
            ):
                env = {k: v for k, v in os.environ.items() if k != "POLYGLOT_ADA_COMPILER"}
                env.update(CARGO_CFG_TARGET_OS=target, POLYGLOT_PROXY_LIB_DIR=str(libs),
                           POLYGLOT_PROXY_LIB_NAME="test_proxy_agg")
                if embedded:
                    # Embedded generation must not query a host GNAT compiler,
                    # even when Cargo runs its build script on a Mac.
                    env["POLYGLOT_ADA_COMPILER"] = str(root / "missing-compiler")
                output = subprocess.check_output([str(binary)], env=env, text=True).splitlines()
                assert f"cargo:rustc-link-search=native={libs}" in output
                assert f"cargo:rerun-if-changed={libs / 'libtest_proxy_agg.a'}" in output
                assert f"cargo:rerun-if-changed={libs}" not in output
                assert "cargo:rustc-link-lib=static=test_proxy_agg" in output
                for var in ("POLYGLOT_PROXY_LIB_DIR", "POLYGLOT_PROXY_LIB_NAME"):
                    assert f"cargo:rerun-if-env-changed={var}" in output
                actual = {line.removeprefix("cargo:rustc-link-lib=") for line in output
                          if line.startswith("cargo:rustc-link-lib=") and "static=" not in line}
                expected = set() if embedded else system_libraries
                assert actual == expected, (embedded, target, actual)

print("Platform support checks passed")
