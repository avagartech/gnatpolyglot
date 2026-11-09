"""Architecture and ABI checks for the supported ESP32 binding probes."""

from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass(frozen=True)
class ChipTarget:
    chip: str
    label: str
    architecture: str
    rust_target: str
    pio_environment: str
    compiler_environment: str
    compiler_flags: tuple[str, ...]
    elf_machine: int
    build_std: bool


TARGETS = {
    "esp32": ChipTarget(
        "esp32", "ESP32/WROOM", "Xtensa", "xtensa-esp32-none-elf", "esp32wroom",
        "XTENSA_ADA_COMPILER", ("-mlongcalls",), 94, True,
    ),
    "esp32c3": ChipTarget(
        "esp32c3", "ESP32-C3", "RISC-V", "riscv32imc-unknown-none-elf", "esp32c3",
        "RISCV_ADA_COMPILER", ("-march=rv32imc", "-mabi=ilp32"), 243, False,
    ),
}


def check_compiler_macros(text: str, target: ChipTarget) -> dict:
    macros = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3 and parts[0] == "#define":
            macros[parts[1]] = parts[2]
    required = {"__SIZEOF_POINTER__": "4", "__BYTE_ORDER__": "__ORDER_LITTLE_ENDIAN__"}
    if target.chip == "esp32c3":
        required.update({
            "__riscv": "1", "__riscv_xlen": "32", "__riscv_float_abi_soft": "1",
            "__riscv_compressed": "1", "__riscv_mul": "1", "__riscv_div": "1",
        })
        if "__riscv_flen" in macros or "__riscv_atomic" in macros:
            raise RuntimeError("ESP32-C3 requires RV32IMC without hardware floating-point or A extensions")
    else:
        required["__XTENSA_WINDOWED_ABI__"] = "1"
    mismatches = [name for name, value in required.items() if macros.get(name) != value]
    if mismatches:
        raise RuntimeError(f"Compiler ABI does not match {target.label}: {', '.join(mismatches)}")
    return {"pointer_bits": 32, "byte_order": "little",
            "abi": "ilp32" if target.chip == "esp32c3" else "windowed",
            "isa": "rv32imc" if target.chip == "esp32c3" else "Xtensa LX6"}


def check_elf(path: Path, target: ChipTarget) -> dict:
    with path.open("rb") as stream:
        header = stream.read(52)
    if (len(header) != 52 or header[:6] != b"\x7fELF\x01\x01"
            or struct.unpack_from("<H", header, 18)[0] != target.elf_machine):
        raise RuntimeError(f"Expected a 32-bit little-endian {target.architecture} ELF: {path}")
    flags = struct.unpack_from("<I", header, 36)[0]
    if target.chip == "esp32c3":
        if flags & 0x6:
            raise RuntimeError(f"ESP32-C3 ELF uses a hard-float ABI instead of ILP32: {path}")
        if flags & 0x8:
            raise RuntimeError(f"ESP32-C3 ELF uses the incompatible RVE ABI: {path}")
        if not flags & 0x1:
            raise RuntimeError(f"ESP32-C3 ELF must declare compressed instructions: {path}")
    return {"machine": target.architecture, "bits": 32, "byte_order": "little", "flags": hex(flags)}
