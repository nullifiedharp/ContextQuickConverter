import re
from pathlib import Path

from PIL import Image, ImageOps

from .util import ConversionError, atomic_output

_heif_registered = False

ALPHA_OK = {"png", "webp", "gif", "tiff", "ico", "avif"}
PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP",
              "gif": "GIF", "tiff": "TIFF", "ico": "ICO", "avif": "AVIF",
              "pdf": "PDF"}
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _register_heif():
    global _heif_registered
    if not _heif_registered:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        _heif_registered = True


def _has_alpha(im: Image.Image) -> bool:
    return (im.mode in ("RGBA", "LA", "PA", "RGBa", "La")
            or "transparency" in im.info)


def _prepare(im: Image.Image, target: str) -> Image.Image:
    """Get the image into a mode the target format can store."""
    if _has_alpha(im):
        im = im.convert("RGBA")
        if target in ALPHA_OK:
            return im
        # JPG/BMP/PDF have no transparency: flatten onto white, not black.
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.getchannel("A"))
        return bg
    if target in ("png", "tiff") and im.mode in ("1", "L", "P", "RGB", "I;16", "I"):
        return im
    if target in ("jpg", "webp", "pdf", "avif") and im.mode in ("L", "RGB"):
        return im
    if target == "gif" and im.mode in ("L", "P", "RGB"):
        return im
    if im.mode in ("I;16", "I", "F"):        # 16-bit grayscale -> 8-bit
        im = im.point(lambda v: v / 256).convert("L")
        return im
    return im.convert("RGB")


def _square_for_ico(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    if w == h:
        return im
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    return canvas


def convert(src: Path, dst: Path, target: str, progress=None, cancel=None) -> Path:
    _register_heif()
    try:
        im = Image.open(src)
    except Exception as e:
        raise ConversionError(f"Couldn't open this image ({e}).") from e

    with im, atomic_output(dst) as tmp:
        fmt = PIL_FORMAT[target]
        frames = getattr(im, "n_frames", 1)
        icc = im.info.get("icc_profile")

        # Animated GIF <-> animated WebP keeps the animation.
        if target in ("gif", "webp") and frames > 1:
            opts = dict(save_all=True, loop=im.info.get("loop", 0))
            if "duration" in im.info:
                opts["duration"] = im.info["duration"]
            if target == "webp":
                opts["quality"] = 90
            im.save(tmp, fmt, **opts)
            return dst

        # Multi-page TIFF -> multi-page PDF.
        if target == "pdf" and frames > 1:
            pages = []
            for i in range(frames):
                im.seek(i)
                pages.append(_prepare(im.copy(), "pdf"))
            pages[0].save(tmp, "PDF", save_all=True, append_images=pages[1:],
                          resolution=_dpi(im))
            return dst

        im.seek(0)
        frame = ImageOps.exif_transpose(im)  # bake in phone-camera rotation
        exif = frame.info.get("exif")
        _save_still(_prepare(frame, target), tmp, target, icc, exif, _dpi(im))
    return dst


def _save_still(frame, tmp, target, icc, exif, dpi):
    """Save one still image with sensible per-format quality settings."""
    fmt = PIL_FORMAT[target]
    opts = {}
    if target == "jpg":
        opts = dict(quality=92, optimize=True)
    elif target == "webp":
        opts = dict(quality=90, method=4)
    elif target == "avif":
        opts = dict(quality=80)
    elif target == "tiff":
        opts = dict(compression="tiff_lzw")
    elif target == "pdf":
        opts = dict(resolution=dpi)
    elif target == "ico":
        frame = _square_for_ico(frame)
        sizes = [(s, s) for s in ICO_SIZES if s <= frame.width] or [(frame.width,) * 2]
        if frame.width > 256:
            frame = frame.resize((256, 256), Image.LANCZOS)
        opts = dict(sizes=sizes)

    if target in ("jpg", "png", "webp", "tiff", "avif"):
        if icc:
            opts["icc_profile"] = icc
        if exif:
            opts["exif"] = exif

    try:
        frame.save(tmp, fmt, **opts)
    except Exception as e:
        raise ConversionError(f"Couldn't save as {target.upper()} ({e}).") from e


def _dpi(im) -> float:
    dpi = im.info.get("dpi")
    try:
        v = float(dpi[0])
        return v if v >= 30 else 150.0
    except Exception:
        return 150.0


# ------------------------------------------------------------------ resize
def parse_resize(spec: str):
    """'50%' -> ('pct', 50) | '1920' or '1920px' -> ('max', 1920)
    | '1920x1080' -> ('box', 1920, 1080). Max/box never upscale."""
    s = spec.strip().lower().replace(" ", "").replace("×", "x").replace("pct", "%")
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)%", s):
        v = float(m[1])
        if 1 <= v <= 1000:
            return ("pct", v)
    elif m := re.fullmatch(r"(\d+)(?:px)?", s):
        v = int(m[1])
        if 8 <= v <= 30000:
            return ("max", v)
    elif m := re.fullmatch(r"(\d+)(?:px)?x(\d+)(?:px)?", s):
        w, h = int(m[1]), int(m[2])
        if 8 <= w <= 30000 and 8 <= h <= 30000:
            return ("box", w, h)
    raise ConversionError(
        f'"{spec}" isn\'t a size I understand.\n'
        'Use a percentage (50%), a longest side in pixels (1600), or a box (1920x1080).')


def resize_tag(parsed) -> str:
    if parsed[0] == "pct":
        return f"{parsed[1]:g}%"
    if parsed[0] == "max":
        return f"{parsed[1]}px"
    return f"{parsed[1]}x{parsed[2]}"


def _new_size(w, h, parsed):
    if parsed[0] == "pct":
        f = parsed[1] / 100
    elif parsed[0] == "max":
        f = min(1.0, parsed[1] / max(w, h))
    else:
        f = min(1.0, parsed[1] / w, parsed[2] / h)
    return max(1, round(w * f)), max(1, round(h * f))


RESIZE_SAVE_AS = {"heic": "jpg", "jfif": "jpg", "jpeg": "jpg", "jpe": "jpg", "tif": "tiff"}


def resize_output(src: Path, spec: str) -> Path:
    from .formats import canon
    from .util import unique_path
    parsed = parse_resize(spec)
    ext = canon(src.suffix)
    ext = RESIZE_SAVE_AS.get(ext, ext)      # iPhone HEIC comes back as JPG
    return unique_path(src.with_name(f"{src.stem} ({resize_tag(parsed)}).{ext}"))


def _for_resize(im):
    # Resampling needs a "real" color mode (palette images can't be smoothed).
    if _has_alpha(im):
        return im.convert("RGBA")
    if im.mode in ("L", "RGB", "I;16", "I", "F"):
        return im if im.mode in ("L", "RGB") else _prepare(im, "jpg")
    return im.convert("RGB")


def resize(src: Path, dst: Path, spec: str, progress=None, cancel=None) -> Path:
    _register_heif()
    parsed = parse_resize(spec)
    target = dst.suffix.lower().lstrip(".")
    try:
        im = Image.open(src)
    except Exception as e:
        raise ConversionError(f"Couldn't open this image ({e}).") from e

    with im:
        upright = ImageOps.exif_transpose(im) if getattr(im, "n_frames", 1) == 1 else im
        w, h = upright.size
        nw, nh = _new_size(w, h, parsed)
        if (nw, nh) == (w, h):
            raise ConversionError(
                f"This image is already {w}×{h}, which fits within {resize_tag(parsed)}.\n"
                "Nothing to do (images are never enlarged by the max-size presets).")
        frames = getattr(im, "n_frames", 1)
        icc = im.info.get("icc_profile")

        with atomic_output(dst) as tmp:
            if frames > 1 and target in ("gif", "webp"):       # keep animation
                out, durations = [], []
                for i in range(frames):
                    if cancel is not None and cancel.is_set():
                        from .util import Cancelled
                        raise Cancelled()
                    im.seek(i)
                    out.append(im.convert("RGBA").resize((nw, nh), Image.LANCZOS))
                    durations.append(im.info.get("duration", 100))
                    if progress:
                        progress((i + 1) / frames)
                opts = dict(save_all=True, append_images=out[1:], duration=durations,
                            loop=im.info.get("loop", 0))
                if target == "gif":
                    opts["disposal"] = 2
                else:
                    opts["quality"] = 90
                out[0].save(tmp, PIL_FORMAT[target], **opts)
                return dst

            exif = upright.info.get("exif")
            small = _for_resize(upright).resize((nw, nh), Image.LANCZOS)
            dpi = _dpi(im)
            _save_still(_prepare(small, target), tmp, target, icc, exif, dpi)
    return dst
