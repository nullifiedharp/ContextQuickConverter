# QuickConvert - right-click file converter for Windows
# Copyright (C) 2026 NullHarp
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE
# file or <https://www.gnu.org/licenses/> for details.

"""Small Tk windows: a progress popup for conversions and the setup window."""
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from .formats import APP_NAME, APP_VERSION
from .util import Cancelled, ConversionError, IS_WINDOWS

SHOW_AFTER_MS = 700   # quick jobs (most images) finish without any window at all


def _dpi_aware():
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _set_icon(root):
    try:
        if getattr(sys, "frozen", False):
            root.iconbitmap(sys.executable)
        else:
            ico = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
            root.iconbitmap(str(ico))
    except Exception:
        pass


def show_error(msg: str, title: str = APP_NAME):
    _dpi_aware()
    root = tk.Tk()
    root.withdraw()
    _set_icon(root)
    messagebox.showerror(title, msg, parent=root)
    root.destroy()


def run_with_progress(src: Path, doing: str, failed: str, job):
    """job(progress_cb, cancel_event, on_wait) -> output path. Runs it on a
    worker thread; shows a progress window only if it takes a while."""
    _dpi_aware()
    cancel = threading.Event()
    state = {"frac": None, "status": doing,
             "done": False, "error": None, "result": None}

    def progress(frac):
        state["frac"] = frac

    def on_wait():
        state["status"] = "Waiting for other conversions to finish..."

    def worker():
        try:
            state["result"] = job(progress, cancel, on_wait)
        except Cancelled:
            pass
        except ConversionError as e:
            state["error"] = str(e)
        except Exception as e:  # unexpected: still tell the user something useful
            state["error"] = f"{type(e).__name__}: {e}"
        finally:
            state["done"] = True

    root = tk.Tk()
    root.withdraw()
    root.title(f"{APP_NAME} - {src.name}")
    root.resizable(False, False)
    _set_icon(root)

    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=src.name, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    status = ttk.Label(frm, text=state["status"])
    status.pack(anchor="w", pady=(4, 8))
    bar = ttk.Progressbar(frm, length=360, mode="indeterminate")
    bar.pack(fill="x")
    bar.start(12)
    row = ttk.Frame(frm)
    row.pack(fill="x", pady=(10, 0))
    pct = ttk.Label(row, text="")
    pct.pack(side="left")

    def do_cancel():
        cancel.set()
        status.config(text="Cancelling...")
    ttk.Button(row, text="Cancel", command=do_cancel).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", do_cancel)

    def show():
        if not state["done"]:
            root.update_idletasks()
            w, h = root.winfo_reqwidth(), root.winfo_reqheight()
            x = (root.winfo_screenwidth() - w) // 2
            y = (root.winfo_screenheight() - h) // 3
            root.geometry(f"+{x}+{y}")
            root.deiconify()
            root.attributes("-topmost", True)
            root.after(300, lambda: root.attributes("-topmost", False))

    def poll():
        if state["done"]:
            root.destroy()
            return
        if not cancel.is_set():
            status.config(text=state["status"])
        f = state["frac"]
        if f is not None:
            if str(bar["mode"]) != "determinate":
                bar.stop()
                bar.config(mode="determinate", maximum=1000)
            bar["value"] = f * 1000
            pct.config(text=f"{f * 100:.0f}%")
        root.after(100, poll)

    threading.Thread(target=worker, daemon=True).start()
    root.after(SHOW_AFTER_MS, show)
    root.after(50, poll)
    root.mainloop()

    if state["error"]:
        show_error(f"{failed}\n\n{state['error']}")
        return None
    return state["result"]


def ask_value(title: str, prompt: str, initial: str = "") -> str | None:
    """Small input box for the "Custom..." menu items. None if cancelled."""
    from tkinter import simpledialog
    _dpi_aware()
    root = tk.Tk()
    root.withdraw()
    _set_icon(root)
    root.attributes("-topmost", True)
    val = simpledialog.askstring(title, prompt, initialvalue=initial, parent=root)
    root.destroy()
    return val.strip() if val and val.strip() else None


# ------------------------------------------------------------------ setup
def setup_window():
    from . import shell_integration as si
    from .convert_doc import backends_available

    _dpi_aware()
    root = tk.Tk()
    root.title(f"{APP_NAME} {APP_VERSION}")
    root.resizable(False, False)
    _set_icon(root)
    frm = ttk.Frame(root, padding=20)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=APP_NAME, font=("Segoe UI", 16, "bold")).pack(anchor="w")
    ttk.Label(frm, text='Adds "Convert to", "Resize image" and "Compress video"\n'
                        "when you right-click images, videos, audio and documents.",
              justify="left").pack(anchor="w", pady=(2, 12))

    status = ttk.Label(frm, font=("Segoe UI", 10, "bold"))
    status.pack(anchor="w")

    b = backends_available()
    if b["office"] and b["libreoffice"]:
        docs = "Documents: Microsoft Office and LibreOffice found"
    elif b["office"]:
        docs = "Documents: using Microsoft Office"
    elif b["libreoffice"]:
        docs = "Documents: using LibreOffice"
    else:
        docs = ("Documents: install Microsoft Office or the free LibreOffice\n"
                "to convert Word/Excel/PowerPoint files (images, video,\n"
                "audio and PDF work without it).")
    ttk.Label(frm, text=docs, justify="left", foreground="#555").pack(anchor="w", pady=(6, 0))
    ttk.Label(frm, text='Windows 11: it appears under "Show more options"\n(or Shift + right-click).',
              justify="left", foreground="#555").pack(anchor="w", pady=(6, 14))

    ttk.Label(frm, foreground="#777", justify="left", font=("Segoe UI", 8),
              text=(f"{APP_NAME} {APP_VERSION}  -  Copyright (C) 2026 NullHarp\n"
                    "Free software under the GNU GPL v3 or later, with NO WARRANTY.\n"
                    "You may share and change it under the license's terms (see LICENSE.txt)."),
              ).pack(anchor="w", pady=(0, 12))

    btns = ttk.Frame(frm)
    btns.pack(fill="x")
    install_btn = ttk.Button(btns)
    uninstall_btn = ttk.Button(btns, text="Uninstall")

    def refresh():
        on = si.is_registered()
        status.config(text="Installed - right-click a file to try it." if on else "Not installed yet.",
                      foreground="#1a7f37" if on else "#9a6700")
        install_btn.config(text="Reinstall / Update" if on else "Install")
        uninstall_btn.state(["!disabled"] if on else ["disabled"])

    def do_install():
        try:
            si.install()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Install failed:\n{e}", parent=root)
        refresh()

    def do_uninstall():
        try:
            si.uninstall()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Uninstall failed:\n{e}", parent=root)
        refresh()

    ttk.Button(btns, text="Close", command=root.destroy).pack(side="right")

    if si.setup_scope():
        # Installed by QuickConvert-Setup.exe: Setup owns the menus and uninstall.
        on = si.is_registered()
        status.config(text="Installed - right-click a file to try it." if on else
                      "The right-click menus are turned off.",
                      foreground="#1a7f37" if on else "#9a6700")
        ttk.Label(frm, foreground="#555", justify="left",
                  text=("To change which menus appear, run the Setup again.\n"
                        "To remove QuickConvert: Settings > Apps > Installed apps.")
                  ).pack(anchor="w", pady=(10, 0), before=btns)
    else:
        install_btn.config(command=do_install)
        uninstall_btn.config(command=do_uninstall)
        install_btn.pack(side="left")
        uninstall_btn.pack(side="left", padx=(8, 0))
        refresh()
    root.mainloop()
