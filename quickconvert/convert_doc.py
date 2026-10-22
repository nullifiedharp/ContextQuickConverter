"""Office documents (via Microsoft Office or LibreOffice) and PDFs (via PyMuPDF)."""
import os
import shutil
import tempfile
from pathlib import Path

from .formats import category, canon
from .util import (ConversionError, atomic_output, find_soffice,
                   office_app_installed, run_quiet, unique_path, IS_WINDOWS)

# ---------------------------------------------------------------- LibreOffice
LO_FILTERS = {
    "word": {"pdf": "pdf:writer_pdf_Export", "docx": "docx:MS Word 2007 XML",
             "odt": "odt", "rtf": "rtf", "txt": "txt:Text (encoded):UTF8"},
    "sheet": {"pdf": "pdf:calc_pdf_Export", "xlsx": "xlsx:Calc MS Excel 2007 XML",
              "ods": "ods", "csv": "csv:Text - txt - csv (StarCalc):44,34,76,1"},
    "slide": {"pdf": "pdf:impress_pdf_Export",
              "pptx": "pptx:Impress MS PowerPoint 2007 XML", "odp": "odp"},
}


def _libreoffice(src: Path, out: Path, target: str, cat: str):
    soffice = find_soffice()
    if not soffice:
        raise ConversionError("LibreOffice isn't installed.")
    with tempfile.TemporaryDirectory(prefix="qc-lo-") as work:
        work = Path(work)
        # Private profile so this works even while LibreOffice is open.
        profile = (work / "profile").as_uri()
        r = run_quiet([soffice, f"-env:UserInstallation={profile}", "--headless",
                       "--norestore", "--convert-to", LO_FILTERS[cat][target],
                       "--outdir", str(work / "out"), str(src)], timeout=600)
        produced = list((work / "out").glob("*")) if (work / "out").exists() else []
        if not produced:
            detail = (r.stderr or r.stdout).strip()[-400:]
            raise ConversionError(f"LibreOffice couldn't convert this file.\n{detail}")
        shutil.move(str(produced[0]), out)


# ---------------------------------------------------------- Microsoft Office
def _office(src: Path, out: Path, target: str, cat: str):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    src_s, out_s = str(src.resolve()), str(out.resolve())
    app = None
    try:
        if cat == "word":
            fmt = {"pdf": 17, "docx": 16, "odt": 23, "rtf": 6, "txt": 2}[target]
            app = win32com.client.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            doc = app.Documents.Open(src_s, ConfirmConversions=False, ReadOnly=True,
                                     AddToRecentFiles=False)
            try:
                if target == "txt":
                    doc.SaveAs2(out_s, FileFormat=fmt, Encoding=65001)  # UTF-8
                else:
                    doc.SaveAs2(out_s, FileFormat=fmt)
            finally:
                doc.Close(SaveChanges=0)
        elif cat == "sheet":
            app = win32com.client.DispatchEx("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            wb = app.Workbooks.Open(src_s, ReadOnly=True, AddToMru=False)
            try:
                if target == "pdf":
                    wb.ExportAsFixedFormat(0, out_s)
                else:
                    fmt = {"xlsx": 51, "ods": 60, "csv": 62}[target]  # 62 = CSV UTF-8
                    wb.SaveAs(out_s, FileFormat=fmt)
            finally:
                wb.Close(SaveChanges=False)
        elif cat == "slide":
            app = win32com.client.DispatchEx("PowerPoint.Application")
            pres = app.Presentations.Open(src_s, ReadOnly=True, Untitled=False,
                                          WithWindow=False)
            try:
                fmt = {"pdf": 32, "pptx": 24, "odp": 35}[target]
                pres.SaveAs(out_s, fmt)
            finally:
                pres.Close()
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


OFFICE_PROGID = {"word": "Word.Application", "sheet": "Excel.Application",
                 "slide": "PowerPoint.Application"}


def backends_available() -> dict:
    return {"office": IS_WINDOWS and office_app_installed("Word.Application"),
            "libreoffice": find_soffice() is not None}


def _office_doc(src: Path, dst: Path, target: str, cat: str):
    errors = []
    with atomic_output(dst) as tmp:
        if IS_WINDOWS and office_app_installed(OFFICE_PROGID[cat]):
            try:
                _office(src, tmp, target, cat)
                return
            except Exception as e:   # fall back to LibreOffice if present
                errors.append(f"Microsoft Office: {e}")
                if tmp.exists():
                    os.remove(tmp)
        if find_soffice():
            _libreoffice(src, tmp, target, cat)
            return
        if errors:
            raise ConversionError("\n".join(errors))
        raise ConversionError(
            "Converting documents needs Microsoft Office or the free LibreOffice "
            "(libreoffice.org). Install either one and try again.")


# ------------------------------------------------------------------------ PDF
def _pdf(src: Path, dst: Path, target: str, progress) -> Path:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    try:
        doc = pymupdf.open(str(src))
    except Exception as e:
        raise ConversionError(f"Couldn't open this PDF ({e}).") from e
    with doc:
        if doc.needs_pass:
            raise ConversionError("This PDF is password-protected.")
        if target == "txt":
            with atomic_output(dst) as tmp:
                text = "\f".join(page.get_text() for page in doc)
                tmp.write_text(text, encoding="utf-8")
            return dst

        def render(page, path):
            pix = page.get_pixmap(dpi=200, alpha=False)
            if target == "jpg":
                pix.save(str(path), jpg_quality=92)
            else:
                pix.save(str(path))

        if doc.page_count == 1:
            with atomic_output(dst) as tmp:
                render(doc[0], tmp)
            return dst
        # Many pages -> a folder of numbered images.
        folder = unique_path(dst.with_name(f"{src.stem} ({target.upper()} pages)"))
        folder.mkdir()
        width = len(str(doc.page_count))
        for i, page in enumerate(doc, 1):
            render(page, folder / f"{src.stem}-{i:0{width}d}.{target}")
            if progress:
                progress(i / doc.page_count)
        return folder


def convert(src: Path, dst: Path, target: str, progress=None, cancel=None) -> Path:
    cat = category(src.suffix)
    if cat == "pdf":
        return _pdf(src, dst, target, progress)
    if canon(src.suffix) == target:
        raise ConversionError("File is already in that format.")
    _office_doc(src, dst, target, cat)
    return dst
