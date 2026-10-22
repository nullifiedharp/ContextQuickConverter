"""Picks the right converter for (source file, target format)."""
from pathlib import Path

from .formats import category, canon, targets_for
from .util import ConversionError, unique_path

HEAVY = {"video", "audio", "word", "sheet", "slide"}  # rationed by JobSlot


def plan(src: Path, target: str):
    """Return (converter_module, output_path, is_heavy)."""
    src = Path(src)
    target = canon(target)
    if not src.is_file():
        raise ConversionError(f"File not found:\n{src}")
    cat = category(src.suffix)
    if cat is None or target not in targets_for(src.suffix):
        raise ConversionError(f"Can't convert {src.suffix or 'this file'} to {target.upper()}.")

    dst = unique_path(src.with_suffix("." + target))

    if cat == "image" and target in ("mp4", "webm"):      # animated GIF -> video
        from . import convert_media as mod
        return mod, dst, True
    if cat == "image":
        from . import convert_image as mod
        return mod, dst, False
    if cat in ("video", "audio"):
        from . import convert_media as mod
        return mod, dst, True
    from . import convert_doc as mod
    return mod, dst, cat in HEAVY


def convert(src, target, progress=None, cancel=None) -> Path:
    mod, dst, _ = plan(src, target)
    return mod.convert(Path(src), dst, canon(target), progress, cancel)


def plan_op(op: str, arg: str, src):
    """For the Resize/Compress menus. Returns (fn(progress, cancel), is_heavy)."""
    from .formats import RESIZE_IN, COMPRESS_IN
    src = Path(src)
    if not src.is_file():
        raise ConversionError(f"File not found:\n{src}")
    ext = src.suffix.lower().lstrip(".")
    if op == "resize" and ext in RESIZE_IN:
        from . import convert_image as m
        dst = m.resize_output(src, arg)
        return (lambda p, c: m.resize(src, dst, arg, p, c)), False
    if op == "compress" and ext in COMPRESS_IN:
        from . import convert_media as m
        dst = m.compress_output(src, arg)
        return (lambda p, c: m.compress(src, dst, arg, p, c)), True
    raise ConversionError(f"Can't {op} {src.suffix or 'this file'}.")
