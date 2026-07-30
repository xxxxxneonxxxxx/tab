from __future__ import annotations

from newbec.guitar_sources import GUITAR_PROVIDERS, GuitarCatalogSource


class FakeClient:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def get_text(self, url: str) -> str:
        return self.pages[url]


def test_registry_contains_ten_guitar_catalogs():
    assert len(GUITAR_PROVIDERS) == 10
    assert all(provider.formats for provider in GUITAR_PROVIDERS)


def test_catalog_reader_returns_only_guitar_file_links():
    catalog = "https://example.test/catalog"
    piece = "https://example.test/piece"
    midi = "https://example.test/piece.mid"
    client = FakeClient(
        {
            catalog: f'<a href="{piece}">Guitar Song</a>',
            piece: f'<html>For guitar solo <a href="{midi}">MIDI</a></html>',
        }
    )
    provider = GUITAR_PROVIDERS[0].__class__("test", "Test Guitar", "https://example.test", (catalog,), ("midi",), "test")
    matches = GuitarCatalogSource(provider, client).search("Guitar Song")
    assert len(matches) == 1
    assert matches[0].file_format == "midi"
    assert matches[0].details["guitar_only_catalog"] is True
