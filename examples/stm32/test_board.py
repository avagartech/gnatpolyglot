"""Read a flashed STM32 probe through a running GDB server; never uploads firmware."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

from targets import TARGETS, check_elf

ROOT = Path(__file__).resolve().parent
MAGIC = 0x47504C54
STATES = {1: "running", 2: "pass", 3: "failed", 4: "Ada runtime check",
          5: "Rust panic", 6: "CPU fault"}


def parse_result(text, target):
    matches = re.findall(r"^GNATPOLYGLOT RESULT magic=(\d+) chip=(\d+) state=(\d+) failures=(\d+)$",
                         text, re.MULTILINE)
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one debugger result from the flashed probe")
    magic, chip, state, failures = map(int, matches[0])
    if magic != MAGIC or chip != target.chip_id:
        raise RuntimeError("Debugger result does not match the selected STM32 probe")
    if state != 2 or failures != 0:
        raise RuntimeError(f"Probe did not pass: {STATES.get(state, 'unknown state')}, mask=0x{failures:08x}")
    return {"magic": hex(magic), "chip_id": hex(chip), "state": "pass", "failure_mask": hex(failures)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chip", choices=TARGETS, default="stm32f405rg")
    parser.add_argument("--remote", required=True, help="running GDB server, for example localhost:3333")
    parser.add_argument("--gdb", default="arm-eabi-gdb")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = TARGETS[args.chip]
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    # GDB treats a pipe-prefixed remote as a command, so accept only host:port here.
    if not re.fullmatch(r"[A-Za-z0-9_.-]+:[0-9]{1,5}", args.remote):
        parser.error("--remote must be a host:port address")
    elf = (args.elf or ROOT / "build" / target.chip / "firmware.elf").resolve()
    check_elf(elf, executable=True)
    report_path = args.output or ROOT / "build" / target.chip / "hardware-validation.json"
    report = {"chip": target.chip, "remote": args.remote, "elf": str(elf),
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "hardware_tested": False, "passed": False}
    commands = ["set confirm off", "set pagination off", "set remotetimeout 5",
                "target extended-remote " + args.remote, "monitor reset halt",
                "thbreak polyglot_stm32_done", "continue",
                'printf "\\nGNATPOLYGLOT RESULT magic=%u chip=%u state=%u failures=%u\\n", '
                'polyglot_stm32_result.magic, polyglot_stm32_result.chip, '
                'polyglot_stm32_result.state, polyglot_stm32_result.failures', "detach"]
    argv = [args.gdb, "-nx", "--batch", str(elf)]
    for command in commands:
        argv += ["-ex", command]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=args.timeout)
        report["debugger_output"] = result.stdout + result.stderr
        result.check_returncode()
        report["hardware_tested"] = True
        report["result"] = parse_result(result.stdout, target)
        report["passed"] = True
        print(f"GNATPOLYGLOT PASS chip={target.chip} mask=0x00000000")
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
