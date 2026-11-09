.. _embedded:

Experimental embedded Rust bindings
===================================

Scope and current status
------------------------

``gnatpolyglot proxy2rust --embedded`` emits a ``#![no_std]`` Cargo library
without the desktop GNATpolyglot runtime dependency. The initial board target
is the **original ESP32/WROOM**, using ``xtensa-esp32-none-elf`` on the Rust
side and an ESP32-configured Xtensa GNAT compiler on the Ada side.

The generator accepts free functions using fixed-width integers through 64
bits, 32/64-bit floating-point values, booleans, characters, void returns, and
scalar reference parameters. It rejects classes/records, enumerations,
exceptions, arrays, strings, pointers, callbacks, returned references,
ownership transfer, and 128-bit scalars in this profile. Use explicit integer
status values for recoverable errors.

The profile checks the interface shape; the foreign library must still obey
the declared C ABI and the Rust reference and scalar validity requirements.
It does not remove allocations or exception handling from an existing Ada
library. The example uses explicit C exports from a pure Ada package with
restrictions against elaboration code, allocators, implicit heap allocation,
and tasking.

The standard Ada2Proxy wrappers depend on the desktop runtime, including
exception and allocation support. This first embedded path uses a reviewed
``proxy.json`` for explicit C exports instead. It does **not** add an embedded
Ada2Proxy scanner/runtime or general embedded support for rich Ada APIs.

Validation passed host execution of the generated wrappers on Apple Silicon,
cross-linked the complete ESP32 firmware, and executed the scalar probe on
ESP32-D0WD-V3 revision 3.1 with 4 MB flash. This branch passed three clean
startups and 300 repeated serial self-tests. The hardware record at
``examples/esp32/validation/esp32-d0wd-v3.json`` identifies the tested source
and image hashes and records observed upload/serial limitations. It does not
establish timing, stack bounds, or general embedded API support. ESP32-S2,
ESP32-S3, RISC-V ESP32 variants, and Intel macOS hosts require separate work
or validation.

Tools
-----

Build the independent Rust generator using JDK 24 and Maven; this does not
require Libadalang:

.. code:: sh

   mvn package -f gnatpolyglot/pom.xml -pl proxy2rust -am

The module can also be run directly, without the full scanner CLI:

.. code:: sh

   java -cp gnatpolyglot/proxy2rust/target/proxy2rust.jar \
       com.adacore.gnatpolyglot.proxy2rust.Proxy2Rust \
       examples/esp32/proxy.json -o /tmp/esp32-bindings --embedded

For Xtensa builds, install:

* An ESP32-targeted GNAT compiler and compatible Ada runtime declarations.
  The tested compiler was GNAT FSF 16.1.0. The example used the ESP32 runtime
  declarations at commit ``2ad6145c50151fed6de930f1d94f4021c09ece6a`` of
  `esp32-gnat-rts <https://github.com/reznikmm/esp32-gnat-rts>`_. It does not
  link that project's full Ada/FreeRTOS runtime.
* Espressif's Rust toolchain with matching ``rust-src``. The tested version
  was ``1.97.0.0``. See the official
  `Rust on ESP toolchain instructions
  <https://docs.espressif.com/projects/rust/book/getting-started/toolchain.html>`_.
* Espressif's ``xtensa_esp32.so`` CPU configuration plugin. The generic GNAT
  Xtensa defaults are not sufficient: the build checks for 32-bit pointers,
  little-endian data, and the windowed ABI before compiling the Ada code.
* PlatformIO for firmware builds. The example pins ``espressif32@6.13.0`` and
  uses the ``esp32dev`` board configuration, Arduino 2.0.17 and the SDK's
  common startup, FreeRTOS, serial, memory helpers and libgcc.
* Python 3.11 or later; ``pyserial`` is needed only by the board-test command.

The generator and build scripts run on the development Mac. The generated
library and firmware are compiled for the ESP32, not for macOS. Put the
Espressif Rust ``cargo``/``rustc`` binaries on ``PATH``, set ``JAVA_HOME``, and
adapt the following paths to your installations:

.. code:: sh

   export XTENSA_ADA_COMPILER="/path/to/gnat/bin/xtensa-esp32-elf-gcc"
   export ESP32_ADA_RUNTIME="/path/to/esp32-runtime/esp32"
   export XTENSA_GNU_CONFIG="/path/to/espressif/lib/xtensa_esp32.so"
   python3 examples/esp32/build.py --firmware

Use ``--offline`` when Cargo's build-std dependencies are already cached.
``--cargo``, ``--java`` and ``--platformio`` can select tool executables.
``--build-dir`` selects an isolated output directory. The command builds
libraries and firmware only; it does not open a serial port or flash hardware.

Build flow
----------

The example compiles the Ada package with range/overflow checks retained,
creates a static archive, and runs the actual Rust generator with
``--embedded``. Cargo then builds a ``no_std`` test library against the
generated crate, using ``-Zbuild-std=core`` and panic-abort behavior.

For the final Arduino/ESP-IDF link, the build makes a separate copy of the
Rust static archive and removes its compiler-builtins objects. This preserves
the SDK's common ROM/IRAM memory helpers and libgcc rather than overriding
them with Rust's generic implementations while flash caches may be disabled.
The Cargo-produced archive is retained unchanged.

The build verifies the ELF architecture and exported Ada/Rust test symbols.
``build/esp32/validation.json`` records the checks, entry-point code sizes and
firmware hash. It records ``hardware_tested: false`` regardless of build
success. The existing SDK startup references ``start_app`` and
``start_app_other_cores`` are recorded separately from binding symbols.

The initial firmware used 21,480 bytes of reported RAM and 268,321 bytes of
reported flash with the tested SDK configuration. These figures include the
Arduino/ESP-IDF application and serial harness; they are not binding-only
memory usage or measured real-time performance. The five Ada probe entry
points plus the Rust self-test entry occupied 407 bytes of symbol-reported
code in that build, excluding any supporting code and data.

Host checks before connecting the board
---------------------------------------

The same Ada functions and generated ``no_std`` wrappers can be executed on
Apple Silicon with the native GNAT compiler:

.. code:: sh

   python3 examples/esp32/build.py --host-test \
       --ada-compiler /path/to/native-gnat/bin/gcc

The host runner explicitly links its host Ada runtime. This does not add a
runtime dependency to the generated embedded crate. A successful run prints
``Embedded Ada/Rust host checks passed`` and records its result under
``build/host/validation.json``. These host checks do not establish Xtensa
runtime behavior; that still requires the board test.

Board test after connection
---------------------------

After connecting and identifying the original ESP32/WROOM, upload the probe
using PlatformIO's normal upload target, substituting its serial port:

.. code:: sh

   pio run -d examples/esp32/firmware -t upload --upload-port <PORT>
   python3 examples/esp32/test_board.py --port <PORT>

The firmware runs its checks on startup and accepts ``TEST`` over serial at
115200 baud. Success is ``GNATPOLYGLOT PASS mask=0x00000000``. Failures report
a nonzero mask, an Ada runtime-check failure, or a Rust panic. The serial
collector saves its observed lines and pass/fail result in
``build/esp32/hardware-validation.json``. It does not flash the board.

The probe tests mutable scalar parameters, accepted arithmetic, overflow
status preservation, a 64-bit integer round trip, 32/64-bit floating-point
calls, and signed 16-bit calls. It contains no actuator-control code.
