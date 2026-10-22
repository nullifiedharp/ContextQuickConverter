"""Entry point.

  QuickConvert.exe                         -> setup window (Install / Uninstall)
  QuickConvert.exe convert png "a.jpg"     -> Convert to > PNG
  QuickConvert.exe resize 50pct "a.jpg"    -> Resize image (50pct, 1920px, 1920x1080, custom)
  QuickConvert.exe compress 10 "a.mp4"     -> Compress video (high, small, <MB>, custom)
  QuickConvert.exe install [--quiet]
  QuickConvert.exe uninstall [--quiet]
"""
import json
import os
import sys
from pathlib import Path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in argv
    argv = [a for a in argv if a != "--quiet"]

    if not argv:
        from .ui import setup_window
        setup_window()
        return 0

    cmd = argv[0].lower()
    if cmd == "convert" and len(argv) >= 3:
        return _convert(argv[1], Path(argv[2]))
    if cmd in ("resize", "compress") and len(argv) >= 3:
        return _op(cmd, argv[1], Path(argv[2]))
    if cmd in ("install", "uninstall"):
        from . import shell_integration as si
        try:
            si.install() if cmd == "install" else si.uninstall()
        except Exception as e:
            if not quiet:
                from .ui import show_error
                show_error(f"{cmd.title()} failed:\n{e}")
            return 1
        return 0

    from .ui import show_error
    show_error(__doc__.strip())
    return 2


def _convert(target: str, src: Path) -> int:
    from . import engine
    from .ui import run_with_progress, show_error
    from .util import ConversionError, JobSlot

    try:
        mod, dst, heavy = engine.plan(src, target)
    except ConversionError as e:
        show_error(str(e))
        return 1

    def job(progress, cancel, on_wait):
        if heavy:
            with JobSlot(cancel, on_wait):
                return mod.convert(src, dst, target, progress, cancel)
        return mod.convert(src, dst, target, progress, cancel)

    t = target.upper()
    return 0 if run_with_progress(src, f"Converting to {t}...",
                                  f"Couldn't convert {src.name} to {t}.", job) else 1


# Last value typed into a "Custom..." box, pre-filled next time (handy when
# you select 20 photos and each one asks).
def _settings_file() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "QuickConvert" / "settings.json"


def _remember(key: str, value: str | None = None) -> str:
    f = _settings_file()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if value is None:
        return data.get(key, "")
    data[key] = value
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass
    return value


ASK = {
    "resize": ("Resize image",
               "New size for {name}:\n\n"
               "  50%          percentage\n"
               "  1600         longest side in pixels\n"
               "  1920x1080    fit inside a box", "50%"),
    "compress": ("Compress video", "Target size for {name} in MB:", "25"),
}


def _op(op: str, arg: str, src: Path) -> int:
    from . import engine
    from .ui import ask_value, run_with_progress, show_error
    from .util import ConversionError, JobSlot

    if arg.lower() == "custom":
        title, prompt, default = ASK[op]
        arg = ask_value(title, prompt.format(name=src.name), _remember(op) or default)
        if arg is None:
            return 0
        _remember(op, arg)

    try:
        fn, heavy = engine.plan_op(op, arg, src)
    except ConversionError as e:
        show_error(str(e))
        return 1

    def job(progress, cancel, on_wait):
        if heavy:
            with JobSlot(cancel, on_wait):
                return fn(progress, cancel)
        return fn(progress, cancel)

    if op == "resize":
        doing = f"Resizing to {arg.replace('pct', '%')}..."
    elif arg in ("high", "small"):
        doing = "Compressing..."
    else:
        doing = f"Compressing to under {arg.rstrip('MBmb ')} MB..."
    return 0 if run_with_progress(src, doing, f"Couldn't {op} {src.name}.", job) else 1
