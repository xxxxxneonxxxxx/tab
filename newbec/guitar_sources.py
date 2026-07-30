"""Read-only adapters for guitar score catalogs.

The catalogs below are intentionally represented as providers rather than one
large scraper. A provider returns metadata and a source/download URL; this
version does not persist or mirror any copyrighted file.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from .http_client import HttpClient
from .models import SourceMatch
from .sources import _LinkParser, _norm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuitarProvider:
    id: str
    name: str
    base_url: str
    catalog_urls: tuple[str, ...]
    formats: tuple[str, ...]
    notes: str


GUITAR_PROVIDERS: tuple[GuitarProvider, ...] = (
    GuitarProvider("tarakanov", "Нотный архив Бориса Тараканова", "https://notes.tarakanov.net/", ("https://notes.tarakanov.net/katalog/instrymenti/gitara1/",), ("pdf",), "HTML-каталог; гитарные PDF и сканы"),
    GuitarProvider("classclef", "ClassClef", "https://www.classclef.com/", ("https://www.classclef.com/",), ("pdf", "midi", "guitarpro"), "Классическая и латиноамериканская гитара"),
    GuitarProvider("classical_guitar_sheet_music", "Classical Guitar Sheet Music", "https://www.classical-guitar-sheet-music.com/", ("https://www.classical-guitar-sheet-music.com/",), ("pdf",), "Каталог классической гитары"),
    GuitarProvider("dirks_guitar_page", "Dirk's Guitar Page", "https://dirk.slowgaffle.com/", ("https://dirk.slowgaffle.com/",), ("pdf", "midi", "tabledit"), "Гитарные PDF, MIDI и TablEdit"),
    GuitarProvider("classtab", "Classical Guitar Tablature", "https://www.classtab.org/", ("https://www.classtab.org/",), ("pdf", "midi", "text"), "Классическая гитара и MIDI-архив"),
    GuitarProvider("daisyfield", "Daisyfield Guitar Music Archive", "https://www.daisyfield.com/", ("https://www.daisyfield.com/music/htm/-genres/guitar.htm",), ("pdf", "midi", "musicxml"), "PDF, MIDI и XML для гитарных пьес"),
    GuitarProvider("john_wakelin", "John Wakelin Free Sheet Music", "https://www.johnwakelin.net/", ("https://www.johnwakelin.net/free-sheet-music.html",), ("pdf",), "Бесплатные ноты для классической гитары"),
    GuitarProvider("heartistry", "Heartistry Music", "https://www.heartistrymusic.com/", ("https://www.heartistrymusic.com/sheetmusic.html",), ("pdf", "midi"), "PDF и MIDI, включая гитарные материалы"),
    GuitarProvider("practito", "Practito", "https://practito.com/", ("https://practito.com/free-sheet-music",), ("pdf", "musicxml"), "Интерактивные партитуры с PDF/MusicXML"),
    GuitarProvider("free_scores", "Free-scores.com", "https://www.free-scores.com/", ("https://www.free-scores.com/",), ("pdf", "midi", "musicxml"), "Каталог нот с фильтром guitar"),
)


_FILE_EXTENSIONS = {
    ".pdf": "pdf",
    ".mid": "midi",
    ".midi": "midi",
    ".xml": "musicxml",
    ".musicxml": "musicxml",
    ".mxl": "musicxml",
    ".gp": "guitarpro",
    ".gp3": "guitarpro",
    ".gp4": "guitarpro",
    ".gp5": "guitarpro",
    ".gpx": "guitarpro",
    ".tef": "tabledit",
}


def _file_format(url: str, label: str) -> str | None:
    lowered = url.lower().split("?", 1)[0]
    for extension, file_format in _FILE_EXTENSIONS.items():
        if lowered.endswith(extension) or extension[1:] in label.lower():
            return file_format
    if "download" in label.lower() or "скач" in label.lower():
        return "pdf"
    return None


class GuitarCatalogSource:
    """Generic read-only HTML reader for one guitar catalog."""

    def __init__(self, provider: GuitarProvider, client: HttpClient | None = None):
        self.provider = provider
        self.client = client or HttpClient()

    def search(self, title: str, limit: int = 5) -> list[SourceMatch]:
        query = _norm(title)
        if not query:
            return []
        results: list[SourceMatch] = []
        seen: set[str] = set()
        for catalog_url in self.provider.catalog_urls:
            try:
                page = self.client.get_text(catalog_url)
            except Exception:
                logger.exception("guitar catalog fetch failed provider=%s url=%s", self.provider.id, catalog_url)
                continue
            parser = _LinkParser()
            parser.feed(page)
            for href, raw_label in parser.links:
                label = html.unescape(raw_label).strip()
                target = urljoin(catalog_url, href)
                if target in seen or target.startswith("mailto:"):
                    continue
                if not self._matches_query(query, label, target):
                    continue
                seen.add(target)
                match = self._read_piece(target, label or title)
                if match:
                    results.append(match)
                if len(results) >= limit:
                    return results
        return results

    @staticmethod
    def _matches_query(query: str, label: str, target: str) -> bool:
        haystack = _norm(f"{label} {target}")
        return all(token in haystack or token.lstrip("0") in haystack for token in query.split())

    def _read_piece(self, url: str, label: str) -> SourceMatch | None:
        direct_format = _file_format(url, label)
        if direct_format and direct_format in self.provider.formats:
            return SourceMatch("catalog:" + self.provider.id, label, score_url=url, download_url=url, file_format=direct_format, details={"provider": self.provider.name, "guitar_only_catalog": True})
        try:
            page = self.client.get_text(url)
        except Exception:
            return None
        if not re.search(r"гитар|guitar|guitare|chitar|gitarr", page, re.IGNORECASE):
            return None
        parser = _LinkParser()
        parser.feed(page)
        for href, raw_label in parser.links:
            file_url = urljoin(url, href)
            file_format = _file_format(file_url, raw_label)
            if file_format in self.provider.formats:
                return SourceMatch("catalog:" + self.provider.id, label, score_url=url, download_url=file_url, file_format=file_format, details={"provider": self.provider.name, "guitar_only_catalog": True})
        # Keep the score page in the response even when the site embeds a
        # viewer or hides the PDF URL. The conversion service will continue
        # to the next source because there is no machine-readable download.
        return SourceMatch("catalog:" + self.provider.id, label, score_url=url, file_format="pdf", details={"provider": self.provider.name, "guitar_only_catalog": True, "message": "guitar score page found; downloadable file link not detected"})


def all_guitar_sources(client: HttpClient | None = None) -> list[GuitarCatalogSource]:
    return [GuitarCatalogSource(provider, client=client) for provider in GUITAR_PROVIDERS]
