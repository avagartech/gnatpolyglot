.. _stm32:

STM32 Arm Cortex-M probes
=========================

Scope and current status
------------------------

``examples/stm32`` extends the experimental scalar-only ``--embedded`` Rust
profile to two STM32 parts:

* **STM32F405RGT6**: Cortex-M4F, single-precision FPv4 FPU, 1 MiB flash.
  The probe uses the contiguous 128 KiB SRAM at ``0x20000000`` and leaves
  the separate CCM/backup memory unused.
* **STM32H743VIT6**: Cortex-M7, single/double-precision FPv5 FPU, 2 MiB flash.
  The probe uses 128 KiB DTCM at ``0x20000000`` and leaves the other memory
  banks unused.

These layouts follow ST's `STM32F405RG specifications
<https://www.st.com/en/microcontrollers-microprocessors/stm32f405rg.html>`_
and `STM32H743VI specifications
<https://www.st.com/en/microcontrollers-microprocessors/stm32h743vi.html>`_.
Both use internal flash starting at ``0x08000000`` with no bootloader offset.
Other parts, flash sizes, boot arrangements, and Cortex-M0/M3/M33 profiles
need their own configuration and validation.

The generated wrappers passed native Ada/Rust execution checks on Apple
Silicon. Both complete Arm firmware images cross-linked and passed compiler,
object attributes, ELF, vector table, and symbol checks. **Physical STM32
execution is pending**. A successful build always records
``hardware_tested: false``; it does not establish measured timing, stack
usage, peripheral operation, or a complete application port.

The supported scalar interfaces and restrictions are the same as
:ref:`embedded`. The example reuses the reviewed ``examples/esp32/proxy.json``
contract and pure Ada probe source, changing only the generated crate name
to ``stm32_bindings``. It does not add an embedded Ada scanner or support
records, arrays, tasking, allocation, or exception propagation across the ABI.

Tools and build
---------------

Use JDK 24, Maven, Python 3.11 or later, a GNAT Arm cross-compiler, and stable
Rust. The tested host used GNAT FSF 16.1.0 and Rust 1.99.1. The
`GNAT FSF Arm release
<https://github.com/alire-project/GNAT-FSF-builds/releases/tag/gnat-16.1.0-1>`_
includes an Apple Silicon build and the required generic Cortex-M runtimes.
The driver is ``arm-eabi-gcc``; a C-only Arm GCC installation cannot compile
the Ada fixture.

Both cores use Rust's ``thumbv7em-none-eabihf`` target. Stable Rust supplies
``core`` for this target; no Espressif fork or ``-Zbuild-std`` is needed.
See the official `Rust Cortex-M4/M7 target documentation
<https://doc.rust-lang.org/rustc/platform-support/thumbv7em-none-eabi.html>`_.

From the repository root, with stable Rust on ``PATH`` and ``JAVA_HOME`` set:

.. code:: sh

   rustup target add thumbv7em-none-eabihf --toolchain stable
   mvn package -f gnatpolyglot/pom.xml -pl proxy2rust -am
   export ARM_ADA_COMPILER="/path/to/gnat/bin/arm-eabi-gcc"
   python3 examples/stm32/build.py --chip stm32f405rg --firmware
   python3 examples/stm32/build.py --chip stm32h743vi --firmware

The independent Rust generator build does not require Libadalang. The script
selects the following Ada flags/runtimes and passes the matching CPU to Rust:

* F405: ``-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard``,
  using ``light-cortex-m4f``.
* H743: ``-mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard``,
  using ``light-cortex-m7df``.

Runtime declarations are auto-detected below
``<gnat-prefix>/arm-eabi/lib/gnat/<runtime>``. For another installation layout,
pass the full directory with ``--ada-runtime`` or ``STM32_ADA_RUNTIME``.
``--ada-compiler``, ``--cargo``, and ``--java`` select alternate tools.
``--build-dir`` changes the output directory. Use ``--offline`` when Cargo's
required files are cached. Omitting ``--firmware`` builds the static libraries
only. Build commands never connect to a board or flash it.

ABI and link checks
-------------------

The build checks 32-bit pointers, little-endian data, Armv7E-M, Thumb, the
hard-float calling convention, and the selected FPU. An Ada compile-time
guard verifies the runtime's word/address sizes. Object attributes and final
ELF checks reject incompatible architecture/FPU and floating-point argument
conventions. The final image must be ELF32/EABI5 with a Thumb entry point.
The vector table must contain the selected RAM's initial stack address and
a reset handler inside the selected flash image.

The binding call convention is AAPCS hard-float for both targets. On F405,
``f64`` arithmetic uses software helpers while scalar arguments still obey
the hard-float ABI. H743 uses double-precision instructions. Software and
hard-float calling conventions must not be mixed, even for a chip with an FPU.

The final link uses the unchanged Rust static library and matching GCC
compiler helpers with ``-nostdlib``. The pure Ada package needs no Ada binder
startup or linked Ada runtime library. Its checks remain enabled and use the
probe's last-chance handler. Rust panics use a separate failure handler.
The build rejects unresolved symbols, missing probe entry points, unexpected
desktop proxy/Rust allocation symbols, static constructors, and static data
overlapping the reserved 4 KiB stack.

Firmware behavior and outputs
-----------------------------

The minimal startup installs a vector table, enables CP10/CP11 and the FPU,
sets VTOR, copies ``.data``, and clears ``.bss`` before calling the probe.
Core/IRQ handlers trap failures. Interrupts stay masked and clocks retain
their reset settings. The example does not configure PLLs, pins, peripherals,
or an RTOS. Use a board/application startup and memory map when integrating
the generated library into a larger firmware.

The probe checks the CPU part number and initialized data, then executes
the mutable ``i32``, checked addition/overflow status, ``u64`` round trip,
``f32``/``f64`` calls, and ``i16`` cases through generated Rust wrappers into
Ada. It writes a debugger-visible ``polyglot_stm32_result`` and stops in
``polyglot_stm32_done`` without requiring serial pin selection.

Each ``examples/stm32/build/<chip>/`` directory contains:

* ``generated/``, ``libabi_probe.a``, and ``libpolyglot_stm32_probe.a``.
* ``firmware.elf``, raw ``firmware.bin``, address-bearing ``firmware.hex``,
  ``firmware.map``, and the generated ``memory.ld``.
* ``validation.json`` with ABI checks, section sizes, image hash, and the
  result symbol's address. Section sizes include debug information separately
  from flash/RAM use; the raw binary size excludes debug sections.

Host and regression checks
--------------------------

Run the same scalar self-test using a native GNAT compiler:

.. code:: sh

   python3 examples/stm32/build.py --host-test \
       --ada-compiler /path/to/native-gnat/bin/gcc
   python3 -m unittest discover -s examples/stm32/tests -v

The host test prints ``STM32 Ada/Rust host checks passed`` and writes
``build/host-stm32f405rg/validation.json``. Add ``--chip stm32h743vi`` to
record a separate host result; both execute the same contract on the host,
not Arm instructions. The regression tests cover incompatible compiler/object
ABIs, invalid boot vectors, and rejecting failed or mismatched debugger results.

Board test after connection
---------------------------

Identify the exact part, flash layout, and debug probe before upload. The
following examples assume ST-Link and OpenOCD. After building the matching
image, upload it explicitly:

.. code:: sh

   openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
       -c "program examples/stm32/build/stm32f405rg/firmware.elf verify reset exit"

For H743, use ``target/stm32h7x.cfg`` and the
``build/stm32h743vi/firmware.elf`` image. Start the matching OpenOCD server
without the ``program`` command, then run the collector in another terminal:

.. code:: sh

   openocd -f interface/stlink.cfg -f target/stm32f4x.cfg
   python3 examples/stm32/test_board.py --chip stm32f405rg \
       --gdb /path/to/gnat/bin/arm-eabi-gdb --remote localhost:3333

The collector resets/halts the board, installs a temporary hardware
breakpoint at completion, continues, and reads the result. It never uploads
firmware. Use ``--elf`` with a custom build directory and ``--output`` for an
alternate report path. A pass requires the probe magic, matching build chip
tag, PASS state, and zero failure mask. The tag identifies the firmware
profile; it is not a silicon identity check. The firmware separately checks
Cortex-M4/M7 CPUID but does not identify the exact STM32 part.

Success prints ``GNATPOLYGLOT PASS chip=stm32f405rg mask=0x00000000`` (or
``stm32h743vi``) and saves ``build/<chip>/hardware-validation.json``.
States 4, 5, and 6 identify an Ada check, Rust panic, and CPU fault. Failure
mask bits 0--6 identify scalar tests; bits 30 and 31 identify RAM initialization
and unexpected CPU core failures. A nonzero mask or any other state fails.
