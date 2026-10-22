# QuickConvert

For compiled versions, please see [Releases](https://github.com/nullifiedharp/ContextQuickConverter/tree/main/Releases)

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
- Installs per-user (no admin), shows up in **Settings → Apps** for uninstalling.

## Install (using the built exe)

1. Unzip `QuickConvert-win64.zip` anywhere.
2. Run `QuickConvert.exe` → **Install**. It copies itself to
   `%LOCALAPPDATA%\Programs\QuickConvert` and adds the menus. You can delete the
   unzipped folder afterwards.
3. Right-click a file. **Windows 11:** the classic menu is under
   **Show more options** (or **Shift + right-click**).

Document conversions use **Microsoft Office** if installed (best fidelity),
otherwise the free **LibreOffice**. Images, video, audio and PDF need nothing
extra — ffmpeg is bundled.

## Build the exe yourself

Needs Python 3.10+ from python.org (with "Add to PATH" ticked). On Windows:

```bat
build.bat
```

That creates a venv, installs requirements, runs the tests, and produces
`dist\QuickConvert\QuickConvert.exe` plus `dist\QuickConvert-win64.zip`.

Or push the repo to GitHub — `.github/workflows/build.yml` builds the zip on
GitHub's Windows runners (download it from the Actions run; tag `v1.0.0` to
publish a Release).

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
QuickConvert.exe install   [--quiet]
QuickConvert.exe uninstall [--quiet]
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
```

**Adding a preset:** add a line to `RESIZE_PRESETS` / `COMPRESS_PRESETS` in
`formats.py`, then Reinstall / Update.

**Adding a format:** add the extension to the right `*_IN` / `*_OUT` list in
`formats.py` (and a label), handle it in the converter if it needs special
options, then run `QuickConvert.exe` → **Reinstall / Update** so the menus refresh.

## Notes

- Excel → CSV saves the first/active sheet only (that's what CSV can hold).
- Windows 11's new compact context menu only accepts apps packaged as signed
  MSIX with a COM shell extension; this uses the classic menu, which works on
  Windows 10 and 11 ("Show more options").
