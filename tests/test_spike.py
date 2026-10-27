import os
import subprocess
import sys
from pathlib import Path

import pytest

from echoes.qloo import ARTIST, MOVIE, TV_SHOW, QlooError
from echoes.spike import (
    DEFAULT_DOMAINS,
    SEEDS,
    CallResult,
    Seed,
    SeedResult,
    is_mock_url,
    looks_like,
    render_report,
    run_spike,
    verdict,
)

ROOT = Path(__file__).resolve().parents[1]


# -- seed list ----------------------------------------------------------------


def test_seed_list_shape():
    assert len(SEEDS) == 10
    by_culture: dict[str, int] = {}
    for s in SEEDS:
        by_culture[s.culture] = by_culture.get(s.culture, 0) + 1
    assert len(by_culture) == 5 and set(by_culture.values()) == {2}
    assert {s.type for s in SEEDS} <= {ARTIST, MOVIE, TV_SHOW}


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("Sholay", "Sholay", True),
        ("Sao Paulo", "São Paulo", True),
        ("Tokyo Story", "Tokyo Story (1953)", True),
        ("Elis Regina", "Elis", True),
        ("Fela Kuti", "Kuti Fela", True),
        ("Sholay", "Titanic", False),
        ("美空ひばり", "Hibari Misora", False),  # non-Latin: unconfirmed, not wrong
    ],
)
def test_looks_like(a, b, expected):
    assert looks_like(a, b) is expected


def test_is_mock_url():
    assert is_mock_url("http://127.0.0.1:8765") and is_mock_url("http://localhost:1")
    assert not is_mock_url("https://hackathon.api.qloo.com")


# -- run_spike ----------------------------------------------------------------


def test_run_spike_against_mock(mock, make_client):
    server, url = mock
    results = run_spike(make_client(url), seeds=SEEDS[:1], take=5)
    r = results[0]
    assert r.match_confirmed and r.match_id.startswith("MOCK-")
    assert [d.call for d in r.domains] == list(DEFAULT_DOMAINS)
    assert r.usable

    # recorded[0] is the search; 1..5 are artist, movie, tv_show, brand, place.
    artist_q, movie_q, place_q = server.recorded[1][1], server.recorded[2][1], server.recorded[5][1]
    assert artist_q["filter.exclude.entities"] == r.match_id  # same type as the seed
    assert artist_q["signal.location.query"] == "Delhi"
    assert "filter.exclude.entities" not in movie_q  # different type: nothing to exclude
    assert place_q["filter.location.query"] == "Delhi"  # places: hard filter, not a signal
    assert "signal.location.query" not in place_q


def test_run_spike_rejects_unknown_domain(mock, make_client):
    with pytest.raises(ValueError, match="Unknown domain"):
        run_spike(make_client(mock[1]), domains=["artist", "weather"])


class _EmptyClient:
    def search(self, *a, **k):
        return []

    def insights(self, *a, **k):
        raise AssertionError("insights must not run for an unresolved seed")


def test_unresolved_seed_skips_insights():
    (r,) = run_spike(_EmptyClient(), seeds=SEEDS[:1])
    assert r.match_id == "" and not r.usable
    assert all(d.error and d.error.startswith("skipped") for d in r.domains)
    assert verdict([r])[0] == "NO-GO"


class _FailingClient:
    def search(self, *a, **k):
        raise QlooError("Qloo 400 on /search: bad param", status=400, body="bad param")


def test_errors_are_recorded_and_hinted():
    results = run_spike(_FailingClient(), seeds=SEEDS[:2])
    assert all(r.search.status == 400 for r in results)
    report = render_report(results, base_url="https://x", is_mock=False, domains=list(DEFAULT_DOMAINS))
    assert "## API errors" in report and "x2: Qloo 400 on /search" in report
    assert "parameter or path name" in report
    assert "call(s) failed" in report  # the verdict warns that errors lower the count


# -- verdict ------------------------------------------------------------------


def _fake(culture: str, usable: bool) -> SeedResult:
    names = ["a", "b", "c"]
    return SeedResult(
        seed=Seed(culture, "City", "S", ARTIST, "1970s"),
        match="S",
        match_id="1",
        match_confirmed=usable,
        domains=[CallResult("artist", names=names), CallResult("movie", names=names)],
    )


def test_verdict_thresholds():
    cultures = ["A", "B", "C", "D", "E"]
    # 7 of 10 usable across 4 cultures -> GO
    go = [_fake(c, True) for c in "AABBCCD"] + [_fake("D", False), _fake("E", False), _fake("E", False)]
    assert verdict(go)[0] == "GO"
    # 7 of 10 usable but only 3 of 5 cultures -> MAYBE
    maybe = [_fake(c, True) for c in "AAABBCC"] + [_fake("D", False), _fake("E", False), _fake("D", False)]
    assert verdict(maybe)[0] == "MAYBE"
    # 3 of 10 -> NO-GO
    no = [_fake(cultures[i % 5], i < 3) for i in range(10)]
    assert verdict(no)[0] == "NO-GO"


# -- report and CLI -----------------------------------------------------------


def test_mock_report_is_labelled_and_has_no_verdict(mock, make_client):
    results = run_spike(make_client(mock[1]), seeds=SEEDS[:2], take=4)
    report = render_report(results, base_url=mock[1], is_mock=True, domains=list(DEFAULT_DOMAINS))
    assert "[MOCK] data" in report and "n/a (mock data)" in report
    assert "**GO**" not in report and "**NO-GO**" not in report


def _cli(args, tmp_path, **env):
    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "spike.py"), *args],
        cwd=tmp_path, env=full_env, capture_output=True, text=True, timeout=60,
        stdin=subprocess.DEVNULL,
    )


def test_cli_mock_end_to_end(tmp_path):
    out = tmp_path / "report"
    p = _cli(["--mock", "--seeds", "3", "--out", str(out)], tmp_path)
    assert p.returncode == 0, p.stderr
    assert "[MOCK] data" in p.stdout
    assert out.with_suffix(".md").is_file() and out.with_suffix(".json").is_file()


def test_cli_without_key_explains_itself(tmp_path):
    p = _cli(["--out", str(tmp_path / "r")], tmp_path, QLOO_API_KEY="")
    assert p.returncode == 2
    assert "Setup problem" in p.stderr and "QLOO_API_KEY" in p.stderr


def test_cli_rejects_url_as_key(tmp_path):
    p = _cli(["--out", str(tmp_path / "r")], tmp_path, QLOO_API_KEY="https://hackathon.api.qloo.com")
    assert p.returncode == 2 and "QLOO_BASE_URL" in p.stderr
