"""JSON-over-HTTP with a disk cache and a global throttle. Rules for NIFS are in docs/nifs-api.md."""

import gzip
import hashlib
import json
import random
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
HEADERS = {"Accept": "application/json", "User-Agent": "altomfotball/0.1"}
MIN_INTERVAL = 0.35  # seconds between request starts, across all threads; NIFS answers bursts with 429

_lock = threading.Lock()
_next_slot = 0.0


def _throttle():
    global _next_slot
    with _lock:
        now = time.monotonic()
        wait = _next_slot - now
        _next_slot = max(now, _next_slot) + MIN_INTERVAL
    if wait > 0:
        time.sleep(wait)


def get_json(url, max_age=1800, retries=6):
    """GET url as JSON. max_age=None caches forever (use for finished matches)."""
    key = hashlib.sha1(url.encode()).hexdigest()
    path = CACHE_DIR / key[:2] / f"{key}.json"
    if path.exists() and (max_age is None or time.time() - path.stat().st_mtime < max_age):
        return json.loads(path.read_bytes())

    target = url
    for attempt in range(retries + 1):
        _throttle()
        try:
            with urllib.request.urlopen(urllib.request.Request(target, headers=HEADERS), timeout=60) as r:
                body = r.read()
            break
        except urllib.error.HTTPError as e:
            if attempt == retries:
                raise
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After") or 5) + random.random())
                continue
            if e.code == 406:
                # NIFS: a cached 406 poisons the URL for 30 min; a cache-busting param bypasses it.
                sep = "&" if "?" in url else "?"
                target = f"{url}{sep}_={random.randrange(10**9)}"
                continue
            if e.code < 500:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(1.5 * (attempt + 1))

    if body[:2] == b"\x1f\x8b":  # data.fotmob.com serves gzip without being asked
        body = gzip.decompress(body)
    data = json.loads(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return data
