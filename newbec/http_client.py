from __future__ import annotations

import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = timeout

    def get_bytes(self, url: str) -> bytes:
        logger.info("http GET %s", url)
        request = Request(url, headers={"User-Agent": "newbec/0.1 (+local guitar tab tool)"})
        with urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def get_text(self, url: str) -> str:
        return self.get_bytes(url).decode("utf-8", errors="replace")

    def get_json(self, url: str, params: dict[str, str | int]) -> dict:
        query = urlencode(params)
        separator = "&" if "?" in url else "?"
        return json.loads(self.get_text(f"{url}{separator}{query}"))
