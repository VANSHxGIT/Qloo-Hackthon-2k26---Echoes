"""Day-1 spike: does Qloo know enough regional, older-era taste for Echoes to work?

Runs 10 seeds (2 per culture, 5 cultures) through /search, then asks /v2/insights
for taste neighbours in several domains. It answers two different questions:

1. Coverage: do the seeds resolve to Qloo entities, and do the insights calls return
   anything? This is counted below. The thresholds are this project's own heuristic,
   not anything Qloo publishes.
2. Plausibility: are the neighbours right for the culture and the era? Only a human
   can judge that, so the report prints the names for you to read.

It also records every failed call with its status code, so a wrong parameter name is
found on day 1 instead of looking like "thin coverage".
"""
from __future__ import annotations

import re
import time
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.parse import urlparse

from .qloo import ARTIST, BRAND, MOVIE, PLACE, TV_SHOW, Entity, QlooClient, QlooError

DOMAINS: dict[str, str] = {
    "artist": ARTIST,
    "movie": MOVIE,
    "tv_show": TV_SHOW,
    "brand": BRAND,
    "place": PLACE,
}
DEFAULT_DOMAINS = tuple(DOMAINS)

MIN_RESULTS = 3  # a domain "works" for a seed if it returns at least this many entities
MIN_WORKING_DOMAINS = 2  # a seed is "usable" if it resolves and this many domains work
GO_SEED_SHARE = 0.7  # share of seeds that must be usable for GO
GO_CULTURE_SHARE = 0.8  # share of cultures with at least one usable seed for GO
MAYBE_SEED_SHARE = 0.4


@dataclass(frozen=True)
class Seed:
    culture: str
    city: str  # the "hometown" signal Echoes would send
    name: str
    type: str
    era: str  # when the imagined person would have loved it (a note for the reader)


# Two seeds per culture. Chosen to be older and regional on purpose: that is where a
# generic LLM defaults to the Western canon, and where Qloo's coverage is least certain.
SEEDS: tuple[Seed, ...] = (
    Seed("Hindi / North India", "Delhi", "Kishore Kumar", ARTIST, "1960s-80s"),
    Seed("Hindi / North India", "Delhi", "Sholay", MOVIE, "1975"),
    Seed("Nigerian / Yoruba", "Lagos", "Fela Kuti", ARTIST, "1970s"),
    Seed("Nigerian / Yoruba", "Lagos", "Living in Bondage", MOVIE, "1992"),
    Seed("Brazilian", "São Paulo", "Elis Regina", ARTIST, "1960s-70s"),
    Seed("Brazilian", "São Paulo", "Roque Santeiro", TV_SHOW, "1985"),
    Seed("Mexican", "Mexico City", "Pedro Infante", ARTIST, "1940s-50s"),
    Seed("Mexican", "Mexico City", "Nosotros los pobres", MOVIE, "1948"),
    Seed("Japanese", "Tokyo", "Hibari Misora", ARTIST, "1950s-80s"),
    Seed("Japanese", "Tokyo", "Tokyo Story", MOVIE, "1953"),
)


@dataclass
class CallResult:
    call: str  # "search" or a domain name
    names: list[str] = field(default_factory=list)
    error: str | None = None
    status: int | None = None


@dataclass
class SeedResult:
    seed: Seed
    match: str = ""
    match_id: str = ""
    match_confirmed: bool = False  # the matched entity's name resembles the seed's
    search: CallResult = field(default_factory=lambda: CallResult("search"))
    domains: list[CallResult] = field(default_factory=list)

    @property
    def working_domains(self) -> int:
        return sum(1 for d in self.domains if len(d.names) >= MIN_RESULTS)

    @property
    def usable(self) -> bool:
        return self.match_confirmed and self.working_domains >= MIN_WORKING_DOMAINS

    @property
    def calls(self) -> list[CallResult]:
        return [self.search, *self.domains]


# -- helpers ----------------------------------------------------------------------


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def looks_like(a: str, b: str) -> bool:
    """Loose name match, tolerant of accents, punctuation and word order.

    Names in non-Latin scripts normalise to nothing and return False, which only
    means "unconfirmed": the report flags them for a human to check.
    """
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    return len(ta & tb) / len(ta | tb) >= 0.5


def is_mock_url(url: str) -> bool:
    return (urlparse(url).hostname or "") in {"127.0.0.1", "localhost", "::1"}


def _label(e: Entity) -> str:
    return f"{e.name} ({e.affinity:.2f})" if isinstance(e.affinity, (int, float)) else e.name


def _attempt(call: str, fn: Callable[[], list[Entity]]) -> tuple[CallResult, list[Entity]]:
    try:
        ents = fn()
    except QlooError as e:  # the message never contains the API key
        return CallResult(call, error=str(e)[:200], status=e.status), []
    return CallResult(call, names=[_label(x) for x in ents]), ents


# -- the spike --------------------------------------------------------------------


def run_spike(
    client: QlooClient,
    seeds: Iterable[Seed] = SEEDS,
    domains: Iterable[str] = DEFAULT_DOMAINS,
    take: int = 8,
    delay: float = 0.0,
    progress: Callable[[int, int, Seed], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[SeedResult]:
    seeds, domains = list(seeds), list(domains)
    unknown = [d for d in domains if d not in DOMAINS]
    if unknown:
        raise ValueError(f"Unknown domain(s) {unknown}; choose from {list(DOMAINS)}")

    results: list[SeedResult] = []
    for i, seed in enumerate(seeds, 1):
        if progress:
            progress(i, len(seeds), seed)
        res = SeedResult(seed=seed)

        res.search, hits = _attempt("search", lambda: client.search(seed.name, types=seed.type, take=5))
        sleep(delay)
        pick = next((h for h in hits if looks_like(h.name, seed.name)), None)
        res.match_confirmed = pick is not None
        pick = pick or (hits[0] if hits else None)
        if pick and pick.id:
            res.match, res.match_id = pick.name, pick.id

        for d in domains:
            if not res.match_id:
                res.domains.append(CallResult(d, error="skipped: seed did not resolve"))
                continue
            is_place = d == "place"
            call, _ = _attempt(
                d,
                lambda d=d, is_place=is_place: client.insights(
                    DOMAINS[d],
                    entities=[res.match_id],
                    # Hometown is a taste signal for most domains, and a hard filter for places.
                    location=None if is_place else seed.city,
                    filter_location=seed.city if is_place else None,
                    # Only same-type results can contain the seed itself.
                    exclude_entities=[res.match_id] if DOMAINS[d] == seed.type else None,
                    take=take,
                ),
            )
            res.domains.append(call)
            sleep(delay)
        results.append(res)
    return results


def verdict(results: list[SeedResult]) -> tuple[str, str]:
    """Coverage-only verdict. It cannot tell you whether the neighbours are any good."""
    if not results:
        return "n/a", "No seeds were run."
    usable = [r for r in results if r.usable]
    cultures = {r.seed.culture for r in results}
    cultures_ok = {r.seed.culture for r in usable}
    seed_share = len(usable) / len(results)
    culture_share = len(cultures_ok) / len(cultures)
    failed = sum(1 for r in results for c in r.calls if c.error and not c.error.startswith("skipped"))
    caveat = f" {failed} call(s) failed; fix those first, because they lower this count." if failed else ""

    if seed_share >= GO_SEED_SHARE and culture_share >= GO_CULTURE_SHARE:
        return "GO", (
            "Coverage looks sufficient. Now read the neighbours below and check they fit each "
            "culture and era before committing." + caveat
        )
    if seed_share >= MAYBE_SEED_SHARE:
        return "MAYBE", (
            "Coverage is patchy. Read the neighbours; if the weak seeds are the older or regional "
            "ones, build the Taste Transplant fallback alongside Echoes." + caveat
        )
    return "NO-GO", (
        "Coverage is too thin for Echoes as specced. Check the API errors section first, since a "
        "wrong parameter name looks like thin coverage. If the errors are clean, pivot to "
        "Taste Transplant." + caveat
    )


# -- reporting --------------------------------------------------------------------


def _hints(statuses: set[int]) -> list[str]:
    out: list[str] = []
    if statuses & {401, 403}:
        out.append(
            "401/403: the key was rejected. Check QLOO_API_KEY (the secret from Qloo's developer "
            "guide, not the base URL)."
        )
    if statuses & {400, 404, 422}:
        out.append(
            "400/404/422: probably a parameter or path name that differs from the live API. "
            "Compare the failing call with Qloo's docs and fix src/echoes/qloo.py."
        )
    if 429 in statuses:
        out.append("429: still rate limited after retries. Re-run with a larger --delay.")
    if statuses & {500, 502, 503, 504}:
        out.append("5xx: Qloo-side error. Re-run later; cached calls will not repeat.")
    return out


def render_report(
    results: list[SeedResult],
    *,
    base_url: str,
    is_mock: bool,
    domains: list[str],
    stats: dict | None = None,
) -> str:
    L: list[str] = ["# Echoes spike report", ""]
    if is_mock:
        L += [
            "> **[MOCK] data.** Fabricated by the local stand-in server. It says nothing about "
            "Qloo's coverage; use it only to check that this script runs.",
            "",
        ]
    L += [
        f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}",
        f"- Base URL: `{base_url}`",
        f"- Seeds: {len(results)}  |  Domains: {', '.join(domains)}",
    ]
    if stats:
        L.append(
            f"- Calls: {stats['requests']} requests, {stats['cache_hits']} cache hits, "
            f"{stats['retries']} retries"
        )
    L.append("")

    if is_mock:
        L += ["## Verdict", "", "n/a (mock data)", ""]
    else:
        v, why = verdict(results)
        L += ["## Verdict", "", f"**{v}**. {why}", ""]
        L += [
            "The verdict counts coverage only. Whether the neighbours suit the culture and era is "
            "for you to judge from the lists below.",
            "",
        ]

    L += ["## Coverage", ""]
    L += ["| Culture | Seed | Matched | Usable | " + " | ".join(domains) + " |"]
    L += ["|---|---|---|---|" + "---|" * len(domains)]
    for r in results:
        matched = (r.match + ("" if r.match_confirmed else " (?)")) if r.match else "none"
        cells = []
        for d in r.domains:
            cells.append("err" if d.error and not d.error.startswith("skipped") else str(len(d.names)))
        L.append(
            f"| {r.seed.culture} | {r.seed.name} | {matched} | {'yes' if r.usable else 'no'} | "
            + " | ".join(cells)
            + " |"
        )
    L += ["", "(?) = the top search hit's name does not resemble the seed; check it by eye.", ""]

    L += ["## Neighbours to read", ""]
    for r in results:
        L += [f"### {r.seed.name} ({r.seed.culture}, {r.seed.era})", ""]
        if r.match:
            L.append(f"- Matched: {r.match} (`{r.match_id}`)" + ("" if r.match_confirmed else " (?)"))
        if r.search.error:
            L.append(f"- Search error: {r.search.error}")
        elif not r.match_confirmed:
            L.append(f"- Search returned: {'; '.join(r.search.names[:3]) or 'nothing'}")
        for d in r.domains:
            if d.error:
                L.append(f"- {d.call}: {d.error}")
            else:
                L.append(f"- {d.call}: " + ("; ".join(d.names[:5]) or "none"))
        L.append("")

    errors = [(c.call, c) for r in results for c in r.calls if c.error and not c.error.startswith("skipped")]
    L += ["## API errors", ""]
    if not errors:
        L += ["None.", ""]
    else:
        counts = Counter(c.error[:100] for _, c in errors)
        for msg, n in counts.most_common():
            L.append(f"- x{n}: {msg}")
        L.append("")
        for h in _hints({c.status for _, c in errors if c.status}):
            L.append(f"- Hint: {h}")
        L.append("")
    return "\n".join(L)


def to_json(results: list[SeedResult]) -> list[dict]:
    return [asdict(r) for r in results]
