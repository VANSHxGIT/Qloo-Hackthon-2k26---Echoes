import pytest

from echoes.mock_server import start_mock
from echoes.qloo import QlooClient


@pytest.fixture
def mock():
    """A running [MOCK] server: (server, base_url). Fabricated data, tests only."""
    server, url = start_mock(0)
    yield server, url
    server.shutdown()


@pytest.fixture
def make_client():
    def _make(url: str, api_key: str = "test-key", **kw) -> QlooClient:
        kw.setdefault("cache_path", None)
        kw.setdefault("sleep", lambda s: None)
        return QlooClient(api_key=api_key, base_url=url, **kw)

    return _make
