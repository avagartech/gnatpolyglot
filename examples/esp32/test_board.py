"""Run the selected flashed ESP32 probe over serial; this command never flashes."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from targets import TARGETS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chip", choices=TARGETS, default="esp32")
    parser.add_argument("--port", required=True)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--output", type=Path,
                        default=None)
    args = parser.parse_args()
    target = TARGETS[args.chip]
    args.output = args.output or Path(__file__).resolve().parent / "build" / target.chip / "hardware-validation.json"
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        import serial
    except ImportError:
        parser.error("install pyserial in the Python environment used for this command")
    report = {"target": target.label, "chip": target.chip, "hardware_tested": False, "passed": False,
              "port": args.port, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "lines": []}
    try:
        with serial.Serial(args.port, 115200, timeout=0.25, write_timeout=2) as board:
            report["hardware_tested"] = True
            deadline = time.monotonic() + args.timeout
            next_request = 0
            while time.monotonic() < deadline:
                if time.monotonic() >= next_request:
                    board.write(b"\nTEST\n")
                    board.flush()
                    next_request = time.monotonic() + 1
                line = board.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                print(line, flush=True)
                report["lines"].append(line)
                if line == f"GNATPOLYGLOT PASS chip={target.chip} mask=0x00000000":
                    report["passed"] = True
                    break
                if "GNATPOLYGLOT FAIL" in line:
                    raise RuntimeError("The board reported a failed Ada/Rust probe")
            if not report["passed"]:
                raise RuntimeError(f"Timed out waiting for the {target.label} binding probe")
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
