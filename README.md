# QuickConvert

**Right-click file conversion for Windows.** Right-click a file in Explorer and
choose **Convert to**, **Resize image** or **Compress video**. The new copy appears
next to the original. Everything runs locally on your PC, with no uploads and no
online converters.

- The original file is never touched, and nothing is ever overwritten: if
  `photo.png` already exists, you get `photo (1).png`.
- Quick jobs finish without any window. Longer ones show a progress bar with
  **Cancel**, and a cancelled or failed job leaves no half-written file behind.

![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-lightgrey.svg)
![Version 1.2.0](https://img.shields.io/badge/version-1.2.0-green.svg)

---

## Features

### Convert to

| Right-click a… | Convert to |
|---|---|
| **Image**: jpg, jpeg, png, webp, bmp, gif, tif/tiff, ico, heic/heif, avif | JPG, PNG, WebP, BMP, GIF, TIFF, ICO, AVIF, PDF (animated GIF also → MP4 / WebM) |
| **Video**: mp4, mkv, mov, avi, webm, wmv, flv, m4v, mpg, ts, 3gp | MP4, MKV, MOV, WebM, AVI, animated GIF, MP3 / M4A (audio only) |
| **Audio**: mp3, wav, flac, m4a, aac, ogg, opus, wma | MP3, WAV, FLAC, M4A, OGG, Opus |
| **Word**: doc, docx, odt, rtf | PDF, DOCX, ODT, RTF, TXT |
| **Spreadsheet**: xls, xlsx, ods, csv | PDF, XLSX, ODS, CSV |
| **Slides**: ppt, pptx, odp | PDF, PPTX, ODP |
| **PDF** | PNG / JPG (one image per page), TXT |

- **MKV → MP4 takes seconds** when the video is already H.264/HEVC with AAC/MP3
  audio, because it repackages the streams instead of re-encoding. Otherwise it
  re-encodes with x264 at CRF 20.
- Transparent PNG → JPG flattens onto white, not black, and phone-photo rotation
  is applied.
- Animated GIF ↔ animated WebP keeps the animation, and a multi-page TIFF becomes
  a multi-page PDF.

### Resize image

Works on every image type except .ico. Presets: **25% · 50% · 75% · Max 3840 /
1920 / 1280 / 800 px · Custom…**

For a custom size, type `40%`, `1600` (longest side in pixels), or `1920x1080`
(fit inside a box).

- Keeps the original format, quality, colour profile, EXIF data and GIF/WebP
  animation.
- The max-size presets never enlarge an image.
- Saved as `photo (50%).jpg`. iPhone HEIC photos come back as JPG.

### Compress video

Works on every video type, and the output is an MP4 (H.264) that plays anywhere.

- **Smaller file – same quality** (CRF 24) · **Much smaller – 720p**
- **Under 10 MB (Discord)** · **Under 25 MB (email)** · **Under 50 MB** · **Custom size (MB)…**
  - Size targets use two-pass encoding and drop the resolution automatically
    (1080p → 720p → 480p) when the budget is tight, so the result still looks decent.
- Saved as `clip (10MB).mp4`. Portrait phone videos are scaled correctly.

### Batches

- Select many files and pick one option: heavy jobs queue up and run a few at a
  time instead of all at once.
- **Custom…** boxes remember your last value, so you only type it once per batch.

---

## Installing

Download `QuickConvert-Setup-<version>.exe` from the
[Releases](../../releases) page, or build it yourself (below), then run it.

- **Who it installs for:** your Windows user by default, with no admin prompt.
  The first screen also offers an all-users install.
- **Menus:** each right-click menu is a checkbox (Convert to, Resize image,
  Compress video). Re-run the setup any time to turn one on or off.
- **Upgrades:** a newer setup upgrades in place.
- **Uninstalling:** from **Settings → Apps → Installed apps**.
- **Windows 11:** the menus are under **Show more options** (or
  **Shift + right-click**).
- **SmartScreen:** the setup isn't code-signed, so Windows may say "Windows
  protected your PC" the first time. Click **More info → Run anyway**.

Document conversions use **Microsoft Office** if it's installed (best fidelity),
otherwise the free [LibreOffice](https://www.libreoffice.org). Images, video,
audio and PDF need nothing extra, because ffmpeg is bundled.

If you used an older version's **Install** button inside `QuickConvert.exe`,
just run the setup. It takes over the same folder and removes the old
Settings → Apps entry.

---

## Building from source

You need [Python 3.10+](https://www.python.org/downloads/) with
"Add python.exe to PATH" ticked.

Double-click **`build.bat`**. It:

1. creates a virtual environment and installs the Python packages,
2. runs the conversion tests,
3. builds `QuickConvert.exe` with ffmpeg bundled (PyInstaller),
4. installs [Inno Setup 6](https://jrsoftware.org/isinfo.php) through winget if
   it's missing,
5. produces **`installer\QuickConvert-Setup-<version>.exe`**.

**GitHub Actions:** `.github/workflows/build.yml` builds the setup on GitHub's
Windows servers for every push, and you can download it from the run's
artifacts. To publish a release, bump `APP_VERSION` in `quickconvert/formats.py`
and push a matching tag such as `v1.2.0`.

### Running from source (no exe)

```bat
pip install -r requirements.txt
python run.py register      REM adds menus that point at pythonw + run.py
python run.py unregister
```

### Tests

```bat
python tests\test_convert.py
```

This converts generated sample files to every offered format and runs every
resize and compress option, checking that each output opens and has the right
size or duration. Document tests run only if LibreOffice is installed.

---

## Command line

```
QuickConvert.exe                          status window
QuickConvert.exe convert png "C:\a.jpg"   Convert to > PNG
QuickConvert.exe resize 50pct "a.jpg"     Resize (50pct, 1920px, 1920x1080, custom)
QuickConvert.exe compress 10 "a.mp4"      Compress (high, small, <MB>, custom)
QuickConvert.exe register   [--all-users] [--quiet]   add the menus for this exe
QuickConvert.exe unregister [--all-users] [--quiet]   remove them
QuickConvert.exe install / uninstall [--quiet]        portable self-install (no setup.exe)
```

---

## Project layout

```
run.py                         entry point
quickconvert/
  formats.py                   menu contents: formats + resize/compress presets  <- edit this
  engine.py                    routes (file, option) to a converter
  convert_image.py             Pillow (+ pillow-heif): convert + resize
  convert_media.py             bundled ffmpeg: convert, fast remux, compress / two-pass size targets
  convert_doc.py               Microsoft Office (COM) / LibreOffice (headless) / PyMuPDF for PDF
  shell_integration.py         right-click menu registry entries (HKCU or HKLM)
  ui.py                        progress popup and status window (tkinter)
  util.py                      safe output naming, job queue
installer/QuickConvert.iss     Inno Setup script
tools/make_installer_menus.py  generates installer/menus.iss from formats.py
tests/test_convert.py          conversion / resize / compress tests
build.bat                      one-click build -> installer\QuickConvert-Setup-<version>.exe
```

- **Adding a format:** add the extension to the right `*_IN` / `*_OUT` list in
  `formats.py` (with a label), and handle it in the converter if it needs special
  options.
- **Adding a preset:** add a line to `RESIZE_PRESETS` / `COMPRESS_PRESETS`.

Either way, bump `APP_VERSION`, run `build.bat`, and run the new setup. The
installer's menu entries are generated from `formats.py`, so they always match
the app.

---

## Notes and limitations

- Excel → CSV saves only the active sheet, because that's all a CSV can hold.
- Password-protected PDFs can't be converted.
- Windows 11's compact right-click menu only accepts apps packaged as signed MSIX
  with a COM shell extension. QuickConvert uses the classic menu, which works on
  both Windows 10 and 11.

---

## License

Copyright (C) 2026 NullHarp

QuickConvert is free software: you can redistribute it and/or modify it under the
terms of the **GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.**

This program is distributed in the hope that it will be useful, but **WITHOUT ANY
WARRANTY**, without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the [GNU General Public License](LICENSE) for more
details.

In plain terms (this summary is not legal advice, and the [LICENSE](LICENSE) is
what actually applies):

- **You can** use, study, share and modify QuickConvert, including commercially.
- **If you distribute it** or anything built from it, modified or not, you must:
  - release the complete source code under the same GPLv3 license,
  - keep the copyright notices and credit intact,
  - mark what you changed.
- **Nobody can** take this code and turn it into a closed-source product.

### Third-party components

The built program bundles the following, each under its own license:

| Component | Used for | License |
|---|---|---|
| [FFmpeg](https://ffmpeg.org) (via [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)) | video and audio | GPL v3 build (includes x264 and other GPL components); the wrapper is BSD-2-Clause |
| [Pillow](https://python-pillow.org) | images | MIT-CMU (HPND) |
| [pillow-heif](https://github.com/bigcat88/pillow_heif) | HEIC/HEIF photos | BSD-3-Clause; bundles libheif and libde265 (LGPL v3) and x265 (GPL v2+) |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | PDF to images/text | GNU AGPL v3 (or Artifex commercial license) |
| [pywin32](https://github.com/mhammond/pywin32) | driving Microsoft Office | PSF-2.0 |
| [Python](https://www.python.org) and tkinter | runtime and UI | PSF-2.0 |
| [PyInstaller](https://pyinstaller.org) bootloader | packaging the .exe | GPL v2+ with a bootloader exception |

All of these are compatible with GPLv3. **PyMuPDF is AGPL v3**, which GPLv3
explicitly allows combining with (GPLv3 section 13). For a desktop app the only
practical effect is that anyone who modifies QuickConvert and offers it to users
**over a network** must also offer those users the source.

Microsoft Office and LibreOffice are **not** bundled. QuickConvert only uses them
if you already have one installed.
