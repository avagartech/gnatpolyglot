.. _esp32c3:

ESP32-C3 RISC-V probe
=====================

Scope and validation
--------------------

The shared ``examples/esp32`` probe supports ESP32-C3 with the RV32IMC
instruction set, little-endian data, and the ILP32 soft-float ABI. It uses the
same scalar-only ``--embedded`` generator profile and reviewed explicit Ada C
exports described in :ref:`embedded`. Automatic embedded Ada scanning and
rich Ada interfaces are outside this prototype's scope.

On an Apple Silicon host, the generated wrappers passed native Ada/Rust
execution checks and the complete C3 firmware cross-linked successfully.
The compiler and final image passed ELF32/RISC-V, compressed-instruction,
and soft-float ABI checks. The original Xtensa firmware also still builds.
**Hardware execution is pending**; build reports retain
``hardware_tested: false``. ESP32-C2, C6, H2, and other RISC-V chips are not
validated by the C3 build.

Tools
-----

Build the independent Rust generator with JDK 24 and Maven:

.. code:: sh

   mvn package -f gnatpolyglot/pom.xml -pl proxy2rust -am

Install the following target tools:

* Stable Rust with ``riscv32imc-unknown-none-elf``. Unlike Xtensa, this target
  does not require Espressif's Rust fork, nightly features, or rebuilding
  ``core``. Follow the official
  `Rust on ESP toolchain instructions
  <https://docs.espressif.com/projects/rust/book/getting-started/toolchain.html>`_:

  .. code:: sh

     rustup target add riscv32imc-unknown-none-elf --toolchain stable

* A RISC-V GNAT compiler with 32-bit Ada runtime declarations. The tested
  `GNAT FSF 16.1.0 RISC-V package
  <https://github.com/alire-project/GNAT-FSF-builds/releases/tag/gnat-16.1.0-1>`_
  includes ``light-rv32im`` even though its driver is named
  ``riscv64-elf-gcc``. The build always passes ``-march=rv32imc -mabi=ilp32``
  and checks both compiler macros and Ada runtime address/word sizes.
  The runtime directory is auto-detected at
  ``<gnat-prefix>/riscv64-elf/lib/gnat/light-rv32im``. For another layout, pass
  the **full directory path** using ``--ada-runtime``; a short runtime name
  is not accepted. This probe compiles against those declarations without
  linking a separate Ada tasking/runtime library.
* PlatformIO with the pinned ``espressif32@6.13.0`` platform. The ``esp32c3``
  environment uses ``esp32-c3-devkitm-1``, Arduino 2.0.17, 4 MB flash,
  DIO at 40 MHz, and serial at 115200 baud. The board configuration will need
  checking against the connected board before upload.
* Python 3.11 or later; ``pyserial`` is needed only for the serial collector.

Put stable Rust's ``cargo`` and ``rustc`` on ``PATH`` and set ``JAVA_HOME``.
No Xtensa CPU configuration plugin is used for C3. The validated host used
Rust 1.99.1 and GNAT 16.1.0.

Build the firmware
------------------

From the repository root, adapting the compiler path:

.. code:: sh

   export RISCV_ADA_COMPILER="/path/to/gnat/bin/riscv64-elf-gcc"
   python3 examples/esp32/build.py --chip esp32c3 --firmware

``--ada-compiler`` can override the compiler environment variable. Unset an
Xtensa-specific ``ESP32_ADA_RUNTIME`` before this build, or explicitly select
the C3 runtime with ``--ada-runtime``. Use ``--offline`` when Cargo's required
packages are already cached. ``--cargo``, ``--java``, ``--platformio``, and
``--build-dir`` select alternate tools or output paths.

The script builds the Ada static library and generated Rust crate, then
links them with SDK startup, serial I/O, and compiler helpers. The SDK's GCC
8.4 linker cannot merge all modern RISC-V object attributes. The build
therefore creates ``build/esp32c3/sdk-linker/`` aliases to GNAT's newer RISC-V
linker and selects it for the final link. SDK compilers, libraries, and object
attributes are retained. Keep the GNAT tools available for later relinks.

As with Xtensa, a separate firmware archive omits Rust compiler-builtins
objects so the final link retains the SDK's ROM/IRAM helpers and libgcc.
The original Cargo archive remains unchanged. The generated binding crate
does not acquire a desktop proxy runtime or allocation dependency.

Outputs are under ``examples/esp32/build/esp32c3/``, including the generated
crate, static libraries, and ``validation.json``. Firmware images are under
``examples/esp32/firmware/.pio/build/esp32c3/``. The validated application used
13,772 bytes of reported RAM and 247,486 bytes of reported flash. These totals
include Arduino/ESP-IDF and the serial harness; they do not measure binding
overhead or real-time performance.

Host and ABI checks
-------------------

Run the same probe through generated wrappers using a native GNAT compiler:

.. code:: sh

   python3 examples/esp32/build.py --chip esp32c3 --host-test \
       --ada-compiler /path/to/native-gnat/bin/gcc

A pass prints ``Embedded Ada/Rust host checks passed`` and records
``build/host-esp32c3/validation.json``. This verifies the scalar contract on
the host; it does not execute RISC-V instructions.

Compiler and ELF checks have toolchain-independent regression tests:

.. code:: sh

   python3 -m unittest discover -s examples/esp32/tests -v

The tests reject RV64, incompatible floating-point or reduced-register ABIs,
missing IMC features, wrong endianness/architecture, and truncated objects,
and retain the original Xtensa checks.

Board test after connection
---------------------------

Build the firmware above first. After identifying the connected ESP32-C3
and its serial port, upload and collect its self-test:

.. code:: sh

   pio run -d examples/esp32/firmware -e esp32c3 -t upload --upload-port <PORT>
   python3 examples/esp32/test_board.py --chip esp32c3 --port <PORT>

For a custom ``--build-dir``, set ``POLYGLOT_PROBE_BUILD_DIR`` to that full
directory when invoking PlatformIO directly so it finds the matching
libraries and linker adapter.

Success is ``GNATPOLYGLOT PASS chip=esp32c3 mask=0x00000000``. The collector
requires the selected chip in the pass line and records its observations in
``build/esp32c3/hardware-validation.json``. It accepts ``TEST`` over serial
at 115200 baud and does not upload firmware itself. The shared probe covers
mutable scalar parameters, checked addition and overflow status, a 64-bit
integer round trip, 32/64-bit floating-point calls, and signed 16-bit calls.
