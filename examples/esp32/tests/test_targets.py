"""Reject incompatible compiler and object ABIs before attempting a board link."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import TARGETS, check_compiler_macros, check_elf


C3_MACROS = {
    "__SIZEOF_POINTER__": "4", "__BYTE_ORDER__": "__ORDER_LITTLE_ENDIAN__",
    "__riscv": "1", "__riscv_xlen": "32", "__riscv_float_abi_soft": "1",
    "__riscv_compressed": "1", "__riscv_mul": "1", "__riscv_div": "1",
}


def macros(values):
    return "\n".join(f"#define {name} {value}" for name, value in values.items())


class CompilerTests(unittest.TestCase):
    def test_c3_ilp32_is_accepted(self):
        result = check_compiler_macros(macros(C3_MACROS), TARGETS["esp32c3"])
        self.assertEqual(result["abi"], "ilp32")
        self.assertEqual(result["pointer_bits"], 32)

    def test_rv64_compiler_is_rejected(self):
        values = {**C3_MACROS, "__riscv_xlen": "64", "__SIZEOF_POINTER__": "8"}
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros(values), TARGETS["esp32c3"])

    def test_missing_imc_features_are_rejected(self):
        for key in ("__riscv_compressed", "__riscv_mul", "__riscv_div"):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                check_compiler_macros(macros({k: v for k, v in C3_MACROS.items() if k != key}), TARGETS["esp32c3"])

    def test_hardware_float_is_rejected(self):
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros({**C3_MACROS, "__riscv_flen": "32"}), TARGETS["esp32c3"])

    def test_atomic_extension_is_rejected(self):
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros({**C3_MACROS, "__riscv_atomic": "1"}), TARGETS["esp32c3"])

    def test_big_endian_compiler_is_rejected(self):
        values = {**C3_MACROS, "__BYTE_ORDER__": "__ORDER_BIG_ENDIAN__"}
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros(values), TARGETS["esp32c3"])

    def test_xtensa_windowed_abi_still_works(self):
        values = {"__SIZEOF_POINTER__": "4", "__BYTE_ORDER__": "__ORDER_LITTLE_ENDIAN__",
                  "__XTENSA_WINDOWED_ABI__": "1"}
        self.assertEqual(check_compiler_macros(macros(values), TARGETS["esp32"])["abi"], "windowed")

    def test_xtensa_rejects_riscv_compiler(self):
        with self.assertRaises(RuntimeError):
            check_compiler_macros(macros(C3_MACROS), TARGETS["esp32"])


class ElfTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "probe.o"

    def elf(self, machine=243, flags=1, elf_class=1, endian=1):
        header = bytearray(52)
        header[:6] = b"\x7fELF" + bytes([elf_class, endian])
        struct.pack_into("<H", header, 18, machine)
        struct.pack_into("<I", header, 36, flags)
        self.path.write_bytes(header)
        return self.path

    def test_c3_elf_is_accepted(self):
        self.assertEqual(check_elf(self.elf(), TARGETS["esp32c3"])["machine"], "RISC-V")

    def test_elf64_is_rejected(self):
        with self.assertRaises(RuntimeError):
            check_elf(self.elf(elf_class=2), TARGETS["esp32c3"])

    def test_big_endian_elf_is_rejected(self):
        with self.assertRaises(RuntimeError):
            check_elf(self.elf(endian=2), TARGETS["esp32c3"])

    def test_hard_float_abis_are_rejected(self):
        for flags in (3, 5, 7):
            with self.subTest(flags=flags), self.assertRaises(RuntimeError):
                check_elf(self.elf(flags=flags), TARGETS["esp32c3"])

    def test_rve_abi_is_rejected(self):
        with self.assertRaises(RuntimeError):
            check_elf(self.elf(flags=9), TARGETS["esp32c3"])

    def test_missing_compressed_flag_is_rejected(self):
        with self.assertRaises(RuntimeError):
            check_elf(self.elf(flags=0), TARGETS["esp32c3"])

    def test_wrong_architecture_is_rejected(self):
        with self.assertRaises(RuntimeError):
            check_elf(self.elf(machine=94), TARGETS["esp32c3"])

    def test_truncated_headers_are_rejected(self):
        for length in (0, 6, 20, 51):
            self.path.write_bytes(b"\x7fELF\x01\x01"[:length].ljust(length, b"\0"))
            with self.subTest(length=length), self.assertRaises(RuntimeError):
                check_elf(self.path, TARGETS["esp32c3"])

    def test_xtensa_headers_still_work(self):
        for flags in (0, 0x300):
            self.assertEqual(check_elf(self.elf(machine=94, flags=flags), TARGETS["esp32"])["machine"], "Xtensa")


if __name__ == "__main__":
    unittest.main()
