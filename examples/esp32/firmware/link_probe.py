from pathlib import Path
import os

Import("env")
root = Path(env["PROJECT_DIR"]).parent
env.Append(LIBPATH=[os.environ.get("POLYGLOT_PROBE_BUILD_DIR", str(root / "build/esp32"))])
env.Append(LIBS=["polyglot_esp32_probe"])
