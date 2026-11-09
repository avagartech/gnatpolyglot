# STM32 Cortex-M Ada–Rust binding probe

This example builds `no_std` Rust bindings and a bare-metal firmware probe for:

| Chip argument | Core | Floating-point configuration | Probe memory layout |
| --- | --- | --- | --- |
| `stm32f405rg` | Cortex-M4F | FPv4 SP, hard-float ABI | 1 MiB flash, 128 KiB SRAM |
| `stm32h743vi` | Cortex-M7 | FPv5 DP, hard-float ABI | 2 MiB flash, 128 KiB DTCM |

The shared reviewed scalar contract and pure Ada source are in
[`../esp32/proxy.json`](../esp32/proxy.json) and [`../esp32/ada/`](../esp32/ada/).
The build changes the generated crate's name to `stm32_bindings` and runs the
actual Rust generator with `--embedded`. The [STM32 guide](../../doc/stm32.rst)
covers installation, ABI checks, the supported subset, and the later board test.

After building `proxy2rust` and installing ARM GNAT plus stable Rust's
`thumbv7em-none-eabihf` target, run from the repository root:

```sh
export ARM_ADA_COMPILER="/path/to/gnat/bin/arm-eabi-gcc"
python3 examples/stm32/build.py --chip stm32f405rg --firmware
python3 examples/stm32/build.py --chip stm32h743vi --firmware
```

Neither command connects to or flashes hardware. Each chip's outputs are in
`build/<chip>/`, including generated bindings, libraries, `firmware.elf`,
`firmware.bin`, `firmware.hex`, `firmware.map`, and `validation.json`.

Host execution and toolchain-independent ABI/boot/result checks:

```sh
python3 examples/stm32/build.py --host-test \
    --ada-compiler /path/to/native-gnat/bin/gcc
python3 -m unittest discover -s examples/stm32/tests -v
```

The firmware enables the FPU, initializes RAM, checks the CPU part number,
and calls the Rust self-test through generated bindings into Ada. A debugger
can inspect `polyglot_stm32_result` when execution reaches
`polyglot_stm32_done`. The probe runs at reset clock settings, keeps interrupts
disabled, and uses no board-specific serial pins. **Physical execution is
pending**; firmware build reports retain `hardware_tested: false`.

Once the matching image is flashed and a GDB server is running, the collector
can reset/run the board and read its result:

```sh
python3 examples/stm32/test_board.py --chip stm32f405rg \
    --gdb /path/to/gnat/bin/arm-eabi-gdb --remote localhost:3333
```

This command does not upload firmware. It saves an observed result in
`build/<chip>/hardware-validation.json` and accepts only a matching probe tag,
PASS state, and zero failure mask. Peripheral drivers, rich Ada APIs, and
RTOS integration require further development.
