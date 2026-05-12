---
name: pdf-parser-benchmarks
description: Python PDF parser comparison — benchmarks, capabilities, and best-use-case for each library
metadata:
  type: reference
---

## Benchmarked parsers (speed per document)

- **marker-pdf** (11.3s): Perfect structure preservation, ideal for high-quality conversions, long time though
- **pymupdf4llm** (0.12s): Excellent markdown output, great balance of speed and quality
- **unstructured** (1.29s): Clean semantic chunks, perfect for RAG workflows
- **textract** (0.21s): Fast with OCR capabilities, minor formatting variations
- **pypdfium2** (0.003s): Blazing speed, clean basic text, no structure
- **pypdf** (0.024s): Reliable extraction, occasional spacing artifacts
- **pdfplumber** (0.10s): Good for tables, text extraction needs configuration

## Library capabilities overview

**Text extraction:**
- **PyPDF / PyPDF2**: Mostly PDF transformation (merge, split, rotate, encrypt); good text extraction support
- **pdfminer.six**: Excellent extraction with advanced layout information
- **PyMuPDF**: Fastest processing, strong text extraction, transformation, table extraction — most full-featured

**Table-focused:**
- **pdfplumber**: Adds table extraction on top of pdfminer
- **Tabula-py**: Primarily focused on table extraction, limited text support
- **Camelot**: Designed for tabular data extraction, not suited for general text/Q&A from content

**OCR:**
- **OCRmyPDF**: Converts scanned PDFs to searchable PDFs (adds OCR text layer)

**How to apply:** When choosing or upgrading PDF processing in InboxClerk (or any project), use this to pick the right parser for the job. Currently InboxClerk uses PyMuPDF + pdfplumber; consider pymupdf4llm or marker-pdf if higher quality extraction is needed. Consider OCRmyPDF as an alternative to pytesseract for scanned PDF handling.
