import pytest
from fastapi.testclient import TestClient

from echoes.agent import ReminiscenceAgent, compute_reminiscence_bump
from echoes.api import app, state
from echoes.db import EchoesDB
from echoes.mock_server import start_mock
from echoes.qloo import ARTIST, MOVIE, QlooClient


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_echoes.db"
    return EchoesDB(str(db_file))


def test_reminiscence_bump_window():
    start, end = compute_reminiscence_bump(1948)
    assert start == 1960
    assert end == 1976


def test_db_patient_crud_and_feedback(temp_db):
    p = temp_db.upsert_patient(
        name="Test Patient",
        birth_year=1945,
        hometown="Delhi",
        culture="Hindi",
        notes="Loves old songs",
    )
    assert p["id"].startswith("pat_")
    assert p["name"] == "Test Patient"

    # Add seeds
    temp_db.set_seeds(
        p["id"],
        [{"name": "Kishore Kumar", "type": ARTIST}, {"name": "Sholay", "type": MOVIE}],
    )
    seeds = temp_db.get_seeds(p["id"])
    assert len(seeds) == 2
    assert seeds[0]["name"] == "Kishore Kumar"

    # Record feedback
    temp_db.record_feedback(
        patient_id=p["id"],
        entity_id="qloo-artist-1",
        entity_name="Kishore Kumar",
        entity_type=ARTIST,
        reaction="lit_up",
    )
    temp_db.record_feedback(
        patient_id=p["id"],
        entity_id="qloo-movie-bad",
        entity_name="Sad Movie",
        entity_type=MOVIE,
        reaction="upset",
    )

    signals = temp_db.get_adaptive_signals(p["id"])
    assert "qloo-artist-1" in signals["positive_entities"]
    assert "qloo-movie-bad" in signals["exclude_entities"]


def test_agent_session_composition(temp_db, mock):
    server, base_url = mock
    client = QlooClient(api_key="mock", base_url=base_url, cache_path=None)
    agent = ReminiscenceAgent(client, temp_db)

    p = temp_db.upsert_patient(name="Asha", birth_year=1950, hometown="Delhi", culture="Hindi")
    result = agent.compose_session(
        patient_id=p["id"],
        name="Asha",
        birth_year=1950,
        hometown="Delhi",
        culture="Hindi",
        seed_inputs=[{"name": "Kishore Kumar", "type": ARTIST}],
    )

    assert "session" in result
    assert "generic_baseline" in result
    session = result["session"]
    assert len(session["chapters"]) > 0
    assert session["stats"]["total_anchors"] > 0
    assert "stats" in session


def test_api_endpoints_end_to_end(temp_db):
    old_db = state.db
    old_agent = state.agent
    state.db = temp_db
    if state.client:
        state.agent = ReminiscenceAgent(state.client, temp_db)
    try:
        with TestClient(app) as client:
        # 1. Status
            res = client.get("/api/status")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "online"

        # 2. Presets
        res = client.get("/api/presets")
        assert res.status_code == 200
        presets = res.json()
        assert len(presets) >= 5
        delhi_preset = next(p for p in presets if p["id"] == "delhi_1942")
        assert delhi_preset["name"] == "Dadi Savitri"

        # 3. Create Patient
        res = client.post(
            "/api/patients",
            json={
                "name": "Maria",
                "birth_year": 1948,
                "hometown": "São Paulo",
                "culture": "Brazilian",
                "seeds": [{"name": "Elis Regina", "type": ARTIST}],
            },
        )
        assert res.status_code == 200
        pat = res.json()
        pid = pat["id"]

        # 4. Generate Session
        res = client.post(
            "/api/sessions/generate",
            json={
                "patient_id": pid,
                "name": "Maria",
                "birth_year": 1948,
                "hometown": "São Paulo",
                "preset_id": "saopaulo_1947",
            },
        )
        assert res.status_code == 200
        sess_resp = res.json()
        assert "session" in sess_resp
        assert "chapters" in sess_resp["session"]
        assert len(sess_resp["session"]["chapters"]) >= 3

        # 5. Adapt / Feedback (Record 'upset' reaction)
        res = client.post(
            "/api/sessions/adapt",
            json={
                "patient_id": pid,
                "entity_id": "MOCK-artist-001",
                "entity_name": "Agitating Song",
                "entity_type": ARTIST,
                "reaction": "upset",
            },
        )
        assert res.status_code == 200
        adapt_resp = res.json()
        assert "MOCK-artist-001" in adapt_resp["updated_signals"]["exclude_entities"]

        # 6. Caregiver Care Sheet Export
        res = client.get(f"/api/patients/{pid}/care-sheet")
        assert res.status_code == 200
        sheet = res.json()
        assert "markdown" in sheet
        assert "Agitating Song" in sheet["markdown"]
    finally:
        state.db = old_db
        state.agent = old_agent
