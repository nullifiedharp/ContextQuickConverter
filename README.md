# QuickConvert

Right-click a file in Windows Explorer → **Convert to**, **Resize image** or
**Compress video** → pick an option. The new copy appears next to the original (the original is never touched,
and nothing is ever overwritten: `photo.png` becomes `photo (1).png` if taken).
Everything runs locally; no uploads.

| Right-click a…  | Convert to |
|---|---|
| **Image** jpg, jpeg, png, webp, bmp, gif, tif/tiff, ico, heic/heif, avif | JPG, PNG, WebP, BMP, GIF, TIFF, ICO, AVIF, PDF (animated GIF also → MP4/WebM) |
| **Video** mp4, mkv, mov, avi, webm, wmv, flv, m4v, mpg, ts, 3gp | MP4, MKV, MOV, WebM, AVI, animated GIF, MP3/M4A (audio only) |
| **Audio** mp3, wav, flac, m4a, aac, ogg, opus, wma | MP3, WAV, FLAC, M4A, OGG, Opus |
| **Word** doc, docx, odt, rtf | PDF, DOCX, ODT, RTF, TXT |
| **Spreadsheet** xls, xlsx, ods, csv | PDF, XLSX, ODS, CSV |
| **Slides** ppt, pptx, odp | PDF, PPTX, ODP |
| **PDF** | PNG / JPG (one image per page), TXT |

**Resize image** (all image types except .ico): 25% · 50% · 75% · Max 3840 / 1920 /
1280 / 800 px · Custom… (type `40%`, `1600` for longest side, or `1920x1080` to fit a box).
Keeps the format, quality, colour profile, EXIF and GIF/WebP animation; never enlarges
with the max-size presets. Saved as `photo (50%).jpg`. iPhone HEIC comes back as JPG.

**Compress video** (all video types, output MP4/H.264 that plays everywhere):
- *Smaller file – same quality* (CRF 24) · *Much smaller – 720p*
- *Under 10 MB (Discord)* · *Under 25 MB (email)* · *Under 50 MB* · *Custom size (MB)…*
  — size targets use two-pass encoding and automatically drop the resolution
  (1080p → 720p → 480p) when the budget is tight, so it still looks decent.
  Tested: a 30 s 1080p clip to "5 MB" came out at 4.6 MB.
- Saved as `clip (10MB).mp4`. Portrait phone videos are handled correctly.
- The Custom… boxes remember your last value, so selecting 20 files and typing it
  once then hitting Enter on the rest is quick.

Nice details:
- **MKV → MP4 is instant** when the video is already H.264/HEVC + AAC/MP3 — it
  repackages the streams instead of re-encoding. Otherwise it re-encodes (x264 CRF 20).
- Transparent PNG → JPG flattens onto white (not black). Phone photo rotation is baked in.
  Animated GIF ↔ animated WebP keeps the animation. Multi-page TIFF → multi-page PDF.
- Quick jobs show no window at all. Longer ones show a progress bar with Cancel;
  a cancelled/failed job leaves no half-written file.
- Select 20 videos and convert them all: they queue up (a few at a time) instead of
  hammering the CPU at once.
- Proper installer (Inno Setup): per-user with no admin prompt (or all users),
  Start menu entry, uninstall from **Settings → Apps**, upgrades in place.

## Build and install

Needs Python 3.10+ from python.org (with "Add python.exe to PATH" ticked).

1. Double-click **build.bat**. It:
   - creates a venv and installs the Python packages
   - runs the conversion tests
   - builds `QuickConvert.exe` with ffmpeg bundled
   - installs Inno Setup through winget if it's missing
   - produces **installer\QuickConvert-Setup-1.2.0.exe**
2. Run the setup. Each right-click menu is a checkbox (Convert to / Resize image /
   Compress video). Re-run it any time to turn one off or on; a newer setup
   upgrades in place.
3. Right-click a file. **Windows 11:** the classic menu is under
   **Show more options** (or **Shift + right-click**).

Document conversions use **Microsoft Office** if installed (best fidelity),
otherwise the free **LibreOffice**. Images, video, audio and PDF need nothing
extra — ffmpeg is bundled.

Already used the older "click Install inside QuickConvert.exe" version? Just run the
setup: it takes over the same folder and removes the old Settings → Apps entry.

The setup isn't code-signed, so the first time Windows SmartScreen may say
"Windows protected your PC" → **More info → Run anyway**.

**GitHub:** push the repo and `.github/workflows/build.yml` builds the setup on
GitHub's Windows servers (download it from the Actions run). Bump `APP_VERSION` in
`quickconvert/formats.py`, then push a matching tag like `v1.2.0` to publish it as a Release.

### Run from source (no exe)

```bat
pip install -r requirements.txt
python run.py install     REM menus point at pythonw + run.py
python run.py uninstall
```

## Command line

```
QuickConvert.exe                         setup window
QuickConvert.exe convert png "C:\a.jpg"  Convert to > PNG
QuickConvert.exe resize 50pct "a.jpg"    Resize (50pct, 1920px, 1920x1080, custom)
QuickConvert.exe compress 10 "a.mp4"     Compress (high, small, <MB>, custom)
QuickConvert.exe install   [--quiet]     portable self-install (no setup.exe)
QuickConvert.exe uninstall [--quiet]
QuickConvert.exe register   [--all-users] [--quiet]   just add menus for this exe
QuickConvert.exe unregister [--all-users] [--quiet]
```

## Code layout

```
run.py                        entry point
quickconvert/
  formats.py                  menu contents: formats + resize/compress presets  ← edit this
  engine.py                   routes (file, target) to a converter
  convert_image.py            Pillow (+ pillow-heif); convert + resize
  convert_media.py            bundled ffmpeg; convert, remux fast-path, compress/2-pass size targets
  convert_doc.py              Office via COM / LibreOffice headless / PyMuPDF for PDF
  shell_integration.py        registry: HKCU\Software\Classes\SystemFileAssociations\.<ext>\shell\QuickConvert
  ui.py                       progress popup + setup window (tkinter)
  util.py                     safe output naming, job queue (named semaphore)
tests/test_convert.py         every conversion, resize and compress option on sample files
installer/QuickConvert.iss    Inno Setup script (setup options, shortcuts, menu checkboxes)
tools/make_installer_menus.py writes installer/menus.iss (the registry entries) from formats.py
build.bat                     one-click build -> installer\QuickConvert-Setup-<version>.exe
```

**Adding a preset:** add a line to `RESIZE_PRESETS` / `COMPRESS_PRESETS` in
`formats.py`, bump `APP_VERSION`, run build.bat and the new setup.

**Adding a format:** add the extension to the right `*_IN` / `*_OUT` list in
`formats.py` (and a label), handle it in the converter if it needs special
options, then rebuild and run the new setup — the installer's menu entries are
generated from `formats.py`, so they always match.

## Notes

- Excel → CSV saves the first/active sheet only (that's what CSV can hold).
- Windows 11's new compact context menu only accepts apps packaged as signed
  MSIX with a COM shell extension; this uses the classic menu, which works on
  Windows 10 and 11 ("Show more options").
