import tempfile
import time
import logging

logger = logging.getLogger(__name__)


def compare_processors(file_path: str) -> list[dict]:
    processors = [
        ("PyMuPDF", _extract_pymupdf),
        ("PyMuPDF4LLM", _extract_pymupdf4llm),
        ("pdfplumber", _extract_pdfplumber),
        ("pdfminer.six", _extract_pdfminer),
        ("pypdf", _extract_pypdf),
        ("pypdfium2", _extract_pypdfium2),
    ]

    results = []
    for name, func in processors:
        start = time.perf_counter()
        try:
            text, meta = func(file_path)
            elapsed = time.perf_counter() - start
            results.append({
                "name": name,
                "text": text,
                "time_ms": round(elapsed * 1000, 1),
                "char_count": len(text),
                "line_count": len(text.splitlines()),
                "meta": meta,
                "error": None,
            })
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.exception("PDF processor %s failed", name)
            results.append({
                "name": name,
                "text": "",
                "time_ms": round(elapsed * 1000, 1),
                "char_count": 0,
                "line_count": 0,
                "meta": {},
                "error": str(e),
            })

    return results


def compare_processors_from_bytes(content: bytes) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        return compare_processors(tmp.name)


def _extract_pymupdf(file_path: str) -> tuple[str, dict]:
    import fitz
    doc = fitz.open(file_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages), {"pages": len(pages), "method": "get_text()"}


def _extract_pymupdf4llm(file_path: str) -> tuple[str, dict]:
    import pymupdf4llm
    text = pymupdf4llm.to_markdown(file_path)
    return text, {"format": "markdown"}


def _extract_pdfplumber(file_path: str) -> tuple[str, dict]:
    import pdfplumber
    pages = []
    tables_count = 0
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
            tables_count += len(page.extract_tables())
    return "\n\n".join(pages), {"pages": len(pages), "tables_found": tables_count}


def _extract_pdfminer(file_path: str) -> tuple[str, dict]:
    from pdfminer.high_level import extract_text
    text = extract_text(file_path)
    return text, {"method": "extract_text with layout"}


def _extract_pypdf(file_path: str) -> tuple[str, dict]:
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages), {"pages": len(pages)}


def _extract_pypdfium2(file_path: str) -> tuple[str, dict]:
    import pypdfium2
    pdf = pypdfium2.PdfDocument(file_path)
    pages = []
    for page in pdf:
        textpage = page.get_textpage()
        pages.append(textpage.get_text_range())
        textpage.close()
        page.close()
    pdf.close()
    return "\n\n".join(pages), {"pages": len(pages)}
