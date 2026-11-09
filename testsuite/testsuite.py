#! /usr/bin/env python

import os
from os.path import isdir
import sys

import tempfile
from e3.testsuite import Testsuite

from drivers import (
    junit_driver, proxy2print_driver, proxy_validator_driver, python_driver,
    scan2proxy_driver
)
from python_support.utils import add_path, run_setup, run


class GNATpolyglotTestsuite(Testsuite):
    tests_subdir = "tests"
    test_driver_map = {
        "junit": junit_driver.JunitDriver,
        "python": python_driver.PythonDriver,
        "scan2proxy": scan2proxy_driver.Scan2Proxy,
        "proxy2print": proxy2print_driver.Proxy2Print,
        "proxy_validator": proxy_validator_driver.ProxyValidator
    }

    def add_options(self, parser) -> None:
        parser.add_argument(
            "--rewrite",
            "-r",
            action="store_true",
            help="Rewrite test baselines according to current output.",
        )

        parser.add_argument(
            "--valgrind",
            action="store_true",
            help="Run test executables with Valgrind to check memory issues.",
        )

        parser.add_argument(
            "--native",
            action="store_true",
            help="Run gnatpolyglot using the native-image build.",
        )

        parser.add_argument(
            "--maven-executable",
            help="Specify the Maven executable to use. The default one is"
            ' "mvn".'
        )

        parser.add_argument(
            "--maven-local-repo",
            help="Specify the Maven repository to use. The default one is the"
            " user's repository (~/.m2).",
        )

        parser.add_argument(
            "--lal_version",
            help="Specify the version of Libadalang to use. The default one is"
            ' "0.1".'
        )

    def set_up(self) -> None:
        super().set_up()

        args = self.main.args

        self.env.rewrite_baselines = args.rewrite

        # Make sure the runtime is available before running the tests
        try:
            runtime_dir = os.environ["GNATPOLYGLOT_RUNTIME"]
        except KeyError:
            runtime_dir = os.path.join(
                os.path.dirname(__file__), "..", "gnatpolyglot", "runtimes"
            )
            os.environ["GNATPOLYGLOT_RUNTIME"] = runtime_dir

        self.env.unsupported_languages = []

        if self.env.build.platform not in (
            "x86_64-linux", "x86_64-windows64", "aarch64-darwin"
        ):
            self.env.unsupported_languages.append("rust")

        if self.env.build.platform in (
            "x86_64-linux", "x86_64-windows64"
        ):
            # Build and install the Java Runtime libraries
            mvn_args = []
            if args.maven_local_repo is not None:
                mvn_args.append(f"-Dmaven.repo.local={self.env.options.maven_local_repo}")
            with tempfile.TemporaryDirectory() as d:
                run_setup(d)
                for r in (["proxy2java"], ["ada", "src2java"]):
                    run([
                        args.maven_executable or "mvn",
                        "install",
                        f"-f{os.path.join(d, *r)}",
                        "-q",
                        *mvn_args
                        ],
                        pipe=True,
                        env={
                            "MAVEN_OPTS": "--enable-native-access=ALL-UNNAMED",
                            **dict(os.environ)
                        }
                    )
        else:
            self.env.unsupported_languages.append("java")

        # Check if the internal testsuite is present
        self.env.control_condition_env = {
            "skip_internal": not os.path.isdir(os.path.join(
                os.path.dirname(__file__), "tests", "internal", "sources"
            ))
        }

sys.exit(GNATpolyglotTestsuite().testsuite_main())
