"""Thin, cached, retrying client for the Qloo API.

Endpoint and parameter names follow Qloo's public docs as seen through community
wrappers. They have NOT been verified against the live API from this scaffold:
the first job once you hold a real key is `python scripts/spike.py`, then fix
anything that comes back 4xx.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import requests

DEFAULT_BASE_URL = "https://hackathon.api.qloo.com"
CACHE_TTL_SECONDS = 7 * 24 * 3600
RETRY_STATUSES = {429, 500, 502, 503, 504}

ARTIST = "urn:entity:artist"
BOOK = "urn:entity:book"
BRAND = "urn:entity:brand"
DESTINATION = "urn:entity:destination"
MOVIE = "urn:entity:movie"
PERSON = "urn:entity:person"
PLACE = "urn:entity:place"
PODCAST = "urn:entity:podcast"
TV_SHOW = "urn:entity:tv_show"
VIDEOGAME = "urn:entity:videogame"


class QlooError(RuntimeError):
    """Raised for any failed Qloo call. Never contains the API key."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass
class Entity:
    id: str
    name: str
    type: str = ""
    popularity: float | None = None
    affinity: float | None = None  # insights only: how strongly the signals point at this entity
    tags: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_raw(cls, d: dict) -> "Entity":
        tags: list[str] = []
        for t in d.get("tags") or []:
            tags.append(str(t.get("name") or t.get("id") or "") if isinstance(t, dict) else str(t))
        types = d.get("types")
        etype = d.get("type") or (types[0] if isinstance(types, list) and types else "")
        q = d.get("query")
        return cls(
            id=str(d.get("entity_id") or d.get("id") or ""),
            name=str(d.get("name") or ""),
            type=str(etype),
            popularity=d.get("popularity"),
            affinity=q.get("affinity") if isinstance(q, dict) else None,
            tags=[t for t in tags if t],
            raw=d,
        )


def load_env(path: str = ".env") -> None:
    """Minimal .env loader (no dependency). Existing environment variables win."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _results(data: Any) -> list[dict]:
    """Qloo wraps lists differently per endpoint; normalise to a list of dicts."""
    res = data.get("results") if isinstance(data, dict) else data
    if isinstance(res, dict):
        res = res.get("entities") or res.get("tags") or []
    return [r for r in (res or []) if isinstance(r, dict)]


class _Cache:
    """Tiny SQLite response cache. path=None keeps it in memory."""

    def __init__(self, path: str | None):
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path or ":memory:", check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, v TEXT NOT NULL, ts REAL NOT NULL)"
            )
            self._conn.commit()

    def get(self, key: str, ttl: float) -> Any | None:
        with self._lock:
            row = self._conn.execute("SELECT v, ts FROM cache WHERE k = ?", (key,)).fetchone()
        if not row or time.time() - row[1] > ttl:
            return None
        return json.loads(row[0])

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (k, v, ts) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time()),
            )
            self._conn.commit()


class QlooClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        cache_path: str | None = ".cache/qloo.sqlite",
        timeout: float = 20.0,
        max_retries: int = 3,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.api_key = (api_key or os.environ.get("QLOO_API_KEY", "")).strip()
        if not self.api_key:
            raise QlooError("No API key. Set QLOO_API_KEY (see .env.example).")
        if self.api_key.lower().startswith(("http://", "https://")):
            raise QlooError(
                "QLOO_API_KEY looks like a URL. That value belongs in QLOO_BASE_URL; "
                "the key is the secret string from Qloo's hackathon developer guide."
            )
        self.base_url = (base_url or os.environ.get("QLOO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self._sleep = sleep
        self._cache = _Cache(cache_path)
        self.stats = {"requests": 0, "cache_hits": 0, "retries": 0}

    # -- transport ---------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        clean: dict[str, Any] = {}
        for k, v in params.items():
            if v is None or v == "" or v == []:
                continue
            clean[k] = ",".join(map(str, v)) if isinstance(v, (list, tuple)) else v

        key = hashlib.sha256(
            (self.base_url + path + json.dumps(clean, sort_keys=True, default=str)).encode()
        ).hexdigest()
        cached = self._cache.get(key, CACHE_TTL_SECONDS)
        if cached is not None:
            self.stats["cache_hits"] += 1
            return cached

        last: QlooError | None = None
        for attempt in range(self.max_retries + 1):
            self.stats["requests"] += 1
            try:
                r = self.session.get(
                    self.base_url + path,
                    params=clean,
                    headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                last = QlooError(f"Network error calling {path}: {type(e).__name__}")
                self._backoff(attempt, None)
                continue
            if r.status_code == 200:
                try:
                    data = r.json()
                except ValueError:
                    raise QlooError(f"Qloo {path} returned non-JSON", status=200, body=r.text[:300])
                self._cache.set(key, data)
                return data
            if r.status_code in RETRY_STATUSES:
                last = QlooError(f"Qloo {r.status_code} on {path}", status=r.status_code, body=r.text[:300])
                self._backoff(attempt, r.headers.get("Retry-After"))
                continue
            raise QlooError(f"Qloo {r.status_code} on {path}: {r.text[:300]}", status=r.status_code, body=r.text[:300])
        assert last is not None
        raise last

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        if attempt >= self.max_retries:
            return
        self.stats["retries"] += 1
        try:
            delay = float(retry_after) if retry_after is not None else min(0.5 * 2**attempt, 8.0)
        except ValueError:
            delay = min(0.5 * 2**attempt, 8.0)
        self._sleep(delay)

    # -- endpoints ---------------------------------------------------------

    def search(self, query: str, types: str | Iterable[str] | None = None, take: int = 5) -> list[Entity]:
        data = self._get("/search", {"query": query, "types": _csv(types), "take": take})
        return [Entity.from_raw(d) for d in _results(data)]

    def tags(self, query: str, take: int = 5) -> list[dict]:
        return _results(self._get("/v2/tags", {"filter.query": query, "take": take}))

    def entities(self, ids: Iterable[str]) -> list[Entity]:
        data = self._get("/entities", {"entity_ids": list(ids)})
        return [Entity.from_raw(d) for d in _results(data)]

    def insights(
        self,
        entity_type: str,
        *,
        entities: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        location: str | None = None,
        filter_location: str | None = None,
        exclude_entities: Iterable[str] | None = None,
        take: int = 10,
        params: dict[str, Any] | None = None,
    ) -> list[Entity]:
        """Taste neighbours of one entity type.

        `location` is a *signal* (what this place's audience likes);
        `filter_location` restricts results to a place (use it for urn:entity:place).
        """
        p: dict[str, Any] = {
            "filter.type": entity_type,
            "signal.interests.entities": _csv(entities),
            "signal.interests.tags": _csv(tags),
            "signal.location.query": location,
            "filter.location.query": filter_location,
            "filter.exclude.entities": _csv(exclude_entities),
            "take": take,
        }
        p.update(params or {})
        return [Entity.from_raw(d) for d in _results(self._get("/v2/insights", p))]


def _csv(v: str | Iterable[str] | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return ",".join(v) or None
