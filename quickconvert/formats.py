"""Which file types get a "Convert to" menu, and what each can become."""

APP_NAME = "QuickConvert"
APP_VERSION = "1.1.0"

# Extensions that are just aliases of another one (so .jpeg doesn't offer "JPG").
CANONICAL = {"jpeg": "jpg", "jfif": "jpg", "jpe": "jpg", "tif": "tiff",
             "heif": "heic", "mpeg": "mpg", "htm": "html"}

# ---- inputs -----------------------------------------------------------------
IMAGE_IN = ["jpg", "jpeg", "jfif", "png", "webp", "bmp", "gif", "tif", "tiff",
            "ico", "heic", "heif", "avif"]
VIDEO_IN = ["mp4", "mkv", "mov", "avi", "webm", "wmv", "flv", "m4v", "mpg",
            "mpeg", "ts", "3gp"]
AUDIO_IN = ["mp3", "wav", "flac", "m4a", "aac", "ogg", "opus", "wma"]
WORD_IN = ["doc", "docx", "odt", "rtf"]
SHEET_IN = ["xls", "xlsx", "ods", "csv"]
SLIDE_IN = ["ppt", "pptx", "odp"]
PDF_IN = ["pdf"]

# ---- outputs ----------------------------------------------------------------
IMAGE_OUT = ["jpg", "png", "webp", "bmp", "gif", "tiff", "ico", "avif", "pdf"]
VIDEO_OUT = ["mp4", "mkv", "mov", "webm", "avi", "gif", "mp3", "m4a"]
AUDIO_OUT = ["mp3", "wav", "flac", "m4a", "ogg", "opus"]
WORD_OUT = ["pdf", "docx", "odt", "rtf", "txt"]
SHEET_OUT = ["pdf", "xlsx", "ods", "csv"]
SLIDE_OUT = ["pdf", "pptx", "odp"]
PDF_OUT = ["png", "jpg", "txt"]

LABELS = {
    "jpg": "JPG", "png": "PNG", "webp": "WebP", "bmp": "BMP", "tiff": "TIFF",
    "ico": "ICO (icon)", "avif": "AVIF", "pdf": "PDF",
    "mp4": "MP4", "mkv": "MKV", "mov": "MOV", "webm": "WebM", "avi": "AVI",
    "mp3": "MP3", "m4a": "M4A (AAC)", "wav": "WAV", "flac": "FLAC",
    "ogg": "OGG (Vorbis)", "opus": "Opus",
    "docx": "DOCX (Word)", "odt": "ODT", "rtf": "RTF", "txt": "TXT (plain text)",
    "xlsx": "XLSX (Excel)", "ods": "ODS", "csv": "CSV",
    "pptx": "PPTX (PowerPoint)", "odp": "ODP",
}


def canon(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    return CANONICAL.get(ext, ext)


def category(ext: str) -> str | None:
    ext = ext.lower().lstrip(".")
    for name, group in (("image", IMAGE_IN), ("video", VIDEO_IN),
                        ("audio", AUDIO_IN), ("word", WORD_IN),
                        ("sheet", SHEET_IN), ("slide", SLIDE_IN), ("pdf", PDF_IN)):
        if ext in group:
            return name
    return None


def targets_for(ext: str) -> list[str]:
    """Output formats offered in the menu for a given input extension."""
    cat = category(ext)
    if cat is None:
        return []
    outs = {
        "image": IMAGE_OUT, "video": VIDEO_OUT, "audio": AUDIO_OUT,
        "word": WORD_OUT, "sheet": SHEET_OUT, "slide": SLIDE_OUT, "pdf": PDF_OUT,
    }[cat]
    outs = list(outs)
    if canon(ext) == "gif":            # animated GIF -> video
        outs += ["mp4", "webm"]
    return [t for t in outs if t != canon(ext)]


def label(target: str, src_ext: str = "") -> str:
    cat = category(src_ext) if src_ext else None
    if cat == "video" and target in ("mp3", "m4a"):
        return f"{LABELS[target]} - audio only"
    if cat == "video" and target == "gif":
        return "GIF (animated)"
    if cat == "image" and target in ("mp4", "webm"):
        return f"{LABELS[target]} (video)"
    if cat == "pdf" and target in ("png", "jpg"):
        return f"{LABELS[target]} (one image per page)"
    if target == "gif":
        return "GIF"
    return LABELS.get(target, target.upper())


def all_inputs() -> list[str]:
    return IMAGE_IN + VIDEO_IN + AUDIO_IN + WORD_IN + SHEET_IN + SLIDE_IN + PDF_IN


# ---- extra right-click menus ----------------------------------------------
# (argument passed on the command line, menu label). "custom" asks for a value.
# "pct" not "%" because Explorer treats % in commands as a placeholder.
RESIZE_IN = [e for e in IMAGE_IN if e != "ico"]
RESIZE_PRESETS = [
    ("25pct", "25%"), ("50pct", "50%"), ("75pct", "75%"),
    ("3840px", "Max 3840 px (4K)"), ("1920px", "Max 1920 px (Full HD)"),
    ("1280px", "Max 1280 px"), ("800px", "Max 800 px (web/email)"),
    ("custom", "Custom size..."),
]

COMPRESS_IN = list(VIDEO_IN)
COMPRESS_PRESETS = [
    ("high", "Smaller file - same quality"),
    ("small", "Much smaller - 720p"),
    ("10", "Under 10 MB (Discord)"),
    ("25", "Under 25 MB (email)"),
    ("50", "Under 50 MB"),
    ("custom", "Custom size (MB)..."),
]
