import io
import logging
import tempfile

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)


def extract_text_pymupdf(file_path: str) -> dict:
    doc = fitz.open(file_path)
    pages = []
    full_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        pages.append({"page": page_num + 1, "text": text})
        full_text.append(text)

    doc.close()
    return {
        "text": "\n".join(full_text),
        "pages": pages,
        "page_count": len(pages),
        "method": "pymupdf",
    }


def extract_text_pdfplumber(file_path: str) -> dict:
    pages = []
    full_text = []
    tables_found = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({"page": page_num + 1, "text": text})
            full_text.append(text)

            tables = page.extract_tables()
            for table in tables:
                tables_found.append({
                    "page": page_num + 1,
                    "rows": table,
                })

    return {
        "text": "\n".join(full_text),
        "pages": pages,
        "page_count": len(pages),
        "tables": tables_found,
        "method": "pdfplumber",
    }


def extract_text_ocr(file_path: str) -> dict:
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        logger.warning("OCR dependencies not available")
        return {"text": "", "pages": [], "page_count": 0, "method": "ocr", "error": "OCR not available"}

    pages = []
    full_text = []

    with tempfile.TemporaryDirectory() as tmpdir:
        images = convert_from_path(file_path, output_folder=tmpdir, dpi=300)
        for page_num, image in enumerate(images):
            text = pytesseract.image_to_string(image)
            pages.append({"page": page_num + 1, "text": text})
            full_text.append(text)

    return {
        "text": "\n".join(full_text),
        "pages": pages,
        "page_count": len(pages),
        "method": "ocr",
    }


def process_pdf(file_path: str) -> dict:
    result = extract_text_pymupdf(file_path)

    has_text = bool(result["text"].strip())

    if has_text:
        plumber_result = extract_text_pdfplumber(file_path)
        result["tables"] = plumber_result.get("tables", [])
        if plumber_result.get("tables"):
            result["method"] = "pymupdf+pdfplumber"
        result["ocr_applied"] = False
        return result

    # Scanned PDF — fall back to OCR
    logger.info("No text found via PyMuPDF, attempting OCR for %s", file_path)
    ocr_result = extract_text_ocr(file_path)
    ocr_result["ocr_applied"] = True
    return ocr_result


def process_pdf_bytes(content: bytes, filename: str = "document.pdf") -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        return process_pdf(tmp.name)
