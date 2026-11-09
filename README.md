# GNATpolyglot

Multi-language binding interface generator.

## Build and usage

GNATpolyglot depends on [Libadalang](https://github.com/AdaCore/libadalang). You must first follow its instructions and install the java bindings.

In order to build GNATpolyglot, you must then run:

```sh
$[gnatpolyglot]> mvn package -f gnatpolyglot/pom.xml
```

You can then run GNATpolyglot using the uber jar:

```
$[gnatpolyglot]> java \
        -cp gnatpolyglot/cli/target/cli.jar \
        --add-exports org.graalvm.truffle/com.oracle.truffle.api.strings=ALL-UNNAMED \
        com.adacore.polylot.cli.GNATpolyglotMain
```

To enable the native-image build, use the `native` profile:
```sh
$[gnatpolyglot]> mvn package -f gnatpolyglot/pom.xml -Pnative
```

You can then run the native application using:

```
$[gnatpolyglot]> ./gnatpolyglot/bin/gnatpolyglot
```

### macOS

The experimental Rust backend initially targets Apple Silicon Macs (arm64).
Intel macOS support is deferred. See [the macOS instructions](doc/macos.rst)
for the required toolchain, standard standalone Ada libraries, runtime linking,
and validation commands.
The Java output backend remains limited to its existing supported platforms.

### ESP32 / Xtensa

The Rust backend also provides an experimental `--embedded` profile for
runtime-free `no_std` scalar bindings. The original ESP32/WROOM example builds
and links Ada and generated Rust code into firmware. See the
[embedded guide](doc/embedded.rst) and [ESP32 example](examples/esp32/README.md).
The scalar probe passed physical execution on an ESP32-D0WD-V3 revision 3.1:
three clean startups and 300 repeated self-tests for the Xtensa feature branch.
See the
[hardware validation record](examples/esp32/validation/esp32-d0wd-v3.json).

## License
This work is licensed under `GPL-3.0-or-later AND Apache-2.0`.

The tools located in
- `gnatpolyglot/ada2proxy`
- `gnatpolyglot/cli`
- `gnatpolyglot/proxy`
- `gnatpolyglot/proxy2cpp`

directories are licensed under `GPL-3.0-or-later`,

The libraries in the `gnatpolyglot/runtimes` directory are licensed under
`Apache-2.0`.

`SPDX-License-Identifier: GPL-3.0-or-later AND Apache-2.0`
