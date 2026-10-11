"""
NOT RUN: NSE's Terms of Use forbid automated data collection without written permission (docs/data_sources.md).
Kept ready for when permission is granted; see docs/permissions/nse_permission_request.md.

One polite HTTP client for NSE's public pages, APIs and archives (FINAL_PLAN_V6 Phase 1; docs/data_sources.md).

- Identity: a browser User-Agent. NSE silently drops requests that identify themselves as scripts (tested on
  11 Oct 2026: every API and archive file timed out with an honest bot User-Agent), and serves the same public
  files to a browser. This is stated openly in docs/data_sources.md; the user approved it.
- Politeness: robots.txt allows these paths (NSE disallows only /market-data-test); at most one request per
  REQUEST_GAP seconds; exponential backoff on refusals (401/403/429/503) and timeouts; a fresh session (cookies)
  every SESSION_CALLS requests; public files only, no logins.
- Resumable: callers keep their own checkpoints; `Checkpoint` is a small helper for "which keys are done".
"""

import json
import time
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
           "Accept": "application/json,text/csv,text/html,application/pdf,*/*", "Accept-Language": "en-US,en;q=0.9",
           "Referer": "https://www.nseindia.com/"}
HOME = "https://www.nseindia.com/"
API = "https://www.nseindia.com/api"
ARCHIVES = "https://nsearchives.nseindia.com"
REQUEST_GAP = 1.1   # seconds between requests: about one a second
SESSION_CALLS = 250
REFUSED = (401, 403, 429, 503)


class Client:
    def __init__(self, gap: float = REQUEST_GAP):
        self.gap, self.calls, self.refusals = gap, 0, 0
        self._last = 0.0
        self._new_session()

    def _new_session(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        try:
            self.s.get(HOME, timeout=30)
        except requests.RequestException:
            pass

    def _wait(self):
        pause = self.gap - (time.monotonic() - self._last)
        if pause > 0:
            time.sleep(pause)
        self._last = time.monotonic()

    def get(self, url: str, attempts: int = 6, timeout: float = 60):
        """The response (any status but the refusals), or raise after `attempts` refusals or timeouts."""
        for attempt in range(attempts):
            self._wait()
            self.calls += 1
            if self.calls % SESSION_CALLS == 0:
                self._new_session()
            try:
                r = self.s.get(url, timeout=timeout)
            except (requests.Timeout, requests.ConnectionError):
                time.sleep(min(15 * 2 ** attempt, 600))
                continue
            if r.status_code in REFUSED:
                self.refusals += 1
                wait = min(60 * 2 ** attempt, 900)
                print(f"    refused ({r.status_code}) {url[:90]}; waiting {wait}s", flush=True)
                time.sleep(wait)
                self._new_session()
                continue
            return r
        raise RuntimeError(f"NSE kept refusing {url}; stopping (rerun later: finished work is kept)")

    def json(self, url: str):
        r = self.get(url)
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None


class Checkpoint:
    """A set of finished keys, stored as JSON lines so an interrupted run loses at most the last line."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.done = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    self.done.add(json.loads(line))
                except ValueError:
                    continue

    def __contains__(self, key) -> bool:
        return key in self.done

    def add(self, key) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(key) + "\n")
        self.done.add(key)
