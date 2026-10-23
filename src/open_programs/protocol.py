"""Versioned stdio author protocol for checking, proposing and solving programs."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, TextIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .cancellation import ActivityCancellation
from .compiler import OpenCompiler
from .evidence import validate_evidence
from .frontend import check
from .model import ContextSnapshot, EvidenceRecord, FrozenModel, ProgramError, ProgramEvent, ProgramRevision, ResolutionBudget, ResolutionResult, SourceBundle
from .store import ProgramStore


class CheckParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: str
    path: str = "<source>"


class InitializeParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    protocol_version: Literal["3.0"] = "3.0"
    client: str = "anonymous-local-client"


class ExplainParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    object_id: str
    context: ContextSnapshot | None = None


class RevisionParams(CheckParams):
    program_id: str
    expected_revision: str | None


class ResolveParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    program_id: str
    expected_revision: str
    goal: str
    input_json: str = "{}"
    budget: ResolutionBudget = ResolutionBudget()


class AnswerParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    program_id: str
    expected_revision: str
    request_id: str
    answer: str = Field(min_length=1)


class EventsParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    program_id: str
    after: int = Field(default=0, ge=0)


class IdParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    object_id: str


class AuthorActivity(FrozenModel):
    activity_id: str
    program_id: str
    revision: str
    goal: str
    state: Literal["running", "blocked", "completed", "cancelled", "failed"] = "running"
    request_id: str = ""
    result: ResolutionResult | None = None
    error: str = ""


def _error(identifier: object, code: int, message: str, detail: str = "") -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message, "data": {"code": detail}}}


class AuthorProtocol:
    def __init__(self, store: ProgramStore, compiler: OpenCompiler | None = None) -> None:
        self.store = store
        self.compiler = compiler
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nexa-author")
        self._cancellations: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(2)

    def handle(self, payload: object) -> dict[str, object] | None:
        if (not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str)
                or type(payload.get("id")) not in {str, int, type(None)} or not isinstance(payload.get("params", {}), dict)
                or set(payload) - {"jsonrpc", "id", "method", "params"}):
            return _error(None, -32600, "Invalid request")
        identifier = payload.get("id")
        try:
            result = self._dispatch(payload["method"], payload.get("params", {}))
            response = {"jsonrpc": "2.0", "id": identifier, "result": result}
        except ValidationError:
            response = _error(identifier, -32602, "Invalid method parameters")
        except ProgramError as error:
            response = _error(identifier, -32601 if error.code == "method_not_found" else -32000, str(error), error.code)
        return response if "id" in payload else None

    def _dispatch(self, method: str, params: object) -> object:
        if method == "initialize":
            InitializeParams.model_validate(params)
            return {"protocol_version": "3.0", "schema_version": 1, "methods": tuple(METHOD_PARAMS), "max_inflight": 2}
        if method == "program/check":
            parsed = CheckParams.model_validate(params)
            return check(SourceBundle(text=parsed.source, path=parsed.path)).model_dump(mode="json")
        if method == "revision/propose":
            return self._propose(RevisionParams.model_validate(params))
        if method == "goal/resolve":
            return self._resolve(ResolveParams.model_validate(params))
        if method == "author/answer":
            return self._answer(AnswerParams.model_validate(params))
        if method == "events/read":
            parsed = EventsParams.model_validate(params)
            return {"events": [{"cursor": cursor, "event": event.model_dump(mode="json")} for cursor, event in self.store.events(parsed.program_id, after=parsed.after)]}
        if method == "evidence/explain":
            parsed = ExplainParams.model_validate(params)
            record = self.store.get(parsed.object_id, EvidenceRecord)
            return {"record": record.model_dump(mode="json"),
                    "validity": validate_evidence(record, parsed.context).model_dump(mode="json") if parsed.context else None}
        if method in {"activity/read", "activity/cancel"}:
            identifier = IdParams.model_validate(params).object_id
            activity = self.store.reference("activity:" + identifier, AuthorActivity)
            if activity is None:
                raise ProgramError("activity_missing", identifier)
            if method == "activity/cancel" and activity.state == "running":
                ActivityCancellation(self.store, identifier).set()
            return activity.model_dump(mode="json")
        raise ProgramError("method_not_found", method)

    def _propose(self, params: RevisionParams) -> dict[str, object]:
        report = check(SourceBundle(text=params.source, path=params.path))
        if not report.ok or report.program is None:
            return {"diagnostics": [item.model_dump(mode="json") for item in report.diagnostics]}
        revision = ProgramRevision(program_id=params.program_id, parent=params.expected_revision, program=report.program)
        digest = self.store.commit_revision(params.expected_revision, revision, [ProgramEvent(kind="revision_proposed", object_id=revision.digest)])
        return {"revision": digest, "obligations": report.obligations}

    def _resolve(self, params: ResolveParams) -> dict[str, str]:
        if self.compiler is None:
            raise ProgramError("model_unavailable", "No compiler environment is bound")
        revision = self.store.current_revision(params.program_id)
        if revision is None or revision.digest != params.expected_revision:
            raise ProgramError("revision_conflict", params.program_id)
        goal = next((goal for goal in revision.program.goals if goal.name == params.goal), None)
        if goal is None:
            raise ProgramError("unknown_goal", params.goal)
        if not self._slots.acquire(blocking=False):
            raise ProgramError("author_busy", "At most two author resolutions may be active", retryable=True)
        activity_id = uuid.uuid4().hex
        activity = AuthorActivity(activity_id=activity_id, program_id=params.program_id, revision=revision.digest, goal=goal.name)
        self.store.set_reference("activity:" + activity_id, None, activity)
        cancel = ActivityCancellation(self.store, activity_id)
        with self._lock:
            self._cancellations[activity_id] = cancel
        self._pool.submit(self._run, activity, params.input_json, cancel, params.budget)
        return {"activity_id": activity_id}

    def _run(self, activity: AuthorActivity, inputs: str, cancel: threading.Event, budget: ResolutionBudget) -> None:
        assert self.compiler is not None
        revision = self.store.get(activity.revision, ProgramRevision)
        goal = next(goal for goal in revision.program.goals if goal.name == activity.goal)
        try:
            result = self.compiler.resolve_goal(goal, input_json=inputs, task_id=activity.activity_id, cancel=cancel, budget=budget)
            state = "completed" if result.status == "accepted" else ("cancelled" if result.status == "cancelled" else "blocked")
            request_id = uuid.uuid4().hex if result.clarification else ""
            updated = activity.model_copy(update={"state": state, "result": result, "request_id": request_id})
            if request_id:
                self.store.set_reference("clarification:" + request_id, None, updated)
        except Exception as error:  # noqa: BLE001 - Persist failures at the background activity boundary.
            updated = activity.model_copy(update={"state": "failed", "error": type(error).__name__})
        self.store.set_reference("activity:" + activity.activity_id, activity.digest, updated)
        with self._lock:
            self._cancellations.pop(activity.activity_id, None)
        self._slots.release()

    def _answer(self, params: AnswerParams) -> dict[str, str]:
        activity = self.store.reference("clarification:" + params.request_id, AuthorActivity)
        if activity is None or activity.program_id != params.program_id:
            raise ProgramError("clarification_missing", params.request_id)
        revision = self.store.current_revision(params.program_id)
        if revision is None or revision.digest != params.expected_revision or activity.revision != revision.digest:
            raise ProgramError("revision_conflict", params.program_id)
        goals = tuple(goal.model_copy(update={"intent": goal.intent + "\nAuthor clarification: " + params.answer}) if goal.name == activity.goal else goal for goal in revision.program.goals)
        updated = ProgramRevision(program_id=params.program_id, parent=revision.digest, program=revision.program.model_copy(update={"goals": goals}))
        self.store.commit_revision(revision.digest, updated, [ProgramEvent(kind="author_answered", object_id=updated.digest, detail=params.request_id)])
        return {"revision": updated.digest}

    def close(self) -> None:
        with self._lock:
            for cancel in self._cancellations.values():
                cancel.set()
        self._pool.shutdown(wait=True)


def serve_stdio(service: AuthorProtocol, input_stream: TextIO, output: TextIO) -> None:
    limit = 2 * 1024 * 1024
    while line := input_stream.readline(limit + 1):
        if len(line) > limit:
            while not line.endswith("\n"):
                line = input_stream.readline(limit + 1)
                if not line:
                    break
            response = _error(None, -32600, "Request exceeds 2 MiB")
        else:
            try:
                response = service.handle(json.loads(line))
            except ValueError:
                response = _error(None, -32700, "Invalid JSON")
        if response is None:
            continue
        output.write(json.dumps(response, ensure_ascii=False) + "\n")
        output.flush()


METHOD_PARAMS: dict[str, type[BaseModel]] = {
    "initialize": InitializeParams, "program/check": CheckParams, "revision/propose": RevisionParams,
    "goal/resolve": ResolveParams, "author/answer": AnswerParams, "events/read": EventsParams,
    "evidence/explain": ExplainParams, "activity/read": IdParams, "activity/cancel": IdParams,
}
