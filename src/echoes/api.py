"""FastAPI REST API server for Echoes.

Provides endpoints for patient intake, Qloo multi-domain search,
agentic reminiscence session synthesis, real-time adaptive feedback loops,
and clinical caregiver care-sheet export.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import ReminiscenceAgent
from .db import EchoesDB
from .mock_server import start_mock
from .presets import PRESETS, get_preset
from .qloo import QlooClient, QlooError, load_env

logger = logging.getLogger("echoes.api")
logging.basicConfig(level=logging.INFO)

ROOT = Path(__file__).resolve().parents[2]


# -- State container ----------------------------------------------------------

class AppState:
    def __init__(self):
        self.db = EchoesDB()
        self.mock_server = None
        self.mock_url = None
        self.is_mock_active = False
        self.client: QlooClient | None = None
        self.agent: ReminiscenceAgent | None = None

    def initialize_client(self, force_mock: bool = False, custom_key: str | None = None) -> None:
        load_env(str(ROOT / ".env"))
        api_key = (custom_key or os.environ.get("QLOO_API_KEY", "")).strip()

        if force_mock or not api_key:
            if not self.mock_server:
                self.mock_server, self.mock_url = start_mock(0)
            self.client = QlooClient(
                api_key="mock-key",
                base_url=self.mock_url,
                cache_path=None,
            )
            self.is_mock_active = True
            logger.info(f"Initialized in [MOCK] offline mode using {self.mock_url}")
        else:
            cache_path = str(ROOT / ".cache" / "qloo.sqlite")
            self.client = QlooClient(api_key=api_key, cache_path=cache_path)
            self.is_mock_active = False
            logger.info("Initialized with Live Qloo API")

        self.agent = ReminiscenceAgent(self.client, self.db)


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    state.initialize_client()
    yield
    # Shutdown
    if state.mock_server:
        state.mock_server.shutdown()


app = FastAPI(
    title="Echoes API - Cultural Reminiscence Companion",
    description="Agentic Cultural Reminiscence platform powered by Qloo's Taste Graph for Alzheimer's & Dementia Care.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Pydantic Schemas ---------------------------------------------------------

class SeedInput(BaseModel):
    name: str
    type: str = "urn:entity:artist"
    era: str = ""
    qloo_id: str = ""


class PatientCreate(BaseModel):
    name: str
    birth_year: int = Field(..., ge=1900, le=2015)
    hometown: str
    culture: str = ""
    notes: str = ""
    seeds: list[SeedInput] = []


class SessionGenerateRequest(BaseModel):
    patient_id: str | None = None
    name: str
    birth_year: int = Field(..., ge=1900, le=2015)
    hometown: str
    culture: str = ""
    seeds: list[SeedInput] = []
    preset_id: str | None = None


class FeedbackRequest(BaseModel):
    patient_id: str
    entity_id: str
    entity_name: str
    entity_type: str
    reaction: str = Field(..., regex="^(lit_up|neutral|upset)$")
    notes: str = ""
    session_id: str = ""


class SearchRequest(BaseModel):
    query: str
    types: str | None = None
    take: int = 5


class ToggleMockRequest(BaseModel):
    enable_mock: bool
    api_key: str | None = None


# -- Endpoints ----------------------------------------------------------------

@app.get("/api/status")
def get_status() -> dict[str, Any]:
    """Returns engine health, active mode (live vs mock), and cache statistics."""
    has_env_key = bool(os.environ.get("QLOO_API_KEY", "").strip())
    patients = state.db.list_patients()
    sessions = state.db.list_sessions()

    return {
        "status": "online",
        "mode": "mock" if state.is_mock_active else "live",
        "api_key_configured": has_env_key,
        "base_url": state.client.base_url if state.client else None,
        "stats": state.client.stats if state.client else {},
        "total_patients": len(patients),
        "total_sessions": len(sessions),
    }


@app.post("/api/toggle-mock")
def toggle_mock(req: ToggleMockRequest) -> dict[str, Any]:
    """Allows toggling between Live Qloo API and Offline Mock at runtime."""
    state.initialize_client(force_mock=req.enable_mock, custom_key=req.api_key)
    return {
        "success": True,
        "mode": "mock" if state.is_mock_active else "live",
        "base_url": state.client.base_url,
    }


@app.get("/api/presets")
def list_presets() -> list[dict[str, Any]]:
    """Returns pre-configured global personas for 1-click hackathon evaluation."""
    return PRESETS


@app.get("/api/presets/{preset_id}")
def get_preset_detail(preset_id: str) -> dict[str, Any]:
    p = get_preset(preset_id)
    if not p:
        raise HTTPException(status_code=404, detail="Preset not found")
    return p


@app.post("/api/search")
def search_entities(req: SearchRequest) -> dict[str, Any]:
    """Autocomplete search against Qloo's taste graph."""
    if not req.query.strip():
        return {"results": []}
    try:
        hits = state.client.search(query=req.query, types=req.types, take=req.take)
        return {
            "results": [
                {
                    "id": h.id,
                    "name": h.name,
                    "type": h.type,
                    "popularity": h.popularity,
                    "tags": h.tags[:3],
                }
                for h in hits
            ]
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/patients")
def create_patient(req: PatientCreate) -> dict[str, Any]:
    """Creates or updates a care recipient profile."""
    patient = state.db.upsert_patient(
        name=req.name,
        birth_year=req.birth_year,
        hometown=req.hometown,
        culture=req.culture,
        notes=req.notes,
    )
    if req.seeds:
        state.db.set_seeds(patient["id"], [s.dict() for s in req.seeds])

    seeds = state.db.get_seeds(patient["id"])
    patient["seeds"] = seeds
    patient["golden_era"] = f"{req.birth_year + 12} - {req.birth_year + 28}"
    return patient


@app.get("/api/patients")
def list_patients() -> list[dict[str, Any]]:
    """Lists all stored patient profiles."""
    patients = state.db.list_patients()
    for p in patients:
        p["seeds"] = state.db.get_seeds(p["id"])
        signals = state.db.get_adaptive_signals(p["id"])
        p["positive_count"] = len(signals.get("positive_entities", []))
        p["excluded_count"] = len(signals.get("exclude_entities", []))
        p["golden_era"] = f"{p['birth_year'] + 12} - {p['birth_year'] + 28}"
    return patients


@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str) -> dict[str, Any]:
    """Retrieves full profile, seeds, feedback reactions, and session transcripts."""
    p = state.db.get_patient(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    p["seeds"] = state.db.get_seeds(patient_id)
    p["feedback"] = state.db.get_feedback_history(patient_id)
    p["adaptive_signals"] = state.db.get_adaptive_signals(patient_id)
    p["sessions"] = state.db.list_sessions(patient_id)
    p["golden_era"] = f"{p['birth_year'] + 12} - {p['birth_year'] + 28}"
    return p


@app.post("/api/sessions/generate")
def generate_session(req: SessionGenerateRequest) -> dict[str, Any]:
    """Composes a 5-chapter Reminiscence Session + side-by-side LLM baseline."""
    try:
        result = state.agent.compose_session(
            patient_id=req.patient_id,
            name=req.name,
            birth_year=req.birth_year,
            hometown=req.hometown,
            culture=req.culture,
            seed_inputs=[s.dict() for s in req.seeds] if req.seeds else None,
            preset_id=req.preset_id,
        )
        return result
    except Exception as e:
        logger.error(f"Session generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/adapt")
def record_adaptation_feedback(req: FeedbackRequest) -> dict[str, Any]:
    """Registers caregiver feedback (lit_up / neutral / upset).

    Distressing items are instantly excluded from future Qloo insight queries.
    """
    fb = state.db.record_feedback(
        patient_id=req.patient_id,
        entity_id=req.entity_id,
        entity_name=req.entity_name,
        entity_type=req.entity_type,
        reaction=req.reaction,
        notes=req.notes,
        session_id=req.session_id,
    )
    signals = state.db.get_adaptive_signals(req.patient_id)
    return {
        "success": True,
        "recorded": fb,
        "updated_signals": signals,
        "message": (
            f"'{req.entity_name}' added to safety exclusion blacklist."
            if req.reaction == "upset"
            else f"'{req.entity_name}' added to positive taste anchors."
        ),
    }


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    """Fetches a saved session with its comparison data."""
    s = state.db.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@app.get("/api/patients/{patient_id}/care-sheet")
def get_care_sheet(patient_id: str) -> dict[str, Any]:
    """Generates an exportable clinical Caregiver Care Sheet."""
    p = state.db.get_patient(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")

    seeds = state.db.get_seeds(patient_id)
    feedback = state.db.get_feedback_history(patient_id)
    signals = state.db.get_adaptive_signals(patient_id)
    sessions = state.db.list_sessions(patient_id)

    lit_up = [f for f in feedback if f["reaction"] == "lit_up"]
    upset = [f for f in feedback if f["reaction"] == "upset"]
    bump = f"{p['birth_year'] + 12} - {p['birth_year'] + 28}"

    markdown_sheet = f"""# Echoes Caregiver Care Sheet & Sensory Profile
**Recipient:** {p['name']} | **Birth Year:** {p['birth_year']} | **Hometown:** {p['hometown']}
**Golden Reminiscence Window:** {bump} | **Culture:** {p['culture'] or 'General'}

---

## 🌟 High-Affinity Memory Triggers (Lit Up)
These cultural anchors consistently spark autobiographical memory, smiling, and calm engagement:
"""
    if lit_up:
        for item in lit_up:
            markdown_sheet += f"- **{item['entity_name']}** ({item['entity_type'].split(':')[-1]})\n"
    else:
        for s in seeds:
            markdown_sheet += f"- **{s['name']}** ({s['entity_type'].split(':')[-1]})\n"

    markdown_sheet += f"""
---

## 🚫 Critical Safety Exclusions (Avoid Agitation)
The following topics, songs, or entities caused distress or sadness and are strictly blacklisted:
"""
    if upset:
        for item in upset:
            markdown_sheet += f"- ❌ **{item['entity_name']}** ({item['entity_type'].split(':')[-1]}) - *Excluded on {item['created_at'][:10]}*\n"
    else:
        markdown_sheet += "- *No negative triggers recorded yet.*\n"

    markdown_sheet += f"""
---

## 🩺 Clinical Notes for Visiting Caregivers & Nursing Staff
1. **Never Quiz:** Do not ask *"Do you remember this song?"*. Say *"Listen to this melody with me."*
2. **Sensory Anchors:** Pair music with familiar regional aromas (tea, spices, familiar baked treats).
3. **Session Pacing:** Keep sessions under 20 minutes to prevent cognitive fatigue.

*Generated by Echoes • Grounded by Qloo Cultural AI*
"""

    return {
        "patient": p,
        "golden_era": bump,
        "lit_up_count": len(lit_up),
        "upset_count": len(upset),
        "total_sessions_conducted": len(sessions),
        "markdown": markdown_sheet,
    }


# Mount static web files if directory exists
web_dir = ROOT / "web"
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="static")
