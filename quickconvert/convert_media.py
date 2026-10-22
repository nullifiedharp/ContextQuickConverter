"""Video/audio conversions via a bundled ffmpeg (from the imageio-ffmpeg package)."""
import os
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .util import ConversionError, Cancelled, NO_WINDOW, atomic_output, run_quiet

COPY_OK_VIDEO = {"h264", "hevc"}
COPY_OK_AUDIO = {"aac", "mp3"}
EVEN = "scale=trunc(iw/2)*2:trunc(ih/2)*2"   # x264/vp9 need even dimensions


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise ConversionError(f"ffmpeg wasn't found ({e}).") from e


@dataclass
class MediaInfo:
    duration: float = 0.0
    video: list = field(default_factory=list)
    audio: list = field(default_factory=list)


def probe(src: Path) -> MediaInfo:
    r = run_quiet([ffmpeg_exe(), "-hide_banner", "-i", str(src)])
    info = MediaInfo()
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if m:
        h, mi, s = m.groups()
        info.duration = int(h) * 3600 + int(mi) * 60 + float(s)
    for line in r.stderr.splitlines():
        sm = re.search(r"Stream #\d+:\d+.*?: (Video|Audio): (\w+)", line)
        if not sm:
            continue
        kind, codec = sm.groups()
        if kind == "Video" and "attached pic" not in line:   # skip MP3 cover art
            info.video.append(codec)
        elif kind == "Audio":
            info.audio.append(codec)
    if not info.video and not info.audio:
        raise ConversionError("ffmpeg couldn't read any audio or video in this file.")
    return info


def _encode_args(target: str, info: MediaInfo) -> list[str]:
    if target in ("mp4", "mov", "mkv"):
        a = ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-vf", EVEN, "-c:a", "aac", "-b:a", "192k"]
        if target != "mkv":
            a += ["-movflags", "+faststart"]
        return a
    if target == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1",
                "-deadline", "good", "-cpu-used", "4", "-pix_fmt", "yuv420p",
                "-vf", EVEN, "-c:a", "libopus", "-b:a", "128k"]
    if target == "avi":
        return ["-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "3", "-vf", EVEN,
                "-c:a", "libmp3lame", "-q:a", "3"]
    if target == "gif":
        return ["-an", "-filter_complex",
                "fps=15,scale='min(720,iw)':-2:flags=lanczos,split[a][b];"
                "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                "-loop", "0"]
    audio = {
        "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
        "m4a": ["-c:a", "aac", "-b:a", "192k"],
        "wav": ["-c:a", "pcm_s16le"],
        "flac": ["-c:a", "flac"],
        "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
        "opus": ["-c:a", "libopus", "-b:a", "128k"],
    }
    if target in audio:
        if not info.audio:
            raise ConversionError("This file has no audio track to convert.")
        return ["-vn"] + audio[target]
    raise ConversionError(f"Don't know how to make {target.upper()}.")


def _copy_args(target: str, info: MediaInfo) -> list[str] | None:
    """Container-only change (e.g. MKV -> MP4 holding H.264/AAC): just copy the
    streams. Takes seconds instead of minutes and loses no quality."""
    if target not in ("mp4", "mov", "mkv") or not info.video:
        return None
    if not set(info.video) <= COPY_OK_VIDEO or not set(info.audio) <= COPY_OK_AUDIO:
        return None
    a = ["-map", "0:v:0", "-map", "0:a?", "-c", "copy"]
    if target != "mkv":
        a += ["-movflags", "+faststart"]
        if "hevc" in info.video:
            a += ["-tag:v", "hvc1"]   # so Windows/Apple players recognise HEVC
    return a


def _run(src: Path, out: Path, args: list[str], duration: float, progress, cancel):
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", "-i", str(src), *args,
           "-progress", "pipe:1", "-nostats", "-loglevel", "error", str(out)]
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=NO_WINDOW)

        def watch_cancel():
            if cancel is None:
                return
            while proc.poll() is None:
                if cancel.wait(0.2):
                    proc.kill()
                    return
        threading.Thread(target=watch_cancel, daemon=True).start()

        for line in proc.stdout:
            if line.startswith("out_time_us=") and duration > 0 and progress:
                try:
                    t = int(line.split("=", 1)[1]) / 1e6
                    progress(min(max(t / duration, 0.0), 1.0))
                except ValueError:
                    pass
        proc.wait()
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if proc.returncode != 0:
            err.seek(0)
            msg = err.read().strip().splitlines()
            raise ConversionError("ffmpeg failed:\n" + "\n".join(msg[-6:]))


def convert(src: Path, dst: Path, target: str, progress=None, cancel=None) -> Path:
    info = probe(src)
    with atomic_output(dst) as tmp:
        copy = _copy_args(target, info)
        if copy:
            try:
                _run(src, tmp, copy, info.duration, progress, cancel)
                return dst
            except ConversionError:
                if tmp.exists():
                    os.remove(tmp)    # fall through to a real re-encode
        _run(src, tmp, _encode_args(target, info), info.duration, progress, cancel)
    return dst


# ---------------------------------------------------------------- compress
def _cap_short_side(px: int) -> str:
    """Scale so the shorter side is at most px (works for portrait phone video
    too), never upscale, keep dimensions even."""
    f = f"min(1,{px}/min(iw,ih))"
    return f"scale=w='trunc({f}*iw/2)*2':h='trunc({f}*ih/2)*2'"


def parse_size_mb(spec: str) -> float:
    s = spec.strip().lower().replace(" ", "").rstrip("b").rstrip("m")
    try:
        v = float(s)
    except ValueError:
        raise ConversionError(f'"{spec}" isn\'t a size in MB (try 8 or 25).') from None
    if not 0.5 <= v <= 100000:
        raise ConversionError("Pick a target size between 0.5 MB and 100 GB.")
    return v


def compress_tag(preset: str) -> str:
    if preset == "high":
        return "compressed"
    if preset == "small":
        return "720p"
    return f"{parse_size_mb(preset):g}MB"


def compress_output(src: Path, preset: str) -> Path:
    from .util import unique_path
    return unique_path(src.with_name(f"{src.stem} ({compress_tag(preset)}).mp4"))


def compress(src: Path, dst: Path, preset: str, progress=None, cancel=None) -> Path:
    info = probe(src)
    if not info.video:
        raise ConversionError("This file has no video track.")
    audio = ["-c:a", "aac", "-b:a", "128k"] if info.audio else ["-an"]
    tail = ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]

    with atomic_output(dst) as tmp:
        if preset in ("high", "small"):
            crf, vf = ("24", EVEN) if preset == "high" else ("27", _cap_short_side(720))
            args = ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "medium",
                    "-crf", crf, "-vf", vf, *audio, *tail]
            _run(src, tmp, args, info.duration, progress, cancel)
        else:
            _compress_to_size(src, tmp, parse_size_mb(preset), info, progress, cancel)

        new, old = tmp.stat().st_size, src.stat().st_size
        if preset in ("high", "small") and new >= old:
            raise ConversionError(
                "This video is already well compressed - the result came out "
                f"{new / 1e6:.1f} MB vs {old / 1e6:.1f} MB, so nothing was saved.")
    return dst


def _compress_to_size(src, out, target_mb, info, progress, cancel):
    if info.duration <= 0:
        raise ConversionError("Couldn't read this video's length, so can't aim for a size.")
    budget = target_mb * 1e6 * 0.94          # margin: container overhead, MB vs MiB
    if src.stat().st_size <= budget:
        raise ConversionError(f"This video is already under {target_mb:g} MB.")

    total_kbps = budget * 8 / info.duration / 1000
    a_kbps = 0 if not info.audio else 128 if total_kbps > 1000 else 96 if total_kbps > 400 else 48
    v_kbps = int(total_kbps - a_kbps)
    if v_kbps < 60:
        mins = info.duration / 60
        raise ConversionError(
            f"A {mins:.0f}-minute video can't fit in {target_mb:g} MB at watchable quality.\n"
            "Try a bigger size, or trim it first.")
    # Lower bitrates look far better at lower resolution.
    cap = 1440 if v_kbps >= 6000 else 1080 if v_kbps >= 2000 else 720 if v_kbps >= 900 \
        else 480 if v_kbps >= 350 else 360
    vf = _cap_short_side(cap)
    audio = (["-c:a", "aac", "-b:a", f"{a_kbps}k"] if a_kbps else ["-an"])

    with tempfile.TemporaryDirectory(prefix="qc-2pass-") as work:
        log = os.path.join(work, "pass")

        def video(kbps, n):
            return ["-map", "0:v:0", "-c:v", "libx264", "-preset", "medium",
                    "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.5)}k",
                    "-bufsize", f"{kbps * 2}k", "-pass", str(n), "-passlogfile", log,
                    "-vf", vf, "-pix_fmt", "yuv420p"]

        def half(offset):
            return (lambda f: progress(offset + f * 0.5)) if progress else None

        _run(src, os.devnull, video(v_kbps, 1) + ["-an", "-f", "null"],
             info.duration, half(0.0), cancel)
        pass2 = video(v_kbps, 2) + ["-map", "0:a:0?", *audio, "-movflags", "+faststart"]
        _run(src, out, pass2, info.duration, half(0.5), cancel)

        # Rare overshoot (very complex footage): one tighter retry of pass 2.
        size = out.stat().st_size
        limit = target_mb * 1e6 * 0.98
        if size > limit:
            v2 = int(v_kbps * (limit / size) * 0.95)
            if progress:
                progress(0.5)
            pass2 = video(v2, 2) + ["-map", "0:a:0?", *audio, "-movflags", "+faststart"]
            _run(src, out, pass2, info.duration, half(0.5), cancel)
