# ESP32/WROOM Ada–Rust binding probe

This example targets the **original ESP32/WROOM (Xtensa LX6)**. It generates
`no_std` Rust bindings for explicit Ada C exports and links a test firmware
using Arduino/ESP-IDF startup and serial I/O. The build never flashes a board.

The [embedded guide](../../doc/embedded.rst) describes toolchain setup, the
supported interface subset, build commands, and the hardware test procedure.

Current validation:

- The same Ada and generated Rust functions pass host tests on Apple Silicon.
- Ada and Rust cross-compile for 32-bit, little-endian Xtensa with the windowed ABI.
- The complete ESP32 firmware links. Its binding symbols resolve, with no
  desktop proxy runtime or Rust allocation entry points in the image.
- **Hardware execution passed** on ESP32-D0WD-V3 revision 3.1 with 4 MB flash:
  three clean startups and 300 repeated self-tests for this branch. See the
  [hardware validation record](validation/esp32-d0wd-v3.json) for source/image
  hashes and observed upload/serial limitations. Build-only reports retain
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

After building, the generated crate is in `build/esp32/generated/`, the firmware
library and validation report are in `build/esp32/`, and the application image
is in `firmware/.pio/build/esp32wroom/firmware.bin`. Host checks use the separate
`build/host/` directory. Use `test_board.py --port <PORT>` only after flashing
the probe on the connected board.
