"""SQLite persistence for anonymous sessions, attempts and learning evidence."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Sequence
from uuid import uuid4

from server.core.activity import active_seconds


class NotFoundError(LookupError):
    pass


class RevisionConflictError(RuntimeError):
    pass


class IdempotencyConflictError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _insert_dialogue(
    db: sqlite3.Connection, session_id: str, attempt_id: str, node_id: str,
    rows: Sequence[tuple[str, str]],
) -> None:
    """Append spoken turns. Ordinal runs across the attempt, not per node, so
    the transcript reads in the order the learner actually lived it."""
    if not rows:
        return
    start = int(db.execute(
        "SELECT COALESCE(MAX(ordinal), 0) n FROM dialogue_turns WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()["n"])
    for offset, (speaker, said) in enumerate(rows, start=1):
        db.execute(
            "INSERT INTO dialogue_turns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid4()), session_id, attempt_id, node_id, start + offset,
             speaker, said, 0, iso_now()),
        )


def payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class Store:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    scenario_id TEXT NOT NULL,
                    scenario_version TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    assisted INTEGER NOT NULL DEFAULT 0,
                    current_node_id TEXT NOT NULL,
                    active_seconds INTEGER NOT NULL DEFAULT 0,
                    model_wait_seconds INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    attempt_id TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
                    client_event_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, client_event_id)
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    attempt_id TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
                    skill_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    observed_response TEXT NOT NULL,
                    interpretation TEXT,
                    policy_clause_ids TEXT NOT NULL,
                    assisted INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skill_projection (
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    skill_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, skill_id)
                );
                CREATE TABLE IF NOT EXISTS model_calls (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dialogue_turns (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    attempt_id TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
                    node_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    speaker TEXT NOT NULL,
                    body TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity_events (
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    attempt_id TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
                    client_event_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, client_event_id)
                );
                """
            )

    def create_session(self, display_name: str, lifetime_hours: int = 24) -> tuple[str, dict[str, Any]]:
        token = secrets.token_urlsafe(32)
        session_id = str(uuid4())
        created_at = utc_now()
        expires_at = created_at + timedelta(hours=lifetime_hours)
        record = {
            "id": session_id,
            "display_name": display_name,
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                (session_id, hash_token(token), display_name, record["expires_at"], iso_now()),
            )
        return token, record

    def get_session(self, token: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT id, display_name, expires_at FROM sessions WHERE token_hash = ?",
                (hash_token(token),),
            ).fetchone()
        if not row:
            return None
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        return dict(row) if expires_at > utc_now() else None

    def delete_session(self, session_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def create_attempt(
        self, session_id: str, scenario_id: str, scenario_version: str, mode: str,
        start_node_id: str, *, assisted: bool = False,
    ) -> dict[str, Any]:
        attempt_id = str(uuid4())
        timestamp = iso_now()
        with self.connect() as db:
            db.execute(
                """INSERT INTO attempts
                (id, session_id, scenario_id, scenario_version, mode, status, revision,
                 assisted, current_node_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'in_progress', 0, ?, ?, ?, ?)""",
                (attempt_id, session_id, scenario_id, scenario_version, mode, int(assisted), start_node_id, timestamp, timestamp),
            )
        return self.get_attempt(session_id, attempt_id)

    def get_attempt(self, session_id: str, attempt_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM attempts WHERE id = ? AND session_id = ?", (attempt_id, session_id)
            ).fetchone()
        if not row:
            raise NotFoundError("Attempt not found")
        result = dict(row)
        result["assisted"] = bool(result["assisted"])
        return result

    def find_event_response(
        self, session_id: str, client_event_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload_hash, response_json FROM events WHERE session_id = ? AND client_event_id = ?",
                (session_id, client_event_id),
            ).fetchone()
        if not row:
            return None
        if row["payload_hash"] != payload_digest(payload):
            raise IdempotencyConflictError("Event ID was already used with a different payload")
        return json.loads(row["response_json"]) if row["response_json"] else None

    def apply_transition(
        self,
        *,
        session_id: str,
        attempt_id: str,
        client_event_id: str,
        expected_revision: int,
        request_payload: dict[str, Any],
        next_node_id: str,
        effect: str,
        skill_id: str | None,
        state: str | None,
        observed_response: str,
        interpretation: str | None,
        policy_clause_ids: list[str],
        response_builder,
        dialogue_rows: Sequence[tuple[str, str]] = (),
        resolve_dialogue: bool = False,
        arrival_line: str = "",
    ) -> dict[str, Any]:
        digest = payload_digest(request_payload)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT payload_hash, response_json FROM events WHERE session_id = ? AND client_event_id = ?",
                (session_id, client_event_id),
            ).fetchone()
            if prior:
                if prior["payload_hash"] != digest:
                    raise IdempotencyConflictError("Event ID was already used with a different payload")
                return json.loads(prior["response_json"])
            attempt = db.execute(
                "SELECT * FROM attempts WHERE id = ? AND session_id = ?", (attempt_id, session_id)
            ).fetchone()
            if not attempt:
                raise NotFoundError("Attempt not found")
            if attempt["revision"] != expected_revision:
                raise RevisionConflictError("Attempt revision is stale")
            if attempt["status"] != "in_progress":
                raise RevisionConflictError("Attempt is already complete")

            new_revision = expected_revision + 1
            completed = effect == "completed" or next_node_id.endswith("_complete")
            status = "completed" if completed else "in_progress"
            evidence_id = None
            resolved_state = state
            if skill_id and state:
                if state == "pass":
                    resolved_state = (
                        "demonstrated"
                        if attempt["mode"] == "verification" and not bool(attempt["assisted"])
                        else "practiced"
                    )
                evidence_id = str(uuid4())
                db.execute(
                    """INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        evidence_id,
                        session_id,
                        attempt_id,
                        skill_id,
                        attempt["scenario_id"],
                        attempt["current_node_id"],
                        observed_response,
                        interpretation,
                        json.dumps(policy_clause_ids),
                        attempt["assisted"],
                        iso_now(),
                    ),
                )
                current = db.execute(
                    "SELECT state FROM skill_projection WHERE session_id = ? AND skill_id = ?",
                    (session_id, skill_id),
                ).fetchone()
                if not current or current["state"] != "demonstrated":
                    db.execute(
                        """INSERT INTO skill_projection VALUES (?, ?, ?, ?)
                        ON CONFLICT(session_id, skill_id) DO UPDATE SET
                          state = excluded.state, updated_at = excluded.updated_at""",
                        (session_id, skill_id, resolved_state, iso_now()),
                    )
            db.execute(
                """UPDATE attempts SET current_node_id = ?, revision = ?, status = ?, updated_at = ?
                WHERE id = ? AND session_id = ?""",
                (next_node_id, new_revision, status, iso_now(), attempt_id, session_id),
            )
            spoken_node_id = attempt["current_node_id"]
            _insert_dialogue(db, session_id, attempt_id, spoken_node_id, dialogue_rows)
            if resolve_dialogue:
                # The arc is over; these rounds stay on screen but stop counting.
                db.execute(
                    "UPDATE dialogue_turns SET resolved = 1 WHERE attempt_id = ? AND node_id = ?",
                    (attempt_id, spoken_node_id),
                )
            if arrival_line and next_node_id != spoken_node_id:
                _insert_dialogue(
                    db, session_id, attempt_id, next_node_id, [("npc", arrival_line)]
                )
            dialogue = [
                {"node_id": row["node_id"], "speaker": row["speaker"], "text": row["body"],
                 "resolved": bool(row["resolved"])}
                for row in db.execute(
                    """SELECT node_id, speaker, body, resolved FROM dialogue_turns
                    WHERE attempt_id = ? ORDER BY ordinal""",
                    (attempt_id,),
                ).fetchall()
            ]
            response = response_builder(
                dict(attempt), new_revision, status, evidence_id, resolved_state, dialogue
            )
            db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()), session_id, attempt_id, client_event_id, digest,
                    json.dumps(response, ensure_ascii=False), iso_now(),
                ),
            )
            return response

    def mark_assisted(
        self, session_id: str, attempt_id: str, expected_revision: int, client_event_id: str
    ) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            attempt = db.execute(
                "SELECT * FROM attempts WHERE id = ? AND session_id = ?", (attempt_id, session_id)
            ).fetchone()
            if not attempt:
                raise NotFoundError("Attempt not found")
            if attempt["revision"] != expected_revision:
                raise RevisionConflictError("Attempt revision is stale")
            revision = expected_revision + 1
            db.execute(
                "UPDATE attempts SET assisted = 1, revision = ?, updated_at = ? WHERE id = ?",
                (revision, iso_now(), attempt_id),
            )
            return {"attempt_id": attempt_id, "revision": revision, "assisted": True}

    def rewind(
        self, session_id: str, attempt_id: str, expected_revision: int, target_node_id: str
    ) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            attempt = db.execute(
                "SELECT * FROM attempts WHERE id = ? AND session_id = ?", (attempt_id, session_id)
            ).fetchone()
            if not attempt:
                raise NotFoundError("Attempt not found")
            if attempt["revision"] != expected_revision:
                raise RevisionConflictError("Attempt revision is stale")
            db.execute(
                "UPDATE attempts SET current_node_id = ?, revision = ?, updated_at = ? WHERE id = ?",
                (target_node_id, expected_revision + 1, iso_now(), attempt_id),
            )
        return self.get_attempt(session_id, attempt_id)

    def dialogue(
        self, session_id: str, attempt_id: str, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        """The conversation so far, oldest first: whole attempt, or one node."""
        query = """SELECT node_id, speaker, body, resolved FROM dialogue_turns
                WHERE session_id = ? AND attempt_id = ?"""
        params: list[Any] = [session_id, attempt_id]
        if node_id is not None:
            query += " AND node_id = ?"
            params.append(node_id)
        with self.connect() as db:
            rows = db.execute(query + " ORDER BY ordinal", params).fetchall()
        return [
            {"node_id": row["node_id"], "speaker": row["speaker"], "text": row["body"],
             "resolved": bool(row["resolved"])}
            for row in rows
        ]

    def append_dialogue(
        self, session_id: str, attempt_id: str, node_id: str, rows: Sequence[tuple[str, str]]
    ) -> None:
        with self.connect() as db:
            _insert_dialogue(db, session_id, attempt_id, node_id, rows)

    def clear_dialogue(self, session_id: str, attempt_id: str, node_id: str) -> None:
        """Rewinding replays the situation, so the pressure starts over too."""
        with self.connect() as db:
            db.execute(
                "DELETE FROM dialogue_turns WHERE session_id = ? AND attempt_id = ? AND node_id = ?",
                (session_id, attempt_id, node_id),
            )

    def last_answered_node(self, session_id: str, attempt_id: str) -> str | None:
        """Node the learner last answered from, i.e. the decision point to rewind to."""
        with self.connect() as db:
            row = db.execute(
                """SELECT node_id FROM evidence WHERE session_id = ? AND attempt_id = ?
                ORDER BY created_at DESC, rowid DESC LIMIT 1""",
                (session_id, attempt_id),
            ).fetchone()
        return str(row["node_id"]) if row else None

    def record_activity(self, session_id: str, attempt_id: str, client_event_id: str, kind: str) -> None:
        self.get_attempt(session_id, attempt_id)
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO activity_events VALUES (?, ?, ?, ?, ?)",
                (session_id, attempt_id, client_event_id, kind, iso_now()),
            )
        self.refresh_active_seconds(session_id, attempt_id)

    def model_calls(self, session_id: str) -> int:
        with self.connect() as db:
            row = db.execute(
                "SELECT COUNT(*) n FROM model_calls WHERE session_id = ?", (session_id,)
            ).fetchone()
        return int(row["n"])

    def record_model_call(self, session_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO model_calls VALUES (?, ?, ?)", (str(uuid4()), session_id, iso_now())
            )

    def add_model_wait(self, session_id: str, attempt_id: str, seconds: float) -> None:
        """Waiting on a model is reported separately from active learning time."""
        if seconds <= 0:
            return
        with self.connect() as db:
            db.execute(
                """UPDATE attempts SET model_wait_seconds = model_wait_seconds + ?, updated_at = ?
                WHERE id = ? AND session_id = ?""",
                (int(round(seconds)), iso_now(), attempt_id, session_id),
            )

    def refresh_active_seconds(self, session_id: str, attempt_id: str) -> int:
        """Recompute the attempt's active time from its own activity events."""
        with self.connect() as db:
            rows = db.execute(
                """SELECT kind, created_at FROM activity_events
                WHERE session_id = ? AND attempt_id = ? ORDER BY created_at""",
                (session_id, attempt_id),
            ).fetchall()
            events = [
                (str(row["kind"]), datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00")))
                for row in rows
            ]
            seconds = active_seconds(events)
            db.execute(
                "UPDATE attempts SET active_seconds = ?, updated_at = ? WHERE id = ? AND session_id = ?",
                (seconds, iso_now(), attempt_id, session_id),
            )
        return seconds

    def coaching_candidates(self, session_id: str, skill_id: str) -> list[dict[str, Any]]:
        """Recent non-coaching evidence, with the source content version attached."""
        with self.connect() as db:
            rows = db.execute(
                """SELECT e.id AS evidence_id, e.scenario_id, e.node_id,
                          e.observed_response, e.interpretation, e.created_at,
                          a.scenario_version
                   FROM evidence AS e
                   JOIN attempts AS a ON a.id = e.attempt_id AND a.session_id = e.session_id
                   WHERE e.session_id = ? AND e.skill_id = ? AND e.scenario_id <> 'ethics-review'
                   ORDER BY e.created_at DESC, e.rowid DESC""",
                (session_id, skill_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def passport(self, session_id: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
        with self.connect() as db:
            states = {
                row["skill_id"]: row["state"]
                for row in db.execute(
                    "SELECT skill_id, state FROM skill_projection WHERE session_id = ?", (session_id,)
                )
            }
            evidence_rows = db.execute(
                "SELECT * FROM evidence WHERE session_id = ? ORDER BY created_at", (session_id,)
            ).fetchall()
            timing = db.execute(
                """SELECT COALESCE(SUM(active_seconds), 0) active_seconds,
                COALESCE(SUM(model_wait_seconds), 0) model_wait_seconds
                FROM attempts WHERE session_id = ?""",
                (session_id,),
            ).fetchone()
        evidence_by_skill: dict[str, list[dict[str, Any]]] = {}
        for row in evidence_rows:
            item = {
                "id": row["id"],
                "skill_id": row["skill_id"],
                "scenario_id": row["scenario_id"],
                "node_id": row["node_id"],
                "observed_response": row["observed_response"],
                "interpretation": row["interpretation"],
                "policy_clause_ids": json.loads(row["policy_clause_ids"]),
                "assisted": bool(row["assisted"]),
                "created_at": row["created_at"],
            }
            evidence_by_skill.setdefault(item["skill_id"], []).append(item)
        labels = {
            "clarify_context": "Gather relevant facts",
            "conflict_awareness": "Recognize risks and applicable conditions",
            "communicate_boundary": "Explain the decision and next step",
        }
        skills = [
            {
                "skill_id": skill_id,
                "label": label,
                "state": states.get(skill_id, "unseen"),
                "evidence": evidence_by_skill.get(skill_id, []),
            }
            for skill_id, label in labels.items()
        ]
        return skills, dict(timing)
