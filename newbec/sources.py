from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin

from .http_client import HttpClient
from .models import SourceMatch


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]+", " ", value.lower()).strip()


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms: list[tuple[str, str, list[tuple[str, str]]] ] = []
        self._action = ""
        self._method = "get"
        self._inputs: list[tuple[str, str]] = []
        self._in_form = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "form":
            self._in_form = True
            self._action = attrs_dict.get("action") or ""
            self._method = (attrs_dict.get("method") or "get").lower()
            self._inputs = []
        elif tag == "input" and self._in_form:
            name = attrs_dict.get("name")
            if name:
                self._inputs.append((name, attrs_dict.get("value") or ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._in_form:
            self.forms.append((self._action, self._method, self._inputs))
            self._in_form = False

class MutopiaSource:
    """HTML search adapter for Mutopia; MIDI files are the preferred output."""

    base_url = "https://www.mutopiaproject.org/"
    search_url = urljoin(base_url, "advsearch.html")

    def __init__(self, client: HttpClient | None = None):
        self.client = client or HttpClient()

    def search(self, title: str, limit: int = 5) -> list[SourceMatch]:
        # Mutopia has an HTML advanced-search form, not a documented JSON API.
        page = self.client.get_text(self.search_url)
        form_parser = _FormParser()
        form_parser.feed(page)
        result_pages: list[str] = [page]
        for action, method, inputs in form_parser.forms:
            if method != "get":
                continue
            names = [name for name, _ in inputs]
            keyword_name = next((name for name in names if any(token in name.lower() for token in ("keyword", "query", "search", "term"))), None)
            if not keyword_name:
                continue
            params = [(name, value) for name, value in inputs if name == keyword_name]
            params = [(name, title if name == keyword_name else value) for name, value in params]
            target = urljoin(self.search_url, action or self.search_url)
            try:
                result_pages.append(self.client.get_text(f"{target}?{urlencode(params)}"))
            except Exception:
                continue
        candidates: list[SourceMatch] = []
        query = _norm(title)
        seen: set[str] = set()
        for result_page in result_pages:
            parser = _LinkParser()
            parser.feed(result_page)
            # Search results expose the downloadable MIDI directly. The title is
            # rendered as nearby text rather than as the link label.
            for href, label in parser.links:
                if ".mid" not in href.lower() and ".midi" not in href.lower():
                    continue
                download_url = urljoin(self.base_url, href)
                if download_url in seen:
                    continue
                path_title = re.sub(r"[-_]+", " ", href.rsplit("/", 1)[-1].rsplit(".", 1)[0])
                path_norm = _norm(path_title)
                query_parts = query.split()
                strict_match = all(part in path_norm for part in query_parts)
                # Search result filenames often contain only the work name
                # (for example moonlight-guitar-duo.mid), while the user may
                # enter "Beethoven — Moonlight Sonata". When an author is
                # supplied, accept a filename containing a meaningful title
                # token; Mutopia's own search already scoped the result.
                relaxed_match = (
                    any(separator in title for separator in ("—", "–", " - "))
                    and any(len(part) > 3 and not part.isdigit() and part in path_norm for part in query_parts)
                )
                if query and not strict_match and not relaxed_match:
                    # The result was returned by Mutopia's own search, so a
                    # strict filename check would incorrectly reject names such
                    # as "Invention 1" -> "invention-01".
                    if not any(part in path_norm for part in query_parts if not part.isdigit()):
                        continue
                seen.add(download_url)
                candidates.append(SourceMatch("mutopia", title or path_title, score_url=download_url.rsplit("/", 1)[0], download_url=download_url, file_format="midi"))
                if len(candidates) >= limit:
                    return candidates
            for href, text in parser.links:
                label = html.unescape(text)
                if not label or not query or not all(part in _norm(label) for part in query.split()):
                    continue
                score_url = urljoin(self.base_url, href)
                if score_url in seen:
                    continue
                seen.add(score_url)
                candidates.append(self._piece_from_page(score_url, label))
                if len(candidates) >= limit:
                    return candidates
        return candidates

    def _piece_from_page(self, url: str, label: str) -> SourceMatch:
        try:
            page = self.client.get_text(url)
        except Exception:
            page = ""
        parser = _LinkParser()
        parser.feed(page)
        files = [(urljoin(url, href), text.lower()) for href, text in parser.links]
        midi = next((href for href, text in files if ".mid" in href.lower() or "midi" in text), None)
        return SourceMatch(
            source="mutopia",
            title=label,
            score_url=url,
            download_url=midi,
            file_format="midi" if midi else None,
            license="See the license on the Mutopia piece page",
        )


class IMSLPSource:
    """IMSLP MediaWiki API adapter for score metadata and machine-readable files."""

    api_url = "https://imslp.org/api.php"
    site_url = "https://imslp.org/wiki/"

    def __init__(self, client: HttpClient | None = None):
        self.client = client or HttpClient()

    def search(self, title: str, limit: int = 5) -> list[SourceMatch]:
        data = self.client.get_json(
            self.api_url,
            {
                "action": "query",
                "list": "search",
                "srsearch": title,
                "srlimit": limit,
                "format": "json",
            },
        )
        result: list[SourceMatch] = []
        for item in data.get("query", {}).get("search", []):
            page_title = item.get("title", "")
            files = self._files_for_page(page_title)
            preferred = next((f for f in files if f.file_format in {"midi", "musicxml", "xml"}), None)
            result.append(
                preferred
                or SourceMatch(
                    source="imslp",
                    title=page_title,
                    score_url=self.site_url + page_title.replace(" ", "_"),
                    file_format="pdf",
                    details={"message": "IMSLP page found; machine-readable notes were not found"},
                )
            )
        return result

    def _files_for_page(self, page_title: str) -> list[SourceMatch]:
        data = self.client.get_json(
            self.api_url,
            {
                "action": "query",
                "titles": page_title,
                "prop": "images",
                "imlimit": "max",
                "format": "json",
            },
        )
        titles = [image.get("title") for page in data.get("query", {}).get("pages", {}).values() for image in page.get("images", [])]
        if not titles:
            return []
        info = self.client.get_json(
            self.api_url,
            {
                "action": "query",
                "titles": "|".join(titles),
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "format": "json",
            },
        )
        found: list[SourceMatch] = []
        for page in info.get("query", {}).get("pages", {}).values():
            title = page.get("title", "")
            image = (page.get("imageinfo") or [{}])[0]
            url = image.get("url")
            ext = title.rsplit(".", 1)[-1].lower() if "." in title else ""
            fmt = {"mid": "midi", "midi": "midi", "xml": "musicxml", "mxl": "musicxml"}.get(ext, ext)
            if url and fmt in {"midi", "musicxml", "xml", "pdf"}:
                found.append(SourceMatch("imslp", page_title, score_url=self.site_url + page_title.replace(" ", "_"), download_url=url, file_format=fmt))
        return found
