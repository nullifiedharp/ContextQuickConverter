"""Adds/removes the Explorer right-click submenus ("Convert to",
"Resize image", "Compress video").

Everything is written under HKEY_CURRENT_USER, so no admin rights are needed
and it only affects the current Windows user.

Layout per extension (e.g. .jpg):
  HKCU\\Software\\Classes\\SystemFileAssociations\\.jpg\\shell\\QuickConvert
      MUIVerb     = "Convert to"
      SubCommands = ""                      <- makes it a cascading submenu
      Icon        = "<exe>,0"
      shell\\00_png      MUIVerb = "PNG"
          command  (default) = "<exe>" convert png "%1"
      shell\\01_webp ...
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .formats import (APP_NAME, APP_VERSION, COMPRESS_IN, COMPRESS_PRESETS,
                      RESIZE_IN, RESIZE_PRESETS, all_inputs, label, targets_for)
from .util import IS_WINDOWS, NO_WINDOW

VERB = APP_NAME
SFA = r"Software\Classes\SystemFileAssociations"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"


def install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / APP_NAME


def frozen() -> bool:
    return getattr(sys, "frozen", False)


def current_app_dir() -> Path:
    return Path(sys.executable).parent


def command_prefix(exe: Path | None = None) -> str:
    """How Explorer should launch us."""
    if frozen():
        return f'"{exe or sys.executable}"'
    # Running from source: use pythonw so no console window appears.
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    runner = Path(__file__).resolve().parent.parent / "run.py"
    return f'"{pyw if pyw.exists() else py}" "{runner}"'


def icon_value(exe: Path | None = None) -> str:
    if frozen():
        return f'{exe or sys.executable},0'
    ico = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    return str(ico)


def _menus():
    """(verb key, menu title, extensions, items(ext) -> [(key, label, cli args)])."""
    return [
        (VERB, "Convert to", all_inputs(),
         lambda ext: [(t, label(t, ext), f"convert {t}") for t in targets_for(ext)]),
        (VERB + "Resize", "Resize image", RESIZE_IN,
         lambda ext: [(_slug(a), lab, f"resize {a}") for a, lab in RESIZE_PRESETS]),
        (VERB + "Compress", "Compress video", COMPRESS_IN,
         lambda ext: [(_slug(a), lab, f"compress {a}") for a, lab in COMPRESS_PRESETS]),
    ]


def _slug(arg: str) -> str:
    return arg.replace("%", "pct").replace(" ", "")


def plan_registry(exe: Path | None = None):
    """List of (subkey, value_name, value) to write. Pure function, testable anywhere."""
    prefix = command_prefix(exe)
    icon = icon_value(exe)
    rows = []
    for verb, title, exts, items in _menus():
        for ext in exts:
            base = rf"{SFA}\.{ext}\shell\{verb}"
            rows += [(base, "MUIVerb", title),
                     (base, "SubCommands", ""),
                     (base, "Icon", icon)]
            # Explorer sorts submenu entries by key name, hence the 00_, 01_ prefix.
            for i, (key, lab, args) in enumerate(items(ext)):
                item = rf"{base}\shell\{i:02d}_{key}"
                rows.append((item, "MUIVerb", lab))
                rows.append((item + r"\command", "", f'{prefix} {args} "%1"'))
    return rows


# ------------------------------------------------------------ registry ops
def _delete_tree(root, path: str):
    import winreg
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    child = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(root, path + "\\" + child)
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass


def _notify_shell():
    import ctypes
    SHCNE_ASSOCCHANGED, SHCNF_IDLIST = 0x08000000, 0
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)


def register(exe: Path | None = None):
    import winreg
    HK = winreg.HKEY_CURRENT_USER
    unregister_menus()
    for key, name, value in plan_registry(exe):
        with winreg.CreateKeyEx(HK, key, 0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    _notify_shell()


def unregister_menus():
    import winreg
    for verb, _, exts, _ in _menus():
        for ext in exts:
            _delete_tree(winreg.HKEY_CURRENT_USER, rf"{SFA}\.{ext}\shell\{verb}")


def is_registered() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{SFA}\.jpg\shell\{VERB}"))
        return True
    except OSError:
        return False


def _write_uninstall_entry(exe: Path, folder: Path):
    import winreg
    size_kb = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) // 1024
    vals = {
        "DisplayName": APP_NAME, "DisplayVersion": APP_VERSION,
        "DisplayIcon": f'"{exe}",0', "InstallLocation": str(folder),
        "UninstallString": f'"{exe}" uninstall',
        "QuietUninstallString": f'"{exe}" uninstall --quiet',
        "Publisher": APP_NAME,
    }
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_WRITE) as k:
        for n, v in vals.items():
            winreg.SetValueEx(k, n, 0, winreg.REG_SZ, v)
        for n, v in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", size_kb)):
            winreg.SetValueEx(k, n, 0, winreg.REG_DWORD, v)


# -------------------------------------------------------- install/uninstall
def install() -> Path:
    """Copy the app to %LOCALAPPDATA%\\Programs\\QuickConvert (if running from
    a download folder) and register the menus. Returns the exe used."""
    if not frozen():
        register()
        return Path(sys.executable)

    src_dir, dest = current_app_dir(), install_dir()
    exe_name = Path(sys.executable).name
    if src_dir.resolve() != dest.resolve():
        if dest.exists():
            try:
                shutil.rmtree(dest)
            except PermissionError as e:
                raise RuntimeError(
                    "The installed copy is in use (a conversion may be running). "
                    "Wait for it to finish and try again.") from e
        shutil.copytree(src_dir, dest)
    exe = dest / exe_name
    register(exe)
    _write_uninstall_entry(exe, dest)
    return exe


def uninstall():
    import winreg
    unregister_menus()
    _delete_tree(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    _notify_shell()
    if not frozen() or not install_dir().exists():
        return
    if current_app_dir().resolve() != install_dir().resolve():
        shutil.rmtree(install_dir(), ignore_errors=True)
    else:
        # Can't delete our own folder while running: let cmd do it after we exit.
        folder = str(install_dir())
        subprocess.Popen(
            f'cmd /c ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{folder}"',
            creationflags=NO_WINDOW | 0x00000008,  # DETACHED_PROCESS
            cwd=os.environ.get("TEMP", "C:\\"),  # not inside the folder being deleted
            close_fds=True)
