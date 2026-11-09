"""Validated build profiles and ABI checks for the initial STM32 probes."""

from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass(frozen=True)
class ChipTarget:
    chip: str
    cpu: str
    fpu: str
    arm_fp: int
    runtime: str
    flash_bytes: int
    chip_id: int
    cpuid_part: int
    rust_target: str = "thumbv7em-none-eabihf"
    flash_origin: int = 0x08000000
    ram_origin: int = 0x20000000
    ram_bytes: int = 128 * 1024

    @property
    def compiler_flags(self):
        return ("-mcpu=" + self.cpu, "-mthumb", "-mfpu=" + self.fpu, "-mfloat-abi=hard")


TARGETS = {
    "stm32f405rg": ChipTarget(
        "stm32f405rg", "cortex-m4", "fpv4-sp-d16", 4, "light-cortex-m4f",
        1024 * 1024, 0xF405, 0xC24,
    ),
    "stm32h743vi": ChipTarget(
        "stm32h743vi", "cortex-m7", "fpv5-d16", 14, "light-cortex-m7df",
        2048 * 1024, 0x743, 0xC27,
    ),
}


def check_compiler_macros(text: str, target: ChipTarget) -> dict:
    macros = {}
    for line in text.splitlines():
        fields = line.split(maxsplit=2)
        if len(fields) == 3 and fields[0] == "#define":
            macros[fields[1]] = fields[2]
    required = {
        "__SIZEOF_POINTER__": "4", "__BYTE_ORDER__": "__ORDER_LITTLE_ENDIAN__",
        "__ARM_EABI__": "1", "__ARM_ARCH_7EM__": "1", "__thumb__": "1",
        "__ARM_PCS_VFP": "1",
    }
    invalid = [key for key, value in required.items() if macros.get(key) != value]
    try:
        fp = int(macros.get("__ARM_FP", "0"), 0)
    except ValueError:
        fp = 0
    if fp != target.arm_fp:
        invalid.append("__ARM_FP")
    if invalid:
        raise RuntimeError(f"Compiler ABI does not match {target.chip}: {', '.join(invalid)}")
    return {"pointer_bits": 32, "byte_order": "little", "isa": "Thumb-2/Armv7E-M",
            "cpu": target.cpu, "fpu": target.fpu, "abi": "AAPCS hard-float"}


def check_arm_attributes(text: str, target: ChipTarget) -> dict:
    attributes = {}
    for line in text.splitlines():
        key, separator, value = line.strip().partition(":")
        if separator and key.startswith("Tag_"):
            attributes[key] = value.strip()
    required = {"Tag_CPU_arch": "v7E-M", "Tag_CPU_arch_profile": "Microcontroller",
                "Tag_THUMB_ISA_use": "Thumb-2", "Tag_ABI_VFP_args": "VFP registers",
                "Tag_FP_arch": ("VFPv4-D16" if target.cpu == "cortex-m4"
                                else "FPv5/FP-D16 for ARMv8")}
    invalid = [key for key, value in required.items() if attributes.get(key) != value]
    if invalid:
        raise RuntimeError("Incompatible Arm object attributes: " + ", ".join(invalid))
    return attributes


def check_elf(path: Path, *, executable=False) -> dict:
    with path.open("rb") as stream:
        header = stream.read(52)
    if (len(header) != 52 or header[:6] != b"\x7fELF\x01\x01"
            or struct.unpack_from("<H", header, 18)[0] != 40):
        raise RuntimeError(f"Expected a 32-bit little-endian Arm ELF: {path}")
    flags = struct.unpack_from("<I", header, 36)[0]
    if flags >> 24 != 5 or flags & 0x200:
        raise RuntimeError(f"Expected EABI5 without soft-float ELF flags: {path}")
    entry = struct.unpack_from("<I", header, 24)[0]
    if executable and (struct.unpack_from("<H", header, 16)[0] != 2
                       or not flags & 0x400 or not entry & 1):
        raise RuntimeError(f"Expected a hard-float Arm executable with a Thumb entry point: {path}")
    return {"machine": "Arm", "bits": 32, "byte_order": "little",
            "flags": hex(flags), "entry": hex(entry)}


def check_vectors(image: bytes, target: ChipTarget, entry: int) -> dict:
    if len(image) < 1024 or len(image) > target.flash_bytes:
        raise RuntimeError("Firmware image does not fit the selected flash layout")
    stack, reset = struct.unpack_from("<II", image)
    if stack != target.ram_origin + target.ram_bytes or stack % 8:
        raise RuntimeError("Invalid initial stack pointer for the selected STM32 RAM")
    if reset != entry or not reset & 1 or not target.flash_origin <= reset < target.flash_origin + len(image):
        raise RuntimeError("Invalid Thumb reset vector for the selected STM32 flash")
    return {"initial_stack": hex(stack), "reset_vector": hex(reset)}
