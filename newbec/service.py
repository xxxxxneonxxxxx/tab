from __future__ import annotations

import logging

from .models import SourceMatch
from .guitar_sources import GUITAR_PROVIDERS, all_guitar_sources
from .sources import IMSLPSource, MutopiaSource
from .tab_converter import events_to_tab, read_midi, read_musicxml

logger = logging.getLogger(__name__)


class SongService:
    def __init__(self, mutopia=None, imslp=None):
        self.mutopia = mutopia or MutopiaSource()
        self.imslp = imslp or IMSLPSource()
        self.guitar_catalogs = all_guitar_sources()

    def convert(self, title: str) -> dict:
        title = title.strip()
        logger.info("song lookup started title=%r", title)
        if not title:
            logger.warning("song lookup rejected: empty title")
            return {"status": "invalid", "message": "title is required"}
        searched: list[dict] = []
        sources = [(self.mutopia, "mutopia"), (self.imslp, "imslp")]
        sources.extend((source, source.provider.id) for source in self.guitar_catalogs)
        for source, label in sources:
            try:
                matches = source.search(title, limit=5)
                # Users commonly enter "Artist — Work". Catalogs usually
                # index only the work title, so retry the part after the dash
                # before declaring a false negative.
                if not matches:
                    title_only = next((part.strip() for separator in ("—", "–", " - ") for part in title.split(separator)[1:]), "")
                    if title_only and title_only != title:
                        logger.info("retrying source=%s with title-only query=%r", label, title_only)
                        matches = source.search(title_only, limit=5)
            except Exception as exc:
                logger.exception("source search failed source=%s title=%r", label, title)
                matches = []
            if matches:
                logger.info("source=%s matches=%d", label, len(matches))
                searched.extend(m.as_dict() for m in matches)
                for match in matches:
                    if match.download_url and match.file_format in {"midi", "musicxml", "xml"}:
                        try:
                            logger.info("downloading source=%s format=%s url=%s", label, match.file_format, match.download_url)
                            data = source.client.get_bytes(match.download_url)
                            events = read_midi(data) if match.file_format == "midi" else read_musicxml(data)
                            if events:
                                logger.info("conversion succeeded source=%s notes=%d", label, len(events))
                                return {"status": "ok", "source": label, "match": match.as_dict(), "tab": events_to_tab(events)}
                        except Exception as exc:
                            logger.exception("conversion failed source=%s format=%s", label, match.file_format)
                # A page without machine-readable notes is not enough; try the next source.
            else:
                logger.info("source=%s no matches", label)
        logger.warning("song unsupported title=%r matches=%d", title, len(searched))
        return {
            "status": "unsupported",
            "matches": searched,
            "message": "song is not available as readable guitar MIDI/MusicXML in configured sources",
        }

    @staticmethod
    def sources() -> list[dict]:
        return [
            {
                "id": provider.id,
                "name": provider.name,
                "url": provider.base_url,
                "formats": list(provider.formats),
                "notes": provider.notes,
                "guitar_only_catalog": True,
            }
            for provider in GUITAR_PROVIDERS
        ]
