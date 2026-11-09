# ESP32 Ada–Rust binding probe

This example targets the **original ESP32/WROOM (Xtensa LX6)** and **ESP32-C3
(RISC-V RV32IMC)**. It generates `no_std` Rust bindings for explicit Ada C
exports and links test firmware using Arduino/ESP-IDF startup and serial I/O.
The build never flashes a board.

The [embedded guide](../../doc/embedded.rst) describes toolchain setup, the
supported interface subset, build commands, and the hardware test procedure.
The [ESP32-C3 guide](../../doc/esp32c3.rst) covers stable Rust, the RV32 Ada
runtime, and the C3 linker setup.

Current validation:

- The same Ada and generated Rust functions pass host tests on Apple Silicon.
- Ada and Rust cross-compile for 32-bit, little-endian Xtensa with the windowed
  ABI and RISC-V RV32IMC with the ILP32 soft-float ABI.
- The complete firmware links for each chip. Its binding symbols resolve, with no
  desktop proxy runtime or Rust allocation entry points in the image.
- **Original ESP32 hardware execution passed** on ESP32-D0WD-V3 revision 3.1
  with 4 MB flash: three clean startups and 300 repeated self-tests for this
  branch. See the [hardware record](validation/esp32-d0wd-v3.json) for exact
  source/image hashes and observed upload/serial limitations.
- **ESP32-C3 hardware execution is pending.** Build-only reports retain
  `hardware_tested: false`; physical evidence is recorded separately.

The test covers a mutable `i32` parameter, accepted addition and rejected
overflow in both directions, a `u64` round trip, `f32`/`f64` arguments and
returns, and signed `i16` arguments and returns. A zero failure mask is a pass.
The Ada package forbids elaboration code, allocators, implicit heap allocation,
and tasking. The Rust binding crate has no dependencies.

`proxy.json` is the reviewed contract for the five explicit exports in
`ada/abi_probe.ads`; it is not produced by Ada2Proxy. The standard Ada2Proxy
runtime and its desktop aggregate-library projects are not ported to ESP32 by
this example.

Select the chip in both build and serial-test commands:

| Chip | Build argument | PlatformIO environment | Output directory | Host output |
| --- | --- | --- | --- | --- |
| ESP32/WROOM | `--chip esp32` (default) | `esp32wroom` | `build/esp32/` | `build/host/` |
| ESP32-C3 | `--chip esp32c3` | `esp32c3` | `build/esp32c3/` | `build/host-esp32c3/` |
| ESP32-C3 native USB | `--chip esp32c3 --usb-console --firmware` | `esp32c3-usb` | `build/esp32c3-usb/` | Use the C3 host check above |

For example, after installing the C3 tools and building the Rust generator:

```sh
python3 examples/esp32/build.py --chip esp32c3 --firmware \
    --ada-compiler /path/to/gnat/bin/riscv64-elf-gcc
```

Each output directory contains `generated/`, the firmware library, and
`validation.json`. Application images are in
`firmware/.pio/build/<environment>/firmware.bin`. The C3 build also creates a
local linker adapter so that the SDK can link modern RISC-V objects.

For a C3 connected through native USB Serial/JTAG, add ``--usb-console`` to
the firmware build. This enables the SDK's hardware USB console and selects
the separate ``esp32c3-usb`` environment. The default C3 environment uses a
UART console for boards with an external USB-to-UART bridge.

After flashing the matching probe, use
`python3 examples/esp32/test_board.py --chip esp32c3 --port <PORT>` (or
`--chip esp32` for WROOM). Success includes the chip name, for example
`GNATPOLYGLOT PASS chip=esp32c3 mask=0x00000000`.

The compiler/ELF compatibility checks can be tested without cross-toolchains:

```sh
python3 -m unittest discover -s examples/esp32/tests -v
```
