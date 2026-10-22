import os
import sys
import shutil
import subprocess
import contextlib
import time
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
# Stops a console window flashing up for every ffmpeg/soffice call.
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


class ConversionError(Exception):
    """An error with a message that is safe to show the user as-is."""


class Cancelled(Exception):
    pass


def unique_path(p: Path) -> Path:
    """'photo.png' -> 'photo (1).png' if taken. Never overwrites anything."""
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    i = 1
    while True:
        cand = p.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand
        i += 1


@contextlib.contextmanager
def atomic_output(dst: Path):
    """Yield a temp path next to dst; move it into place only on success,
    so a failed/cancelled conversion never leaves a half-written file."""
    tmp = dst.with_name(f".~{dst.stem}.qc-tmp{dst.suffix}")
    try:
        yield tmp
        if not tmp.exists():
            raise ConversionError("The converter finished but produced no file.")
        os.replace(tmp, dst)
    finally:
        with contextlib.suppress(OSError):
            if tmp.exists():
                tmp.unlink()


def run_quiet(args, **kw):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          creationflags=NO_WINDOW, **kw)


def find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("soffice.exe")
    if found:
        return found
    if IS_WINDOWS:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            cand = Path(base) / "LibreOffice" / "program" / "soffice.exe"
            if cand.exists():
                return str(cand)
    return None


def office_app_installed(prog_id: str) -> bool:
    """True if e.g. 'Word.Application' is registered (Microsoft Office)."""
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id + r"\CLSID"))
        return True
    except OSError:
        return False


class JobSlot:
    """Limits how many heavy conversions (video, Office) run at once.

    Selecting 15 videos and choosing "Convert to MP4" makes Explorer start 15
    copies of this program; a system-wide semaphore makes them take turns.
    """

    def __init__(self, cancel_event=None, on_wait=None):
        self.cancel_event = cancel_event
        self.on_wait = on_wait
        self.handle = None

    def __enter__(self):
        if not IS_WINDOWS:
            return self
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.CreateSemaphoreW.restype = ctypes.c_void_p
        slots = max(1, min(3, (os.cpu_count() or 4) // 4))
        self.handle = k32.CreateSemaphoreW(None, slots, slots, "Local\\QuickConvertJobs")
        if not self.handle:
            return self
        WAIT_OBJECT_0, told = 0, False
        while True:
            r = k32.WaitForSingleObject(ctypes.c_void_p(self.handle), 250)
            if r == WAIT_OBJECT_0:
                return self
            if not told and self.on_wait:
                self.on_wait()
                told = True
            if self.cancel_event is not None and self.cancel_event.is_set():
                k32.CloseHandle(ctypes.c_void_p(self.handle))
                self.handle = None
                raise Cancelled()
            time.sleep(0.05)

    def __exit__(self, *exc):
        if self.handle:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.ReleaseSemaphore(ctypes.c_void_p(self.handle), 1, None)
            k32.CloseHandle(ctypes.c_void_p(self.handle))
        return False
