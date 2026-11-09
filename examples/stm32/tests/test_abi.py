"""Reject incompatible Cortex-M objects, boot images, and debugger results."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import TARGETS, check_arm_attributes, check_compiler_macros, check_elf, check_vectors
from test_board import MAGIC, parse_result

F4 = TARGETS["stm32f405rg"]
H7 = TARGETS["stm32h743vi"]
MACROS = {"__SIZEOF_POINTER__": "4", "__BYTE_ORDER__": "__ORDER_LITTLE_ENDIAN__",
          "__ARM_EABI__": "1", "__ARM_ARCH_7EM__": "1", "__thumb__": "1",
          "__ARM_PCS_VFP": "1", "__ARM_FP": "4"}
ATTRIBUTES = {"Tag_CPU_arch": "v7E-M", "Tag_CPU_arch_profile": "Microcontroller",
              "Tag_THUMB_ISA_use": "Thumb-2", "Tag_ABI_VFP_args": "VFP registers",
              "Tag_FP_arch": "VFPv4-D16"}


def macros(values):
    return "\n".join(f"#define {key} {value}" for key, value in values.items())


def attributes(values):
    return "\n".join(f"  {key}: {value}" for key, value in values.items())


class CompilerTests(unittest.TestCase):
    def test_f405_hard_float(self):
        self.assertEqual(check_compiler_macros(macros(MACROS), F4)["cpu"], "cortex-m4")

    def test_h743_double_precision(self):
        result = check_compiler_macros(macros({**MACROS, "__ARM_FP": "0xe"}), H7)
        self.assertEqual(result["fpu"], "fpv5-d16")

    def test_missing_abi_features(self):
        for key in MACROS:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                check_compiler_macros(macros({k: v for k, v in MACROS.items() if k != key}), F4)

    def test_soft_float(self):
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros({**MACROS, "__ARM_PCS_VFP": "0"}), F4)

    def test_64_bit_pointers(self):
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros({**MACROS, "__SIZEOF_POINTER__": "8"}), F4)

    def test_big_endian(self):
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros({**MACROS, "__BYTE_ORDER__": "__ORDER_BIG_ENDIAN__"}), F4)

    def test_wrong_fpu(self):
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros(MACROS), H7)
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros({**MACROS, "__ARM_FP": "14"}), F4)


class AttributeTests(unittest.TestCase):
    def test_f4_attributes(self):
        self.assertEqual(check_arm_attributes(attributes(ATTRIBUTES), F4)["Tag_CPU_arch"], "v7E-M")

    def test_h7_attributes(self):
        values = {**ATTRIBUTES, "Tag_FP_arch": "FPv5/FP-D16 for ARMv8"}
        self.assertEqual(check_arm_attributes(attributes(values), H7)["Tag_ABI_VFP_args"], "VFP registers")

    def test_missing_attributes(self):
        for key in ATTRIBUTES:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                check_arm_attributes(attributes({k: v for k, v in ATTRIBUTES.items() if k != key}), F4)

    def test_wrong_core_profile(self):
        with self.assertRaises(RuntimeError):
            check_arm_attributes(attributes({**ATTRIBUTES, "Tag_CPU_arch_profile": "Application"}), F4)

    def test_wrong_float_calling_convention(self):
        with self.assertRaises(RuntimeError):
            check_arm_attributes(attributes({**ATTRIBUTES, "Tag_ABI_VFP_args": "Base AAPCS"}), F4)

    def test_double_precision_object_rejected_for_f4(self):
        with self.assertRaises(RuntimeError):
            check_arm_attributes(attributes({**ATTRIBUTES, "Tag_FP_arch": "FPv5/FP-D16 for ARMv8"}), F4)


class ElfTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "firmware.elf"

    def elf(self, machine=40, flags=0x05000400, entry=0x08000401,
            elf_class=1, endian=1, elf_type=2):
        header = bytearray(52)
        header[:6] = b"\x7fELF" + bytes([elf_class, endian])
        struct.pack_into("<HHI", header, 16, elf_type, machine, 1)
        struct.pack_into("<I", header, 24, entry)
        struct.pack_into("<I", header, 36, flags)
        self.path.write_bytes(header)
        return self.path

    def test_valid_hard_float_image(self):
        self.assertEqual(check_elf(self.elf(), executable=True)["machine"], "Arm")

    def test_relocatable_object_uses_attributes_for_float_abi(self):
        check_elf(self.elf(flags=0x05000000, entry=0, elf_type=1))

    def test_wrong_machine_class_or_endianness(self):
        for values in [{"machine": 243}, {"elf_class": 2}, {"endian": 2}]:
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                check_elf(self.elf(**values), executable=True)

    def test_old_eabi_or_soft_float(self):
        for flags in [0x04000400, 0x05000200, 0x05000600, 0x05000000]:
            with self.subTest(flags=flags), self.assertRaises(RuntimeError):
                check_elf(self.elf(flags=flags), executable=True)

    def test_arm_state_entry(self):
        with self.assertRaises(RuntimeError):
            check_elf(self.elf(entry=0x08000400), executable=True)

    def test_relocatable_not_accepted_as_firmware(self):
        with self.assertRaises(RuntimeError):
            check_elf(self.elf(elf_type=1), executable=True)

    def test_truncated_header(self):
        for length in [0, 6, 20, 51]:
            self.path.write_bytes(bytes(length))
            with self.subTest(length=length), self.assertRaises(RuntimeError):
                check_elf(self.path)


class VectorTests(unittest.TestCase):
    def image(self, stack=0x20020000, reset=0x08000401, size=2048):
        return struct.pack("<II", stack, reset) + bytes(max(0, size - 8))

    def test_both_profiles_have_valid_vectors(self):
        for target in [F4, H7]:
            check_vectors(self.image(), target, 0x08000401)

    def test_wrong_or_unaligned_stack(self):
        for stack in [0, 0x24080000, 0x2001fffc]:
            with self.subTest(stack=stack), self.assertRaises(RuntimeError):
                check_vectors(self.image(stack=stack), F4, 0x08000401)

    def test_reset_must_match_thumb_entry_in_flash(self):
        for reset, entry in [(0x08000400, 0x08000400), (0x08000405, 0x08000401),
                             (0x20000401, 0x20000401), (0x08008001, 0x08008001)]:
            with self.subTest(reset=reset), self.assertRaises(RuntimeError):
                check_vectors(self.image(reset=reset), F4, entry)

    def test_truncated_or_oversized_image(self):
        for size in [16, 1023, F4.flash_bytes + 4]:
            with self.subTest(size=size), self.assertRaises(RuntimeError):
                check_vectors(self.image(size=size), F4, 0x08000401)


class BoardResultTests(unittest.TestCase):
    def result(self, magic=MAGIC, chip=F4.chip_id, state=2, failures=0):
        return f"GNATPOLYGLOT RESULT magic={magic} chip={chip} state={state} failures={failures}\n"

    def test_pass(self):
        self.assertEqual(parse_result(self.result(), F4)["state"], "pass")

    def test_wrong_image_magic_or_chip(self):
        for values in [{"magic": 0}, {"chip": H7.chip_id}]:
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                parse_result(self.result(**values), F4)

    def test_failure_states_and_nonzero_masks(self):
        for state, mask in [(1, 0), (3, 1), (4, 0xffffffff), (5, 0xffffffff),
                            (6, 0xffffffff), (0, 0), (2, 1)]:
            with self.subTest(state=state, mask=mask), self.assertRaises(RuntimeError):
                parse_result(self.result(state=state, failures=mask), F4)

    def test_missing_ambiguous_or_malformed_result(self):
        for text in ["", "GNATPOLYGLOT PASS", self.result() * 2,
                     self.result().replace("state=2", "state=pass")]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                parse_result(text, F4)


if __name__ == "__main__":
    unittest.main()
