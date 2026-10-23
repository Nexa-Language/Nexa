"""Durable cooperative cancellation shared by independent local clients."""
from __future__ import annotations

import threading
import time

from .model import FrozenModel
from .store import ProgramStore


class CancellationRequest(FrozenModel):
    activity_id: str
    requested_at: float


class ActivityCancellation(threading.Event):
    def __init__(self, store: ProgramStore, activity_id: str) -> None:
        super().__init__()
        self.store = store
        self.activity_id = activity_id
        self.reference = "cancellation:" + activity_id

    def is_set(self) -> bool:
        if super().is_set():
            return True
        if self.store.reference(self.reference, CancellationRequest) is not None:
            super().set()
        return super().is_set()

    def set(self) -> None:
        with self.store.lease(self.reference):
            if self.store.reference(self.reference, CancellationRequest) is None:
                self.store.set_reference(self.reference, None, CancellationRequest(activity_id=self.activity_id, requested_at=time.time()))
        super().set()
