import pytest
import requests

from echoes.qloo import ARTIST, MOVIE, PLACE, Entity, QlooClient, QlooError, load_env


# -- configuration ------------------------------------------------------------


def test_requires_key(monkeypatch):
    monkeypatch.delenv("QLOO_API_KEY", raising=False)
    with pytest.raises(QlooError, match="No API key"):
        QlooClient(cache_path=None)


def test_url_pasted_as_key_is_caught():
    # The base URL is easy to paste into the key field by mistake.
    with pytest.raises(QlooError, match="QLOO_BASE_URL"):
        QlooClient(api_key="https://hackathon.api.qloo.com", cache_path=None)


def test_default_base_url(monkeypatch):
    monkeypatch.delenv("QLOO_BASE_URL", raising=False)
    assert QlooClient(api_key="k", cache_path=None).base_url == "https://hackathon.api.qloo.com"


def test_load_env_does_not_override_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nQLOO_API_KEY="from-file"\nQLOO_BASE_URL=http://x\n\nBROKEN LINE\n')
    monkeypatch.setenv("QLOO_API_KEY", "from-env")
    monkeypatch.delenv("QLOO_BASE_URL", raising=False)
    load_env(str(env))
    import os

    assert os.environ["QLOO_API_KEY"] == "from-env"
    assert os.environ["QLOO_BASE_URL"] == "http://x"
    monkeypatch.delenv("QLOO_BASE_URL", raising=False)


# -- endpoints and parameter mapping -----------------------------------------


def test_search_parses_entities(mock, make_client):
    server, url = mock
    hits = make_client(url).search("Sholay", types=MOVIE, take=3)
    assert len(hits) == 3
    assert hits[0].name == "Sholay"
    assert hits[0].id.startswith("MOCK-movie-")
    assert hits[0].type == MOVIE
    assert server.recorded[0] == ("/search", {"query": "Sholay", "types": MOVIE, "take": "3"})


def test_insights_param_mapping(mock, make_client):
    server, url = mock
    make_client(url).insights(ARTIST, entities=["a", "b"], location="Delhi", exclude_entities=["a"], take=4)
    path, q = server.recorded[0]
    assert path == "/v2/insights"
    assert q == {
        "filter.type": ARTIST,
        "signal.interests.entities": "a,b",
        "signal.location.query": "Delhi",
        "filter.exclude.entities": "a",
        "take": "4",
    }


def test_insights_places_use_location_as_filter(mock, make_client):
    server, url = mock
    make_client(url).insights(PLACE, entities=["a"], filter_location="Lagos")
    _, q = server.recorded[0]
    assert q["filter.location.query"] == "Lagos"
    assert "signal.location.query" not in q


def test_insights_extra_params_pass_through(mock, make_client):
    server, url = mock
    make_client(url).insights(ARTIST, entities=["a"], params={"bias.trends": "high"})
    assert server.recorded[0][1]["bias.trends"] == "high"


def test_tags_and_entities(mock, make_client):
    c = make_client(mock[1])
    assert c.tags("jazz")[0]["name"] == "[MOCK] jazz"
    assert [e.id for e in c.entities(["x1", "x2"])] != []


def test_entity_from_raw_variants():
    e = Entity.from_raw(
        {
            "id": "E1",
            "name": "N",
            "types": ["urn:entity:movie"],
            "popularity": 0.4,
            "query": {"affinity": 0.87},
            "tags": ["plain", {"name": "named"}, {"id": "urn:tag:only-id"}],
        }
    )
    assert (e.id, e.type, e.popularity, e.affinity) == ("E1", "urn:entity:movie", 0.4, 0.87)
    assert e.tags == ["plain", "named", "urn:tag:only-id"]
    assert Entity.from_raw({"entity_id": "E2", "name": "M"}).affinity is None


# -- transport behaviour ------------------------------------------------------


def test_retries_429_then_succeeds(mock, make_client):
    c = make_client(mock[1])
    assert c.search("ratelimit")
    assert c.stats["requests"] == 2 and c.stats["retries"] == 1


def test_does_not_retry_400(mock, make_client):
    c = make_client(mock[1])
    with pytest.raises(QlooError) as ei:
        c.search("badrequest")
    assert ei.value.status == 400
    assert c.stats["requests"] == 1


def test_error_never_contains_key(mock, make_client):
    c = make_client(mock[1], api_key="SECRET-KEY-123")
    with pytest.raises(QlooError) as ei:
        c.search("badrequest")
    assert "SECRET-KEY-123" not in str(ei.value)
    assert "SECRET-KEY-123" not in (ei.value.body or "")


def test_cache_prevents_repeat_requests(mock, make_client):
    server, url = mock
    c = make_client(url)
    c.search("Sholay")
    c.search("Sholay")
    assert len(server.recorded) == 1
    assert c.stats["cache_hits"] == 1


class _FakeResponse:
    status_code = 200
    headers: dict = {}
    text = "{}"

    def json(self):
        return {"results": []}


class _FakeSession:
    def __init__(self, exc: Exception | None = None):
        self.calls: list[tuple] = []
        self.exc = exc

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        if self.exc:
            raise self.exc
        return _FakeResponse()


def test_sends_key_in_x_api_key_header():
    s = _FakeSession()
    QlooClient(api_key="k", base_url="http://h", cache_path=None, session=s).search("x")
    url, _, headers = s.calls[0]
    assert url == "http://h/search"
    assert headers["X-Api-Key"] == "k"


def test_network_errors_retry_then_raise_without_leaking_url():
    s = _FakeSession(exc=requests.ConnectionError("boom http://secret-host"))
    c = QlooClient(api_key="k", base_url="http://h", cache_path=None, session=s, max_retries=2, sleep=lambda x: None)
    with pytest.raises(QlooError, match="Network error") as ei:
        c.search("x")
    assert len(s.calls) == 3
    assert "secret-host" not in str(ei.value)
