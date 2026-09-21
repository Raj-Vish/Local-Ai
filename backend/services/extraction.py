"""Stage 1: turn an uploaded document into plain text.

Two routes in, one result out:

  digital PDF  -> pdfplumber reads the text layer directly
  photograph   -> Tesseract reads the pixels (OCR)

A PDF that is really a photograph -- a scan, or a phone picture saved as PDF --
has no text layer, so pdfplumber returns almost nothing. That case falls back
to rasterising the pages and running OCR over them, which is the whole reason
a crumpled taxi receipt is readable at all.

Nothing here produces a figure that reaches the database. Extraction yields
text; a human still confirms every expense. See the AI safety rule in the
project handoff: the database calculates, the model only phrases.
"""
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from config import settings

log = logging.getLogger("uvicorn.error")

PDF_MIME = "application/pdf"
IMAGE_MIMES = {"image/jpeg", "image/png"}

# Collapses runs of blank lines, and trailing spaces, without touching the
# line structure -- a receipt's layout carries meaning worth keeping.
_TRAILING_SPACE = re.compile(r"[ \t]+$", re.M)
_BLANK_RUN = re.compile(r"\n{3,}")


class ExtractionError(Exception):
    """Raised with a message meant to be stored and shown to the uploader."""


@dataclass
class ExtractionResult:
    text: str
    ocr_used: bool
    pages: int


def tidy(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_SPACE.sub("", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def poppler_available() -> bool:
    return shutil.which("pdftoppm") is not None


def _ocr_image(path: Path) -> str:
    """Run Tesseract over one image file."""
    if not tesseract_available():
        raise ExtractionError(
            "Tesseract OCR is not installed on the server, so photographs "
            "cannot be read yet."
        )
    # Imported here rather than at module load: the backend must still start
    # on a machine where OCR has not been set up.
    import pytesseract
    from PIL import Image

    try:
        with Image.open(path) as img:
            # Tesseract is trained on black-on-white text; a colour photo
            # converted to greyscale reads more reliably and uses less memory.
            return pytesseract.image_to_string(
                img.convert("L"),
                lang=settings.OCR_LANG,
                config=f"--psm {settings.OCR_PSM}",
            )
    except pytesseract.TesseractNotFoundError:
        raise ExtractionError("Tesseract OCR is not installed on the server.")
    except Exception as exc:
        raise ExtractionError(f"Could not read that image ({type(exc).__name__}).")


def _pdf_text_layer(path: Path) -> tuple[str, int]:
    """Read whatever text the PDF already carries. Returns (text, page count)."""
    import pdfplumber

    try:
        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            limit = min(total, settings.EXTRACT_MAX_PAGES)
            parts = []
            for index in range(limit):
                page = pdf.pages[index]
                parts.append(page.extract_text() or "")
                # pdfplumber caches every glyph per page; on a long document
                # that grows without bound. This machine has ~1.7 GB free.
                page.flush_cache()
            return "\n\n".join(parts), total
    except Exception as exc:
        raise ExtractionError(
            f"That PDF could not be opened -- it may be damaged or encrypted "
            f"({type(exc).__name__})."
        )


def _ocr_pdf(path: Path) -> str:
    """Rasterise the PDF and OCR each page. For scans and photo-PDFs."""
    if not poppler_available():
        raise ExtractionError(
            "poppler-utils is not installed on the server, so scanned PDFs "
            "cannot be converted for reading."
        )
    if not tesseract_available():
        raise ExtractionError(
            "Tesseract OCR is not installed on the server, so scanned PDFs "
            "cannot be read yet."
        )

    with tempfile.TemporaryDirectory(prefix="extract_") as tmp:
        stem = Path(tmp) / "page"
        try:
            subprocess.run(
                [
                    "pdftoppm", "-png",
                    "-r", str(settings.OCR_DPI),
                    "-l", str(settings.EXTRACT_MAX_PAGES),
                    str(path), str(stem),
                ],
                check=True,
                capture_output=True,
                timeout=settings.EXTRACT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise ExtractionError("Reading that document took too long and was stopped.")
        except subprocess.CalledProcessError as exc:
            # poppler writes several lines of syntax warnings to stderr. Only
            # the first says anything useful, and error_message is shown to a
            # person, not tailed from a log.
            noise = (exc.stderr or b"").decode("utf-8", "replace")
            first = next((ln.strip() for ln in noise.splitlines() if ln.strip()), "")
            detail = f" ({first[:120]})" if first else ""
            raise ExtractionError(
                f"That PDF could not be read -- it may be damaged or not a real PDF{detail}."
            )

        pages = sorted(Path(tmp).glob("page*.png"))
        if not pages:
            raise ExtractionError("That PDF produced no readable pages.")
        return "\n\n".join(_ocr_image(p) for p in pages)


def extract(file_path: str | Path, mime_type: str) -> ExtractionResult:
    """Turn one stored document into text. Raises ExtractionError on failure."""
    path = Path(file_path)
    if not path.exists():
        raise ExtractionError("The stored file is no longer on the server.")

    if mime_type in IMAGE_MIMES:
        return ExtractionResult(text=tidy(_ocr_image(path)), ocr_used=True, pages=1)

    if mime_type == PDF_MIME:
        text, pages = _pdf_text_layer(path)
        tidied = tidy(text)
        # A digital PDF gives plenty of characters. Almost none means the page
        # is a picture, so fall through to OCR rather than storing emptiness.
        if len(tidied) >= settings.EXTRACT_MIN_CHARS:
            return ExtractionResult(text=tidied, ocr_used=False, pages=pages)

        if not settings.OCR_ENABLED:
            raise ExtractionError(
                "This PDF has no text layer and OCR is disabled on the server."
            )
        log.info("extraction: %s has no usable text layer, falling back to OCR", path.name)
        return ExtractionResult(text=tidy(_ocr_pdf(path)), ocr_used=True, pages=pages)

    raise ExtractionError(f"There is no way to read a {mime_type} file yet.")
