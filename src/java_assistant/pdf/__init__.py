"""PDF discovery and offline extraction."""

from .discovery import discover_pdfs
from .extract import PdfEvidence, PdfExtractionError, PdfExtractor

__all__ = ["PdfEvidence", "PdfExtractionError", "PdfExtractor", "discover_pdfs"]
