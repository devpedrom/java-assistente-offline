"""Offline PDF text extraction with OCR fallback."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from pathlib import Path
import subprocess
import tempfile
from typing import Callable
from .layout import extract_diagram


class PdfExtractionError(RuntimeError):
    """Raised when neither the text layer nor OCR yields usable evidence."""


@dataclass(frozen=True)
class PdfEvidence:
    text: str
    source: str
    warnings: tuple[str, ...]
    diagram_text: str = ""


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _default_runner(args, **kwargs):
    return subprocess.run(args, **kwargs)


def _tsv_to_text(tsv: str) -> str:
    lines: dict[tuple[str, str, str, str], list[str]] = {}
    try:
        rows = csv.DictReader(io.StringIO(tsv), delimiter="\t")
        for row in rows:
            word = (row.get("text") or "").strip()
            if not word:
                continue
            key = (
                row.get("page_num", ""),
                row.get("block_num", ""),
                row.get("par_num", ""),
                row.get("line_num", ""),
            )
            lines.setdefault(key, []).append(word)
    except (csv.Error, AttributeError) as exc:
        raise PdfExtractionError("A saída do OCR está corrompida.") from exc
    return "\n".join(" ".join(words) for words in lines.values())


class PdfExtractor:
    def __init__(
        self,
        pdftotext: Path | str = "pdftotext",
        pdftoppm: Path | str = "pdftoppm",
        tesseract: Path | str = "tesseract",
        runner: Runner = _default_runner,
        timeout_s: int = 90,
    ) -> None:
        self._pdftotext = str(pdftotext)
        self._pdftoppm = str(pdftoppm)
        self._tesseract = str(tesseract)
        self._runner = runner
        self._timeout_s = timeout_s

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return self._runner(
                args,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PdfExtractionError(f"Falha ao executar {Path(args[0]).name}: {exc}") from exc

    def extract(self, path: Path) -> PdfEvidence:
        pdf = path.resolve(strict=True)
        if not pdf.is_file() or pdf.suffix.casefold() != ".pdf":
            raise PdfExtractionError("O arquivo selecionado não é um PDF válido.")

        with tempfile.TemporaryDirectory(prefix="java-assistente-pdf-") as temp:
            work = Path(temp)
            text_file = work / "texto.txt"
            text_result = self._run(
                [self._pdftotext, "-layout", "-enc", "UTF-8", str(pdf), str(text_file)]
            )
            text = ""
            if text_result.returncode == 0 and text_file.is_file():
                text = text_file.read_text(encoding="utf-8", errors="replace").strip()

            prefix = work / "pagina"
            render_result = self._run(
                [self._pdftoppm, "-gray", "-r", "140", str(pdf), str(prefix)]
            )
            if render_result.returncode != 0:
                if text:
                    return PdfEvidence(text, "text", ("Não foi possível verificar o diagrama por OCR.",))
                raise PdfExtractionError("Não foi possível renderizar o PDF para OCR.")

            page_texts: list[str] = []
            diagrams: list[str] = []
            images = sorted(work.glob("pagina-*.pgm")) or sorted(work.glob("pagina-*.png"))
            for image in images:
                if image.suffix == ".pgm":
                    def recognize(crop):
                        result = self._run([self._tesseract, str(crop), "stdout", "-l", "por+eng", "--psm", "6"])
                        return result.stdout if result.returncode == 0 else ""
                    try:
                        diagram = extract_diagram(image, recognize)
                    except ValueError as error:
                        raise PdfExtractionError(f"Não foi possível interpretar o layout: {error}") from error
                    if diagram:
                        diagrams.append(diagram)
                ocr_result = self._run(
                    [self._tesseract, str(image), "stdout", "-l", "por+eng", "tsv"]
                )
                if ocr_result.returncode == 0:
                    page = _tsv_to_text(ocr_result.stdout).strip()
                    if page:
                        page_texts.append(page)

            ocr_text = "\n\n".join(page_texts).strip()
            if text and not diagrams and not ocr_text:
                return PdfEvidence(text=text, source="text", warnings=())
            if not text and not ocr_text and not diagrams:
                raise PdfExtractionError(
                    "O PDF não possui texto legível e o OCR não encontrou conteúdo."
                )
            return PdfEvidence(
                text=text or ocr_text or "\n\n".join(diagrams),
                source="text+ocr" if text else "ocr",
                warnings=(("Conteúdo obtido por OCR; confirme nomes e símbolos do UML.",)
                          + (("Regras textuais não recuperadas; forneça o texto do enunciado.",) if not text and not ocr_text else ())),
                diagram_text="\n\n".join(diagrams) or (ocr_text if text else ""),
            )
