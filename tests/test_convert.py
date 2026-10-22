"""Round-trip tests for the conversion engine (runs on Windows, Linux or macOS).

    python -m pytest tests -q          (or just: python tests/test_convert.py)

Document tests are skipped unless LibreOffice/Office is available.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from quickconvert import engine  # noqa: E402
from quickconvert.convert_doc import backends_available  # noqa: E402
from quickconvert.convert_media import ffmpeg_exe, probe  # noqa: E402
from quickconvert.formats import targets_for  # noqa: E402
from quickconvert.util import NO_WINDOW  # noqa: E402


def make_samples(d: Path) -> dict:
    s = {}
    im = Image.new("RGBA", (301, 201), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse((20, 20, 280, 180), fill=(220, 60, 40, 255))
    s["png"] = d / "alpha.png"
    im.save(s["png"])
    s["jpg"] = d / "photo.jpg"
    im.convert("RGB").save(s["jpg"], quality=90)
    frames = [Image.new("RGB", (120, 80), c) for c in ("red", "green", "blue")]
    s["gif"] = d / "anim.gif"
    frames[0].save(s["gif"], save_all=True, append_images=frames[1:], duration=200, loop=0)

    ff = ffmpeg_exe()
    s["mkv"] = d / "clip.mkv"   # H.264 + AAC in MKV -> exercises the fast remux path
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=321x241:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
                    "-c:v", "libx264", "-c:a", "aac", str(s["mkv"])], check=True, creationflags=NO_WINDOW)
    s["wav"] = d / "tone.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "2", str(s["wav"])], check=True, creationflags=NO_WINDOW)
    s["pdf"] = d / "two-pages.pdf"
    pages = [Image.new("RGB", (400, 500), c) for c in ("white", "lightblue")]
    pages[0].save(s["pdf"], save_all=True, append_images=pages[1:])
    return s


def check_all(sample: Path, results: list):
    for t in targets_for(sample.suffix):
        try:
            out = engine.convert(sample, t)
            assert out.exists(), "no output"
            if out.is_file():
                assert out.stat().st_size > 0, "empty output"
                if t in ("mp4", "mkv", "mov", "webm", "avi", "mp3", "m4a", "wav", "flac", "ogg", "opus"):
                    info = probe(out)
                    min_d = 0.4 if sample.suffix == ".gif" else 1.5
                    assert info.duration > min_d, f"duration {info.duration}"
                elif t in ("jpg", "png", "webp", "bmp", "gif", "tiff", "ico", "avif"):
                    with Image.open(out) as im:
                        im.load()
            results.append((sample.name, t, "ok", out.name))
        except Exception as e:
            results.append((sample.name, t, "FAIL", f"{type(e).__name__}: {e}"))


def check_ops(d: Path, samples: dict, results: list):
    """Resize image / Compress video menus."""
    def run(name, op, arg, src, verify):
        try:
            fn, _ = engine.plan_op(op, arg, src)
            out = fn(None, None)
            verify(out)
            results.append((src.name, f"{op} {arg}", "ok", out.name))
        except Exception as e:
            results.append((src.name, f"{op} {arg}", "FAIL", f"{type(e).__name__}: {e}"))

    def dims(expect, frames=None):
        def v(out):
            with Image.open(out) as im:
                assert im.size == expect, f"{im.size} != {expect}"
                if frames:
                    assert im.n_frames == frames, f"{im.n_frames} frames"
        return v

    run("jpg", "resize", "50pct", samples["jpg"], dims((150, 100)))     # 301x201
    run("png", "resize", "200px", samples["png"], dims((200, 134)))
    run("png", "resize", "100x50", samples["png"], dims((75, 50)))
    run("gif", "resize", "50pct", samples["gif"], dims((60, 40), frames=3))

    # "already small enough" must be a friendly error, not an upscale
    try:
        engine.plan_op("resize", "4000px", samples["jpg"])[0](None, None)
        results.append(("photo.jpg", "resize 4000px", "FAIL", "should have refused"))
    except Exception as e:
        ok = "already" in str(e)
        results.append(("photo.jpg", "resize 4000px", "ok" if ok else "FAIL", str(e)[:60]))

    big = d / "big.mp4"   # ~1080p, noisy so it compresses like real footage
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=1920x1080:rate=30,noise=alls=20:allf=t", "-f", "lavfi",
                    "-i", "sine=frequency=330", "-t", "6", "-c:v", "libx264", "-preset",
                    "ultrafast", "-crf", "26", "-c:a", "aac", str(big)],
                   check=True, creationflags=NO_WINDOW)
    src_mb = big.stat().st_size / 1e6

    def smaller(out):
        assert out.stat().st_size < big.stat().st_size, "not smaller"

    def under(mb):
        def v(out):
            got = out.stat().st_size / 1e6
            assert got <= mb, f"{got:.2f} MB > {mb} MB"
            assert probe(out).duration > 5.5
        return v

    def short_side(px):
        def v(out):
            r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(out)],
                               capture_output=True, text=True, creationflags=NO_WINDOW)
            import re
            w, h = map(int, re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", r.stderr).groups())
            assert min(w, h) == px, f"{w}x{h}"
        return v

    run("mp4", "compress", "high", big, smaller)
    run("mp4", "compress", "small", big, lambda o: (smaller(o), short_side(720)(o)))
    target = round(src_mb / 4, 1)
    run("mp4", "compress", str(target), big, under(target))


def make_docs(d: Path) -> dict:
    """Create .docx/.xlsx/.pptx via LibreOffice from simple sources."""
    from quickconvert.util import find_soffice, run_quiet
    so = find_soffice()
    txt = d / "letter.txt"
    txt.write_text("Hello from QuickConvert.\nSecond line.\n", encoding="utf-8")
    csv = d / "table.csv"
    csv.write_text("name,qty\nbolt,4\nnut,8\n", encoding="utf-8")
    out = {}
    run_quiet([so, "--headless", "--convert-to", "docx:MS Word 2007 XML", "--outdir", str(d), str(txt)])
    out["docx"] = d / "letter.docx"
    out["csv"] = csv
    return out


def main():
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        samples = make_samples(d)
        for s in samples.values():
            check_all(s, results)
        if backends_available()["libreoffice"]:   # samples are generated with LibreOffice
            docs = make_docs(d)
            check_all(docs["docx"], results)
            check_all(docs["csv"], results)
            # and a generated .xlsx -> everything
            xlsx = d / "table.xlsx"
            if xlsx.exists():
                check_all(xlsx, results)
        else:
            print("(skipping document tests: no Office/LibreOffice)")
        check_ops(d, samples, results)
        # never-overwrite check
        a = engine.convert(samples["jpg"], "png")
        assert a.name == "photo (1).png", a.name
    fails = [r for r in results if r[2] != "ok"]
    for r in results:
        print(f"{r[2]:4}  {r[0]:16} -> {r[1]:5}  {r[3]}")
    print(f"\n{len(results) - len(fails)}/{len(results)} conversions passed")
    return 1 if fails else 0


def test_all():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
