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

### ESP32 / Xtensa and RISC-V

The Rust backend also provides an experimental `--embedded` profile for
runtime-free `no_std` scalar bindings. The shared example builds and links Ada
and generated Rust code for the original ESP32/WROOM (Xtensa) and ESP32-C3
(RISC-V). See the [embedded guide](doc/embedded.rst),
[ESP32-C3 setup](doc/esp32c3.rst), and [ESP32 example](examples/esp32/README.md).
Both targets have passed physical scalar-probe execution: three clean startups
and 300 repeated self-tests each for the original ESP32 and ESP32-C3 with
native USB. See the [ESP32 hardware record](examples/esp32/validation/esp32-d0wd-v3.json)
and [ESP32-C3 hardware record](examples/esp32/validation/esp32c3-qfn32.json).

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
