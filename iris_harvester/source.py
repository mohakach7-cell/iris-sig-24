import json
import time
from pathlib import Path
from urllib.parse import urlsplit
import requests


class SourceError(ValueError):
    pass


def validate_page(page):
    if not isinstance(page, dict) or page.get("contract") != "iris-demo-v1":
        raise SourceError("Expected iris-demo-v1, not a native MaStR response")
    if not isinstance(page.get("items"), list):
        raise SourceError("Page items must be a list")
    cursor = page.get("next_cursor")
    if cursor is not None and (not isinstance(cursor, str) or not cursor):
        raise SourceError("Invalid next_cursor")
    return page["items"], cursor


class FixtureSource:
    def __init__(self, path):
        self.path = Path(path)

    def pages(self, since, until):
        try:
            bundle = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SourceError("Cannot read fixture JSON") from exc
        if not isinstance(bundle, list) or not bundle:
            raise SourceError("Fixture must contain at least one page")
        cursors = set()
        for i, page in enumerate(bundle):
            items, cursor = validate_page(page)
            if cursor in cursors or (cursor is None) != (i == len(bundle) - 1):
                raise SourceError("Broken fixture pagination")
            cursors.add(cursor)
            yield items


class RestSource:
    """Optional authorized gateway implementing OUR contract, not official MaStR SOAP."""
    def __init__(self, endpoint, token=None, session=None, sleep=time.sleep, max_pages=1000):
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise SourceError("Endpoint must be HTTPS without credentials, query or fragment")
        self.endpoint, self.session = endpoint, session or requests.Session()
        self.headers = {"Accept": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.sleep, self.max_pages = sleep, max_pages

    def _get(self, params):
        for attempt in range(3):
            try:
                response = self.session.get(self.endpoint, params=params, headers=self.headers,
                                            timeout=(10, 30), allow_redirects=False)
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 2:
                    raise SourceError("Network request failed after 3 attempts") from None
                self.sleep(2 ** attempt)
                continue
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt == 2:
                    raise SourceError(f"Retry limit reached: HTTP {response.status_code}")
                self.sleep(2 ** attempt)
                continue
            if response.status_code != 200:
                raise SourceError(f"Unexpected HTTP {response.status_code}; no redirect followed")
            try:
                return response.json()
            except ValueError:
                raise SourceError("Invalid JSON response") from None
        raise SourceError("No response")

    def pages(self, since, until):
        cursor = None
        seen = set()
        for _ in range(self.max_pages):
            items, cursor = validate_page(self._get({"since": since, "until": until, "cursor": cursor}))
            if cursor is not None and cursor in seen:
                raise SourceError("Repeated pagination cursor")
            yield items
            if cursor is None:
                return
            seen.add(cursor)
        raise SourceError("Page limit reached; run incomplete")

