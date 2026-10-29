"""Local-first SQLite storage for Echoes.

Ensures complete patient data privacy (HIPAA/GDPR compliant local-first design).
Maintains patient profiles, cultural seeds, session transcripts, and adaptive
feedback loops (lit_up positive signals and upset exclusion blacklists).
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def get_default_db_path() -> str:
    """Returns database path, falling back to writable /tmp in serverless (e.g. Vercel)."""
    if "ECHOES_DB_PATH" in os.environ:
        return os.environ["ECHOES_DB_PATH"]
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = Path("/tmp/echoes.db")
        seed_db = ROOT / "data" / "echoes.db"
        if seed_db.is_file() and not tmp_db.exists():
            try:
                shutil.copy(seed_db, tmp_db)
            except Exception:
                pass
        return str(tmp_db)
    return str(ROOT / "data" / "echoes.db")


DEFAULT_DB_PATH = get_default_db_path()


def _get_conn(db_path: str | None = None) -> sqlite3.Connection:
    target = db_path or get_default_db_path()
    p = Path(target)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class EchoesDB:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_default_db_path()
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                try:
                    conn.execute("PRAGMA journal_mode = WAL;")
                except sqlite3.OperationalError:
                    pass
                conn.executescript(
                    """

                    CREATE TABLE IF NOT EXISTS patients (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        birth_year INTEGER NOT NULL,
                        hometown TEXT NOT NULL,
                        culture TEXT DEFAULT '',
                        notes TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS patient_seeds (
                        id TEXT PRIMARY KEY,
                        patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        entity_type TEXT NOT NULL,
                        qloo_id TEXT DEFAULT '',
                        era TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS patient_feedback (
                        id TEXT PRIMARY KEY,
                        patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                        entity_id TEXT NOT NULL,
                        entity_name TEXT NOT NULL,
                        entity_type TEXT NOT NULL,
                        reaction TEXT CHECK(reaction IN ('lit_up', 'neutral', 'upset')),
                        notes TEXT DEFAULT '',
                        session_id TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        session_data TEXT NOT NULL,
                        comparison_data TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE INDEX IF NOT EXISTS idx_feedback_patient ON patient_feedback(patient_id);
                    CREATE INDEX IF NOT EXISTS idx_sessions_patient ON sessions(patient_id);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    # -- Patients -------------------------------------------------------------

    def upsert_patient(
        self,
        name: str,
        birth_year: int,
        hometown: str,
        culture: str = "",
        notes: str = "",
        patient_id: str | None = None,
    ) -> dict[str, Any]:
        pid = patient_id or f"pat_{uuid.uuid4().hex[:10]}"
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO patients (id, name, birth_year, hometown, culture, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        birth_year = excluded.birth_year,
                        hometown = excluded.hometown,
                        culture = excluded.culture,
                        notes = excluded.notes
                    """,
                    (pid, name, birth_year, hometown, culture, notes),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM patients WHERE id = ?", (pid,)).fetchone()
                return dict(row)
            finally:
                conn.close()

    def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def list_patients(self) -> list[dict[str, Any]]:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                rows = conn.execute("SELECT * FROM patients ORDER BY created_at DESC").fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    # -- Seeds ----------------------------------------------------------------

    def set_seeds(self, patient_id: str, seeds: list[dict[str, Any]]) -> None:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                conn.execute("DELETE FROM patient_seeds WHERE patient_id = ?", (patient_id,))
                for s in seeds:
                    sid = f"seed_{uuid.uuid4().hex[:8]}"
                    conn.execute(
                        """
                        INSERT INTO patient_seeds (id, patient_id, name, entity_type, qloo_id, era)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (sid, patient_id, s.get("name", ""), s.get("type", ""), s.get("qloo_id", ""), s.get("era", "")),
                    )
                conn.commit()
            finally:
                conn.close()

    def get_seeds(self, patient_id: str) -> list[dict[str, Any]]:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                rows = conn.execute(
                    "SELECT * FROM patient_seeds WHERE patient_id = ? ORDER BY created_at ASC",
                    (patient_id,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    # -- Feedback & Exclusion Blacklist ---------------------------------------

    def record_feedback(
        self,
        patient_id: str,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        reaction: str,
        notes: str = "",
        session_id: str = "",
    ) -> dict[str, Any]:
        fid = f"fb_{uuid.uuid4().hex[:8]}"
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO patient_feedback (id, patient_id, entity_id, entity_name, entity_type, reaction, notes, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (fid, patient_id, entity_id, entity_name, entity_type, reaction, notes, session_id),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM patient_feedback WHERE id = ?", (fid,)).fetchone()
                return dict(row)
            finally:
                conn.close()

    def get_feedback_history(self, patient_id: str) -> list[dict[str, Any]]:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                rows = conn.execute(
                    "SELECT * FROM patient_feedback WHERE patient_id = ? ORDER BY created_at DESC",
                    (patient_id,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_adaptive_signals(self, patient_id: str) -> dict[str, list[str]]:
        """Returns positive signals (lit_up) and exclusion blacklist (upset)."""
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                rows = conn.execute(
                    "SELECT entity_id, reaction FROM patient_feedback WHERE patient_id = ?",
                    (patient_id,),
                ).fetchall()
                positive: list[str] = []
                excluded: list[str] = []
                for r in rows:
                    if r["reaction"] == "lit_up" and r["entity_id"] not in positive:
                        positive.append(r["entity_id"])
                    elif r["reaction"] == "upset" and r["entity_id"] not in excluded:
                        excluded.append(r["entity_id"])
                return {"positive_entities": positive, "exclude_entities": excluded}
            finally:
                conn.close()

    # -- Sessions -------------------------------------------------------------

    def save_session(
        self,
        patient_id: str,
        title: str,
        session_data: dict[str, Any],
        comparison_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sid = f"sess_{uuid.uuid4().hex[:10]}"
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO sessions (id, patient_id, title, session_data, comparison_data)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (sid, patient_id, title, json.dumps(session_data), json.dumps(comparison_data or {})),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
                d = dict(row)
                d["session_data"] = json.loads(d["session_data"])
                d["comparison_data"] = json.loads(d["comparison_data"])
                return d
            finally:
                conn.close()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
                if not row:
                    return None
                d = dict(row)
                d["session_data"] = json.loads(d["session_data"])
                d["comparison_data"] = json.loads(d["comparison_data"])
                return d
            finally:
                conn.close()

    def list_sessions(self, patient_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            conn = _get_conn(self.db_path)
            try:
                if patient_id:
                    rows = conn.execute(
                        "SELECT id, patient_id, title, created_at FROM sessions WHERE patient_id = ? ORDER BY created_at DESC",
                        (patient_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, patient_id, title, created_at FROM sessions ORDER BY created_at DESC"
                    ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()
