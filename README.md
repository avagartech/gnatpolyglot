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
