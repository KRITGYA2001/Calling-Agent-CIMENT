import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.services import db

_LEGACY_JSON = Path(__file__).resolve().parent.parent / "data" / "calls.json"  # pre-SQLite storage, imported once


@dataclass
class CallState:
    call_id: str
    # dialling | in_progress | escalated | completed | declined | callback | ended
    status: str = "in_progress"
    mode: str = "phone"  # phone | web
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    lead_id: str | None = None
    lead_name: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)  # field_id -> prefilled | voice
    failures: dict[str, int] = field(default_factory=dict)  # field_id -> failed capture attempts
    validation_errors: int = 0
    consent: bool | None = None
    transcript: list[dict] = field(default_factory=list)  # [{role, text, ts}]
    signals: list[dict] = field(default_factory=list)  # [{type, text, ts}]
    events: list[dict] = field(default_factory=list)  # activity timeline [{kind, text, ts}]
    escalation: dict | None = None  # {category, reason, summary_for_human, ts, auto}
    outcome: str | None = None  # completed | escalated | declined | callback | no_answer | dropped
    callback_time: str | None = None
    submission: dict | None = None  # sandbox receipt
    human_joined_at: float | None = None
    dnc_check: dict | None = None
    recording_url: str | None = None
    resume_section: str | None = None
    summary: str | None = None  # Vapi's post-call summary
    ended_reason: str | None = None

    def event(self, kind: str, text: str) -> None:
        self.events.append({"kind": kind, "text": text, "ts": time.time()})

    def to_dict(self) -> dict:
        return asdict(self)


class CallStateStore:
    """In-memory call state (persisted to SQLite) + pub/sub for live dashboard updates via SSE."""

    def __init__(self) -> None:
        self._calls: dict[str, CallState] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._global: list[asyncio.Queue] = []
        self._load()

    def _load(self) -> None:
        try:
            rows = db.load_calls()
            if not rows and _LEGACY_JSON.exists():  # one-time import of the old JSON file
                rows = json.loads(_LEGACY_JSON.read_text(encoding="utf-8"))
                for raw in rows:
                    db.save_call(raw)
                _LEGACY_JSON.rename(_LEGACY_JSON.with_suffix(".json.imported"))
            for raw in rows:
                self._calls[raw["call_id"]] = CallState(**raw)
        except (OSError, ValueError, TypeError):
            pass

    def _save(self, call: CallState) -> None:
        try:
            db.save_call(call.to_dict())
        except Exception:  # noqa: BLE001 - storage trouble must never break a live call
            pass

    def get_or_create(self, call_id: str) -> CallState:
        if call_id not in self._calls:
            self._calls[call_id] = CallState(call_id=call_id)
        return self._calls[call_id]

    def get(self, call_id: str) -> CallState | None:
        return self._calls.get(call_id)

    def list_recent(self, limit: int = 50) -> list[CallState]:
        return sorted(self._calls.values(), key=lambda c: c.started_at, reverse=True)[:limit]

    def all(self) -> list[CallState]:
        return list(self._calls.values())

    async def publish(self, call_id: str) -> None:
        call = self._calls.get(call_id)
        if call is None:
            return
        self._save(call)
        data = call.to_dict()
        for queue in self._subscribers.get(call_id, []):
            await queue.put(data)
        for queue in self._global:
            await queue.put(data)

    def subscribe(self, call_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(call_id, []).append(queue)
        return queue

    def unsubscribe(self, call_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(call_id, [])
        if queue in subs:
            subs.remove(queue)

    def subscribe_all(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._global.append(queue)
        return queue

    def unsubscribe_all(self, queue: asyncio.Queue) -> None:
        if queue in self._global:
            self._global.remove(queue)


store = CallStateStore()
