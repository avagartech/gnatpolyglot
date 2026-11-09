from pathlib import Path
import os

Import("env")
root = Path(env["PROJECT_DIR"]).parent
chip = "esp32c3" if env["PIOENV"] == "esp32c3" else "esp32"
build = Path(os.environ.get("POLYGLOT_PROBE_BUILD_DIR", str(root / "build" / chip)))
env.Append(LIBPATH=[str(build)])
env.Append(LIBS=["polyglot_esp32_probe"])
if chip == "esp32c3":
    linker_dir = Path(os.environ.get("POLYGLOT_PROBE_LINKER_DIR", str(build / "sdk-linker")))
    if not (linker_dir / "ld").is_file() and not (linker_dir / "ld.exe").is_file():
        raise RuntimeError("Build the C3 libraries/linker adapter with build.py --chip esp32c3 --firmware first")
    env.Prepend(LINKFLAGS=["-B" + str(linker_dir) + os.sep])
